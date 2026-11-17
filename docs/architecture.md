# 🏗️ 系統架構

## 分層

```
┌──────────────────────── ui/ ────────────────────────┐
│  text_mode.play()   widget_mode.play_widgets()   scripts/play_cli.py │
└───────────────┬─────────────────────────────────────┘
                │ 玩家指令 / 畫面更新
┌───────────────▼──────── session.py ─────────────────┐
│ preprocess → think（背景執行緒）→ apply → tick → feedback │
│        │            │                  │             │
│   gameplay/      agent/             world/           │
│   心情 血壓 計分   Prompt 記憶 驗證    地圖 引擎 事件   │
│   突發事件 成就      │                                 │
│                   llm/（課程 API ／ FakeLLM）          │
└─────────────────────────────────────────────────────┘
          render/（等角 2.5D、HUD、ASCII）   evaluation/（指標、實驗、圖表）
```

**原則：只用結構化資料溝通。** Agent 給「動作清單」（JSON），遊戲回「事件清單」（dict），
玩法系統只讀事件、只改自己的數值或呼叫 `game.fail()`。所以：

- `world/` 完全不知道 LLM 存在 → 可以單獨測試、換成 pygame 也不用動
- `agent/` 只讀世界狀態、不改世界 → `think()` 可以安全地丟到背景執行緒
- `gameplay/` 可以整個關掉（`Session(gameplay=False)`）→ 評估時公平比較模型

## 一個回合的資料流

```
"笨蛋快點前進三格"
  │ session.preprocess
  ├─ gameplay.analyze_tone → Tone(delta=-20, tags=[罵人, 催促], bp=+5)
  ├─ mood.apply_tone → 心情 65→45（不爽）→ 事件 {"type": "mood"}
  ├─ agent.update_rules_from_text（禁區）
  └─ mood.should_refuse(rng) → refuse=False
  │ session.think（ThreadPoolExecutor）
  ├─ agent.build_messages：人設＋賣蠢強度(關卡 2 + 心情 +1)＋ACTION_SPEC＋世界描述＋記憶＋【你的心情】
  ├─ llm.chat → '{"actions":[{"op":"forward","n":3}],"say":"做就做嘛","emotion":"委屈"}'
  └─ parsing.parse_reply → 白名單驗證（失敗重試一次 → 仍失敗就發呆）
  │ session.apply → game.set_plan（展開成微步驟）
  │ session.tick × N
  ├─ game.step → 事件（cleaned / lego / smeared / ...）
  ├─ incidents.on_step → 突發事件
  └─ _absorb → 心情、血壓、分數、失敗判定、結算、成就、存檔
  │ 若被中斷 → pending_feedback → 再 think 一次（事件回饋閉環）
```

## 三層把關

| 層 | 位置 | 檢查什麼 | 為什麼 |
|---|---|---|---|
| 1. 白名單驗證 | `agent/parsing.py` | JSON 格式、動作名稱、參數範圍；`turn_*`／`suck` 可帶 `n`（展開成重複動作） | 模型輸出不可信；失敗自動重試一次，再失敗就「發呆」 |
| 2. 程式護欄 | `agent/guardrail.py` | 在複製的世界模擬計畫，會闖禁區就在前一步截斷 | 實測 7B 模型 67–83% 的計畫無視禁區；`Session(guardrail=True)` 或遊戲中 `/guard` 開啟 |
| 3. 遊戲規則 | `world/game.py`、`gameplay/` | 碰撞、電量、血壓、指令上限 | 世界本身的物理與勝負 |

另外，遊戲中的世界描述會附上【路線提示】（`agent/perception.py: route_hints`）：
BFS 算好「去最近那坨灰塵」的動作 JSON，因為實測 7B 模型規劃不出多段路線。評估時預設關閉。

## 執行緒安全

- `Session.lock`（RLock）保護 `game` 與玩法狀態；`Agent.think` 只在組 Prompt 時上鎖，呼叫 LLM 時不鎖
- 渲染用 matplotlib 物件導向 API（`Figure` + `FigureCanvasAgg`），不碰 pyplot 全域狀態，背景執行緒可用
- 即時模式：背景執行緒每 `tick` 秒呼叫一次 `session.tick()`；按「停！」會把正在想的那句標記為 `discard`

## Log 與存檔

- `logs/game_log.jsonl`：每回合一行（指令、模型原話、驗證結果、事件、心情、血壓、電量、分數、延遲）
- `logs/eval_*.csv`、`logs/mood_eval_*.csv`：評估結果
- `saves/progress.json`：星星、最佳分數、成就、累積事件數
- 兩者都在 `.gitignore`；位置可用環境變數 `BENDAN_LOG_DIR`、`BENDAN_SAVE_DIR` 改

## 測試

```bash
pytest -q          # 100+ 個測試，全部用離線 FakeLLM，不需要 API
```

涵蓋：每個關卡與 40 張隨機地圖可解、移動／碰撞／新障礙物／電量、JSON 驗證、語氣與心情、血壓失敗、指令上限、
突發事件、計分星級、成就、存檔解鎖、完整 Session 閉環、評估流程、渲染。
