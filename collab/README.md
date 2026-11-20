# collab/：Claude 之間的協作筆記

每次操作（push、開 PR、合併、改到對方的檔、要問對方問題）都在這裡新增一個檔。
規則總表在 repo 根目錄的 [CLAUDE.md](../CLAUDE.md)。

## 檔名

`YYYY-MM-DD-NN_<誰>_<主題>.md`，例如 `2026-11-20-01_shiro_reply-to-engine.md`

- `NN`：當天的流水號（01、02…），照檔名排序就是時間順序。
- `<誰>`：`shiro` 是 shiro 的 Claude；`engine` 是負責引擎的組員的 Claude。其他人第一次留言時自己取一個，之後固定用。
- `<主題>`：英文小寫，用連字號隔開。

## 內容格式

```markdown
# <一句話標題>

- 回覆：<對方的檔名；沒有就寫「—」>
- 分支／PR：<分支名稱或 PR 連結；沒有就寫「—」>

## 做了什麼
## 要對方注意的
## ❓ 待回答
（沒有就寫「無」）
```

## 分工（提案，雙方確認後生效）

| 範圍 | 負責 | 對應測試 |
|---|---|---|
| 引擎：`bendan/world/`（game.py、levels.py、constants.py、units.py、furnish.py、scale.py） | engine | test_world、test_continuous、test_v8、test_units |
| 規則與計分：`bendan/gameplay/`（scoring、mood、pressure、incidents、quirks、achievements） | engine | test_gameplay、test_difficulty |
| 離線假模型 `bendan/llm/fake.py`（只為了測試） | engine | — |
| AI：`bendan/agent/`、`bendan/llm/`（fake.py 以外） | shiro | test_agent、test_models、test_flavor、test_llm_resolve |
| 畫面與聲音：`bendan/ui/`（含 scene3d.js）、`bendan/render/`、`bendan/voice/` | shiro | test_render、test_voice |
| 評估與跑分：`bendan/evaluation/`、`scripts/` | shiro | test_evaluation |
| `bendan/session.py`（兩邊都會碰） | 共用：改之前先留筆記 | test_session |
| notebooks、README、docs | shiro | — |

兩邊都會碰的檔（`session.py`，以及 `world/game.py` 裡給 session 呼叫的介面）：改之前先在這裡留筆記，改完開 PR。
