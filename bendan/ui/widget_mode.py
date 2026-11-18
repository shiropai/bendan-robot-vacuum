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
- 🎤 語音輸入：
  - 有 Whisper（`bendan.voice`，在自己電腦上跑）：**按住 🎤 講話、放開送出**（只點一下＝開始錄，再點一下結束）。
    瀏覽器錄 16 kHz WAV → 透過一個隱藏的 widget 交給 Python → Whisper 在背景執行緒轉文字 → 當成指令送出。
    用吼的（音量很大）會被當成「大吼」，笨笨會不開心。
  - 沒有 Whisper：改用 Chrome 的 Web Speech API。
  - 兩種都需要「安全來源」（https 或 localhost）。課程 JupyterHub 是 http，瀏覽器不給麥克風（實測 `not-allowed`），
    按下去會顯示替代方案（電腦內建聽寫）。評估與設定見 `docs/voice_input.md`。
"""
import html
import json
import random
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from ..gameplay.progress import Progress
from ..gameplay.scoring import stars_text
from ..render import bubble_html, history_html, render_svg, side_html
from ..session import EXECUTOR, Session
from ..world.constants import E
from ..world.levels import CAMPAIGN, level_title
from .commands import COAX_LINES, HELP, change_level, handle_slash, next_level

_ACTIVE_UI = None
STT_EXECUTOR = ThreadPoolExecutor(max_workers=1)     # 語音辨識另外一條執行緒，不跟 LLM 搶

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
    // ipywidgets 收到 change 才會同步到 Python；先送空字串再送內容，同一句話（例如語音填進來的）也能再送一次
    var v = i.value;
    i.value = ''; i.dispatchEvent(new Event('change', { bubbles: true }));
    i.value = v; i.dispatchEvent(new Event('change', { bubbles: true }));
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
      else if (act === 'mic') { if (micMode() !== 'whisper') mic(a); }
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
  // ---- 🎤 Whisper（Python 端辨識）：按住講話、放開送出；只點一下＝開始錄，再點一下結束 ----
  var recState = null, pressing = false, pressT = 0;
  function micMode() { var b = q('.bd-mic'); return b ? b.getAttribute('data-stt') : ''; }
  function canRecord() {
    return window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia;
  }
  async function recStart(btn) {
    if (recState) return;
    if (!canRecord()) { toast(MIC_HELP, 0); return; }
    var stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    } catch (err) { toast('🎤 拿不到麥克風（' + err.name + '）：請允許這個網站使用麥克風。', 8000); return; }
    var Ctx = window.AudioContext || window.webkitAudioContext, ctx;
    try { ctx = new Ctx({ sampleRate: 16000 }); } catch (err) { ctx = new Ctx(); }   // 16 kHz＝Whisper 的取樣率
    var src = ctx.createMediaStreamSource(stream), node = ctx.createScriptProcessor(4096, 1, 1), chunks = [];
    node.onaudioprocess = function (e) {
      var d = e.inputBuffer.getChannelData(0), s = 0;
      chunks.push(new Float32Array(d));
      for (var k = 0; k < d.length; k += 8) s += d[k] * d[k];
      btn.style.boxShadow = '0 0 0 ' + Math.min(14, Math.sqrt(s / (d.length / 8)) * 90).toFixed(1) + 'px rgba(230,57,70,.35)';
    };
    src.connect(node); node.connect(ctx.destination);
    recState = { ctx: ctx, stream: stream, src: src, node: node, chunks: chunks, rate: ctx.sampleRate, toggle: false };
    recState.timer = setTimeout(function () { recStop(btn); }, 15000);          // 最長 15 秒
    btn.classList.add('on'); btn.textContent = '🔴';
    if (!pressing) { recState.toggle = true; toast('🎤 錄音中……講完再按一次 🎤', 4000); }
  }
  function recStop(btn) {
    var r = recState; if (!r) return; recState = null;
    clearTimeout(r.timer);
    try { r.node.disconnect(); r.src.disconnect(); } catch (err) { /* 已經斷開 */ }
    r.stream.getTracks().forEach(function (t) { t.stop(); });
    r.ctx.close();
    btn.classList.remove('on'); btn.textContent = '🎤'; btn.style.boxShadow = '';
    var n = 0; r.chunks.forEach(function (c) { n += c.length; });
    var pcm = new Int16Array(n), o = 0;
    r.chunks.forEach(function (c) {
      for (var k = 0; k < c.length; k++) { var v = Math.max(-1, Math.min(1, c[k])); pcm[o++] = v < 0 ? v * 32768 : v * 32767; }
    });
    sendAudio(pcm, r.rate);
  }
  function wavBase64(pcm, rate) {
    var buf = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(buf);
    function str(off, t) { for (var k = 0; k < t.length; k++) v.setUint8(off + k, t.charCodeAt(k)); }
    str(0, 'RIFF'); v.setUint32(4, 36 + pcm.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, rate, true);
    v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    str(36, 'data'); v.setUint32(40, pcm.length * 2, true);
    for (var k = 0; k < pcm.length; k++) v.setInt16(44 + k * 2, pcm[k], true);
    var bytes = new Uint8Array(buf), bin = '';
    for (var j = 0; j < bytes.length; j += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(j, j + 0x8000));
    return btoa(bin);
  }
  function sendAudio(pcm, rate) {
    var box = q('.bendan-audio input'); if (!box) return;
    var auto = q('.bd-autosend');
    box.value = JSON.stringify({ wav: wavBase64(pcm, rate), auto: !auto || auto.checked, id: Date.now() });
    box.dispatchEvent(new Event('change', { bubbles: true }));
  }
  // 測試用：不用麥克風，直接把一段聲音（Float32Array、取樣率）送進辨識流程
  root.__bendanSendAudio = function (floats, rate) {
    var pcm = new Int16Array(floats.length);
    for (var k = 0; k < floats.length; k++) { var v = Math.max(-1, Math.min(1, floats[k])); pcm[k] = v < 0 ? v * 32768 : v * 32767; }
    sendAudio(pcm, rate || 16000);
  };
  root.addEventListener('pointerdown', function (e) {
    var b = e.target.closest('[data-act=mic]');
    if (!b || micMode() !== 'whisper') return;
    e.preventDefault();
    if (recState) { if (recState.toggle) recStop(b); return; }
    try { b.setPointerCapture(e.pointerId); } catch (err) { /* 舊瀏覽器 */ }
    pressing = true; pressT = Date.now();
    recStart(b);
  });
  root.addEventListener('pointerup', function () {
    if (!pressing) return;
    pressing = false;
    if (!recState || recState.toggle) return;
    if (Date.now() - pressT < 350) { recState.toggle = true; toast('🎤 錄音中……講完再按一次 🎤', 4000); }
    else recStop(q('.bd-mic'));
  });
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


def mic_html(stt_label=""):
    """🎤 按鈕。有 Whisper 時 data-stt="whisper"（按住說話），否則用瀏覽器的語音辨識。"""
    if stt_label:
        mode, tip = "whisper", f"按住說話、放開送出（只點一下＝開始，再點一下結束）｜{stt_label}"
    else:
        mode, tip = "browser", "語音輸入（按一下開始說話）"
    return (f"<div class='bd-micbox'><button class='bd-mic' data-act='mic' data-stt='{mode}' "
            f"title='{html.escape(tip, quote=True)}'>🎤</button>"
            "<label title='辨識完自動送出（取消的話會先放進輸入框，讓你改一改再按 Enter）'>"
            "<input type='checkbox' class='bd-autosend' checked>自動送出</label></div>")


MIC_HTML = mic_html()
CLOSE_POPUP = ("<img src='data:,' alt='' style='display:none' onerror=\"var r=this.closest('.bendan-game');"
               "if(r&&r.classList.contains('bendan-popped'))window.close();\">")


class WidgetGame:
    def __init__(self, level=0, mode="silly", tick=0.3, feedback_rounds=1, progress=None, seed=None, view="iso",
                 stt=None):
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
        self._filling = False
        self.closed = False
        self.stt = stt                              # 語音辨識後端（bendan.voice）；None＝用瀏覽器的語音辨識
        self.stt_future = None

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
        self.mic = W.HTML(mic_html(getattr(stt, "label", "") if stt else ""))
        self.audio_in = W.Text(continuous_update=False, layout=W.Layout(display="none"))   # 瀏覽器錄音 → Python
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
        self.audio_in.add_class("bendan-audio")
        self.audio_in.observe(self._on_audio, names="value")
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
        self.box = W.VBox([self.js, self.head, controls, main, self.extra, self.audio_in])
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
        if change["new"].strip() and not self._filling:
            self._take_input()

    # ---------- 🎤 語音 ----------
    def _on_audio(self, change):
        raw = change["new"]
        if not raw:
            return
        self.audio_in.value = ""                    # 清掉，下一段錄音才會再觸發
        try:
            msg = json.loads(raw)
        except ValueError:
            return
        if self.stt is None:
            self.say = "🎤 這台電腦沒有 Whisper：pip install mlx-whisper（Mac）或 faster-whisper，再重新執行這一格。"
            self.dirty = True
            return
        if self.stt_future is not None:
            self.say = "🎧 上一句還在聽寫，等一下再講。"
            self.dirty = True
            return
        from ..voice import transcribe
        self.stt_future = STT_EXECUTOR.submit(transcribe, msg["wav"], self.stt)
        self.stt_auto = bool(msg.get("auto", True))
        self.say = "🎧 聽寫中……"
        self.dirty = True

    def _voice_done(self, fut):
        """語音辨識完成（在背景迴圈裡呼叫）：送出指令，或放進輸入框讓玩家改。"""
        try:
            tr = fut.result()
        except Exception as exc:   # noqa: BLE001
            self.say = f"🎤 語音辨識出錯：{type(exc).__name__}: {str(exc)[:80]}"
            self.dirty = True
            return
        if not tr.text:
            self.say = f"🎤 {tr.note or '沒聽清楚，再說一次？'}"
            self.dirty = True
            return
        text = tr.text + ("！！！" if tr.shout else "")    # 用吼的 → 語氣分析會判成「大吼」
        self.events.append(E("voice", f"🎤 聽到：「{text}」（{tr.seconds:.1f} 秒錄音，辨識 {tr.latency:.1f} 秒）"))
        if tr.shout:
            self.events.append(E("shout", "📢 你用吼的！笨笨嚇了一跳。"))
        if self.stt_auto:
            self._take_input(text, source="voice")
        else:
            self._filling = True
            try:
                self.cmd.value = text
            finally:
                self._filling = False
            self.say = "🎤 聽到了，確認一下再按 Enter 送出。"
        self.dirty = True

    def _take_input(self, text=None, source="text"):
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
        pre = self.session.preprocess(text, source=source)
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
                if self.stt_future is not None and self.stt_future.done():
                    fut, self.stt_future = self.stt_future, None
                    self._voice_done(fut)
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


def play_widgets(level=None, mode="silly", tick=0.3, feedback_rounds=1, unlock_all=False, seed=None, view="iso",
                 voice="auto"):
    """▶️ 遊戲視窗（推薦）。level=None 會從「還沒破的第一關」開始。

    voice："auto"＝有裝 Whisper 就用（按住 🎤 說話）；"off"＝不用 Whisper（🎤 改用瀏覽器語音辨識）；
    也可以直接給 `bendan.voice.connect_stt(...)` 回傳的後端。
    """
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
    stt = None
    if voice not in (None, False, "off"):
        from .. import voice as voice_mod
        if isinstance(voice, str):
            stt = voice_mod.STATE.backend or voice_mod.connect_stt(voice)
        else:
            stt = voice
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.quit()
    _ACTIVE_UI = WidgetGame(level, mode, tick, feedback_rounds, progress=progress, seed=seed, view=view, stt=stt)
    display(_ACTIVE_UI.box)
    return _ACTIVE_UI
