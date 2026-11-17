# 🤖 笨笨掃地機

以 LLM 為大腦、會「賣蠢」的 2.5D 掃地機器人指令遊戲（代理型人工智慧基礎與應用實作｜期末專題）。

玩家**只能用中文打字**指揮掃地機器人「笨笨」。笨笨的大腦是課程提供的 LLM，只能從固定動作選單挑選並回 JSON；
程式驗證白名單後交給遊戲引擎執行，碰撞、闖禁區等事件再回饋給 LLM，形成完整的 Agent 閉環。

**v2 玩法**（靈感：《教妹妹開車》——只能動口、對方不一定照做、語氣太兇會鬧脾氣）：
💗 笨笨的心情會被你的語氣影響（罵它會頂嘴、罷工）｜🩸 出包會讓主人血壓飆高，爆表就失敗｜🔋 電量｜
🎲 寵物亂跑、打翻果汁、狗便便、門鈴等突發事件｜⭐ 連擊、三星評價｜🏅 14 個成就｜🔓 關卡解鎖＋每日挑戰地圖。
詳見 [docs/gameplay.md](docs/gameplay.md)。

## 專案結構

```
笨笨掃地機/
├── bendan/                    # 主程式套件
│   ├── config.py              #   路徑與設定（logs/、saves/）
│   ├── llm/                   #   LLM 連線層
│   │   ├── client.py          #     課程 OpenAI-compatible API、選模型、延遲測試
│   │   └── fake.py            #     離線 FakeLLM（沒有 API 也能測）
│   ├── world/                 #   遊戲世界（完全不依賴 LLM）
│   │   ├── constants.py       #     方向、地圖字元、障礙物、動作白名單
│   │   ├── levels.py          #     7 個關卡＋評估場景
│   │   ├── mapgen.py          #     今日挑戰：隨機地圖產生器（BFS 驗證可解）
│   │   └── game.py            #     引擎：移動、碰撞、電量、障礙物、BFS 回充
│   ├── agent/                 #   大腦
│   │   ├── prompts.py         #     動作規格、人設、心情／拒絕指示
│   │   ├── perception.py      #     以機器人為中心的世界描述
│   │   ├── memory.py          #     禁區、已清掃、最近指令
│   │   ├── parsing.py         #     JSON 解析＋白名單驗證
│   │   ├── guardrail.py       #     程式護欄：執行前模擬，攔下闖禁區的計畫
│   │   └── agent.py           #     組 Prompt → LLM → 驗證 → 重試 → 發呆
│   ├── gameplay/              #   玩法系統
│   │   ├── mood.py            #     語氣分析、笨笨的心情
│   │   ├── pressure.py        #     主人血壓計
│   │   ├── scoring.py         #     分數、連擊、星級
│   │   ├── incidents.py       #     突發事件導演
│   │   ├── achievements.py    #     成就
│   │   └── progress.py        #     存檔、關卡解鎖
│   ├── session.py             #   Agent 迴圈＋玩法＋非同步＋事件回饋＋JSONL log
│   ├── render/                #   等角 2.5D（matplotlib）、HUD（HTML）、ASCII
│   ├── ui/                    #   文字模式 play()、即時模式 play_widgets()、斜線指令
│   └── evaluation/            #   照做率、格式正確率、記憶遵守率、心情實驗、log 分析
├── notebooks/
│   ├── 01_快速開始_遊玩.ipynb   # 連線 → 玩法說明 → 開始玩
│   ├── 02_Agent_原理展示.ipynb # 一步步拆解 Agent 閉環與玩法系統
│   ├── 03_評估.ipynb           # 評估指標＋心情 vs 照做率實驗
│   └── archive/               # v1 單檔版 Notebook（保留參考）
├── tests/                     # pytest（全部離線，不需要 API）
├── scripts/
│   ├── play_cli.py            # 終端機版（純文字地圖）
│   └── pack_for_jupyterhub.py # 打包成 zip 上傳 JupyterHub
├── docs/
│   ├── gameplay.md            # 玩法設計文件
│   ├── architecture.md        # 系統架構
│   ├── evaluation_results.md  # 課程 JupyterHub × Qwen2.5-7B 實測結果
│   └── proposal/              # 期末專題提案
└── requirements.txt
```

## 使用方式

### 在課程 JupyterHub
1. 在自己電腦執行 `python scripts/pack_for_jupyterhub.py`，得到 `dist/bendan_jupyterhub.zip`。
2. 上傳 zip 到 JupyterHub，在 Terminal 執行
   `python3 -c "import zipfile; zipfile.ZipFile('bendan_jupyterhub.zip').extractall('笨笨掃地機')"`。
3. 打開 `笨笨掃地機/notebooks/01_快速開始_遊玩.ipynb`，**Kernel 選「Python 3 (ipykernel)」**，由上往下執行。

> ⚠️ 實測：「Python (Lab 1)」Kernel 只有 openai，沒有 matplotlib／pandas／ipywidgets（遊戲會退回 emoji 文字地圖、不能跑評估）；
> 「Python 3 (ipykernel)」全部都有，API 設定也讀得到。第一格的 `bendan.check_env()` 會列出缺什麼。

實測結果（Qwen2.5-7B 的照做率、禁區遵守率、心情實驗、遊玩紀錄）見 [docs/evaluation_results.md](docs/evaluation_results.md)。

### 在自己電腦
```bash
pip install -r requirements.txt
jupyter lab notebooks/01_快速開始_遊玩.ipynb   # 沒有 API 設定時自動用離線 FakeLLM
python scripts/play_cli.py --level 0           # 或直接在終端機玩
pytest -q                                      # 跑測試
```

### 在程式裡用
```python
from bendan import llm, play, play_widgets
llm.connect()                  # 連線課程 API（或 FakeLLM）
play(level=0)                  # 文字模式；/help 看指令
play_widgets(level=4, unlock_all=True)
```

請勿將 API Key 提交到 repo。`logs/`、`saves/`、`dist/` 已在 `.gitignore`。
