#!/usr/bin/env python3
"""難度曲線實測：用「腳本玩家」把每一關跑一遍，檢查越後面的關卡是不是真的越難。

兩種腳本玩家（語氣都很溫和、都有「請」，只看難度機制本身的影響）：
- lazy（偷懶玩家）：一直說「請去吸最近的灰塵」，完全靠 AI 自己找路。v2 這樣就能輕鬆過關 → 「AI 太聰明」。
- precise（精準玩家）：看整張地圖算好最短路線，講「請往前走3格，右轉，往前走2格，吸」這種精確指令，
  並照關卡「一次記得幾個動作」拆句。
兩種玩家都會在灰塵清完、或出現低電量警告時說「請回充電座」。
  （停電關它也看得到整張地圖 → 是「理想玩家」的上限，真人只會更難。）

    python scripts/difficulty_probe.py --runs 2 --levels 0-10      # 課程 API（約 20–40 分鐘）
    python scripts/difficulty_probe.py --fake --levels 0-3         # 離線 FakeLLM 測流程

輸出：logs/difficulty_probe.csv（每一局一列）＋印出 Markdown 摘要表。存檔寫到暫存位置，不影響正式進度。
"""
import argparse
import csv
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bendan import config, llm  # noqa: E402
from bendan.agent.perception import path_to_actions  # noqa: E402
from bendan.gameplay import Progress  # noqa: E402
from bendan.session import JsonlLogger, Session  # noqa: E402
from bendan.world import CAMPAIGN, level_title  # noqa: E402

OP_TEXT = {"turn_left": "左轉", "turn_right": "右轉", "suck": "吸"}


def op_text(a):
    return f"往前走{a['n']}格" if a["op"] == "forward" else OP_TEXT[a["op"]]


def lazy_command(s):
    g = s.game
    if not g.dirt or g.low_battery:          # 有聽低電量警告的玩家
        return "請回充電座"
    return "請去吸最近的灰塵"


def precise_command(s):
    g = s.game
    if not g.dirt or g.low_battery:          # 有聽低電量警告的玩家
        return "請回充電座"
    best = None
    for d in g.dirt:
        if g.in_forbidden(d):
            continue
        path = g.find_route(g.pos, g.facing, d)
        if path and (best is None or len(path) < len(best)):
            best = path
    if best is None:
        return "請回充電座"
    ops = path_to_actions(best, g.facing) + [{"op": "suck"}]
    ops = ops[:min(g.cfg.get("max_plan") or 8, 8)]       # 真人一句話也不會講超過 8 個動作
    return "請" + "，".join(op_text(a) for a in ops)


STRATEGIES = {"lazy": lazy_command, "precise": precise_command}


def drive(session, command):
    """一個完整回合（同 ui.run_turn，但不畫圖）。"""
    pre = session.preprocess(command)
    if not pre["handled"]:
        res = session.think(command, None, pre["refuse"])
        session.apply(command, res)
    while session.busy():
        session.tick()
    while (fb := session.pop_feedback()):
        res = session.think(fb["command"], fb)
        session.apply(fb["command"], res, kind="feedback", depth=fb["depth"])
        while session.busy():
            session.tick()


def play_one(level, strategy, run, logger, save_dir):
    progress = Progress(path=Path(save_dir) / f"p_{level}_{strategy}_{run}.json", unlock_all=True)
    s = Session(level, "silly", feedback_rounds=1, logger=logger, progress=progress, seed=1000 + run)
    cap = (s.command_limit or 24) + 1
    t0 = time.perf_counter()
    for _ in range(cap):
        if s.game.over:
            break
        drive(s, STRATEGIES[strategy](s))
    g, ev = s.game, s.event_counts
    r = s.result or {}
    return {"level": level, "name": g.cfg["name"], "strategy": strategy, "run": run, "cleared": g.cleared,
            "failed": g.failed or ("" if g.cleared else "gave_up"), "n_commands": s.n_commands, "steps": g.steps,
            "dirt_left": len(g.dirt), "quirks": ev["quirk"], "forgot": ev["forgot"], "refused": ev["refused"],
            "collisions": ev["collision"], "violations": g.violations, "bp_peak": s.bp.mmhg if not r else r["bp_peak_mmhg"],
            "stars": r.get("stars", 0), "score": r.get("score", 0), "seconds": round(time.perf_counter() - t0, 1)}


def parse_levels(text):
    if "-" in text:
        a, b = text.split("-")
        return [lv for lv in CAMPAIGN if int(a) <= lv <= int(b)]
    return [int(x) for x in text.split(",")]


def summary(rows):
    by = defaultdict(list)
    for r in rows:
        by[(r["level"], r["strategy"])].append(r)
    strategies = sorted({r["strategy"] for r in rows})
    head = "| 關卡 | " + " | ".join(f"{st}：過關率／平均指令／恍神次數／失敗原因" for st in strategies) + " |"
    lines = [head, "|---|" + "---|" * len(strategies)]
    for lv in sorted({r["level"] for r in rows}):
        cells = []
        for st in strategies:
            rs = by[(lv, st)]
            if not rs:
                cells.append("—")
                continue
            clear = sum(r["cleared"] for r in rs) / len(rs)
            cmds = sum(r["n_commands"] for r in rs) / len(rs)
            quirks = sum(r["quirks"] for r in rs) / len(rs)
            fails = Counter(r["failed"] for r in rs if not r["cleared"])
            why = "、".join(f"{k}×{v}" for k, v in fails.items()) or "—"
            cells.append(f"{clear:.0%}／{cmds:.1f}／{quirks:.1f}／{why}")
        lines.append(f"| {level_title(lv)} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--levels", default="0-10")
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--strategies", default="lazy,precise")
    ap.add_argument("--model", default=None)
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--out", default=str(config.LOG_DIR / "difficulty_probe.csv"))
    args = ap.parse_args()

    llm.connect(model=args.model, use_fake=True if args.fake else None, verbose=True)
    if args.fake:
        llm.STATE.fake.think_time = None
    config.ensure_dirs()
    logger = JsonlLogger(config.LOG_DIR / "difficulty_probe_log.jsonl")
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for lv in parse_levels(args.levels):
            for st in args.strategies.split(","):
                for run in range(args.runs):
                    row = play_one(lv, st, run, logger, tmp)
                    rows.append(row)
                    print(f"L{lv:>2} {st:<7} run{run}: {'過關' if row['cleared'] else '失敗(' + row['failed'] + ')'}"
                          f"  指令 {row['n_commands']:>2}  恍神 {row['quirks']}  記性 {row['forgot']}  "
                          f"拒絕 {row['refused']}  {row['seconds']}s", flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\n模型：{llm.model_name()}　存到：{out}\n")
    print(summary(rows))


if __name__ == "__main__":
    main()
