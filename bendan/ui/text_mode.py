"""文字模式（最穩定，任何 Jupyter 都能玩）：input() 讀指令，畫面在同一個位置更新。"""
import time
from collections import deque

from ..gameplay.progress import Progress
from ..render import HAS_MPL, hud_html, map_html, render_png
from ..session import EXECUTOR, Session
from .commands import HELP, handle_slash


class NotebookView:
    """在同一個位置更新畫面、對話框，以及額外資訊（選關／成就）。"""

    def __init__(self, session):
        from IPython.display import HTML, display
        self.session = session
        self.say = session.game.cfg["intro"]
        self.events = deque(maxlen=8)
        self.frame = 0
        self.h_img = display(HTML("<i>載入畫面中……</i>"), display_id=True)
        self.h_txt = display(HTML(""), display_id=True)
        self.h_extra = display(HTML(""), display_id=True)
        self.update()

    def update(self, say=None, events=(), thinking=False):
        from IPython.display import HTML, Image
        if say is not None:
            self.say = say
        self.events.extend(events)
        self.frame += 1
        s = self.session
        with s.lock:
            if HAS_MPL:
                pic = Image(data=render_png(s.game, thinking=thinking, frame=self.frame, emotion=s.emotion,
                                            mood=s.mood.name if s.gameplay and s.mode == "silly" else None))
            else:
                pic = HTML(map_html(s.game))
            txt = hud_html(s, self.say, self.events, thinking)
        self.h_img.update(pic)
        self.h_txt.update(HTML(txt))

    def extra(self, html_text):
        from IPython.display import HTML
        self.h_extra.update(HTML(html_text or ""))

    def clear_events(self):
        self.events.clear()


def _wait_thinking(session, view, fut, tick):
    """LLM 在背景思考時：畫面持續更新「思考中」，機器人繼續執行還沒做完的動作。"""
    while not fut.done():
        view.update(events=session.tick(), thinking=True)
        time.sleep(tick)
    return fut.result()


def _run_until_idle(session, view, tick):
    while session.busy():
        view.update(events=session.tick())
        time.sleep(tick)
    view.update()


def run_turn(session, view, command, tick=0.25):
    """完整處理一句玩家指令（含事件回饋閉環）。"""
    pre = session.preprocess(command)
    if pre["handled"]:
        view.update(say=pre["say"], events=pre["events"])
        _run_until_idle(session, view, tick)
        return
    view.update(events=pre["events"], thinking=True)
    res = _wait_thinking(session, view, EXECUTOR.submit(session.think, command, None, pre["refuse"]), tick)
    ev = session.apply(command, res)
    view.update(say=res["say"] or "……", events=ev)
    _run_until_idle(session, view, tick)
    # 事件回饋：被中斷時，把事件交回 LLM 回應／修正（Agent 閉環）
    while (fb := session.pop_feedback()):
        res = _wait_thinking(session, view, EXECUTOR.submit(session.think, fb["command"], fb), tick)
        ev = session.apply(fb["command"], res, kind="feedback", depth=fb["depth"])
        view.update(say=res["say"] or "……", events=ev)
        _run_until_idle(session, view, tick)


def play(level=1, mode="silly", tick=0.25, feedback_rounds=1, unlock_all=False, seed=None, progress=None):
    """▶️ 文字模式。特殊指令見 /help；q 離開。"""
    progress = progress or Progress(unlock_all=unlock_all)
    if not progress.is_unlocked(level):
        print(f"🔒 第 {level} 關還沒解鎖，先從第 1 關開始（或用 play(level={level}, unlock_all=True)）。")
        level = 1
    session = Session(level, mode, feedback_rounds, progress=progress, seed=seed)
    view = NotebookView(session)
    view.extra(HELP)
    while True:
        try:
            cmd = input("🧹 你的指令 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        if cmd.lower() in ("q", "quit", "exit", "離開"):
            break
        slash = handle_slash(session, cmd)
        if slash is not None:
            if slash.get("changed"):
                view.clear_events()
            view.extra(slash.get("html", ""))
            view.update(say=slash["say"])
            continue
        view.extra("")
        run_turn(session, view, cmd, tick)
    print("👋 遊戲結束，log 存在：", session.logger.path)
    return session
