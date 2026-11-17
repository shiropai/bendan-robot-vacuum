"""即時模式（ipywidgets）：遊戲迴圈在背景執行緒持續跑，LLM 也在背景思考。

**機器人執行動作時你可以隨時按「停！」**——趕在它撞上樂高之前！
笨笨鬧彆扭的時候，按「💗 哄一下」說好話給它聽。
"""
import html
import random
import threading
import time
from collections import deque

from ..gameplay.progress import Progress
from ..gameplay.scoring import stars_text
from ..render import HAS_MPL, hud_html, map_html, render_png
from ..session import EXECUTOR, Session
from ..world.levels import CAMPAIGN, level_title
from .commands import COAX_LINES, HELP, change_level, handle_slash

_ACTIVE_UI = None


class WidgetGame:
    def __init__(self, level=1, mode="silly", tick=0.35, feedback_rounds=1, progress=None, seed=None):
        import ipywidgets as W
        self.W = W
        self.progress = progress or Progress()
        self.session = Session(level, mode, feedback_rounds, progress=self.progress, seed=seed)
        self.tick_s = tick
        self.say = self.session.game.cfg["intro"]
        self.events = deque(maxlen=8)
        self.future, self.future_info = None, None
        self.dirty, self.frame = True, 0
        self._busy_ui = False

        self.img = W.Image(format="png", layout=W.Layout(width="640px")) if HAS_MPL else W.HTML()
        self.hud = W.HTML()
        self.extra = W.HTML()
        self.cmd = W.Text(placeholder="輸入指令後按 Enter，例如：請往前走三格然後吸",
                          continuous_update=False, layout=W.Layout(width="340px"))
        self.btn_send = W.Button(description="送出", button_style="primary", layout=W.Layout(width="70px"))
        self.btn_stop = W.Button(description="停！", button_style="danger", layout=W.Layout(width="70px"))
        self.btn_home = W.Button(description="回充", layout=W.Layout(width="70px"))
        self.btn_coax = W.Button(description="💗 哄一下", button_style="warning", layout=W.Layout(width="90px"))
        self.dd_level = W.Dropdown(options=self._level_options(), value=level, layout=W.Layout(width="230px"))
        self.tb_mode = W.ToggleButtons(options=[("賣蠢模式", "silly"), ("正經模式", "serious")], value=mode)
        self.btn_reset = W.Button(description="重來", layout=W.Layout(width="60px"))
        self.btn_info = W.ToggleButton(description="📋 關卡/成就", layout=W.Layout(width="110px"))
        self.btn_quit = W.Button(description="結束遊戲", layout=W.Layout(width="80px"))

        self.cmd.observe(self._on_cmd, names="value")
        self.btn_send.on_click(lambda _: self._take_input())
        self.btn_stop.on_click(self._on_stop)
        self.btn_home.on_click(self._on_home)
        self.btn_coax.on_click(self._on_coax)
        self.dd_level.observe(self._on_level, names="value")
        self.tb_mode.observe(self._on_mode, names="value")
        self.btn_reset.on_click(lambda _: self._reset(self.session.game.level_id))
        self.btn_info.observe(self._on_info, names="value")
        self.btn_quit.on_click(lambda _: self.quit())

        self.box = W.VBox([
            W.HBox([self.dd_level, self.tb_mode]),
            W.HBox([self.btn_reset, self.btn_info, self.btn_quit]),
            self.img, self.hud,
            W.HBox([self.cmd, self.btn_send, self.btn_stop, self.btn_home, self.btn_coax]),
            self.extra,
        ])
        self.alive = threading.Event()
        self.alive.set()
        self._render(force=True)
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _level_options(self):
        opts = []
        for lid in CAMPAIGN + ["daily"]:
            lock = "" if self.progress.is_unlocked(lid) else "🔒 "
            stars = stars_text(self.progress.stars(lid)) if self.progress.level(lid).get("clears") else ""
            opts.append((f"{lock}{level_title(lid)} {stars}", lid))
        return opts

    # ---------- 玩家操作 ----------
    def _on_cmd(self, change):
        if change["new"].strip():
            self._take_input()

    def _take_input(self, text=None):
        text = (self.cmd.value if text is None else text).strip()
        self.cmd.value = ""
        if not text:
            return
        slash = handle_slash(self.session, text)
        if slash is not None:
            if slash.get("changed"):
                self._after_level_change()
            self.extra.value = slash.get("html", "")
            self.say = slash["say"]
            self.dirty = True
            return
        if self.future is not None:
            self.say = "等等，我還在想上一句！（急的話先按「停！」）"
            self.dirty = True
            return
        pre = self.session.preprocess(text)
        self.events.extend(pre["events"])
        if pre["handled"]:
            self.say = pre["say"]
        else:
            self.future = EXECUTOR.submit(self.session.think, text, None, pre["refuse"])
            self.future_info = {"command": text, "kind": "command", "depth": 0}
        self.dirty = True

    def _on_stop(self, _):
        self.events.extend(self.session.stop())
        if self.future_info:
            self.future_info["discard"] = True    # 正在想的那句也不要了
        self.say = "收到！緊急煞車！"
        self.dirty = True

    def _on_home(self, _):
        self.events.extend(self.session.local_plan([{"op": "return_home"}], "回充"))
        self.say = "好啦，回家充電。"
        self.dirty = True

    def _on_coax(self, _):
        self._take_input(random.choice(COAX_LINES))

    def _on_mode(self, change):
        self.session.agent.mode = change["new"]
        self.say = f"切換成{'正經' if change['new'] == 'serious' else '賣蠢'}模式。"
        self.dirty = True

    def _on_level(self, change):
        if self._busy_ui:
            return
        ok, msg = change_level(self.session, change["new"])
        if ok:
            self._after_level_change()
        else:
            self._busy_ui = True
            self.dd_level.value = change["old"]
            self._busy_ui = False
        self.say = msg
        self.dirty = True

    def _on_info(self, change):
        from ..render.hud import achievements_html, levels_html
        self.extra.value = (levels_html(self.progress) + achievements_html(self.progress) + HELP) if change["new"] else ""

    def _reset(self, level):
        ok, msg = change_level(self.session, level)
        if ok:
            self._after_level_change()
        self.say = msg
        self.dirty = True

    def _after_level_change(self):
        if self.future_info:
            self.future_info["discard"] = True
        self.events.clear()
        self._busy_ui = True
        self.dd_level.options = self._level_options()
        self.dd_level.value = self.session.game.level_id
        self._busy_ui = False

    # ---------- 背景遊戲迴圈 ----------
    def _loop(self):
        was_over = False
        while self.alive.is_set():
            try:
                ev = self.session.tick()
                if ev:
                    self.events.extend(ev)
                    self.dirty = True
                if self.future is not None and self.future.done():
                    fut, info = self.future, self.future_info
                    self.future = self.future_info = None
                    try:
                        res = fut.result()
                    except Exception as exc:   # noqa: BLE001
                        res, self.say = None, f"（大腦當機：{type(exc).__name__}）"
                    if res is not None and not info.get("discard"):
                        self.events.extend(self.session.apply(info["command"], res, kind=info["kind"],
                                                              depth=info["depth"]))
                        self.say = res["say"] or "……"
                    self.dirty = True
                if self.future is None:
                    fb = self.session.pop_feedback()
                    if fb:
                        self.future = EXECUTOR.submit(self.session.think, fb["command"], fb)
                        self.future_info = {"command": fb["command"], "kind": "feedback", "depth": fb["depth"]}
                        self.dirty = True
                over = self.session.game.over
                if over and not was_over:            # 剛結束：更新選關清單（可能解鎖了新關卡）
                    self._busy_ui = True
                    self.dd_level.options = self._level_options()
                    self.dd_level.value = self.session.game.level_id
                    self._busy_ui = False
                was_over = over
                self._render()
            except Exception as exc:   # noqa: BLE001
                self.hud.value = f"<pre>背景迴圈錯誤：{html.escape(repr(exc))}</pre>"
            time.sleep(self.tick_s)

    def _render(self, force=False):
        thinking = self.future is not None
        if not (force or self.dirty or thinking):
            return
        self.dirty = False
        self.frame += 1
        s = self.session
        with s.lock:
            if HAS_MPL:
                pic = render_png(s.game, thinking=thinking, frame=self.frame, emotion=s.emotion,
                                 mood=s.mood.name if s.gameplay and s.mode == "silly" else None)
            else:
                pic = map_html(s.game)
            txt = hud_html(s, self.say, self.events, thinking)
        self.img.value = pic
        self.hud.value = txt

    def quit(self):
        self.alive.clear()
        for w in (self.cmd, self.btn_send, self.btn_stop, self.btn_home, self.btn_coax, self.dd_level,
                  self.tb_mode, self.btn_reset, self.btn_quit, self.btn_info):
            w.disabled = True
        self.say = "遊戲結束，謝謝遊玩！"
        self._render(force=True)


def play_widgets(level=1, mode="silly", tick=0.35, feedback_rounds=1, unlock_all=False, seed=None):
    """▶️ 即時模式。"""
    global _ACTIVE_UI
    try:
        import ipywidgets  # noqa: F401
        from IPython.display import display
    except ImportError:
        print("沒有 ipywidgets：請改用 play() 文字模式，或執行 %pip install ipywidgets")
        return None
    progress = Progress(unlock_all=unlock_all)
    if not progress.is_unlocked(level):
        print(f"🔒 第 {level} 關還沒解鎖，先從第 1 關開始（或用 unlock_all=True）。")
        level = 1
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.quit()
    _ACTIVE_UI = WidgetGame(level, mode, tick, feedback_rounds, progress=progress, seed=seed)
    display(_ACTIVE_UI.box)
    return _ACTIVE_UI
