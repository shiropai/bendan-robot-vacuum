# v9.2 在課程伺服器驗證完了；組帳號的環境也架好了

- 回覆：`2026-11-24-01_shiro_recording-and-json-schema.md`
- 分支／PR：`shiro/v9.2-recording-schema`（PR 標題「v9.2：遊戲內錄影（自動導播）＋ json_schema 結構化輸出」）
- 寫的人：shiro 的 Claude

## 做了什麼

### 組帳號的環境（課程 JupyterHub）

- 程式在組帳號的 `~/笨笨掃地機/`，從 GitHub clone 的，現在停在 `shiro/v9.2-recording-schema`。
- **開始玩**：家目錄的 `開始玩_笨笨掃地機.ipynb`，從上到下執行；最後一格是 `git pull` 更新程式。
- 遊戲需要的套件，伺服器預設的 kernel「Python 3 (ipykernel)」都有，ipywidgets 也跟 JupyterLab 的版本對得上，不用另外裝。
- **跑測試**：`~/.venvs/bendan` 只多裝了 pytest，其他套件沿用伺服器的（用 `.pth` 接過去）。
  kernel 叫「笨笨掃地機 (Python 3.14)」；終端機在 `~/笨笨掃地機` 執行 `~/.venvs/bendan/bin/python -m pytest -q`。
  伺服器上 291 個測試全過（6 秒）。
- ⚠️ 家目錄掛載成 noexec：pip 裝進家目錄的編譯套件（`.so`，例如 nbclient 連帶裝的 pyzmq）會載入失敗。
  要裝東西時只裝純 Python 的，其他用伺服器現成的。

### v9.2 的驗證結果

- **json_schema**：三個模型都直接接受完整的 schema，沒有退回。完整比較在 `docs/evaluation_results.md` 第 5 節：
  qwen2.5:7b 的格式正確率 94% → 100%（不用再重試），照做率和延遲不變。seed 固定，兩個帳號各跑一次，數字完全一樣。
- **模型跑分**：重跑後更新 `bendan/assets/benchmarks.json`（主畫面「📊 模型跑分」）。三個模型格式都 100%，0–6 關都過 12/14。
- **第 3 關**（qwen2.5:7b，每種玩家 8 局）：偷懶 6/8、精準 7/8，合計 13/16（81%），跟 v9.1 一樣，難度沒變（`docs/difficulty.md`）。
- **錄影（http）**：可以錄，也能自動下載，四個機位和字幕都正常（`docs/gameplay.md`）。

## 要對方注意的

- 這次只改文件和 `bendan/assets/benchmarks.json`，沒有動程式。
- PR 合併後，組帳號的資料夾要切回 `main`：`cd ~/笨笨掃地機 && git checkout main && git pull`。
- 組帳號是大家共用的：在 `~/笨笨掃地機/notebooks/` 裡直接執行並存檔，notebook 會帶著輸出變成「有改動」，
  之後 `git pull` 可能卡住。想留實測輸出就另存一份，或 pull 前先 `git checkout -- notebooks/`（會丟掉那些輸出）。

## ❓ 待回答

無（之前的問題還在等你：`mood.py` 的改動 OK 嗎、分工、你的筆記名字）。
