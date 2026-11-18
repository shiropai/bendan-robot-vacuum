"""Session：完整 Agent 迴圈＋玩法系統＋非同步＋事件回饋＋Log。

```
玩家指令 ─► preprocess（語氣分析→心情/血壓、禁區寫入記憶、「停」不經 LLM、決定笨笨要不要鬧彆扭）
         ─► think（背景執行緒呼叫 LLM，畫面不卡住）
         ─► apply（記性差→截斷、恍神→改計畫、護欄→攔禁區，再放進佇列取代舊計畫）
         ─► tick（每次走一步 → 突發事件 → 心情/血壓/分數 → 失敗判定）
         ─► 計畫結束：寫 log、寫記憶；若被中斷 → 把事件回饋給 LLM 再回應一次（閉環）
         ─► 關卡結束：結算星級、檢查成就、存檔
```
每一回合寫成一行 JSON 到 `logs/game_log.jsonl`，評估模組會自動算指標；
同時記在 `session.history`（畫面上對話框下方的「指令紀錄」）。

`gameplay=False` 會關掉心情／血壓／突發事件／計分（＝原始版本），評估時用來公平比較模型。
"""
import json
import random
import re
import threading
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from . import config, llm
from .agent import Agent, Memory, actions_to_text, guard_forbidden, update_rules_from_text
from .gameplay import (BloodPressure, IncidentDirector, Mood, Progress, Scoreboard, analyze_tone,
                       check_achievements, stars_text)
from .gameplay.quirks import limit_plan, maybe_quirk, quirk_chance
from .world import INTERRUPT_EVENTS, QUIET_EVENTS, E, Game


class JsonlLogger:
    def __init__(self, path=None):
        self.path = Path(path) if path else config.LOG_DIR / "game_log.jsonl"
        self._lock = threading.Lock()

    def write(self, record):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


class NullLogger:
    path = Path("/dev/null")

    def write(self, record):
        pass


def pick_quote(quotes):
    """結算的「本關金句」：頂嘴（拒絕）＞出包後的回應＞生氣／委屈＞得意＞其他；同一級挑最長的。"""
    def rank(q):
        if q.get("refused"):
            return 4
        if q.get("kind") == "feedback":
            return 3
        return {"生氣": 2, "委屈": 2, "得意": 1}.get(q.get("emotion"), 0)
    if not quotes:
        return ""
    return max(quotes, key=lambda q: (rank(q), len(q["say"])))["say"]


STOP_RE = re.compile(r"\s*(停|停止|停下|停下來|煞車|別動|stop)[!！。.\s]*", re.I)
HOME_RE = re.compile(r"回充|充電|回家|回去充")
# 整句只是「回去充電」→ 跟「停」一樣直接處理（實測：模型常在 return_home 前自己加「前進 10 格」，撞牆就回不了家）
GO_HOME_RE = re.compile(r"\s*(請|麻煩|拜託)?\s*(你|笨笨)?\s*(快)?\s*(回到?充電座|回去充電座?|回充電座?|回充|回家|去充電)"
                        r"\s*(吧|啦|喔|了|好嗎|謝謝)?[!！。.~～\s]*")
EXECUTOR = ThreadPoolExecutor(max_workers=2)


class Session:
    def __init__(self, level_id=1, mode="silly", feedback_rounds=1, logger=None, progress=None, seed=None,
                 gameplay=True, guardrail=False):
        self.lock = threading.RLock()
        self.logger = logger or JsonlLogger()
        self.progress = progress if progress is not None else Progress()
        self.agent = Agent(mode, seed=seed, route_hints=gameplay)
        self.feedback_rounds = feedback_rounds   # 事件回饋最多幾輪（0 = 不回饋）
        self.gameplay = gameplay
        self.guardrail = guardrail             # True＝程式攔截闖禁區的計畫（新手友善；關掉才看得到 LLM 闖禁區的笑點）
        self.seed = seed
        self.view = "iso"                     # 畫面視角：iso＝2.5D、top＝俯視（UI 用）
        self.game = None
        self.reset(level_id)

    @property
    def mode(self):
        return self.agent.mode

    def reset(self, level_id=None):
        with self.lock:
            lid = level_id if level_id is not None else self.game.level_id
            self.rng = random.Random(self.seed)
            self.game = Game(lid, seed=self.seed)
            cfg = self.game.cfg
            self.agent.memory = Memory()
            self.mood = Mood(cfg.get("mood_start", 65))
            self.bp = BloodPressure(cfg.get("bp_start", 10))
            self.score = Scoreboard()
            specs = cfg.get("incidents", []) if self.gameplay else []
            self.director = IncidentDirector(specs, random.Random(self.rng.random()))
            self.event_counts, self.tone_counts = Counter(), Counter()
            self.id = uuid.uuid4().hex[:8]
            self.current = None
            self.pending_feedback = None
            self.n_commands = 0
            self.last_command = None
            self.last_tone = None
            self.result = None             # 關卡結算（結束後才有）
            self.new_achievements = []
            self.quotes = []               # 笨笨講過的話（結算時挑最好笑的）
            self.emotion = None
            self.history = []              # 指令紀錄（畫面上對話框下方）

    # ---------- 小工具 ----------
    @property
    def command_limit(self):
        return self.game.cfg.get("command_limit") if self.gameplay else None

    def commands_left(self):
        lim = self.command_limit
        return None if lim is None else max(lim - self.n_commands, 0)

    def busy(self):
        return bool(self.game.queue)

    @property
    def guard_allowed(self):
        """這關能不能開禁區護欄（進階關卡會停用）。"""
        return self.game.cfg.get("guardrail", True) is not False

    @property
    def guard_on(self):
        return self.guardrail and self.guard_allowed

    def quirk_chance(self):
        if not self.gameplay:
            return 0.0
        return quirk_chance(self.game.cfg, self.mood, self.mode)

    def modifiers(self):
        """本關的難度標籤（畫面上顯示用）：[(圖示, 文字), ...]。"""
        cfg, g, out = self.game.cfg, self.game, []
        if not self.gameplay:
            return out
        if cfg.get("route_hints", True) is False:
            out.append(("🧭", "導航壞了：要你指路"))
        if cfg.get("quirks"):
            out.append(("🙃", f"恍神率 {self.quirk_chance():.0%}（看心情）"))
        if cfg.get("max_plan"):
            out.append(("🧠", f"一次只記得 {cfg['max_plan']} 個動作"))
        if self.command_limit is not None:
            out.append(("💬", f"剩 {self.commands_left()} 句"))
        if g.step_limit:
            out.append(("⏱️", f"剩 {g.steps_left} 步"))
        if g.dark:
            out.append(("🌑", "停電：只看得到附近"))
        if cfg.get("vision"):
            out.append(("👓", f"笨笨只看得到 {cfg['vision']} 格內"))
        if cfg.get("fatigue"):
            out.append(("😪", f"會累：每句話心情 −{cfg['fatigue']}"))
        if not self.guard_allowed:
            out.append(("🛡️", "本關護欄停用"))
        elif self.guardrail:
            out.append(("🛡️", "護欄開啟"))
        if g.forbidden:
            out.append(("🚫", "禁區：" + "、".join(sorted(g.forbidden))))
        if g.need_home:
            out.append(("🏠", "最後要回充電座"))
        return out

    def _new_entry(self, command, kind, say="", actions=(), flags=()):
        entry = {"no": self.n_commands, "cmd": command, "kind": kind, "say": say,
                 "tone": self.last_tone.describe() if (self.last_tone and kind == "command") else "",
                 "plan": actions_to_text(list(actions)) if actions is not None else "",
                 "flags": list(flags), "result": [], "done": False}
        self.history.append(entry)
        del self.history[:-50]
        return entry

    def _count_command(self):
        """多用一句指令；超過上限就失敗。回傳事件。"""
        lim = self.command_limit
        if lim is not None and self.n_commands >= lim:
            return self._absorb(self.game.fail("time_up", self.game.cfg.get("fail_text", "指令用完了，這關失敗。")))
        self.n_commands += 1
        return []

    # ---- 1) 玩家輸入的本地處理 ----
    def preprocess(self, command):
        """回傳 {"handled": bool, "say": str, "events": [...], "refuse": bool}。handled=True 代表不用問 LLM。"""
        with self.lock:
            if self.game.over:
                return {"handled": True, "say": "這關已經結束囉！/reset 重來，或換下一關。", "events": [], "refuse": False}
            events = self._count_command()
            if self.game.over:
                return {"handled": True, "say": "……來不及了。", "events": events, "refuse": False}
            tone = analyze_tone(command, self.last_command)
            self.last_command, self.last_tone = command, tone
            if self.gameplay:
                self.tone_counts.update(tone.tags)
                tone_ev = []
                if tone.tags:
                    tone_ev.append(E("tone", f"🗣️ 語氣：{tone.describe()}（心情 {tone.delta:+d}）", tags=tone.tags))
                tone_ev += self.mood.apply_tone(tone)
                if self.game.cfg.get("fatigue"):          # 進階關卡：笨笨會累，每句話心情往下掉
                    tone_ev += self.mood.apply(-self.game.cfg["fatigue"])
                self.bp.add(tone.bp)
                events += self._absorb(tone_ev, from_events=False)
            events += self._absorb([E("rule", n) for n in update_rules_from_text(self.game, command)])
            if self.game.over:
                return {"handled": True, "say": "……", "events": events, "refuse": False}
        if STOP_RE.fullmatch(command):            # 保底動作：「停」直接處理，不等 LLM
            return {"handled": True, "say": "收到！緊急煞車！", "events": events + self.stop(command), "refuse": False}
        if GO_HOME_RE.fullmatch(command):         # 保底動作：「回充」也直接處理
            res = {"actions": [{"op": "return_home"}], "say": "好啦，回家充電。", "ok": True, "format_ok": True,
                   "raws": [], "latency": 0.0}
            return {"handled": True, "say": res["say"], "events": events + self.apply(command, res, kind="home"),
                    "refuse": False}
        refuse = (self.gameplay and self.mode == "silly" and not tone.coaxing and not HOME_RE.search(command)
                  and self.mood.should_refuse(self.rng))
        return {"handled": False, "say": "", "events": events, "refuse": refuse}

    def stop(self, command="停"):
        with self.lock:
            self.game.queue.clear()
            ev = E("stopped", "收到「停」，動作佇列已清空。")
            if self.gameplay:
                self.event_counts["stopped"] += 1
            if self.current:
                self.current["events"].append(ev)
                self._finish()
            self.pending_feedback = None
            entry = self._new_entry(command, "stop", "收到！緊急煞車！", [])
            entry.update(plan="（緊急煞車）", done=True)
            self._log({"kind": "local_stop", "command": command})
        return [ev]

    def local_plan(self, actions, label):
        """保底按鈕（例如「回充」）：不經 LLM 直接執行。回傳事件。"""
        with self.lock:
            if self.game.over:
                return []
            events = self._count_command()
            if self.game.over:
                return events
        res = {"actions": actions, "say": label, "ok": True, "format_ok": True, "raws": [], "latency": 0.0}
        return events + self.apply(label, res, kind="local")

    # ---- 2) 思考（在背景執行緒呼叫）----
    def think(self, command, feedback=None, refuse=False):
        events = feedback["events"] if feedback else None
        mood = self.mood if self.gameplay else None
        return self.agent.think(self.game, command, feedback_events=events, lock=self.lock, mood=mood,
                                refuse=refuse and feedback is None)

    # ---- 3) 套用計畫 ----
    def apply(self, command, result, kind="command", depth=0):
        with self.lock:
            if self.game.over:
                return []
            if self.current:
                self._finish(replaced=True)
            if result.get("emotion"):
                self.emotion = result["emotion"]
            if result.get("say") and kind not in ("local", "home"):      # 程式自動回的話不算「金句」
                self.quotes.append({"say": result["say"], "emotion": result.get("emotion"), "command": command,
                                    "refused": bool(result.get("refused")), "kind": kind})
            extra, flags = [], []
            llm_actions = result.get("actions", [])
            if (self.gameplay and kind in ("command", "feedback")
                    and not result.get("refused") and not result.get("dazed")):
                acts, ev = limit_plan(llm_actions, self.game.cfg.get("max_plan"))      # 記性差
                if ev:
                    extra.append(ev)
                    flags.append("🧠 忘了後面")
                acts, ev = maybe_quirk(acts, self.game.cfg, self.rng, self.mood, self.mode)  # 恍神
                if ev:
                    extra.append(ev)
                    flags.append("🙃 " + ev["name"])
                if acts is not llm_actions:
                    result = dict(result, actions=acts, llm_actions=llm_actions,
                                  quirk=ev["quirk"] if ev else None, forgot=any(e["type"] == "forgot" for e in extra))
            if self.guard_on and kind != "local":
                safe, note = guard_forbidden(self.game, result["actions"])
                if note:
                    result = dict(result, actions=safe, guarded=True)
                    extra.append(E("guardrail", note))
                    flags.append("🛡️ 護欄攔下")
            self.game.set_plan(result["actions"])
            if result.get("refused"):
                flags.append("🙅 拒絕")
            if result.get("dazed"):
                flags.append("😵 當機")
            label = "（回報）" if kind == "feedback" else command
            entry = self._new_entry(label, kind, result.get("say", ""), result["actions"], flags)
            self.current = {"command": command, "kind": kind, "depth": depth, "result": result, "events": [],
                            "entry": entry}
            if result.get("refused"):
                extra.append(E("refused", "🙅 笨笨拒絕了這個指令！（試試說「請」、稱讚或道歉）"))
            if result.get("dazed"):
                extra.append(E("dazed", "😵 笨笨的腦袋當機，發呆中……"))
            out = self._absorb(extra)
            if self.current is not None and not self.game.queue:
                self._finish()
            return out

    # ---- 4) 每個 tick 執行一步 ----
    def tick(self):
        with self.lock:
            before = self.game.steps
            events = self.game.step()
            if self.gameplay and self.game.steps > before and not self.game.over:
                events += self.director.on_step(self.game)
            events = self._absorb(events)
            if self.current is not None and not self.game.queue:
                self._finish()
            return events

    def pop_feedback(self):
        with self.lock:
            fb, self.pending_feedback = self.pending_feedback, None
            return fb

    # ---- 玩法系統：處理事件 → 心情／血壓／分數／失敗判定／結算 ----
    def _absorb(self, events, from_events=True):
        derived = []
        if self.gameplay and events:
            self.event_counts.update(e["type"] for e in events)
            if from_events:
                derived += self.mood.apply_events(events)
                self.bp.apply_events(events)
                derived += self.score.on_events(events)
            if self.bp.maxed and not self.game.over:
                derived += self.game.fail("owner_faint", "🤯 主人血壓飆到 200，氣到昏倒了……這關失敗。")
            self.event_counts.update(e["type"] for e in derived)
        out = list(events) + derived
        if self.current is not None:
            self.current["events"] += out
        if self.game.over and self.result is None:
            if self.current is not None:
                self._finish()
            out += self._conclude()
        return out

    def _conclude(self):
        g = self.game
        if not self.gameplay:
            self.result = {"cleared": g.cleared, "failed": g.failed, "n_commands": self.n_commands}
            return []
        res = self.score.finalize(g, self.n_commands, self.bp, self.mood)
        res["quote"] = pick_quote(self.quotes)
        stats = {"events": self.event_counts, "tones": self.tone_counts, "result": res, "mood": self.mood,
                 "bp": self.bp, "level_id": g.level_id, "total_dirt": g.total_dirt}
        totals = self.progress.totals + Counter(self.event_counts)
        new = check_achievements(stats, totals, self.progress.unlocked_achievements)
        self.progress.record(res, self.event_counts, new)
        self.result, self.new_achievements = res, new
        self._log({"kind": "level_end", "stars": res["stars"], "score": res["score"], "failed": g.failed,
                   "achievements": [a["id"] for a in new], "best_combo": res["best_combo"]})
        title = "過關" if g.cleared else "失敗"
        events = [E("level_result", f"🏁 {title}！{stars_text(res['stars'])}  {res['score']} 分", result=res)]
        events += [E("achievement", f"🏅 解鎖成就「{a['icon']} {a['name']}」：{a['desc']}", id=a["id"]) for a in new]
        return events

    # ---- 5) 計畫結束：log＋記憶＋決定要不要回饋 ----
    def _finish(self, replaced=False):
        cur, self.current = self.current, None
        r, evs = cur["result"], cur["events"]
        types = [e["type"] for e in evs]
        interrupted = any(t in INTERRUPT_EVENTS for t in types)
        self._log({
            "kind": cur["kind"], "depth": cur["depth"], "command": cur["command"],
            "raw_outputs": r.get("raws", []), "format_ok": r.get("format_ok"), "retried": r.get("retried", False),
            "parse_ok": r.get("ok"), "dazed": r.get("dazed", False), "refused": r.get("refused", False),
            "errors": r.get("errors", [])[:5], "actions": r.get("actions", []), "say": r.get("say", ""),
            "emotion": r.get("emotion"), "latency_s": round(r.get("latency", 0.0), 3),
            "events": types, "interrupted": interrupted, "replaced": replaced,
            "forbidden_violation": "entered_forbidden" in types,
            "quirk": r.get("quirk"), "forgot": r.get("forgot", False), "llm_actions": r.get("llm_actions"),
        })
        entry = cur.get("entry")
        if entry is not None:
            shown = [e for e in evs if e["type"] not in QUIET_EVENTS | {"tone", "quirk", "forgot", "guardrail",
                                                                         "refused", "dazed"}]
            entry["result"] = [{"type": e["type"], "msg": e["msg"]} for e in shown[:4]]
            entry["interrupted"], entry["done"] = interrupted, True
        label = cur["command"] if cur["kind"] != "feedback" else f"（修正）{cur['command']}"
        self.agent.memory.remember_turn(label, r.get("actions", []), evs)
        if (not replaced and interrupted and cur["kind"] != "local"
                and cur["depth"] < self.feedback_rounds and not self.game.over):
            self.pending_feedback = {"command": cur["command"], "events": evs, "depth": cur["depth"] + 1}

    def _log(self, rec):
        g = self.game
        base = {"ts": datetime.now().isoformat(timespec="seconds"), "session": self.id, "level": g.level_id,
                "mode": self.agent.mode, "model": llm.model_name(), "gameplay": self.gameplay,
                "n_commands": self.n_commands, "level_cleared": g.cleared, "level_failed": g.failed,
                "dirt_left": len(g.dirt), "forbidden_rooms": sorted(g.forbidden), "violations_total": g.violations,
                "mood": round(self.mood.value, 1), "bp_mmhg": self.bp.mmhg, "battery": round(g.battery_pct, 1),
                "score": self.score.score}
        self.logger.write({**base, **rec})
