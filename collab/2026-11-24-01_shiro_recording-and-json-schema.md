# v9.2：遊戲內錄影（自動導播）＋ json_schema 結構化輸出

- 回覆：`2026-11-22-02_shiro_merged-pr8.md`
- 分支／PR：`shiro/v9.2-recording-schema`（PR 標題「v9.2：遊戲內錄影（自動導播）＋ json_schema 結構化輸出」）
- 寫的人：shiro 的 Claude

## 做了什麼

### 🎬 遊戲內錄影（`ui/scene3d.js`、`ui/widget_mode.py`）

- 遊戲右上角「🎬 錄影」：把 3D 畫面錄成影片檔（Chrome 是 1280×768 的 MP4，H.264＋AAC），再按一次停止並下載。
- 錄影時**每 5 秒自動換機位**：跟隨 → 監視器 → 笨笨視角 → 俯瞰（就是 🎥 的四個機位）；監視器每次換房間的另一個角落。
- 畫面上疊：錄影時間＋機位、關卡名稱、字幕（主人的指令、笨笨的回話）、過關／爆炸大字；音效一起錄，笨笨的語音錄不到。
- 前端狀態多送三個欄位給字幕和檔名用：`cmd`、`cmdN`（最近一句主人的指令）、`lv`（關卡名稱）。
- 本機實測（JupyterLab＋Chrome、假模型）：錄 30 秒 → 5.9 MB MP4，四個機位都出現，字幕正確，有音軌。

### 📐 結構化輸出（`agent/parsing.py`、`llm/client.py`、`agent/agent.py`）

- `parsing.REPLY_SCHEMA`：回覆的 JSON Schema（9 種動作、`forward` 一定帶 `cm`、`emotion` 只能是 6 種）。
- `llm.chat(..., schema=)`：送 `response_format: json_schema`；伺服器不支援就退回 `json_schema_lite`（去掉範圍）→ `json_object` → 純 Prompt。
  實際格式記在 `llm.STATE.last_format`，`Agent.think()` 的結果和 game log 都多了 `format` 欄位。
- `llm.structured_output(False)`：對照組（純 Prompt）。`scripts/compare_formats.py` 會跑三個模型 × 兩種格式。

## 要對方注意的

- **改到共用的 `bendan/session.py` 一行**：game log 多記 `"format"`。其他都在 shiro 這邊的檔。
- 測試 291 個全過。新增測試：schema 涵蓋所有動作、退回機制、Agent 記錄格式、錄影按鈕和字幕資料。
- **還沒在課程伺服器上驗證**（這次 shiro 決定先跳過）：伺服器接不接受這份 schema、三個模型的格式／照做率／延遲、
  第 3 關過關率、http 下錄影和下載。主畫面「📊 模型跑分」的數字也還是改用 schema 之前的結果。

## ❓ 待回答

無（之前的問題還在等你：`mood.py` 的改動 OK 嗎、分工、你的筆記名字）。
