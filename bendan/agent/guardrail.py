"""安全護欄（Guardrail）：LLM 的計畫真的執行前，先在「複製的世界」裡模擬一次。

第一層驗證是 JSON 白名單（parsing.py）：只檢查「格式」。
第二層就是這裡：檢查「後果」——如果計畫會闖進禁區，就在闖入前那一步截斷。

為什麼需要？實測 Qwen2.5-7B（評估場景，臥室設為禁區）：
Prompt 明明寫「絕對不能進去」，正經模式只有 17%、賣蠢模式 33% 的計畫沒闖禁區。
光靠 Prompt 管不住 7B 模型，關鍵規則要由程式把關——這正是 Agent 設計裡「LLM 規劃、程式驗證」的分工。
"""
import copy

from ..world.constants import INTERRUPT_EVENTS
from ..world.game import run_to_end


def guard_forbidden(game, actions):
    """回傳 (安全的動作清單, 說明或 None)。說明不是 None 代表有動作被截掉。"""
    if not game.forbidden or not actions:
        return actions, None
    g = copy.deepcopy(game)
    g.queue.clear()
    kept = []
    for a in actions:
        steps = [{"op": "forward", "n": 1}] * a["n"] if a["op"] == "forward" else [a]
        done = 0
        for step in steps:
            g.set_plan([step])
            events = run_to_end(g)
            types = {e["type"] for e in events}
            if "entered_forbidden" in types:
                if done:
                    kept.append({"op": "forward", "n": done})
                return kept, f"🛡️ 護欄攔下：再走就會闖進禁區「{g.room_of(g.pos)}」，後面的動作取消了。"
            if types & INTERRUPT_EVENTS or g.over:
                return actions, None      # 真的執行時會先被別的事件打斷，不會走到禁區
            done += 1
        kept.append(a)
    return actions, None
