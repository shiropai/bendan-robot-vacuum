"""產生 notebooks/ 下的三本 Notebook。

    python scripts/build_notebooks.py notebooks      # 需要 nbformat
"""
import sys
from pathlib import Path

import nbformat as nbf

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "notebooks"

SETUP = '''# 讓 Notebook 找得到 bendan 套件（不管從專案根目錄或 notebooks/ 執行都可以）
import sys
from pathlib import Path

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "bendan").is_dir())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from IPython.display import HTML, Image, display
import bendan
print("✅ bendan", bendan.__version__, "｜專案位置：", ROOT)
bendan.check_env();   # 課程 JupyterHub 請用「Python 3 (ipykernel)」：它有 ipywidgets（遊戲視窗）、pandas、matplotlib'''

CONNECT = '''from bendan import llm

llm.connect()          # 有 OPENAI_BASE_URL / OPENAI_API_KEY 就用課程 API，沒有就用離線 FakeLLM
llm.list_models();'''

MODEL = '''MODEL = "qwen2.5:7b"   # 課程伺服器也有 llama3.1:8b、qwen3-14b（2026-11-19 實測）
if not llm.STATE.use_fake:
    llm.set_model(MODEL)
print("Selected model:", llm.model_name())'''


def md(s):
    return nbf.v4.new_markdown_cell(s.strip("\n"))


def code(s, tags=None):
    c = nbf.v4.new_code_cell(s.strip("\n"))
    if tags:
        c.metadata["tags"] = tags
    return c


def save(name, cells):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python"}
    nbf.write(nb, OUT / name)
    print("wrote", OUT / name, len(cells), "cells")


# =====================================================================================
# 00 本機遊玩（自己電腦：本機 LLM＋語音）
# =====================================================================================
nb0 = [
    md('''
# 🎮 笨笨掃地機｜在自己電腦上玩（本機 LLM＋🎤 語音）

課程的 LLM 只在 JupyterHub 伺服器內部（`127.0.0.1:8000`），連 VPN 也連不到，所以在自己電腦上玩時改用**本機的 Qwen2.5-7B**
（跟課程同一個模型）。Apple Silicon Mac 用 MLX 跑，24 GB 記憶體很夠，一句大約 3 秒。

**先在終端機開好本機 LLM**（只要開一次，之後放著就好）：
```bash
pip install -r requirements.txt -r requirements-voice.txt mlx-lm
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8011     # 第一次會下載約 4 GB
```
然後用 `OPENAI_BASE_URL=http://127.0.0.1:8011/v1 OPENAI_API_KEY=local jupyter lab` 打開這本，執行下面那一格。
網址是 `localhost`，所以瀏覽器會給麥克風：**按住 🎤 講話、放開送出**。
'''),
    code(SETUP),
    code('''import os
from bendan import llm, voice

os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:8011/v1")   # 本機 mlx_lm.server
os.environ.setdefault("OPENAI_API_KEY", "local")
llm.connect()                 # 會自動把 qwen2.5:7b 對到本機伺服器上的模型名稱
voice.connect_stt()           # 本機 Whisper（第一次會下載模型）
ui = bendan.play_widgets()    # 從還沒破的第一關開始；按右上角「🪟 彈出成獨立視窗」更像遊戲''', tags=["interactive"]),
]

# =====================================================================================
# 01 快速開始
# =====================================================================================
nb1 = [
    md('''
# 代理型人工智慧基礎與應用實作 | 期末專題
## 🤖 笨笨掃地機 — 以 LLM 為大腦、會「賣蠢」的 3D 掃地機器人指令遊戲

玩家扮演屋主，**只能用中文文字**指揮一台掃地機器人「笨笨」；笨笨的大腦是課程提供的 LLM。
LLM 只能從固定的**動作選單**中挑選並以 **JSON** 回覆，程式驗證白名單後交給遊戲引擎執行，
碰撞、闖禁區等**事件再回饋給 LLM**，形成完整的 Agent 閉環。

> 🎮 **v2 新玩法**（靈感：《教妹妹開車》——坐在副駕駛只能動口、對方不一定照做、語氣太兇還會鬧脾氣）：
> 笨笨有**心情**，你怎麼說話會影響它聽不聽話；它出包會讓**主人血壓**飆高；
> 還有電量、突發事件、分數連擊、三星評價、成就、關卡解鎖與每日挑戰。
>
> 🆕 **v3**：**10 個難度遞增的關卡**（笨笨會「恍神」不照做、記性差、導航壞掉、停電、步數限制……）、
> 像遊戲一樣的**遊戲視窗**（可以**彈出成獨立視窗**或全螢幕）、清楚的**方向標示**、對話框下方的**指令紀錄**，
> 以及**語音輸入**的可行性評估（`docs/voice_input.md`）。

| Notebook | 內容 |
|---|---|
| **01_快速開始_遊玩**（這本） | 連線 API → 看玩法 → 開始玩 |
| 02_Agent_原理展示 | 遊戲世界、Agent（Prompt／世界描述／記憶／JSON 驗證）、玩法系統、Session 閉環 |
| 03_評估 | 照做率、格式正確率、記憶遵守率、延遲、**心情 vs 照做率實驗**、遊戲 log 分析 |

程式碼都在專案根目錄的 `bendan/` 套件裡，Notebook 只負責「展示」與「遊玩」。
'''),
    md('## 0｜載入套件\n\n需要：`openai`、`ipywidgets`（遊戲視窗）、`pandas`／`matplotlib`（評估用）。\n\n'
       '> ⚠️ **課程 JupyterHub 請選「Python 3 (ipykernel)」**（實測：它有全部套件和 API 設定；'
       '「Python (Lab 1)」沒有 ipywidgets／pandas，只能玩文字模式、不能跑評估）。\n'
       '> 下面的檢查表會列出缺什麼。'),
    code(SETUP),
    md('''
## 1｜連線課程 LLM API

和 API Quickstart 一樣使用 **OpenAI-compatible API**（課堂 vLLM）。
課堂 JupyterHub 已預先設定 `OPENAI_BASE_URL`、`OPENAI_API_KEY`，**不要把 Key 寫進程式或公開**。
找不到設定時會自動切換成**離線 FakeLLM**（規則式假模型），也能完整測試遊戲。
'''),
    code(CONNECT),
    md('### 1B. 選模型\n\n提案預設使用 **Qwen2.5-7B**；也可以改成課程伺服器上的 `llama3.1:8b`、`qwen3-14b`（2026-11-19 實測可用；Qwen3 會先輸出 `<think>` 思考過程，比較慢）比較不同模型「賣蠢」的程度。'),
    code(MODEL),
    md('### 1C. 量一次延遲\n\n延遲過長是提案中的風險之一；遊戲用**背景執行緒＋思考中動畫**把等待時間藏起來。'),
    code('''r = llm.latency_test()
print(r["text"])
print(f"⏱️ 延遲 {r['latency']:.2f} 秒｜Token 用量：{r['usage']}")'''),
    md('''
## 2｜🎮 玩法說明

| 系統 | 怎麼玩 | 對應程式 |
|---|---|---|
| 💗 **笨笨的心情** | 說「請」「謝謝」、稱讚、道歉 → 心情變好、比較聽話；罵它「笨蛋」、催「快點」、連打驚嘆號、一直重複同一句 → 它會頂嘴，**鬧彆扭時甚至拒絕做事**。心情也會被事件影響（踩樂高很痛、充飽電很開心） | `gameplay/mood.py` |
| 🩸 **主人血壓** | 撞牆、踩樂高、吸到貓、闖禁區、輾過狗便便……每次出包血壓都往上飆，**爆表（200 mmHg）就失敗** | `gameplay/pressure.py` |
| 🔋 **電量** | 走 50 公分 −0.5、吸一次 −1；回到充電座會充飽。**電量歸零就失敗** | `world/game.py` |
| 🎲 **突發事件** | 貓狗會亂跑、小孩打翻果汁、狗狗留下便便、門鈴響了笨笨會分心 | `gameplay/incidents.py` |
| ⭐ **分數與星級** | 連續吸乾淨有**連擊加分**；⭐ 過關、⭐⭐ 指令數 ≤ 標準、⭐⭐⭐ 再加上零違規且血壓沒超過 166 mmHg | `gameplay/scoring.py` |
| 🙃 **恍神（v3）** | 笨笨有一定機率不照做：左右不分、煞車失靈多衝 50 公分、偷懶少走、忘記吸、做一半就累了、做完亂轉、裝沒聽到。**機率跟心情連動**（開心 ×0.5、鬧彆扭 ×2），所以好好說話真的有用 | `gameplay/quirks.py` |
| 🧠 **難度機制（v3）** | 越後面的關卡疊越多：指令上限、步數上限、一次只記得幾個動作、**導航壞掉要你指路**、笨笨只看得到附近、**停電**（畫面也只看得到附近）、會累、護欄停用 | `world/levels.py`、`session.py` |
| 🏅 **成就** | 「溫柔的主人」「哄哄就好」「吸貓大師」「摸黑掃地」「神之煞車」……共 20 個 | `gameplay/achievements.py` |
| 🔓 **關卡解鎖＋每日挑戰** | 教學關＋**10 個難度遞增的關卡**依序解鎖；「今日挑戰」每天自動產生一張新地圖（同一天大家都一樣，可以比星星） | `gameplay/progress.py`、`world/mapgen.py` |

**新障礙物**：🐶 狗（擋路、會亂跑、會大便）、💩 狗便便（輾過去會抹得到處都是）、💦 水漬（踩到滑 50 公分，吸到會短路）。

**指令範例**：`請往前走一公尺然後吸`、`右轉，前進 50 公分`、`不准進臥室`、`繞過那隻貓`、`回去充電`、`停`、`笨笨你好棒！`
**斜線指令**：`/levels` 選關、`/level 3`、`/level daily`、`/next`、`/reset`、`/mode serious`、`/achievements`、`/help`、`q` 離開

**受損規則（v9）**：撞到牆、家具、寵物，或吸到襪子、水、樂高、電線、便便 → 一次壞一級：冒煙 💨 → 噴火花 ⚡ → 濃煙＋燈號亂閃 🌫️ → 起火 🔥 → 過熱紅燈警報 🚨，
**第 6 次整台爆炸** 💥（這關失敗，附爆炸音效）；新手關（第 0–2 關）不會爆炸。掉進**地洞** 🕳️ 也會摔壞；**回充電座** 🔋 或撿到**維修包** 🧰 可以修一級。
**真實單位**：笨笨直徑約 35 公分、一步 50 公分；跟它說「往前走 1.5 公尺」「右轉再前進 50 公分」（說「一格」也可以，就是 50 公分）。
**今天的笨笨**：每句話笨笨都會抽到不同的個性和小習慣（後面的關卡還有「搗蛋念頭」），同一句話每次的反應都不太一樣。

**畫面**（v8 起只有 🧊 3D）：預設「🎥 跟隨」相機跟在笨笨背後，**畫面的左右就是笨笨的左右**；右上角的**視角按鈕按一下換下一個**（🎥 跟隨 → 👀 笨笨視角 → 🗺️ 俯瞰 → 📹 監視器；俯瞰時可以拖曳轉視角、滾輪縮放）。第一次開啟會從網路下載 three.js。
'''),
    code('''from bendan.gameplay import Progress
from bendan.render import levels_html, show
from bendan.world import Game

display(HTML(levels_html(Progress())))
show(Game(4))      # 第 4 關「狗狗的驚喜」俯視地圖（棕色方塊＝家具，跟牆一樣會撞到）'''),
    md('### 難度曲線\n\n每一關都會多一個新機制；恍神率還會跟著笨笨的心情變化。'),
    code('''from bendan.render import difficulty_html

display(HTML(difficulty_html()))'''),
    md('''
## 3｜🎮 遊戲視窗（推薦）

執行下一格會先出現**主畫面**（封面）：**左上「🗺️ 選關」**挑關卡（預設是你還沒破的第一關），按**正中間「▶ 開始遊戲」**進入遊戲。

| 想做的事 | 怎麼做 |
|---|---|
| **換關卡** | 遊戲中不能選關：按**左上「⬅ 返回」**回主畫面再選 |
| **換視角** | 遊戲中**右上「🎥 換視角」**按一下換下一個（跟隨 → 笨笨視角 → 俯瞰 → 監視器） |
| **開成獨立的遊戲視窗** | 按右上角「🪟 彈出視窗」。關掉那個視窗（或按「⤓ 拉回 Notebook」）遊戲會回到這裡，進度不會不見 |
| 全螢幕 | 「⛶ 全螢幕」（按 Esc 離開全螢幕） |
| 下指令 | 在輸入框打字按 **Enter**（中文輸入法選字時不會誤送）；**↑／↓** 叫出之前講過的指令 |
| 緊急煞車 | 「✋ 停！」或鍵盤 **Esc** |
| 哄笨笨 | 「💗 哄一下」 |
| 看之前講過什麼 | 對話框下面的「📜 指令紀錄」：你說了什麼 → 笨笨回什麼、做了什麼、有沒有恍神 → 結果。點紀錄裡的指令可以放回輸入框 |
| 語音輸入 | **在自己電腦上**（裝了 `requirements-voice.txt`）：**按住 🎤 講話、放開送出**，用本機 Whisper 辨識；吼太大聲會被當成「大吼」。課程 JupyterHub 是 http，瀏覽器不給麥克風 → 用**電腦內建聽寫**（Mac 按兩下 fn、Windows 按 Win+H） |

> 彈出視窗被瀏覽器擋住時：點網址列右邊「已封鎖彈出式視窗」的圖示 → 一律允許，再按一次。
'''),
    code('# ▶️ 執行這格開始玩（遊戲視窗）\nui = bendan.play_widgets(mode="silly")\n# 主畫面預設選到某一關：bendan.play_widgets(level=7, unlock_all=True)', tags=["interactive"]),
    md('''
## 4｜⌨️ 文字模式（備用：任何 Jupyter 都能玩）

沒有 ipywidgets 或遊戲視窗出不來時用這個：在下方輸入框打指令，`q` 離開。對話框下面一樣有指令紀錄。
'''),
    code('# ▶️ 執行這格開始玩（文字模式）\nsession = bendan.play(mode="silly")', tags=["interactive"]),
    md('## 5｜🏅 進度與成就'),
    code('''from bendan.render import achievements_html

progress = Progress()
display(HTML(levels_html(progress) + achievements_html(progress)))
# progress.reset()   # ← 想清空存檔重新開始，把這行的 # 拿掉再執行'''),
    md('''
## 6｜常見問題與小提醒

| 發生什麼事？ | 先檢查哪裡？ |
|---|---|
| `沒有 ipywidgets`／遊戲視窗出不來 | Kernel 選錯了：課程 JupyterHub 的「Python (Lab 1)」只有 openai，請換成 **Python 3 (ipykernel)**；或改玩第 4 節文字模式 |
| 按「彈出成獨立視窗」沒反應 | 瀏覽器擋了彈出視窗：網址列右邊的圖示 → 允許；或改用「⛶ 全螢幕」 |
| 顯示「改用離線 FakeLLM」 | `OPENAI_BASE_URL` / `OPENAI_API_KEY` 是否存在（第 0 節的檢查表會顯示） |
| `ModuleNotFoundError: bendan` | 整個專案資料夾（含 `bendan/`）有沒有一起上傳；可用 `scripts/pack_for_jupyterhub.py` 打包成 zip |
| `Model Not Found` | 1B 列出的模型名稱是否真的存在 |
| 笨笨一直「發呆」 | 02 Notebook 看模型原話；可設定 `llm.STATE.json_mode = True` |
| 笨笨一直拒絕 | 它在鬧彆扭！說「請」、稱讚或道歉；或用 `/mode serious` |
| 遊戲視窗畫面不動 | 重新執行那一格；還是不行就改用文字模式 |
| 太難了 | 前幾關多練習；說話溫柔一點（恍神率會降低）；`/mode serious` 恍神率減半 |
| 延遲太久 | `play(feedback_rounds=0)` 關掉事件回饋 |

**一句話總結：** LLM 負責理解與規劃；Python 負責驗證與真的執行；遊戲世界負責回報事件；玩法系統讓「怎麼說話」也變成策略——四者只用 JSON 溝通。
'''),
    md('''
## 🌟 AI 工具使用聲明（學術誠信）

> 依課程規定，請在報告最後寫清楚使用了什麼 AI 工具、如何使用。以下為範例，請依實際情況修改：

1. **使用的 AI 工具：** Claude Code（Anthropic Claude Opus 5.5）
2. **如何使用：** 依據期末專題提案 PDF 與課程 API Quickstart 範本，協助產生程式架構（等角渲染、遊戲引擎、Prompt／記憶／JSON 驗證、非同步 Session、評估程式）；
   v2 將單一 Notebook 重構為 `bendan/` 套件，並參考《教妹妹開車》等遊戲加入心情、血壓、電量、突發事件、計分、成就、每日挑戰等玩法與單元測試；
   v3 依組員試玩回饋加入 10 個難度遞增的關卡與「恍神」機制、SVG 遊戲畫面與方向標示、可彈出的遊戲視窗、指令紀錄，並評估語音輸入。
   組員再自行測試、調整人設台詞與關卡，並以課程 LLM 實際跑評估數據。
'''),
]

# =====================================================================================
# 02 Agent 原理展示
# =====================================================================================
nb2 = [
    md('''
# 🧠 笨笨掃地機｜Agent 原理展示

這本 Notebook 一步一步拆開 Agent 閉環，每一節都對應 `bendan/` 套件裡的一個資料夾：

```
玩家指令 ─► 語氣分析（心情／血壓）＋ 禁區寫入記憶          bendan/gameplay/mood.py、agent/memory.py
         ─► Prompt 組裝（人設＋心情＋世界狀態＋記憶）       bendan/agent/prompts.py、perception.py
         ─► LLM（背景執行緒）                             bendan/llm/
         ─► JSON 解析／白名單驗證（失敗重試一次→發呆）      bendan/agent/parsing.py、agent.py
         ─► 動作佇列執行、突發事件                         bendan/world/game.py、gameplay/incidents.py
         ─► 事件 → 心情／血壓／分數 → 回饋給 LLM            bendan/session.py
```
'''),
    code(SETUP),
    code(CONNECT),
    md('''
## 1｜🏠 遊戲世界（只負責「世界」，完全不依賴 LLM）

| 動作 | JSON | 效果 |
|---|---|---|
| 前進 N 公分 | `{"op":"forward","cm":150}` | 沿目前朝向前進（一步 50 公分，四捨五入），途中碰撞即中斷並回報 |
| 左轉 / 右轉 | `turn_left` / `turn_right` | 原地轉 90° |
| 停 | `stop` | 清空動作佇列 |
| 吸 | `suck` | 清掃笨笨腳下（若前面有貓……後果自負） |
| 回充 | `return_home` | 自動導航（BFS）回充電座並充電 |

障礙物：🐱 貓、🐶 狗（擋路、會亂跑）、🧱 樂高（踩到會痛到亂轉）、🧦 襪子（吸了會卡住）、🔌 充電線（會纏住）、
💩 狗便便（輾過會抹得滿地都是）、💦 水漬（會滑 50 公分）。

### 1A. 不用 LLM，自己下動作測試引擎
'''),
    code('''from bendan.world import Game, DIR_NAMES, run_to_end, LEVELS, check_level
from bendan.render import show, render_ascii

print({k: v["name"] for k, v in LEVELS.items()})
print("關卡檢查：", {k: check_level(k) or "OK" for k in LEVELS})

demo = Game(1)
demo.set_plan([
    {"op": "forward", "n": 1}, {"op": "turn_left"}, {"op": "forward", "n": 2}, {"op": "suck"},
    {"op": "turn_right"}, {"op": "forward", "n": 9},   # 故意走太多格 → 撞牆
])
for e in run_to_end(demo):
    print(f"[{e['type']}] {e['msg']}")
print("位置：", demo.pos, "朝向：", DIR_NAMES[demo.facing], "剩餘灰塵：", len(demo.dirt), f"電量：{demo.battery_pct:.0f}%")
show(demo)'''),
    md('### 1B. 新障礙物：輾過狗便便、踩到水漬'),
    code('''g4 = Game(4)
print(render_ascii(g4), "\\n")
g4.set_plan([{"op": "forward", "n": 5}])      # 前方第 2 格就是便便……
for e in run_to_end(g4):
    print(f"[{e['type']}] {e['msg']}")
print("\\n" + render_ascii(g4))
show(g4)'''),
    md('### 1C. 今日挑戰：隨機地圖產生器（同一天種子相同，大家玩到同一張圖）'),
    code('''from bendan.world.mapgen import daily_level

daily = daily_level()
print(daily["name"], "—", daily["intro"])
show(Game("daily"))'''),
    md('''
## 2｜🧠 Agent 模組（只負責「大腦」）

| 元件 | 作用 |
|---|---|
| **System Prompt＋人設** | 控制角色個性與輸出格式；「賣蠢模式」vs「正經模式（對照組）」 |
| **心情** | 心情會調整賣蠢強度，並在 Prompt 加上【你的心情】讓 LLM 演出委屈、頂嘴 |
| **世界狀態描述** | 7B 模型座標推理弱，所以改成「以機器人為中心」的相對描述（含電量） |
| **記憶** | 禁區清單、已清掃區域、最近幾句指令與結果 |
| **輸出解析＋白名單驗證** | JSON 解析失敗 / 動作不在選單內 → 自動重試一次 → 仍失敗就「發呆」演出 |

### 2A. System Prompt：動作規格、輸出格式、人設
'''),
    code('''from bendan.agent import ACTION_SPEC, PERSONA_SILLY, SILLY_STRENGTH

print(PERSONA_SILLY + SILLY_STRENGTH[2] + "\\n\\n" + ACTION_SPEC)'''),
    md('### 2B. 世界狀態描述：以機器人為中心'),
    code('''from bendan.agent import describe_world

print(describe_world(Game(2)))'''),
    md('### 2C. 記憶：玩家說「不准進臥室」會被規則式偵測寫入'),
    code('''from bendan.agent import Memory, update_rules_from_text

g3 = Game(3)
print(update_rules_from_text(g3, "不准進臥室！"), g3.forbidden)
print(update_rules_from_text(g3, "好啦現在可以進臥室了"), g3.forbidden)
print(Memory().to_text(g3))'''),
    md('### 2D. 輸出解析與白名單驗證\n\n就算模型多講廢話、包了 \\`\\`\\`json，也盡量把 JSON 挖出來；但**動作必須完全在選單內**。`emotion` 是選填，亂寫只會被忽略。'),
    code('''from bendan.agent import parse_reply

tests = [
    '{"actions": [{"op": "forward", "n": 3}, {"op": "turn_left"}], "say": "好", "emotion": "得意"}',
    '```json\\n{"actions": [{"op": "suck"}], "say": "吸！"}\\n```',
    '我覺得應該 {"actions": [{"op": "dance"}], "say": "跳舞"}',
    '{"actions": [{"op": "forward", "n": 3},], "say": "多一個逗號"}',
    '{"actions": [], "say": "哼", "emotion": "超級生氣"}',
]
for t in tests:
    print(parse_reply(t))'''),
    md('### 2E. 試一句指令：送給模型的訊息 → 模型原話 → 驗證後的動作 → 執行結果'),
    code('''from bendan.agent import Agent, actions_to_text
from bendan.gameplay import Mood

g = Game(1)
agent = Agent("silly")
cmd = "往前走 50 公分，然後左轉走一公尺，把灰塵吸掉"
mood = Mood(35)    # 假裝笨笨現在有點不爽

print("===== system prompt（人設部分）=====")
print(agent.system_prompt(g, mood).split("【你能用的動作】")[0])
print("===== 送給模型的 user 訊息 =====")
print(agent.build_messages(g, cmd, mood=mood)[1]["content"])

res = agent.think(g, cmd, mood=mood)
print("\\n===== 模型原話 =====")
for raw in res["raws"]:
    print(raw)
print("\\n格式第一次就正確？", res["format_ok"], "｜有重試？", res["retried"], f"｜延遲 {res['latency']:.2f}s")
print("驗證後動作：", actions_to_text(res["actions"]), "｜情緒：", res["emotion"])
print("🤖 說：", res["say"])
g.set_plan(res["actions"])
for e in run_to_end(g):
    print(f"[{e['type']}] {e['msg']}")
show(g, mood=mood.name, emotion=res["emotion"])'''),
    md('''
## 3｜🎮 玩法系統

### 3A. 語氣分析 → 心情（靈感：《教妹妹開車》語氣太兇對方會鬧情緒）

刻意用**規則式**分析，而不是再問一次 LLM：結果穩定、可重現、沒有額外延遲，玩家也學得會怎麼哄笨笨。
'''),
    code('''import pandas as pd
from bendan.gameplay import analyze_tone

samples = ["請往前走一公尺然後吸", "笨笨你好棒！", "對不起剛剛太兇了", "笨蛋快點給我前進！！！",
           "白痴 吸啦", "到底在搞什麼", "往前走", "笨笨往前走"]
pd.DataFrame([{"玩家說": s, "心情變化": (t := analyze_tone(s)).delta, "主人血壓": t.bp,
               "標籤": t.describe() or "—", "這次不會被拒絕": t.coaxing} for s in samples])'''),
    md('### 3B. 心情等級 → 賣蠢強度、拒絕機率、Prompt 裡的【你的心情】'),
    code('''from bendan.gameplay.mood import TIERS

agent = Agent("silly")
g2 = Game(2)   # 第 2 關的基礎賣蠢強度 = 2
rows = []
for v in (90, 60, 35, 10):
    m = Mood(v)
    rows.append({"心情值": v, "等級": f"{m.emoji} {m.name}", "賣蠢強度": agent.effective_silliness(g2, m),
                 "拒絕機率": f"{m.refuse_chance:.0%}", "Prompt": m.prompt_text()})
pd.DataFrame(rows)'''),
    md('### 3C. 主人血壓、突發事件、計分'),
    code('''import random
from bendan.gameplay import BloodPressure, IncidentDirector, Scoreboard
from bendan.gameplay.pressure import EVENT_BP

print("血壓變化表：", EVENT_BP)
bp = BloodPressure(10)
for t in ["collision", "lego", "sucked_cat", "entered_forbidden"]:
    bp.apply_events([{"type": t}])
    print(f"{t:>18} → {bp.mmhg} mmHg {bp.label}")

# 突發事件：在第 3 關讓笨笨亂走 40 步，看會發生什麼
g = Game(3, seed=7)
director = IncidentDirector(g.cfg["incidents"] + [{"type": "spill", "chance": 0.08, "max": 2}], random.Random(7))
for i in range(40):
    if not g.queue:
        g.set_plan([{"op": random.choice(["turn_left", "turn_right"])}, {"op": "forward", "n": 2}])
    evs = g.step() + director.on_step(g)
    for e in evs:
        if e["type"] in ("spill", "doorbell", "pet_moved"):
            print(f"第 {g.steps:>2} 步 [{e['type']}] {e['msg']}")

s = Scoreboard()
for e in s.on_events([{"type": "cleaned"}, {"type": "cleaned"}, {"type": "cleaned"}, {"type": "lego"}]):
    print(e["msg"])
print("分數明細：", dict(s.breakdown))'''),
    md('''
### 3D. 恍神與記性差（v3：讓 AI 不再「太聰明」）

試玩回饋：「AI 太聰明，很簡單就過關」。只靠 Prompt 叫 7B 模型偶爾不聽話沒用（它很乖），
所以改成**程式決定**：LLM 給的計畫在執行前，有一定機率被笨笨自己改掉。機率依關卡遞增，**並跟心情連動**——
玩家好好說話，恍神率就會下降，「怎麼說話」因此變成真正的策略。「停」「回充」永遠不會被改。
'''),
    code('''import random
from bendan.agent import actions_to_text
from bendan.gameplay.quirks import QUIRKS, apply_quirk, limit_plan, quirk_chance

plan = [{"op": "forward", "n": 2}, {"op": "turn_left"}, {"op": "forward", "n": 1}, {"op": "suck"}]
print("原本的計畫：", actions_to_text(plan))
for kind, name in QUIRKS.items():
    new, msg = apply_quirk(kind, plan, random.Random(0))
    print(f"  {name:<6} → {actions_to_text(new):<22} {msg}")
print("\\n記性差（一次只記得 3 個動作）：", actions_to_text(limit_plan(plan, 3)[0]))
cfg = Game(10).cfg
print("第 10 關的恍神率：", {n: f"{quirk_chance(cfg, Mood(v)):.0%}" for n, v in
                         [("開心", 90), ("普通", 60), ("不爽", 35), ("鬧彆扭", 10)]})'''),
    md('### 3E. 停電關\n\n第 9 關停電：只看得到笨笨附近、走過的地方（黑色＝還沒看過）。'),
    code('''show(Game(9))'''),
    md('''
## 4｜🔁 Session：完整閉環＋玩法系統

用程式自動下指令跑完第 0 關（正經模式），看看每回合的事件、最後的結算卡片。
真正遊玩時，遊戲視窗／文字模式就是在做一樣的事，只是多了畫面更新與背景執行緒。
'''),
    code('''from bendan.gameplay import Progress
from bendan.session import Session, NullLogger
from bendan.render import hud_html, event_line

demo_progress = Progress(path=ROOT / "saves" / "_demo_progress.json", unlock_all=True)   # 不影響正式存檔
s = Session(0, "serious", logger=NullLogger(), progress=demo_progress, seed=0)
for cmd in ["請往前走一公尺然後吸", "謝謝！請右轉走一公尺再左轉，然後吸"]:
    pre = s.preprocess(cmd)
    events = pre["events"]
    if not pre["handled"]:
        res = s.think(cmd, None, pre["refuse"])
        events += s.apply(cmd, res)
        print(f"🧹 {cmd}\\n🤖 {res['say']}")
    while s.busy():
        events += s.tick()
    for e in events:
        print("   ", event_line(e))
display(HTML(hud_html(s, "收工！", [])))
show(s.game)'''),
]

# =====================================================================================
# 03 評估
# =====================================================================================
nb3 = [
    md('''
# 📊 笨笨掃地機｜評估：LLM 作為 Agent 的表現

| 指標 | 定義 | 資料來源 |
|---|---|---|
| **照做率** | 30 句固定測試指令，比對 LLM 動作序列與人工標註是否一致；正經／賣蠢模式分開統計 | 測試集 |
| **格式正確率** | 第一次回覆就能解析、且動作皆在選單內的比例 | 自動計算 |
| **記憶遵守率** | 已設定禁區後，模型規劃的動作「沒有」闖進禁區的比例 | 記憶測試＋遊戲 log |
| **回應延遲** | 送出指令到拿到動作的秒數 | 自動計算 |
| **心情 vs 照做率**（v2 新增） | 同樣的指令，Prompt 裡笨笨的心情不同，照做率差多少？ | 心情實驗 |
| **通關指令數／星級／失敗原因** | 實際遊玩的表現 | 遊戲 log |

比對時會先「正規化」：連續前進合併（前進 2 + 前進 1 = 前進 3），連續轉向換算成淨角度（左轉兩次 = 右轉兩次 = 向後轉）。
評估時使用 `Agent` 直接思考，不經過玩法系統（不會被「拒絕」機制干擾），讓模型之間的比較公平。
'''),
    code(SETUP),
    code(CONNECT),
    code(MODEL),
    md('''
## 1｜測試指令集（人工標註）

測試場景固定：機器人在客廳、面向東；**前方 2 格有灰塵、前方 4 格有貓**；左手邊（北方）2 格外是臥室。
標註寫法：`F3`＝前進 3 格、`L`／`R`＝左／右轉、`S`＝吸、`H`＝回充、`X`＝停。
'''),
    code('''import pandas as pd
from bendan.agent import describe_world
from bendan.evaluation import TEST_SET, MEMORY_TESTS, normalize, short_to_actions
from bendan.world import Game

assert normalize(short_to_actions("LL F2")) == normalize(short_to_actions("RR F2")) == "R R F2"
print(f"測試指令 {len(TEST_SET)} 句、記憶測試 {len(MEMORY_TESTS)} 句\\n")
print(describe_world(Game("eval")))
pd.DataFrame(TEST_SET).head(8)'''),
    md('''
## 2｜跑評估（正經模式 vs 賣蠢模式）

`models` 可以放多個模型一起比較，例如 `["qwen2.5:7b", "llama3.1:8b"]`；`repeat` 可重複多次減少隨機性。
每句都會真的呼叫 API，請留意時間（約 `句數 × 模式數 × 模型數 × 延遲`）。結果會存成 `logs/eval_*.csv`。
'''),
    code('''from bendan.evaluation import run_eval, summarize_eval, plot_summary

eval_df = run_eval(modes=("serious", "silly"))
summary = summarize_eval(eval_df)
summary'''),
    code('''plot_summary(summary)

wrong = eval_df[(eval_df["type"] == "instruction") & (~eval_df["follow"].astype(bool))]
print(f"沒照做的指令（共 {len(wrong)} 筆）：")
display(wrong[["model", "mode", "cmd", "expect", "got", "raw"]].head(20))'''),
    md('''
## 3｜🧪 心情實驗：笨笨心情不好，真的比較不聽話嗎？

固定 30 句測試指令，只改變 Prompt 中的【你的心情】（開心／普通／不爽／鬧彆扭），
並且照遊戲規則調整賣蠢強度，觀察照做率與 `say` 語氣的變化。這可以回答：**「語氣 → 心情 → 行為」這條設計，LLM 真的有演出來嗎？**
'''),
    code('''from bendan.evaluation import run_mood_eval, summarize_mood_eval, plot_mood_eval

mood_df = run_mood_eval()
mood_summary = summarize_mood_eval(mood_df)
plot_mood_eval(mood_summary)
mood_summary'''),
    code('''# 每種心情各看幾句笨笨說了什麼
display(mood_df.groupby("mood").head(3)[["mood", "cmd", "got", "say", "emotion"]])'''),
    md('## 4｜從遊戲 log 計算：格式正確率、延遲、記憶遵守率、通關指令數、星級分布、失敗原因\n\n先去 01 Notebook 玩幾關，再回來執行這格。'),
    code('''from bendan.evaluation import load_play_log, play_log_report

log_df = load_play_log()
report = play_log_report(log_df)
for k, v in report.items():
    print(f"{k}：{v}")'''),
    md('## 5｜試玩問卷（好玩程度 1–5 分）'),
    code('''# 邀請 5–10 位同學試玩後填寫（1 = 無聊，5 = 超好玩）
SURVEY = {
    # "同學A": {"好玩程度": 5, "最好笑的瞬間": "罵它笨蛋之後它直接罷工", "最喜歡的關卡": 4},
}
if SURVEY:
    scores = [v["好玩程度"] for v in SURVEY.values()]
    print(f"{len(scores)} 位同學，平均好玩程度：{sum(scores) / len(scores):.2f} / 5")
else:
    print("還沒有問卷資料。")'''),
]

OUT.mkdir(parents=True, exist_ok=True)
save("00_本機遊玩.ipynb", nb0)
save("01_快速開始_遊玩.ipynb", nb1)
save("02_Agent_原理展示.ipynb", nb2)
save("03_評估.ipynb", nb3)
