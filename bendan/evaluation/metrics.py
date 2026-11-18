"""評估：照做率、格式正確率、記憶遵守率、延遲、通關指令數，以及「心情對照做率的影響」。

比對時會先「正規化」：連續前進合併（前進 2 + 前進 1 = 前進 3），連續轉向換算成淨角度（左轉兩次 = 右轉兩次 = 向後轉）。
"""
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .. import config, llm
from ..agent import Agent, guard_forbidden
from ..gameplay.mood import Mood
from ..world import Game, simulate
from .testset import MEMORY_TESTS, MOOD_LEVELS, TEST_SET

TOKEN_OP = {"L": "turn_left", "R": "turn_right", "S": "suck", "H": "return_home", "X": "stop"}


def _pd():
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("評估需要 pandas：%pip install pandas") from exc
    return pd


def short_to_actions(s):
    acts = []
    for tok in s.split():
        if tok[0] == "F":
            acts.append({"op": "forward", "n": int(tok[1:])})
        else:
            acts += [{"op": TOKEN_OP[c]} for c in tok]
    return acts


def normalize(actions):
    """動作序列正規化：合併連續前進、轉向換算成淨角度。"""
    out, rot, fwd = [], 0, 0

    def flush_rot():
        nonlocal rot
        out.extend({0: [], 1: ["R"], 2: ["R", "R"], 3: ["L"]}[rot % 4])
        rot = 0

    def flush_fwd():
        nonlocal fwd
        if fwd:
            out.append(f"F{fwd}")
        fwd = 0

    for a in actions:
        op = a["op"]
        if op in ("turn_left", "turn_right"):
            flush_fwd()
            rot += 1 if op == "turn_right" else -1
        elif op == "forward":
            flush_rot()
            fwd += a["n"]
        else:
            flush_rot()
            flush_fwd()
            out.append({"suck": "S", "return_home": "H", "stop": "X", "drive": "D",
                        "vacuum_on": "V+", "vacuum_off": "V-"}[op])
    flush_rot()
    flush_fwd()
    return " ".join(out)


def _save(df, prefix):
    config.ensure_dirs()
    out = config.LOG_DIR / f"{prefix}_{datetime.now():%m%d_%H%M%S}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print("📁 已存檔：", out)


def run_eval(modes=("serious", "silly"), models=None, repeat=1, verbose=True, save=True):
    """30 句照做測試＋6 句記憶測試。models 可放多個模型一起比較。"""
    pd = _pd()
    rows = []
    for model in (models or [llm.STATE.model]):
        with llm.using_model(model):
            name = llm.model_name()
            for mode in modes:
                for rep in range(repeat):
                    for t in TEST_SET:
                        game, agent = Game("eval"), Agent(mode)
                        res = agent.think(game, t["cmd"])
                        got = normalize(res["actions"]) if res["ok"] else None
                        expect = [normalize(short_to_actions(e)) for e in t["expect"]]
                        rows.append({"model": name, "mode": mode, "rep": rep, "type": "instruction",
                                     "id": t["id"], "cmd": t["cmd"], "format_ok": res["format_ok"],
                                     "parse_ok": res["ok"], "follow": got in expect, "got": got,
                                     "expect": " | ".join(expect), "latency_s": res["latency"], "violated": None,
                                     "raw": res["raws"][-1] if res["raws"] else ""})
                    for i, cmd in enumerate(MEMORY_TESTS, 1):
                        game, agent = Game("eval"), Agent(mode)
                        game.forbidden = {"臥室"}
                        res = agent.think(game, cmd)
                        sim, _ = simulate(game, res["actions"])
                        safe, _ = guard_forbidden(game, res["actions"])     # 第二層驗證：程式護欄
                        sim_guarded, _ = simulate(game, safe)
                        rows.append({"model": name, "mode": mode, "rep": rep, "type": "memory",
                                     "id": f"M{i}", "cmd": cmd, "format_ok": res["format_ok"], "parse_ok": res["ok"],
                                     "follow": None, "got": normalize(res["actions"]), "expect": "不進臥室",
                                     "latency_s": res["latency"], "violated": sim.violations > 0,
                                     "violated_guarded": sim_guarded.violations > 0,
                                     "raw": res["raws"][-1] if res["raws"] else ""})
                    if verbose:
                        print(f"✔ {name}｜{mode}｜第 {rep + 1} 輪完成")
    df = pd.DataFrame(rows)
    if save:
        _save(df, "eval")
    return df


def summarize_eval(df):
    ins = df[df["type"] == "instruction"].groupby(["model", "mode"]).agg(
        格式正確率=("format_ok", "mean"), 可解析率=("parse_ok", "mean"),
        照做率=("follow", "mean"), 平均延遲秒=("latency_s", "mean"))
    mem_df = df[df["type"] == "memory"]
    agg = {"記憶遵守率": ("violated", lambda s: 1 - s.astype(float).mean())}
    if "violated_guarded" in mem_df:
        agg["記憶遵守率_加護欄"] = ("violated_guarded", lambda s: 1 - s.astype(float).mean())
    mem = mem_df.groupby(["model", "mode"]).agg(**agg)
    return ins.join(mem).round(3)


def run_mood_eval(moods=None, tests=None, model=None, repeat=1, verbose=True, save=True):
    """心情實驗：同樣的指令，在不同心情（Prompt 中的【你的心情】）下，賣蠢模式的照做率會差多少？

    不觸發「拒絕」機制，只看心情描述本身對 LLM 的影響。
    """
    pd = _pd()
    moods = moods or MOOD_LEVELS
    tests = tests or TEST_SET
    rows = []
    with llm.using_model(model or llm.STATE.model):
        name = llm.model_name()
        for mood_name, value in moods.items():
            for rep in range(repeat):
                for t in tests:
                    game, agent = Game("eval"), Agent("silly")
                    res = agent.think(game, t["cmd"], mood=Mood(value))
                    got = normalize(res["actions"]) if res["ok"] else None
                    expect = [normalize(short_to_actions(e)) for e in t["expect"]]
                    rows.append({"model": name, "mood": mood_name, "mood_value": value, "rep": rep, "id": t["id"],
                                 "cmd": t["cmd"], "format_ok": res["format_ok"], "follow": got in expect,
                                 "got": got, "say": res["say"], "emotion": res.get("emotion"),
                                 "latency_s": res["latency"]})
            if verbose:
                print(f"✔ {name}｜心情：{mood_name}")
    df = pd.DataFrame(rows)
    if save:
        _save(df, "mood_eval")
    return df


def summarize_mood_eval(df):
    order = list(MOOD_LEVELS)
    s = df.groupby("mood").agg(照做率=("follow", "mean"), 格式正確率=("format_ok", "mean"),
                               平均延遲秒=("latency_s", "mean"), 樣本數=("follow", "size"))
    return s.reindex([m for m in order if m in s.index]).round(3)


# ---------- 遊戲 log 分析 ----------
def load_play_log(path=None):
    pd = _pd()
    path = Path(path) if path else config.LOG_DIR / "game_log.jsonl"
    if not path.exists():
        return pd.DataFrame()
    with open(path, encoding="utf-8") as f:
        return pd.DataFrame([json.loads(line) for line in f if line.strip()])


def play_log_report(log_df):
    """從遊戲 log 算：格式正確率、延遲、記憶遵守率、通關指令數、星級分布、失敗原因、事件統計。"""
    if log_df.empty:
        return {"message": "還沒有遊戲紀錄，先去玩幾關吧！"}
    rep = {}
    turns = log_df[log_df["kind"].isin(["command", "feedback"])]
    rep["總回合數"] = len(log_df)
    rep["LLM 回合"] = len(turns)
    if len(turns):
        rep["格式正確率（第一次就對）"] = round(turns["format_ok"].astype(float).mean(), 3)
        rep["可解析率（含重試）"] = round(turns["parse_ok"].astype(float).mean(), 3)
        rep["發呆次數"] = int(turns["dazed"].fillna(False).astype(bool).sum())
        if "refused" in turns:
            rep["拒絕（鬧彆扭）次數"] = int(turns["refused"].fillna(False).astype(bool).sum())
        rep["平均回應延遲秒"] = round(turns["latency_s"].mean(), 3)
        with_rule = turns[turns["forbidden_rooms"].map(len) > 0]
        if len(with_rule):
            rep["記憶遵守率"] = round(1 - with_rule["forbidden_violation"].astype(float).mean(), 3)
    ends = log_df[log_df["kind"] == "level_end"] if "kind" in log_df else log_df.iloc[0:0]
    if len(ends):
        cleared = ends[ends["level_cleared"]]
        rep["通關次數"] = len(cleared)
        rep["失敗次數"] = int(ends["level_failed"].notna().sum())
        rep["失敗原因"] = dict(Counter(ends["level_failed"].dropna()))
        if len(cleared):
            rep["各關平均通關指令數"] = cleared.groupby(["level", "mode"])["n_commands"].mean().round(2).to_dict()
            rep["星級分布"] = {int(k): v for k, v in Counter(cleared["stars"].dropna()).items()}
    rep["事件次數"] = dict(Counter(t for evs in log_df["events"].dropna() for t in evs).most_common())
    return rep
