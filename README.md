# 笨笨掃地機

以 LLM 為大腦、會「賣蠢」的 2.5D 掃地機器人指令遊戲（代理型人工智慧基礎與應用實作｜期末專題）。

## 使用方式
1. 在課程 JupyterHub 開啟 `笨笨掃地機_Agent.ipynb`（課程 Kernel 已設定 `OPENAI_BASE_URL`、`OPENAI_API_KEY`）。
2. 由上往下執行；第 5 節開始遊玩（文字模式 `play()` 或即時模式 `play_widgets()`）。
3. 第 6 節執行評估（照做率、格式正確率、記憶遵守率、延遲）。

沒有 API 設定時會自動改用離線 FakeLLM 測試流程。請勿將 API Key 提交到 repo。
