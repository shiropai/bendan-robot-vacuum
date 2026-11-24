"""🎮 遊戲視窗（ipywidgets）：像遊戲一樣的單一畫面，可以「彈出成獨立視窗」或全螢幕。

主畫面（一開始）：封面圖（`bendan/assets/cover.jpg`）＋大標題；左上 🗺️ 選關、正中間 ▶ 開始遊戲。
遊戲中不能選關：左上「⬅ 返回」回主畫面選關，右上「🎥 換視角」。

    ┌ [⬅ 返回] 🧹 笨笨掃地機  第 3 關……   [🪟 彈出] [⛶ 全螢幕] [🎥 換視角] ┐
    │ 賣蠢/正經｜🔊｜↺ 重來｜📋 成就／說明｜結束                           │
    │ ┌──────── 遊戲畫面（3D，Three.js）────────┐ ┌──── 右側面板 ────┐ │
    │ │ 〔🎥 跟隨 ▸〕按一下換下一個視角           │ │ 🧭 面向東 ➡       │ │
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
import base64
import html
import json
import random
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import llm
from ..gameplay.progress import Progress
from ..gameplay.scoring import stars_text
from ..render import bubble_html, history_html, side_html
from ..render.board import EMOTION_ICON, MOOD_LID
from ..render.scene import scene_html
from ..session import EXECUTOR, Session
from ..world.constants import E
from ..world.levels import CAMPAIGN, level_title
from .commands import COAX_LINES, HELP, change_level, handle_slash

COVER = Path(__file__).resolve().parent.parent / "assets" / "cover.jpg"
LEVEL_CMD_RE = re.compile(r"^\s*/(levels?|next|unlock)\b", re.I)    # 遊戲中不能換關（要回主畫面選）
WIDGET_HELP = re.sub(r"<b>斜線指令</b>.*?<br>", "", HELP, count=1, flags=re.S)


def cover_html():
    """主畫面的封面：AI 產生的插畫（沒有字）＋用 HTML 疊上去的大標題。沒有圖檔時用漸層背景。"""
    if COVER.exists():
        bg = f"url(data:image/jpeg;base64,{base64.b64encode(COVER.read_bytes()).decode()})"
    else:
        bg = "linear-gradient(135deg,#0f4c5c,#e36414)"
    return (f"<div class='bd-cover' style=\"background-image:{bg}\">"
            "<div class='bd-cover-shade'></div>"
            "<div class='bd-cover-title'><div class='bd-cover-sub'>用嘴巴指揮掃地機器人</div>"
            "<div class='bd-cover-main'>笨笨<br>掃地機</div>"
            "<div class='bd-cover-tag'>它會聽話……大概吧！</div></div></div>")

_ACTIVE_UI = None
STT_EXECUTOR = ThreadPoolExecutor(max_workers=1)     # 語音辨識另外一條執行緒，不跟 LLM 搶

# 3D 用的 Three.js（鎖定版本、ESM；第一次切到 3D 時才下載，約 750 KB）。3D 場景的程式在 scene3d.js
THREE_BASE = "https://cdn.jsdelivr.net/npm/three@0.160.0"
SCENE3D_JS = (Path(__file__).with_name("scene3d.js")).read_text(encoding="utf-8")

MIC_HELP = (
    "🎤 <b>瀏覽器不給麥克風權限</b>：課程 JupyterHub 是 http（不是 https），Chrome 只在安全連線開放麥克風。<br>"
    "✅ <b>現在就能用的方法：電腦內建聽寫</b>——Mac 按兩下 <kbd>fn</kbd>（或 🌐 鍵）、Windows 按 <kbd>Win</kbd>+<kbd>H</kbd>，"
    "對著輸入框直接講中文，講完按 Enter。<br>"
    "⚙️ 想讓 🎤 按鈕直接能用：請助教幫 JupyterHub 加上 https；或只在自己的電腦上，到 Chrome 的 "
    "<code>chrome://flags/#unsafely-treat-insecure-origin-as-secure</code> 加入這個網址後重開瀏覽器。"
    " <button class='bd-btn' data-act='close-toast'>知道了</button>")

GAME_CSS = """
.bd-titlescreen{position:relative!important;width:100%!important;aspect-ratio:16/9;min-height:300px;border-radius:14px;overflow:hidden;container-type:inline-size;
  margin:4px 0 6px 0;background:#0f4c5c}
.bd-coverbox{position:absolute!important;inset:0;margin:0!important;width:100%!important;height:100%!important}
.bd-coverbox>div,.bd-cover{width:100%;height:100%}
.bd-cover{position:relative;background-size:cover;background-position:center}
.bd-cover-shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.45) 0%,rgba(0,0,0,.12) 38%,rgba(0,0,0,0) 60%)}
.bd-cover-title{position:absolute;left:4%;top:17%;text-align:left;line-height:1.02;transform:rotate(-4deg)}
.bd-cover-main{font-size:8.6cqw;font-weight:900;letter-spacing:2px;
  background:linear-gradient(180deg,#fff27a 0%,#ffd000 38%,#ff8a00 72%,#ff5a00 100%);-webkit-background-clip:text;background-clip:text;color:transparent;
  -webkit-text-stroke:max(2px,.35cqw) #fff;paint-order:stroke fill;filter:drop-shadow(0 6px 0 #7a2e00) drop-shadow(0 10px 18px rgba(0,0,0,.45))}
.bd-cover-sub{display:inline-block;font-size:2.3cqw;font-weight:900;color:#fff;background:#222;border:3px solid #fff;
  border-radius:10px;padding:4px 12px;margin-bottom:10px;box-shadow:0 4px 0 rgba(0,0,0,.35)}
.bd-cover-tag{margin-top:1.4cqw;font-size:2.2cqw;font-weight:900;color:#fff;-webkit-text-stroke:1px #333;
  text-shadow:0 3px 0 #333,0 6px 12px rgba(0,0,0,.5)}
.bd-start{position:absolute!important;left:0!important;right:0!important;top:50%;margin:0 auto!important;transform:translateY(-50%);
  width:max-content!important;max-width:none!important;height:auto!important;
  font-size:max(18px,3.6cqw)!important;font-weight:900!important;padding:1.2cqw 4.8cqw!important;border-radius:999px!important;
  background:linear-gradient(180deg,#ffe066,#ff9f1c 60%,#ff7b00)!important;color:#4a2300!important;border:4px solid #fff!important;
  box-shadow:0 6px 0 #b85600,0 12px 26px rgba(0,0,0,.4)!important;z-index:3;line-height:1.3!important;cursor:pointer}
.bd-start:hover{filter:brightness(1.1)}
.bd-start:active{box-shadow:0 2px 0 #b85600!important;margin-top:4px!important}
.bd-levelpick{position:absolute!important;top:12px;left:12px;z-index:3;width:auto!important;margin:0!important}
.bd-levelpick select{font-size:15px!important;font-weight:bold;height:36px!important;border-radius:10px!important;border:3px solid #fff!important;
  background:rgba(255,255,255,.95)!important;min-width:260px}
.bd-levelpick label{color:#fff!important;font-weight:900;font-size:16px!important;text-shadow:0 2px 3px #000}
.bd-levelinfo{position:absolute!important;bottom:12px;left:12px;z-index:3;max-width:42%;margin:0!important}
.bd-levelinfo .bd-li{background:rgba(255,255,255,.9);border-radius:10px;padding:6px 10px;font-size:max(12px,1.5cqw);line-height:1.4;color:#333;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.bd-back{font-weight:bold!important;border-radius:10px!important}
.bd-topbar{align-items:center;gap:6px}
.bd-topbar>.widget-html{flex:1 1 auto}
.bd-3dbar{display:none!important}
.bd-modelpick{position:absolute!important;top:12px;right:12px;z-index:3;width:auto!important;margin:0!important}
.bd-modelpick .widget-label{color:#fff!important;font-weight:900;text-shadow:0 2px 3px #000}
.bd-modelpick button{background:rgba(255,255,255,.92)!important;font-weight:bold;border-radius:8px!important;margin-left:3px!important}
.bd-modelpick button.mod-active{background:#ffb703!important;box-shadow:inset 0 0 0 2px #c98a00!important}
.bd-benchbtn{position:absolute!important;top:54px;right:12px;z-index:3;width:auto!important;margin:0!important;font-weight:bold!important;
  border-radius:8px!important;background:rgba(255,255,255,.92)!important}
.bd-benchbtn.mod-active{background:#ffb703!important}
.bd-benchpanel{position:absolute!important;top:96px;left:4%;right:4%;bottom:12px;z-index:4;margin:0!important;overflow:auto;
  background:rgba(255,255,255,.97);border-radius:14px;box-shadow:0 8px 30px rgba(0,0,0,.45);padding:4px 14px!important}
.bd-bench h3{margin:6px 0}
.bd-bench table{border-collapse:collapse;width:100%;font-size:13px;margin:4px 0}
.bd-bench th,.bd-bench td{border-bottom:1px solid #eee;padding:5px 8px;text-align:center;vertical-align:top}
.bd-bench tr>th:first-child{text-align:left;white-space:nowrap}
.bd-bench .bd-tip{font-size:11px;color:#888;font-weight:normal;white-space:normal}
.bd-bench .bd-bar{height:6px;background:#ff9f1c;border-radius:3px;margin-top:4px}
.bd-bench .bd-best{background:#e7f7ea;font-weight:bold}
.bd-benchmeta{font-size:12px;color:#666;margin:2px 0}
.bd-cam{background:#ffb703!important;border-color:#c98a00!important;font-weight:bold}
.bd-stats{position:absolute;top:8px;left:8px;z-index:2;background:rgba(0,0,0,.62);color:#9ef7c8;font:12px/1.5 ui-monospace,monospace;padding:5px 9px;border-radius:8px;pointer-events:none;white-space:pre}
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
.bd-3dhost{position:relative;width:100%;min-height:120px}
.bd-3dhost canvas{width:100%!important;height:auto!important;border-radius:12px;display:block;touch-action:none}
.bd-3dbar{position:absolute;top:8px;right:8px;display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end}
.bd-3dbar .bd-btn{background:rgba(255,255,255,.88);font-size:13px;padding:4px 8px}
.bd-3dbar .bd-btn.on{background:#ffb703;border-color:#c98a00;font-weight:bold}
.bd-3dhint{position:absolute;left:10px;bottom:8px;font-size:11px;color:#fff;background:rgba(0,0,0,.35);border-radius:6px;padding:1px 6px;pointer-events:none}
.bd-rec{display:none;position:absolute;left:12px;top:10px;font:bold 13px monospace;color:#ff4d4d;text-shadow:0 0 3px #000;pointer-events:none}
.bd-cctv .bd-rec{display:block}
.bd-cctv canvas{filter:grayscale(.45) contrast(1.15) brightness(1.05)}
.bd-cctv:after{content:'';position:absolute;inset:0;border-radius:12px;pointer-events:none;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,.08) 0 2px,transparent 2px 4px),radial-gradient(ellipse at center,transparent 55%,rgba(0,0,0,.45))}
.bd-3dover{display:none;position:absolute;left:0;right:0;top:42%;text-align:center;font-size:40px;font-weight:bold;
  color:#2a9d8f;background:rgba(255,255,255,.85);padding:6px 0}
.bd-3dmsg{padding:40px;text-align:center;color:#666}
.bd-recbadge{display:none;position:absolute;right:10px;top:10px;font:bold 13px system-ui,sans-serif;color:#fff;background:rgba(214,40,40,.85);border-radius:8px;padding:3px 9px;pointer-events:none;animation:bdblink 1.6s infinite}
.bd-recdone{display:none;position:absolute;right:10px;bottom:8px;font-size:13px;background:rgba(255,255,255,.92);border-radius:8px;padding:3px 9px}
.bd-recbtn .bd-rec-on{display:none}.bd-recording .bd-recbtn .bd-rec-on{display:inline}.bd-recording .bd-recbtn .bd-rec-off{display:none}.bd-recording .bd-recbtn{background:#d62828;color:#fff;border-color:#9b1c1c}
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
      else if (act === 'cam') { var b3 = root.__bendan3d; if (b3 && b3.cycleCam) b3.cycleCam(); }
      else if (act === 'quality') { var b4 = root.__bendan3d; if (b4 && b4.cycleQuality) b4.cycleQuality(); }
      else if (act === 'stats') { var b5 = root.__bendan3d; if (b5 && b5.toggleStats) b5.toggleStats(); }
      else if (act === 'rec') { var b6 = root.__bendan3d; if (b6 && b6.toggleRec) b6.toggleRec(); else toast('🎬 3D 畫面還沒載入好，等一下再按。', 5000); }
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
    try { if (window.speechSynthesis) window.speechSynthesis.cancel(); } catch (err) { }   // 講話時笨笨先閉嘴，免得被錄進去
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

  // ===== v7：笨笨連續移動（每移動一格或轉 90 度＝30 幀）=====
  // 遊戲邏輯還是格子（房間、灰塵、碰撞都用格子算，LLM 也用格子描述），但畫面上的笨笨由前端自己畫：
  // Python 每個 tick 送來「笨笨現在在哪一格、面向哪」，這裡把上一格 → 這一格切成 30 個畫格播放，
  // 效果等於把地圖放大 30 倍、笨笨每幀走 1/30 格（3D 場景 scene3d.js 用這個 Motion）。
  var FRAMES = 30;
  function Motion() {
    var cur = null, q = [], seg = null, lastT = 0, ema = 0;
    function tail() { return q.length ? q[q.length - 1] : (seg ? seg.to : cur); }
    return {
      push: function (x, y, r, tickMs, now) {
        var t = tail();
        if (!t) { cur = { x: x, y: y, r: r }; lastT = now; return; }
        r = t.r + Math.atan2(Math.sin(r - t.r), Math.cos(r - t.r));          // 轉最近的方向
        if (Math.abs(x - t.x) + Math.abs(y - t.y) + Math.abs(r - t.r) < 1e-6) return;
        var gap = now - lastT; lastT = now;
        gap = Math.min(Math.max(gap, tickMs * 0.6), tickMs * 1.6);
        ema = ema ? ema * 0.7 + gap * 0.3 : tickMs;                           // 跟著實際的更新節奏走，才不會走走停停
        var d = Math.abs(x - t.x) + Math.abs(y - t.y);
        if (d > 3) { q = []; seg = null; cur = { x: x, y: y, r: r }; return; } // 換關、重來：直接跳過去
        q.push({ x: x, y: y, r: r, dur: ema * Math.max(1, d) });
      },
      at: function (now) {
        if (!cur) return null;
        if (!seg && q.length) seg = { from: cur, to: q.shift(), t0: now };
        while (seg) {
          var dur = seg.to.dur * (q.length > 1 ? 0.6 : 1);                  // 落後太多就走快一點追上
          var k = Math.min(1, (now - seg.t0) / dur);
          k = Math.floor(k * FRAMES + 1e-6) / FRAMES;                         // 一格切成 30 幀
          var f = seg.from, t = seg.to;
          cur = { x: f.x + (t.x - f.x) * k, y: f.y + (t.y - f.y) * k, r: f.r + (t.r - f.r) * k };
          if (k < 1) break;
          var end = seg.t0 + dur;
          seg = q.length ? { from: cur, to: q.shift(), t0: Math.max(end, now - 40) } : null;
          if (seg && seg.t0 > now) break;
        }
        return cur;
      },
      moving: function () { return !!seg || q.length > 0; },
      jump: function (x, y, r) { q = []; seg = null; cur = { x: x, y: y, r: r }; lastT = Date.now(); }   // 瞬間移動（掉洞後被撈回充電座）
    };
  }

  // 笨笨的即時狀態（隱藏的 .bd-botjs）：朗讀笨笨的話、音效開關。畫面上的笨笨由 3D 場景畫（scene3d.js）
  var bot = { st: null, raw: '' };
  function botSync() {
    var el = q('.bd-botjs');
    if (!el || el.textContent === bot.raw) return;
    bot.raw = el.textContent;
    try { bot.st = JSON.parse(bot.raw); } catch (err) { return; }
    speakLine(bot.st);
  }

  // ===== v7：🔊 笨笨說話（瀏覽器內建語音合成，不用裝東西；Mac 有「美佳」、Chrome 有「Google 國語（臺灣）」）=====
  var tts = { n: -1, voice: null };
  var EMO_VOICE = { '開心': [1.45, 1.1], '得意': [1.35, 1.05], '生氣': [0.85, 1.25], '委屈': [1.25, 0.9],
                    '害怕': [1.6, 1.3], '普通': [1.2, 1.05] };       // [音高, 語速]：跟著笨笨的情緒變
  function pickVoice() {
    var S = window.speechSynthesis, vs = (S && S.getVoices()) || [];
    function find(lang, name) {
      for (var i = 0; i < vs.length; i++) if (lang.test(vs[i].lang) && (!name || name.test(vs[i].name))) return vs[i];
      return null;
    }
    return find(/zh[-_]TW/i, /Google/) || find(/zh[-_]TW/i, /Meijia|美佳/) || find(/zh[-_]TW/i) || find(/^zh/i);
  }
  if (window.speechSynthesis) window.speechSynthesis.onvoiceschanged = function () { tts.voice = pickVoice(); };
  function speakLine(s) {
    var S = window.speechSynthesis;
    if (!S) return;
    if (!s.tts) { if (tts.n !== -1 && S.speaking) S.cancel(); tts.n = s.sayN; return; }
    if (s.sayN === tts.n) return;
    var first = tts.n === -1;
    tts.n = s.sayN;
    if (first) return;                           // 剛打開遊戲那一句不唸（瀏覽器規定要先有互動）
    var text = String(s.say || '').replace(/[（(][^）)]*[）)]/g, '')
      .replace(/[\u{1F000}-\u{1FAFF}\u{2190}-\u{2BFF}\u{FE0F}\u{200D}]/gu, '').trim();
    if (!text) return;
    var u = new SpeechSynthesisUtterance(text);
    u.lang = 'zh-TW';
    tts.voice = tts.voice || pickVoice();
    if (tts.voice) u.voice = tts.voice;
    var pv = EMO_VOICE[s.sayEmo] || EMO_VOICE['普通'];
    u.pitch = pv[0]; u.rate = pv[1];
    S.cancel();                                  // 只唸最新的一句
    S.speak(u);
  }
  new MutationObserver(botSync).observe(root, { subtree: true, childList: true, characterData: true });
  botSync();

/*SCENE3D*/
  setTimeout(function () { var i = input(); if (i && !root.__win) i.focus(); }, 400);
})();
"""


def _js_loader():
    code = ("var MIC_HELP = " + json.dumps(MIC_HELP) + ";\nvar THREE_BASE = " + json.dumps(THREE_BASE) + ";\n"
            + GAME_JS.replace("/*SCENE3D*/", SCENE3D_JS))
    handler = "new Function('el', " + json.dumps(code) + ")(this)"
    return (f"<style>{GAME_CSS}</style><div class='bd-toast'></div>"
            f"<img src='data:,' alt='' style='display:none' onerror=\"{html.escape(handler, quote=True)}\">")


def mic_html(stt_label=""):
    """🎤 按鈕。有 Whisper 時 data-stt="whisper"（按住說話），否則用瀏覽器的語音辨識。"""
    if stt_label:
        mode, tip = "whisper", f"按住說話、放開送出（只點一下＝開始，再點一下結束）｜{stt_label}"
    else:
        mode, tip = "browser", "語音輸入（按一下開始說話）｜這台電腦沒有 Whisper，改用瀏覽器的語音辨識"
    return (f"<div class='bd-micbox'><button class='bd-mic' data-act='mic' data-stt='{mode}' "
            f"title='{html.escape(tip, quote=True)}'>🎤</button>"
            "<label title='辨識完自動送出（取消的話會先放進輸入框，讓你改一改再按 Enter）'>"
            "<input type='checkbox' class='bd-autosend' checked>自動送出</label></div>")


MIC_HTML = mic_html()
CLOSE_POPUP = ("<img src='data:,' alt='' style='display:none' onerror=\"var r=this.closest('.bendan-game');"
               "if(r&&r.classList.contains('bendan-popped'))window.close();\">")


class WidgetGame:
    def __init__(self, level=0, mode="silly", tick=0.5, feedback_rounds=1, progress=None, seed=None, view="3d",
                 stt=None, tts=True):
        import ipywidgets as W
        self.W = W
        self.progress = progress or Progress()
        self.session = Session(level, mode, feedback_rounds, progress=self.progress, seed=seed)
        self.session.view = view
        self.tick_s = tick
        self.say_n = 0                              # 笨笨講了第幾句（前端看到變了就唸出來）
        self._talk(self.session.game.cfg["intro"])
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
        self.board3d = W.HTML("<div class='bd-3dhost'></div>")   # Three.js 畫在這裡（v8 起是唯一的遊戲畫面）
        from ..render.assets3d import assets_html
        self.assets3d = W.HTML(assets_html(), layout=W.Layout(display="none"))   # 3D 素材包（家具、寵物），一開始就送
        self.side = W.HTML()
        self.bubble = W.HTML()
        self.history = W.HTML()
        self.keys = W.HTML("<div class='bd-keys'><kbd>Enter</kbd> 送出　<kbd>Esc</kbd> 停！　<kbd>↑</kbd><kbd>↓</kbd> "
                           "叫出之前的指令　點紀錄裡的指令可以放回輸入框</div>")
        self.extra = W.HTML()
        self.cmd = W.Text(placeholder="跟笨笨說話，按 Enter 送出（例如：請往前走一公尺然後吸）", continuous_update=False)
        self.btn_send = W.Button(description="送出", button_style="primary", layout=W.Layout(width="64px"))
        self.mic = W.HTML(mic_html(getattr(stt, "label", "") if stt else ""))
        self.audio_in = W.Text(continuous_update=False, layout=W.Layout(display="none"))   # 瀏覽器錄音 → Python
        self.btn_stop = W.Button(description="✋ 停！", button_style="danger", tooltip="鍵盤 Esc 也可以",
                                 layout=W.Layout(width="82px"))
        self.btn_home = W.Button(description="🔋 回充", layout=W.Layout(width="82px"))
        self.btn_coax = W.Button(description="💗 哄一下", button_style="warning", layout=W.Layout(width="92px"))
        self.dd_level = W.Dropdown(options=self._level_options(), value=level, description="🗺️ 選關",
                                   style={"description_width": "64px"}, layout=W.Layout(width="auto"))
        self.cover = W.HTML(cover_html())
        self.level_info = W.HTML()
        self.btn_start = W.Button(description="▶ 開始遊戲", tooltip="開始玩左上角選的這一關")
        self.btn_back = W.Button(description="⬅ 返回", tooltip="回主畫面（選關）", layout=W.Layout(width="86px"))
        self.course = llm.on_course_server() and not llm.STATE.use_fake      # 課程伺服器：三個模型可以選
        if self.course and llm.STATE.model not in llm.COURSE_MODELS:
            llm.set_model("qwen2.5:7b")
        opts = ([(f"🧠 {label}", key) for key, label in llm.COURSE_MODELS.items()] if self.course
                else [(f"🧠 {llm.model_name()}", llm.STATE.model)])
        self.model_pick = W.ToggleButtons(options=opts, value=llm.STATE.model if self.course else opts[0][1],
                                          tooltips=[o[1] for o in opts], style={"button_width": "auto"},
                                          disabled=not self.course)
        self.btn_bench = W.ToggleButton(description="📊 模型跑分", tooltip="看三個模型的跑分")
        self.bench_panel = W.HTML(layout=W.Layout(display="none"))
        self.tb_mode = W.ToggleButtons(options=[("賣蠢", "silly"), ("正經", "serious")], value=mode,
                                       style={"button_width": "56px"}, tooltips=["賣蠢模式", "正經模式（對照組）"])
        self.btn_reset = W.Button(description="↺ 重來", layout=W.Layout(width="74px"))
        self.btn_info = W.ToggleButton(description="📋 成就／說明", tooltip="成就與指令說明",
                                       layout=W.Layout(width="120px"))
        self.btn_quit = W.Button(description="結束", layout=W.Layout(width="60px"))
        self.tb_tts = W.ToggleButton(value=tts, description="🔊", tooltip="笨笨說話（用瀏覽器語音唸出笨笨的回答）",
                                     layout=W.Layout(width="48px"))
        self.botw = W.HTML(layout=W.Layout(display="none"))     # 笨笨的即時狀態（前端連續移動＋朗讀用）

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
        self.btn_start.on_click(self._on_start)
        self.model_pick.observe(self._on_model, names="value")
        self.btn_bench.observe(self._on_bench, names="value")
        self.btn_back.on_click(self._on_back)
        self.tb_mode.observe(self._on_mode, names="value")
        self.btn_reset.on_click(lambda _: self._reset(self.session.game.level_id))
        self.btn_info.observe(self._on_info, names="value")
        self.tb_tts.observe(lambda _: setattr(self, "dirty", True), names="value")
        self.btn_quit.on_click(lambda _: self.quit())

        controls = W.HBox([self.tb_mode, self.tb_tts, self.btn_reset, self.btn_info, self.btn_quit])
        inputrow = W.HBox([self.cmd, self.btn_send, self.mic, self.btn_stop, self.btn_home, self.btn_coax])
        left = W.VBox([self.board, self.board3d, self.bubble, inputrow, self.keys, self.history])
        right = W.VBox([self.side])
        main = W.HBox([left, right])
        topbar = W.HBox([self.btn_back, self.head])
        self.title_screen = W.Box([self.cover, self.dd_level, self.level_info, self.btn_start, self.model_pick,
                                   self.btn_bench, self.bench_panel])
        self.game_screen = W.VBox([topbar, controls, main, self.extra])
        for w, cls in ((controls, "bendan-controls"), (inputrow, "bendan-inputrow"), (left, "bendan-left"),
                       (right, "bendan-right"), (main, "bendan-main"), (topbar, "bd-topbar"),
                       (self.title_screen, "bd-titlescreen"), (self.cover, "bd-coverbox"), (self.dd_level, "bd-levelpick"),
                       (self.level_info, "bd-levelinfo"), (self.btn_start, "bd-start"), (self.btn_back, "bd-back"),
                       (self.model_pick, "bd-modelpick"), (self.btn_bench, "bd-benchbtn"),
                       (self.bench_panel, "bd-benchpanel")):
            w.add_class(cls)
        self.box = W.VBox([self.js, self.title_screen, self.game_screen, self.audio_in, self.assets3d, self.botw])
        self.box.add_class("bendan-game")
        self._controls = [self.cmd, self.btn_send, self.btn_stop, self.btn_home, self.btn_coax, self.dd_level,
                          self.tb_mode, self.tb_tts, self.btn_reset, self.btn_info, self.btn_quit, self.btn_start,
                          self.btn_back, self.model_pick, self.btn_bench]
        self._show_title(True)
        self.alive = threading.Event()
        self.alive.set()
        self._render(force=True)
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _talk(self, text):
        """笨笨說的話：顯示在對話框；開著 🔊 時前端也會用語音唸出來（系統訊息用 self.say，不會唸）。"""
        self.say = text
        self.say_n += 1

    def _bot_html(self, mood):
        """笨笨的即時狀態（小小的 JSON）：前端用它畫連續移動（每格 30 幀）和朗讀笨笨說的話。"""
        s, g = self.session, self.session.game
        st = {"x": g.pos[0], "y": g.pos[1], "f": g.facing, "tick": self.tick_s,
              "lid": MOOD_LID.get(mood, "#98c1d9"), "emo": EMOTION_ICON.get(s.emotion, ""),
              "think": self.future is not None, "low": g.battery_pct < 25, "vac": g.vacuum, "drv": g.driving,
              "sayN": self.say_n, "say": self.say, "sayEmo": s.emotion or "普通", "tts": bool(self.tb_tts.value),
              # 🎬 錄影的字幕和檔名用：最近一句主人的指令、關卡名稱
              "cmdN": s.history[-1]["no"] if s.history else 0, "cmd": s.history[-1]["cmd"] if s.history else "",
              "lv": level_title(g.level_id)}
        data = json.dumps(st, ensure_ascii=False).replace("</", "<\\/")
        return f"<script type='application/json' class='bd-botjs'>{data}</script>"

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
                f"{best} <span style='font-size:13px;color:#555'>🧠 {html.escape(llm.COURSE_MODELS.get(llm.STATE.model, llm.model_name()))}</span>"
                f"</div><div>"
                "<button class='bd-btn bd-hide-popped' data-act='popout' title='開一個獨立的遊戲視窗'>🪟 彈出視窗</button>"
                "<button class='bd-btn bd-only-popped' data-act='dock'>⤓ 拉回 Notebook</button>"
                "<button class='bd-btn' data-act='fullscreen'>⛶ 全螢幕</button>"
                "<button class='bd-btn' data-act='quality' title='畫質：低（不要陰影、最省）→ 中（預設）→ 高（最漂亮）'>⚙️ 畫質</button>"
                "<button class='bd-btn' data-act='stats' title='顯示 FPS、每張畫面的繪圖次數'>📈 效能</button>"
                "<button class='bd-btn bd-cam' data-act='cam' title='按一下換下一個視角：跟隨 → 笨笨視角 → 俯瞰 → 監視器'>"
                "🎥 換視角</button>"
                "<button class='bd-btn bd-recbtn' data-act='rec' title='把 3D 畫面（含字幕和音效）錄成影片檔；錄影時每 5 秒自動換機位：跟隨 → 監視器 → 笨笨視角 → 俯瞰'>"
                "<span class='bd-rec-off'>🎬 錄影</span><span class='bd-rec-on'>⏹ 停止錄影</span></button>"
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
        if LEVEL_CMD_RE.match(text):
            self.say = "遊戲中不能換關：按左上「⬅ 返回」回主畫面選關。"
            self.dirty = True
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
            self._talk("等等，我還在想上一句！（急的話先按「停！」）")
            self.dirty = True
            return
        pre = self.session.preprocess(text, source=source)
        self.events.extend(pre["events"])
        if pre["handled"]:
            self._talk(pre["say"])
        else:
            self.future = EXECUTOR.submit(self.session.think, text, None, pre["refuse"])
            self.future_info = {"command": text, "kind": "command", "depth": 0}
        self.dirty = True

    def _on_stop(self, _):
        self.events.extend(self.session.stop())
        if self.future_info:
            self.future_info["discard"] = True    # 正在想的那句也不要了
        self._talk("收到！緊急煞車！")
        self.dirty = True

    def _on_home(self, _):
        self.events.extend(self.session.local_plan([{"op": "return_home"}], "回充"))
        self._talk("好啦，回家充電。")
        self.dirty = True

    def _on_coax(self, _):
        self._take_input(random.choice(COAX_LINES))

    def _on_mode(self, change):
        self.session.agent.mode = change["new"]
        self.say = f"切換成{'正經' if change['new'] == 'serious' else '賣蠢'}模式。"
        self.dirty = True

    def _on_level(self, change):
        """主畫面選關：只是選，按「▶ 開始遊戲」才真的開始。"""
        if not self._busy_ui:
            self._level_info()

    def _level_info(self):
        from ..world.levels import get_level
        lid = self.dd_level.value
        cfg = get_level(lid)
        if not self.progress.is_unlocked(lid):
            txt = "🔒 還沒解鎖：先把前一關過關吧！"
        else:
            best = self.progress.stars(lid) if self.progress.level(lid).get("clears") else 0
            txt = (f"<b>{html.escape(level_title(lid))}</b> {stars_text(best) if best else ''}<br>"
                   f"{html.escape(cfg.get('new') or cfg.get('intro', ''))}<br>"
                   f"<span style='color:#7a4b00'>🧠 大腦：{html.escape(llm.COURSE_MODELS.get(llm.STATE.model, llm.model_name()))}</span>")
        self.level_info.value = f"<div class='bd-li'>{txt}</div>"

    def _on_model(self, change):
        """主畫面選模型：之後每一句都交給這個模型（課程伺服器的三個模型）。"""
        if self.course and change["new"] in llm.COURSE_MODELS:
            llm.set_model(change["new"])
        self._level_info()
        self.dirty = True

    def _on_bench(self, change):
        from ..evaluation.benchmark import bench_html
        if change["new"]:
            self.bench_panel.value = bench_html()
        self.bench_panel.layout.display = "block" if change["new"] else "none"

    def _show_title(self, on):
        self.on_title = on
        self.title_screen.layout.display = "flex" if on else "none"
        self.game_screen.layout.display = "none" if on else "flex"
        if on:
            self._set_dropdown(self.session.game.level_id if not self.session.game.cleared
                               else self.progress.next_level())
            self._level_info()

    def _on_start(self, _):
        lid = self.dd_level.value
        if not self.progress.is_unlocked(lid):
            self.level_info.value = "<div class='bd-li'>🔒 這一關還沒解鎖，先玩前面的關卡！</div>"
            return
        ok, msg = change_level(self.session, lid)          # 每次開始都是新的一局
        if ok:
            self._after_level_change()
            self._talk(msg)
            self._show_title(False)
        else:
            self.level_info.value = f"<div class='bd-li'>{html.escape(msg)}</div>"
        self.dirty = True

    def _on_back(self, _):
        """⬅ 返回主畫面：先讓笨笨停下來、正在想的那句不要了，再回去選關。"""
        self.events.extend(self.session.stop())
        if self.future_info:
            self.future_info["discard"] = True
        self._show_title(True)
        self.dirty = True

    def _on_info(self, change):
        from ..render.hud import achievements_html
        self.extra.value = (achievements_html(self.progress) + WIDGET_HELP) if change["new"] else ""

    def _reset(self, level):
        ok, msg = change_level(self.session, level)
        if ok:
            self._after_level_change()
        self._talk(msg)
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
                g = self.session.game
                before = (g.steps, g.pos, g.facing, g.vacuum, g.driving)
                # 模型在想「新指令」時，笨笨先停下來聽（世界也一起暫停）。新計畫是照下指令那一刻的位置和方向算的；
                # 以前笨笨會照舊計畫多走 1–2 秒（2–3 步），新計畫到了就從錯的位置開始 → 走到乾淨的地方空吸、撞牆。
                # 舊計畫反正會被新計畫取代，停下來不會少做什麼；回饋回合是動作做完才問，不受影響。
                ev = [] if self._listening() else self.session.tick()
                g = self.session.game
                if ev:
                    self.events.extend(ev)
                    self.dirty = True
                if (g.steps, g.pos, g.facing, g.vacuum, g.driving) != before:   # v6：每走一步都要重畫，移動才連續
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
                        self._talk(res["say"] or "……")
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
                    self.events.append(E("level_result", "🏁 這一關結束了：按左上「⬅ 返回」回主畫面選下一關，或按「↺ 重來」。"))
                    self.dirty = True
                was_over = over
                self._render()
            except Exception as exc:   # noqa: BLE001
                self.side.value = f"<pre>背景迴圈錯誤：{html.escape(repr(exc))}</pre>"
            time.sleep(self.tick_s)

    def _listening(self):
        """正在等模型回覆玩家剛下的指令（不是回饋回合）→ 笨笨停下來聽。"""
        info = self.future_info
        return self.future is not None and bool(info) and info.get("kind") == "command"

    def _render(self, force=False):
        thinking = self.future is not None
        if not (force or self.dirty or thinking):
            return
        self.dirty = False
        s = self.session
        with s.lock:
            mood = s.mood.name if s.gameplay and s.mode == "silly" else None
            board = scene_html(s.game, mood=mood, emotion=s.emotion, thinking=thinking, tick=self.tick_s)
            values = {
                "board": board,
                "side": side_html(s, self.events),
                "bubble": bubble_html(s, self.say, thinking),
                "history": history_html(s, limit=12),
                "head": self._head_html(),
                "botw": self._bot_html(mood),
            }
        for name, value in values.items():
            w = getattr(self, name)
            if w.value != value:
                w.value = value

    def quit(self):
        self.alive.clear()
        self.closed = True
        for w in self._controls:
            w.disabled = True
        self.say = "遊戲結束，謝謝遊玩！（重新執行這一格就能再玩）"
        self._render(force=True)


def play_widgets(level=None, mode="silly", tick=0.5, feedback_rounds=1, unlock_all=False, seed=None, view="3d",
                 voice="auto", tts=True):
    """▶️ 遊戲視窗（推薦）。level=None 會從「還沒破的第一關」開始。

    tick：笨笨每移動一格（或轉 90 度）要幾秒；畫面上分成 30 幀播放（0.5 秒 ≈ 60 fps）。
    view：保留相容用；v8 起遊戲畫面只有 3D（遊戲中右上角「🎥 換視角」按一下換下一個：跟隨／笨笨視角／俯瞰／監視器）。
    一開始是主畫面：左上選關、正中間「▶ 開始遊戲」；遊戲中左上「⬅ 返回」回主畫面（遊戲中不能選關）。
    tts：True＝笨笨的回答用瀏覽器的語音唸出來（畫面上的 🔊 可以隨時關掉）。
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
            # "auto" 安靜偵測：找不到 Whisper 就改用瀏覽器語音辨識，狀態寫在 🎤 的提示文字裡。
            # 不要在遊戲視窗上方印「找不到 Whisper」（課程伺服器一定沒有，錄影片會拍到）；明確指定後端時才印。
            stt = voice_mod.STATE.backend or voice_mod.connect_stt(voice, verbose=voice != "auto")
        else:
            stt = voice
    if _ACTIVE_UI is not None:
        _ACTIVE_UI.quit()
    _ACTIVE_UI = WidgetGame(level, mode, tick, feedback_rounds, progress=progress, seed=seed, view=view, stt=stt,
                            tts=tts)
    display(_ACTIVE_UI.box)
    return _ACTIVE_UI
