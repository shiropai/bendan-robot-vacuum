"""🎮 遊戲視窗（ipywidgets）：像遊戲一樣的單一畫面，可以「彈出成獨立視窗」或全螢幕。

    ┌ 🧹 笨笨掃地機  第 3 關……            [🪟 彈出成獨立視窗] [⛶ 全螢幕] ┐
    │ 選關｜賣蠢/正經｜🔄 視角｜↺ 重來｜下一關 ▶｜📋 說明｜結束             │
    │ ┌──────────── 遊戲畫面（SVG）────────────┐ ┌──── 右側面板 ────┐ │
    │ │  黃箭頭＝前方、1 2 3＝往前幾格、左／右   │ │ 🧭 面向東 ➡       │ │
    │ └─────────────────────────────────────────┘ │ 🔋💗🩸 量表        │ │
    │ 🤖 笨笨：「收到，但撞到不是我的錯」            │ 難度標籤、事件     │ │
    │ [ 跟笨笨說話…    ][送出][🎤][✋ 停！][🔋 回充][💗 哄一下]  └──────────┘ │
    │ 📜 指令紀錄（最新在上）：你說了什麼 → 笨笨回什麼、做了什麼 → 結果       │
    └──────────────────────────────────────────────────────────────────────┘

技術說明：
- 遊戲迴圈與 LLM 都在背景執行緒，按「停！」可以隨時打斷。畫面是 ipywidgets（透過 Jupyter 的 comm 跟 Python 溝通）。
- 「彈出視窗」是一小段前端 JS：把整個遊戲的 DOM 搬進 `window.open()` 開的新視窗（同一個網域，
  widget 的事件和通訊照常運作）；關掉視窗會自動搬回 Notebook。**不需要安裝任何 JupyterLab 擴充套件**。
  實測課程 JupyterHub（JupyterLab 4.6、ipywidgets 8）：只有 widgets 擴充套件、沒有 jupyter-server-proxy／voila，
  所以沒辦法另開一個網頁伺服器；這是不用裝東西就能做到「彈出式遊戲視窗」的方法。
- 鍵盤：Enter 送出（中文輸入法選字時不會誤送）、Esc＝停！、↑／↓ 叫出之前講過的指令；點指令紀錄可以把那句放回輸入框。
- 🎤 語音輸入：Chrome 的 Web Speech API。課程 JupyterHub 是 http，瀏覽器不給麥克風（實測 `not-allowed`），
  按下去會顯示替代方案（電腦內建聽寫）。評估見 `docs/voice_input.md`。
"""
import html
import json
import random
import threading
import time
from collections import deque

from ..gameplay.progress import Progress
from ..gameplay.scoring import stars_text
from ..render import bubble_html, history_html, render_svg, side_html
from ..session import EXECUTOR, Session
from ..world.levels import CAMPAIGN, level_title
from .commands import COAX_LINES, HELP, change_level, handle_slash, next_level

_ACTIVE_UI = None

MIC_HELP = (
    "🎤 <b>瀏覽器不給麥克風權限</b>：課程 JupyterHub 是 http（不是 https），Chrome 只在安全連線開放麥克風。<br>"
    "✅ <b>現在就能用的方法：電腦內建聽寫</b>——Mac 按兩下 <kbd>fn</kbd>（或 🌐 鍵）、Windows 按 <kbd>Win</kbd>+<kbd>H</kbd>，"
    "對著輸入框直接講中文，講完按 Enter。<br>"
    "⚙️ 想讓 🎤 按鈕直接能用：請助教幫 JupyterHub 加上 https；或只在自己的電腦上，到 Chrome 的 "
    "<code>chrome://flags/#unsafely-treat-insecure-origin-as-secure</code> 加入這個網址後重開瀏覽器。"
    " <button class='bd-btn' data-act='close-toast'>知道了</button>")

GAME_CSS = """
.bendan-game{background:#fffdf8;border:2px solid #e9c46a;border-radius:16px;padding:10px 12px;color:#222;
  max-width:1200px;box-sizing:border-box;font-family:-apple-system,'PingFang TC','Noto Sans TC','Microsoft JhengHei',sans-serif}
.bendan-game.bendan-popped,.bendan-game:fullscreen{max-width:none;border:none;border-radius:0;min-height:100vh;overflow:auto}
body.bendan-popup-body{overflow:auto!important;margin:0;background:#fffdf8!important;position:static!important}
.bendan-main{display:flex!important;flex-flow:row wrap!important;gap:12px;align-items:flex-start}
.bendan-left{flex:1 1 560px!important;min-width:320px}
.bendan-right{flex:0 1 340px!important;min-width:260px;background:#fff;border:1px solid #eee2c6;border-radius:12px;padding:4px 10px}
.bendan-controls,.bendan-inputrow{flex-wrap:wrap!important;gap:4px;align-items:center}
.bendan-cmd{flex:1 1 220px!important;width:auto!important;min-width:180px}
.bendan-cmd input{font-size:16px!important;height:38px!important;border-radius:8px!important}
.bendan-inputrow .widget-button{height:38px;font-size:14px}
.bendan-game .bendan-board{max-height:62vh}
.bendan-popped .bendan-board,.bendan-game:fullscreen .bendan-board{max-height:70vh}
.bd-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}
.bd-title{font-size:20px;font-weight:bold}
.bd-btn{font-size:14px;padding:5px 10px;border-radius:8px;border:1px solid #bbb;background:#fff;cursor:pointer;margin-left:4px;color:#222}
.bd-btn:hover{background:#fff3d6}
.bd-only-popped{display:none}
.bendan-popped .bd-only-popped{display:inline-block}
.bendan-popped .bd-hide-popped{display:none}
.bd-toast{display:none;position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:10000;width:min(760px,92vw);
  background:#fff3cd;border:1px solid #f0ad4e;border-radius:12px;padding:10px 14px;font-size:13px;line-height:1.7;
  color:#222;box-shadow:0 8px 24px rgba(0,0,0,.18)}
.bd-mic{font-size:20px;height:38px;width:46px;border-radius:8px;border:1px solid #ccc;background:#fff;cursor:pointer}
.bd-mic.on{background:#ffe3e3;border-color:#e63946;animation:bdpulse 1s infinite}
.bd-micbox{display:flex;align-items:center;gap:4px;font-size:11px;color:#666}
@keyframes bdpulse{50%{transform:scale(1.1)}}
.bd-thinking i{animation:bdblink 1.2s infinite;font-style:normal;font-weight:bold}
.bd-thinking i:nth-child(2){animation-delay:.2s}.bd-thinking i:nth-child(3){animation-delay:.4s}
.bd-blink{animation:bdblink .8s infinite}
@keyframes bdblink{0%,100%{opacity:.15}50%{opacity:1}}
.bd-placeholder{padding:14px;border:2px dashed #e9c46a;border-radius:12px;background:#fffdf0;font-size:15px;color:#222}
.bendan-game [data-cmd]{cursor:pointer}.bendan-game [data-cmd]:hover{text-decoration:underline}
.bd-keys{font-size:11px;color:#888;margin:2px 0 4px}
kbd{border:1px solid #bbb;border-bottom-width:2px;border-radius:4px;padding:0 4px;font-size:11px;background:#fafafa}
"""

GAME_JS = r"""
var tries = 0;
(function boot() {
  var root = el.closest('.bendan-game');
  if (!root) { if (tries++ < 60) setTimeout(boot, 100); return; }
  if (root.__bendan) return;
  root.__bendan = true;
  var q = function (s) { return root.querySelector(s); };
  var input = function () { return q('.bendan-cmd input'); };
  var hist = [], hpos = 0, ph = null, rec = null, toastTimer = null;

  function toast(msg, ms) {
    var t = q('.bd-toast'); if (!t) return;
    t.innerHTML = msg; t.style.display = 'block';
    clearTimeout(toastTimer);
    if (ms !== 0) toastTimer = setTimeout(function () { t.style.display = 'none'; }, ms || 6000);
  }
  function clickBtn(cls) { var b = q('.' + cls); if (b && !b.disabled) b.click(); }
  function send(text) {
    var i = input(); if (!i) return;
    if (text !== undefined) i.value = text;
    if (!i.value.trim()) return;
    hist.push(i.value); hpos = hist.length;
    i.dispatchEvent(new Event('change', { bubbles: true }));   // ipywidgets 收到 change 才會同步到 Python
  }

  root.addEventListener('keydown', function (e) {
    var i = input();
    if (i && e.target === i) {
      if (e.key === 'Enter') {
        if (e.isComposing || e.keyCode === 229) return;          // 中文輸入法還在選字
        e.preventDefault(); e.stopPropagation(); send(); return;
      }
      if (e.key === 'ArrowUp' && hist.length) { e.preventDefault(); hpos = Math.max(0, hpos - 1); i.value = hist[hpos]; return; }
      if (e.key === 'ArrowDown' && hist.length) { e.preventDefault(); hpos = Math.min(hist.length, hpos + 1); i.value = hist[hpos] || ''; return; }
    }
    if (e.key === 'Escape') { e.preventDefault(); clickBtn('bendan-stop'); }
  }, true);

  root.addEventListener('click', function (e) {
    var a = e.target.closest('[data-act]');
    if (a) {
      var act = a.getAttribute('data-act');
      if (act === 'popout') popout();
      else if (act === 'dock') dock(false);
      else if (act === 'fullscreen') fullscreen();
      else if (act === 'mic') mic(a);
      else if (act === 'close-toast') { var t = q('.bd-toast'); if (t) t.style.display = 'none'; }
      return;
    }
    var c = e.target.closest('[data-cmd]');
    if (c) { var i = input(); if (i) { i.value = c.getAttribute('data-cmd'); i.focus(); } }
  });

  function popout() {
    if (root.__win && !root.__win.closed) { root.__win.focus(); return; }
    var w = window.open('', '', 'width=1240,height=920');
    if (!w) { toast('😵 彈出視窗被瀏覽器擋住了：點網址列右邊「已封鎖彈出式視窗」的圖示 → 一律允許，再按一次。', 10000); return; }
    var d = w.document;
    d.open();
    d.write('<!doctype html><html><head><meta charset="utf-8"><title>🧹 笨笨掃地機</title></head><body></body></html>');
    d.close();
    document.querySelectorAll('style, link[rel="stylesheet"]').forEach(function (n) {
      var c = n.cloneNode(true); if (n.tagName === 'LINK') c.href = n.href; d.head.appendChild(c);
    });
    (document.adoptedStyleSheets || []).forEach(function (sh) {
      try {
        var st = d.createElement('style');
        st.textContent = Array.prototype.map.call(sh.cssRules, function (r) { return r.cssText; }).join('\n');
        d.head.appendChild(st);
      } catch (err) { /* 跨網域的樣式表讀不到，略過 */ }
    });
    Array.prototype.forEach.call(document.body.attributes, function (a) {
      if (a.name !== 'class' && a.name !== 'style') d.body.setAttribute(a.name, a.value);
    });
    d.body.className = document.body.className + ' bendan-popup-body';
    ph = document.createElement('div');
    ph.className = 'bd-placeholder';
    ph.innerHTML = '🪟 遊戲正在獨立視窗裡進行（找不到的話看看其他視窗）。關掉那個視窗，遊戲就會回到這裡。 ';
    var back = document.createElement('button');
    back.className = 'bd-btn'; back.textContent = '⤓ 把遊戲拉回這裡';
    back.onclick = function () { dock(false); };
    ph.appendChild(back);
    root.parentNode.insertBefore(ph, root);
    d.body.appendChild(root);
    root.classList.add('bendan-popped');
    root.__win = w;
    w.addEventListener('pagehide', function () { dock(true); });
    window.addEventListener('beforeunload', function () { try { w.close(); } catch (err) {} });
    setTimeout(function () { var i = input(); if (i) i.focus(); }, 200);
  }
  function dock(fromClose) {
    var w = root.__win; root.__win = null;
    if (ph && ph.isConnected) { ph.parentNode.insertBefore(root, ph); ph.remove(); }
    ph = null;
    root.classList.remove('bendan-popped');
    if (!fromClose && w && !w.closed) w.close();
  }
  function fullscreen() {
    var d = root.ownerDocument;
    if (d.fullscreenElement) { d.exitFullscreen(); return; }
    if (root.requestFullscreen) root.requestFullscreen().catch(function (err) { toast('無法全螢幕：' + err.message); });
  }
  function mic(btn) {
    var R = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (rec) { rec.stop(); return; }
    if (!R || !window.isSecureContext) { toast(MIC_HELP, 0); return; }
    var i = input(), finalText = '';
    rec = new R(); rec.lang = 'zh-TW'; rec.interimResults = true; rec.continuous = false;
    btn.classList.add('on'); btn.textContent = '🔴';
    rec.onresult = function (ev) {
      var t = ''; finalText = '';
      for (var k = 0; k < ev.results.length; k++) {
        t += ev.results[k][0].transcript;
        if (ev.results[k].isFinal) finalText += ev.results[k][0].transcript;
      }
      if (i) i.value = t;
    };
    rec.onerror = function (ev) {
      if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') toast(MIC_HELP, 0);
      else if (ev.error !== 'no-speech' && ev.error !== 'aborted') toast('🎤 語音辨識錯誤：' + ev.error);
    };
    rec.onend = function () {
      btn.classList.remove('on'); btn.textContent = '🎤'; rec = null;
      var auto = q('.bd-autosend');
      if (finalText.trim() && (!auto || auto.checked)) send(finalText);
    };
    try { rec.start(); } catch (err) { rec = null; btn.classList.remove('on'); btn.textContent = '🎤'; toast(MIC_HELP, 0); }
  }
  setTimeout(function () { var i = input(); if (i && !root.__win) i.focus(); }, 400);
})();
"""


def _js_loader():
    code = "var MIC_HELP = " + json.dumps(MIC_HELP) + ";\n" + GAME_JS
    handler = "new Function('el', " + json.dumps(code) + ")(this)"
    return (f"<style>{GAME_CSS}</style><div class='bd-toast'></div>"
            f"<img src='data:,' alt='' style='display:none' onerror=\"{html.escape(handler, quote=True)}\">")


MIC_HTML = ("<div class='bd-micbox'><button class='bd-mic' data-act='mic' title='語音輸入（按一下開始說話）'>🎤</button>"
            "<label title='辨識完自動送出'><input type='checkbox' class='bd-autosend' checked>自動送出</label></div>")
CLOSE_POPUP = ("<img src='data:,' alt='' style='display:none' onerror=\"var r=this.closest('.bendan-game');"
               "if(r&&r.classList.contains('bendan-popped'))window.close();\">")


class WidgetGame:
    def __init__(self, level=0, mode="silly", tick=0.3, feedback_rounds=1, progress=None, seed=None, view="iso"):
        import ipywidgets as W
        self.W = W
        self.progress = progress or Progress()
        self.session = Session(level, mode, feedback_rounds, progress=self.progress, seed=seed)
        self.session.view = view
        self.tick_s = tick
        self.say = self.session.game.cfg["intro"]
        self.events = deque(maxlen=8)
        self.future, self.future_info = None, None
        self.dirty = True
        self._busy_ui = False
        self.closed = False

        self.js = W.HTML(_js_loader())
        self.head = W.HTML()
        self.board = W.HTML()
        self.side = W.HTML()
        self.bubble = W.HTML()
        self.history = W.HTML()
        self.keys = W.HTML("<div class='bd-keys'><kbd>Enter</kbd> 送出　<kbd>Esc</kbd> 停！　<kbd>↑</kbd><kbd>↓</kbd> "
                           "叫出之前的指令　點紀錄裡的指令可以放回輸入框</div>")
        self.extra = W.HTML()
        self.cmd = W.Text(placeholder="跟笨笨說話，按 Enter 送出（例如：請往前走三格然後吸）", continuous_update=False)
        self.btn_send = W.Button(description="送出", button_style="primary", layout=W.Layout(width="64px"))
        self.mic = W.HTML(MIC_HTML)
        self.btn_stop = W.Button(description="✋ 停！", button_style="danger", tooltip="鍵盤 Esc 也可以",
                                 layout=W.Layout(width="82px"))
        self.btn_home = W.Button(description="🔋 回充", layout=W.Layout(width="82px"))
        self.btn_coax = W.Button(description="💗 哄一下", button_style="warning", layout=W.Layout(width="92px"))
        self.dd_level = W.Dropdown(options=self._level_options(), value=level, layout=W.Layout(width="270px"))
        self.tb_mode = W.ToggleButtons(options=[("賣蠢", "silly"), ("正經", "serious")], value=mode,
                                       style={"button_width": "56px"}, tooltips=["賣蠢模式", "正經模式（對照組）"])
        self.btn_view = W.Button(description="🔄 視角", tooltip="切換 2.5D／俯視（上方＝北）", layout=W.Layout(width="80px"))
        self.btn_reset = W.Button(description="↺ 重來", layout=W.Layout(width="74px"))
        self.btn_next = W.Button(description="下一關 ▶", layout=W.Layout(width="88px"))
        self.btn_info = W.ToggleButton(description="📋 關卡／成就／說明", tooltip="選關、成就與指令說明",
                                       layout=W.Layout(width="150px"))
        self.btn_quit = W.Button(description="結束", layout=W.Layout(width="60px"))

        self.cmd.add_class("bendan-cmd")
        self.btn_send.add_class("bendan-send")
        self.btn_stop.add_class("bendan-stop")
        self.cmd.observe(self._on_cmd, names="value")
        self.btn_send.on_click(lambda _: self._take_input())
        self.btn_stop.on_click(self._on_stop)
        self.btn_home.on_click(self._on_home)
        self.btn_coax.on_click(self._on_coax)
        self.dd_level.observe(self._on_level, names="value")
        self.tb_mode.observe(self._on_mode, names="value")
        self.btn_view.on_click(self._on_view)
        self.btn_reset.on_click(lambda _: self._reset(self.session.game.level_id))
        self.btn_next.on_click(self._on_next)
        self.btn_info.observe(self._on_info, names="value")
        self.btn_quit.on_click(lambda _: self.quit())

        controls = W.HBox([self.dd_level, self.tb_mode, self.btn_view, self.btn_reset, self.btn_next, self.btn_info,
                           self.btn_quit])
        inputrow = W.HBox([self.cmd, self.btn_send, self.mic, self.btn_stop, self.btn_home, self.btn_coax])
        left = W.VBox([self.board, self.bubble, inputrow, self.keys, self.history])
        right = W.VBox([self.side])
        main = W.HBox([left, right])
        for w, cls in ((controls, "bendan-controls"), (inputrow, "bendan-inputrow"), (left, "bendan-left"),
                       (right, "bendan-right"), (main, "bendan-main")):
            w.add_class(cls)
        self.box = W.VBox([self.js, self.head, controls, main, self.extra])
        self.box.add_class("bendan-game")
        self._controls = [self.cmd, self.btn_send, self.btn_stop, self.btn_home, self.btn_coax, self.dd_level,
                          self.tb_mode, self.btn_view, self.btn_reset, self.btn_next, self.btn_info, self.btn_quit]
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

    def _head_html(self):
        g = self.session.game
        best = self.progress.stars(g.level_id) if self.progress.level(g.level_id).get("clears") else 0
        best = f"<span title='最佳紀錄'>{stars_text(best)}</span>" if best else ""
        closer = CLOSE_POPUP if self.closed else ""
        return ("<div class='bd-head'><div><span class='bd-title'>🧹 笨笨掃地機</span>　"
                f"<span style='font-size:17px;font-weight:bold;color:#7a4b00'>{html.escape(level_title(g.level_id))}</span> "
                f"{best}</div><div>"
                "<button class='bd-btn bd-hide-popped' data-act='popout' title='開一個獨立的遊戲視窗'>🪟 彈出成獨立視窗</button>"
                "<button class='bd-btn bd-only-popped' data-act='dock'>⤓ 拉回 Notebook</button>"
                "<button class='bd-btn' data-act='fullscreen'>⛶ 全螢幕</button>"
                f"</div></div>{closer}")

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

    def _on_view(self, _):
        self.session.view = "top" if self.session.view == "iso" else "iso"
        self.say = "俯視視角：地圖上方＝北。" if self.session.view == "top" else "2.5D 視角：看右上角的指北針分辨方向。"
        self.dirty = True

    def _on_level(self, change):
        if self._busy_ui:
            return
        ok, msg = change_level(self.session, change["new"])
        if ok:
            self._after_level_change()
        else:
            self._set_dropdown(change["old"])
        self.say = msg
        self.dirty = True

    def _on_next(self, _):
        ok, msg = next_level(self.session)
        if ok:
            self._after_level_change()
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

    def _set_dropdown(self, value):
        self._busy_ui = True
        try:
            self.dd_level.options = self._level_options()
            self.dd_level.value = value
        finally:
            self._busy_ui = False

    def _after_level_change(self):
        if self.future_info:
            self.future_info["discard"] = True
        self.events.clear()
        self._set_dropdown(self.session.game.level_id)

    def _next_unlocked(self):
        lid = self.session.game.level_id
        if lid in CAMPAIGN and CAMPAIGN.index(lid) + 1 < len(CAMPAIGN):
            return self.progress.is_unlocked(CAMPAIGN[CAMPAIGN.index(lid) + 1])
        return True

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
                    self._set_dropdown(self.session.game.level_id)
                    self.dirty = True
                was_over = over
                self._render()
            except Exception as exc:   # noqa: BLE001
                self.side.value = f"<pre>背景迴圈錯誤：{html.escape(repr(exc))}</pre>"
            time.sleep(self.tick_s)

    def _render(self, force=False):
        thinking = self.future is not None
        if not (force or self.dirty or thinking):
            return
        self.dirty = False
        s = self.session
        with s.lock:
            mood = s.mood.name if s.gameplay and s.mode == "silly" else None
            values = {
                "board": render_svg(s.game, view=s.view, thinking=thinking, mood=mood, emotion=s.emotion,
                                    max_width=920),
                "side": side_html(s, self.events),
                "bubble": bubble_html(s, self.say, thinking),
                "history": history_html(s, limit=12),
                "head": self._head_html(),
            }
        for name, value in values.items():
            w = getattr(self, name)
            if w.value != value:
                w.value = value
        self.btn_next.disabled = self.closed or not self._next_unlocked()

    def quit(self):
        self.alive.clear()
        self.closed = True
        for w in self._controls:
            w.disabled = True
        self.say = "遊戲結束，謝謝遊玩！（重新執行這一格就能再玩）"
        self._render(force=True)


def play_widgets(level=None, mode="silly", tick=0.3, feedback_rounds=1, unlock_all=False, seed=None, view="iso"):
    """▶️ 遊戲視窗（推薦）。level=None 會從「還沒破的第一關」開始。"""
    global _ACTIVE_UI
    try:
        import ipywidgets  # noqa: F401
        from IPython.display import display
    except ImportError:
        print("沒有 ipywidgets：請改用 play() 文字模式，或把 Kernel 換成「Python 3 (ipykernel)」")
        return None
    progress = Progress(unlock_all=unlock_all)
    if level is None:
        level = progress.next_level()
    if not progress.is_unlocked(level):
        print(f"🔒 {level_title(level)} 還沒解鎖，先從第 1 關開始（或用 unlock_all=True）。")
        level = 1
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.quit()
    _ACTIVE_UI = WidgetGame(level, mode, tick, feedback_rounds, progress=progress, seed=seed, view=view)
    display(_ACTIVE_UI.box)
    return _ACTIVE_UI
