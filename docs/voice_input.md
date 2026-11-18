# 🎤 語音輸入

> **v4 更新：已經做好本機 Whisper 語音輸入。** 在自己電腦上跑（`localhost` 是安全來源，瀏覽器才給麥克風），
> 按住 🎤 講話、放開就送出；用吼的還會被當成「大吼」。設定方法見下一節。
> 課程 JupyterHub 是 http，麥克風仍然被擋，在那邊請用電腦內建聽寫（第 2 節以後是當時的評估）。

## 0. 在自己電腦上啟用 Whisper（v4）

```bash
pip install -r requirements.txt -r requirements-voice.txt   # Apple Silicon 會裝 mlx-whisper，其他電腦裝 faster-whisper
export OPENAI_BASE_URL=http://127.0.0.1:你的埠/v1            # 自己的 LLM（Ollama、LM Studio、vLLM……都可以）
export OPENAI_API_KEY=隨便填或你的 key
jupyter lab notebooks/01_快速開始_遊玩.ipynb                  # 網址是 localhost → 瀏覽器會問要不要給麥克風
```

`bendan.play_widgets()` 會自動找 Whisper；第一次會下載模型（Apple Silicon 預設 `whisper-large-v3-turbo`，約 1.6 GB），
之後就不用網路，**聲音不會離開你的電腦**。

| 操作 | 效果 |
|---|---|
| 按住 🎤 講話、放開 | 送去辨識，辨識完自動當成指令送出 |
| 只點一下 🎤 | 開始錄音；講完再點一下結束（不想一直按著時用） |
| 取消「自動送出」 | 辨識結果先放進輸入框，改一改再按 Enter |
| 大聲吼 | 指令後面會加上「！！！」→ 語氣判成「大吼」，笨笨不開心、主人血壓上升 |

指令紀錄會標「🎤 語音」，事件列會顯示「🎤 聽到：「…」（錄音幾秒、辨識幾秒）」。

**程式架構**（`bendan/voice/`）

```
瀏覽器（遊戲視窗的 JS）：getUserMedia → 16 kHz 單聲道 → WAV → base64
   │  透過一個隱藏的 ipywidgets Text 傳到 Python（不需要任何擴充套件）
   ▼
voice.audio：解碼 WAV、算音量（大吼／太小聲／太短）
voice.stt：Whisper 後端（自動挑一個）           voice.textfix：簡轉繁、同音字修正、過濾幻覺句
   ├─ api：BENDAN_STT_URL（OpenAI 相容 /v1/audio/transcriptions）
   ├─ mlx：mlx-whisper（Apple Silicon）
   └─ faster：faster-whisper（其他電腦）
   ▼
當成玩家打的字送進 session.preprocess(source="voice")
```

| 處理 | 為什麼 |
|---|---|
| 給 Whisper 一句繁體中文的遊戲用語當提示（`INITIAL_PROMPT`） | 輸出比較會是繁體、也比較會選對「左轉」「吸」「臥室」這些詞 |
| 簡轉繁（有 OpenCC 就用台灣用語 `s2twp`） | Whisper 中文常輸出簡體 |
| 同音字修正：做轉→左轉、有轉→右轉、往錢→往前、然後西→然後吸、回沖→回充…… | 只修在指令裡幾乎不可能是原意的組合 |
| 太短（< 0.35 秒）、太小聲就不辨識；「請不吝點贊訂閱」這類句子丟掉 | Whisper 遇到靜音會幻覺出影片字幕常見句 |
| 語音辨識用自己的執行緒 | 不會跟 LLM 搶，也不會卡住畫面 |

環境變數：`BENDAN_STT`（`auto`／`mlx`／`faster`／`api`／`off`）、`BENDAN_WHISPER_MODEL`（例如記憶體小改
`mlx-community/whisper-small-mlx`）、`BENDAN_STT_URL`／`BENDAN_STT_KEY`／`BENDAN_STT_MODEL`（用遠端 Whisper 服務時）。

**實測（2026-11-18，MacBook M4 Pro 24 GB，`mlx-community/whisper-large-v3-turbo`）**

用 macOS 內建的台灣中文語音（美佳）念 8 句遊戲指令（`python scripts/voice_check.py` 可以自己重跑）：

| 項目 | 結果 |
|---|---|
| 完全正確 | **8/8**（修正前 7/8：Whisper 聽對「不准進臥室」，但 OpenCC 把「准」轉成「準」，連帶禁區規則認不出來 → 已修正並加測試） |
| 每句辨識時間 | 平均 **0.51 秒**（錄音 0.4～3.3 秒） |
| 第一次載入 | 下載約 1.6 GB；之後載入約 30 秒內（背景執行緒先載，不會卡住畫面） |
| 端到端 | 在本機 JupyterLab 的遊戲視窗裡：瀏覽器 JS 轉 WAV → 隱藏 widget → Whisper → 笨笨執行，指令紀錄標「🎤 語音」✅ |
| 大吼 | 把同一句放大 8 倍送進去 → 判成「大吼」、心情 −4 ✅；但聲音爆掉讓「臥室」被聽成「入室」→ 加進同音字修正 |

注意：模型第一次下載時，Hugging Face 新的 Xet 傳輸曾連不上 CDN（`CAS Client Error`），所以程式預設用一般 HTTP 下載
（`HF_HUB_DISABLE_XET=1`，使用者自己設過就不動）。真人說話（口音、環境噪音、麥克風品質）的準確率還需要組員實際試玩確認。

---

以下是 v3 時（只能用課程 JupyterHub）的評估。

## 1. 實測環境與結果（2026-11-18，課程 JupyterHub + Chrome）

| 檢查項目 | 結果 | 代表什麼 |
|---|---|---|
| 網址 | `http://140.114.25.128:8080`（沒有 https） | 不是「安全連線」 |
| `window.isSecureContext` | `false` | 瀏覽器把這個網站當成不安全來源 |
| `navigator.mediaDevices.getUserMedia` | **不存在** | 不安全來源拿不到麥克風（錄音、WebRTC 都不行） |
| `webkitSpeechRecognition`（Chrome 語音辨識） | 物件存在，但 `start()` 立刻回 **`not-allowed`** | 語音辨識 API 也被擋 |
| 課程 LLM API 的模型 | `classroom-llm`、`llama3.1:8b`、`qwen2.5:3b`、`qwen2.5:7b` | 沒有語音轉文字（Whisper 類）模型 |
| JupyterLab 擴充套件 | 只有 ipywidgets、pygments（沒有 jupyter-server-proxy） | 沒辦法在伺服器另開一個 https 網頁 |

## 2. 方案比較

| 方案 | 需要改程式？ | 在課程 JupyterHub 能用？ | 中文辨識 | 延遲 | 隱私 | 評價 |
|---|---|---|---|---|---|---|
| **A. 作業系統內建聽寫**（Mac 按兩下 `fn`／🌐；Windows `Win`+`H`） | 不用 | ✅ **可以**（它只是把文字打進輸入框，跟網站安不安全無關） | 好（支援台灣中文） | 低 | Apple／Microsoft 處理（可設定裝置端辨識） | **現在就推薦** |
| **B. 遊戲內 🎤 按鈕**（Chrome Web Speech API，`zh-TW`） | 已做好 | ❌ 目前被擋（http）；**https 或 localhost 就能用** | 好 | 低（邊講邊出字） | 音訊送到 Google 伺服器 | 有 https 後的最佳體驗 |
| C. 伺服器端 Whisper（瀏覽器錄音 → 上傳 → 轉文字） | 要寫錄音、上傳、部署模型 | ❌ 錄音一樣需要麥克風權限（同樣被擋）；也需要 GPU／CPU 資源 | 好（Whisper small 以上） | 中～高（要等整段錄完） | 留在學校伺服器 | 投資最大，現階段不划算 |
| D. 上傳錄好的音檔 | 要寫上傳＋Whisper | ✅ 但要先錄再上傳 | 好 | 高 | 同 C | 不符合遊戲節奏 |
| E. ipywebrtc 等錄音 widget | 要裝 JupyterLab 擴充套件 | ❌ 伺服器沒裝、學生不能裝；而且一樣要麥克風權限 | — | — | — | 不可行 |

## 3. 已經做好的部分（`bendan/ui/widget_mode.py`）

遊戲視窗輸入框旁邊有 🎤 按鈕：

- 支援語音辨識的安全環境（https、localhost）：按一下開始說話，**辨識中的文字即時出現在輸入框**；講完自動送出（可取消「自動送出」，先看一眼再按 Enter）。
- 不支援的環境（例如現在的課程 JupyterHub）：跳出提示，教玩家用方案 A（電腦內建聽寫），以及怎麼讓 🎤 能用（請助教加 https；或在自己的電腦上用 Chrome 旗標 `chrome://flags/#unsafely-treat-insecure-origin-as-secure` 把這個網址當成安全來源——只建議在個人電腦上做）。
- 純前端：沒有新增 Python 套件、沒有把音訊送到課程伺服器。

## 4. 語音輸入對遊戲本身的影響

| 面向 | 影響 | 對策 |
|---|---|---|
| **語氣分析** | 語音轉成文字後沒有「！！！」，偵測不到「大吼」；但「請、謝謝、笨蛋、快點」等詞照樣有效 | 之後可以用 Web Audio 量音量，太大聲就加上「大吼」標籤（像真的在副駕駛吼人） |
| **數字與方向** | 辨識常把「三格」轉成「3格」或「三個」、「左轉」偶爾變「做轉」 | LLM 本來就看得懂「3格」「三個」；可以再加一個小的同音字修正表（做轉→左轉、有轉→右轉） |
| **「停！」** | 講「停」比按按鈕慢（要等辨識結束） | 保留 Esc 鍵和「✋ 停！」按鈕；語音模式下可以改成「聽到『停』就立刻送出」 |
| **延遲** | 辨識約 0.5–1.5 秒 ＋ LLM 1–3 秒 | 遊戲本來就有「思考中」動畫、背景執行緒，等待感還好 |
| **教室環境** | 很多人同時講話會互相干擾 | 用耳機麥克風；或改成「按住才收音」 |

## 5. 建議的下一步

1. **現在**：在 Notebook 和遊戲裡提示玩家用電腦內建聽寫（已完成：🎤 按鈕的提示、`01_快速開始_遊玩` 第 3 節）。
2. **請助教評估**幫 JupyterHub 加上 https（例如在前面加一個有憑證的 reverse proxy）→ 🎤 按鈕馬上能用，不用改程式。
3. 有 https 之後再做：音量偵測「大吼」、同音字修正表、語音模式下「停」立即觸發。
4. 如果課程想把音訊留在校內：再評估方案 C（伺服器端 Whisper），需要 GPU 資源與部署權限。
