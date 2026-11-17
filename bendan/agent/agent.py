"""Agent：組 Prompt → 呼叫 LLM → 解析驗證 →（失敗重試一次）→ 發呆演出。

`think()` 只回傳**結構化結果**，不直接動到遊戲世界。
"""
import random
import time
from contextlib import nullcontext

from .. import llm
from .memory import Memory, events_to_text
from .parsing import parse_reply
from .perception import describe_world
from .prompts import (ACTION_SPEC, FEEDBACK_TEXT, PERSONA_SERIOUS, PERSONA_SILLY, REFUSE_TEXT,
                      SILLY_STRENGTH)

DAZE_ACTIONS = [
    [],                                                                       # 原地發呆
    [{"op": "turn_left"}] * 4,                                                # 原地轉一圈
    [{"op": "turn_right"}, {"op": "turn_left"}, {"op": "turn_right"}, {"op": "turn_left"}],  # 原地亂扭
]


class Agent:
    def __init__(self, mode="silly", silliness=None, seed=None, route_hints=False):
        self.mode = mode              # "silly"＝賣蠢模式；"serious"＝正經模式（對照組）
        self.silliness = silliness    # None＝依關卡設定（再被心情修正）
        self.route_hints = route_hints  # True＝世界描述附上「去最近灰塵」的路線（遊戲中開啟，評估預設關閉）
        self.memory = Memory()
        self.rng = random.Random(seed)

    def effective_silliness(self, game, mood=None):
        base = game.cfg.get("silliness", 1) if self.silliness is None else self.silliness
        shift = mood.silliness_shift if mood is not None else 0
        return max(0, min(3, base + shift))

    def system_prompt(self, game, mood=None):
        if self.mode == "serious":
            persona = PERSONA_SERIOUS
        else:
            persona = PERSONA_SILLY + SILLY_STRENGTH[self.effective_silliness(game, mood)]
        return persona + "\n\n" + ACTION_SPEC

    def build_messages(self, game, command, feedback_events=None, mood=None, refuse=False):
        world, mem = describe_world(game, hints=self.route_hints), self.memory.to_text(game)
        mood_txt = f"\n\n【你的心情】{mood.prompt_text()}" if (mood is not None and self.mode == "silly") else ""
        if feedback_events is None:
            user = f"【世界狀態】\n{world}\n\n【記憶】\n{mem}{mood_txt}\n\n【主人指令】\n{command}"
            if refuse:
                user = REFUSE_TEXT + "\n\n" + user
        else:
            user = (f"【執行結果】你剛剛為了主人的指令「{command}」執行動作，結果：{events_to_text(feedback_events)}\n\n"
                    f"【世界狀態】\n{world}\n\n【記憶】\n{mem}{mood_txt}\n\n" + FEEDBACK_TEXT)
        return [{"role": "system", "content": self.system_prompt(game, mood)}, {"role": "user", "content": user}]

    def think(self, game, command, feedback_events=None, lock=None, mood=None, refuse=False):
        with (lock or nullcontext()):          # 讀取世界狀態時上鎖（背景執行緒安全）
            messages = self.build_messages(game, command, feedback_events, mood, refuse)
        temperature = 0.2 if self.mode == "serious" else 0.8
        result = {"command": command, "mode": self.mode, "raws": [], "errors": [],
                  "format_ok": False, "retried": False, "ok": False, "dazed": False,
                  "actions": [], "say": "", "emotion": None, "refused": False}
        t0 = time.perf_counter()
        for attempt in range(2):                # 解析失敗自動重試一次
            try:
                raw = llm.chat(messages, temperature=temperature)
            except Exception as exc:            # noqa: BLE001 — API 出錯就發呆，不讓遊戲當掉
                result["errors"].append(f"API 錯誤：{type(exc).__name__}: {str(exc)[:100]}")
                break
            result["raws"].append(raw)
            plan, errs = parse_reply(raw)
            if plan is not None:
                result.update(plan, ok=True, format_ok=(attempt == 0))
                break
            result["errors"] += errs
            if attempt == 0:
                result["retried"] = True
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": "你的回覆不符合格式：" + "；".join(errs[:3])
                     + '。請只輸出一個 JSON 物件，例如 {"actions": [{"op": "forward", "n": 1}], "say": "好"}'},
                ]
        result["latency"] = time.perf_counter() - t0
        if not result["ok"]:                    # 兩次都失敗 → 發呆演出，把模型原話秀出來
            raw0 = result["raws"][-1].strip() if result["raws"] else ""
            result["actions"] = self.rng.choice(DAZE_ACTIONS)
            result["say"] = "（發呆中……）" + (f"我剛剛想說：「{raw0[:60]}」" if raw0 else "腦袋連不上線。")
            result["dazed"] = True
        if refuse:                              # 拒絕是「遊戲機制」決定的：模型就算照做也不算數
            result["actions"] = []
            result["refused"] = True
            result["say"] = result["say"] or "哼。"
        return result
