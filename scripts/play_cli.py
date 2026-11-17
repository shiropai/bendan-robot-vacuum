#!/usr/bin/env python3
"""終端機版笨笨掃地機（純文字地圖），不需要 Jupyter。

    python scripts/play_cli.py --level 1
    python scripts/play_cli.py --level daily --mode serious
    python scripts/play_cli.py --fake            # 強制用離線 FakeLLM

地圖符號：^>v< 笨笨  H 充電座  D 灰塵  C 貓  G 狗  L 樂高  S 襪子  W 充電線  P 狗便便  O 水漬  x 禁區
"""
import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bendan import llm  # noqa: E402
from bendan.gameplay import Progress  # noqa: E402
from bendan.render import render_ascii  # noqa: E402
from bendan.render.hud import event_line  # noqa: E402
from bendan.session import Session  # noqa: E402
from bendan.ui.commands import handle_slash  # noqa: E402
from bendan.world import QUIET_EVENTS, level_title  # noqa: E402


def strip_html(text):
    text = re.sub(r"</t[dh]>", "  ", text or "")
    text = re.sub(r"<br\s*/?>|</(div|li|tr)>", "\n", text)
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def status(s):
    g = s.game
    line = f"[{level_title(g.level_id)}] 灰塵剩 {len(g.dirt)}｜電量 {g.battery_pct:.0f}%｜指令 {s.n_commands}"
    if s.commands_left() is not None:
        line += f"（剩 {s.commands_left()} 句）"
    if s.gameplay:
        line += (f"｜心情 {s.mood.emoji}{s.mood.name}({s.mood.value:.0f})｜血壓 {s.bp.mmhg}mmHg"
                 f"｜分數 {s.score.score}")
    return line


def show_events(events):
    for e in events:
        if e["type"] not in QUIET_EVENTS:
            print(f"   {event_line(e)}")


def run(s, command):
    pre = s.preprocess(command)
    show_events(pre["events"])
    if pre["handled"]:
        print("🤖", pre["say"])
    else:
        print("   🤔 思考中……")
        res = s.think(command, None, pre["refuse"])
        print("🤖", res["say"] or "……")
        show_events(s.apply(command, res))
    while True:
        while s.busy():
            show_events(s.tick())
        fb = s.pop_feedback()
        if not fb:
            break
        res = s.think(fb["command"], fb)
        print("🤖", res["say"] or "……")
        show_events(s.apply(fb["command"], res, kind="feedback", depth=fb["depth"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", default="0")
    ap.add_argument("--mode", default="silly", choices=["silly", "serious"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--fake", action="store_true", help="強制使用離線 FakeLLM")
    ap.add_argument("--unlock-all", action="store_true")
    args = ap.parse_args()

    llm.connect(model=args.model, use_fake=True if args.fake else None)
    level = int(args.level) if args.level.isdigit() else args.level
    progress = Progress(unlock_all=args.unlock_all)
    if not progress.is_unlocked(level):
        print(f"🔒 {level_title(level)} 還沒解鎖，從第 1 關開始。")
        level = 1
    s = Session(level, args.mode, progress=progress)
    print(s.game.cfg["intro"], "\n輸入 /help 看指令，q 離開。")
    while True:
        print("\n" + render_ascii(s.game))
        print(status(s))
        try:
            cmd = input("🧹 你的指令 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        if cmd.lower() in ("q", "quit", "exit", "離開"):
            break
        slash = handle_slash(s, cmd)
        if slash is not None:
            print("🤖", slash["say"])
            if slash.get("html"):
                print(strip_html(slash["html"]))
            continue
        run(s, cmd)
    print("👋 掰掰！")


if __name__ == "__main__":
    main()
