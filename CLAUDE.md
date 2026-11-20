# 給在這個 repo 工作的 Claude（還有組員）

這個專案同時有不只一個 Claude 在改：shiro 本機的 Claude，還有組員在 GitHub 上用的 Claude。
為了不要改到同一個檔，也讓對方知道你做了什麼，請照下面的規則。

## 協作規則（必讀）

1. **開始工作前**：先看 `collab/` 裡最新的幾個筆記（檔名照時間排序）。有「❓ 待回答」而且是問你的，先回。
2. **每次操作都留一個筆記檔**：push、開 PR、合併、改到對方負責的檔、或有事要問對方時，
   在 `collab/` 新增一個檔（格式見 [collab/README.md](collab/README.md)），跟改動放在同一個 commit 或 PR 裡。
3. **不要改別人的筆記**。要回覆就新增一個檔，在開頭寫「回覆：<對方的檔名>」。
4. **要改對方負責的檔**（分工表在 `collab/README.md`）→ 開 PR，請對方看過再合併，不要直接推 `main`。
5. **不要把 API Key、組帳號密碼、任何人的 email 寫進 repo**，筆記也一樣。

## 專案慣例

- 遊戲介面的文字、筆記、回覆一律用台灣繁體中文。
- `notebooks/*.ipynb` 是 `scripts/build_notebooks.py` 產生的：要改 notebook 內容，請改腳本再重新產生。
- 測試：`python -m pytest -q`（全部離線，用 FakeLLM）。改到 agent 或 LLM 相關的程式，還要在課程伺服器上用真模型驗證。
- 單位：1 格 = 50 公分；模型回的 `forward` 用 `cm`（parser 也接受 `m` 和舊的格數 `n`）。
- 原則：「程式決定、LLM 演出」：會不會出事、扣多少分由程式決定，LLM 只負責講話和選動作。
