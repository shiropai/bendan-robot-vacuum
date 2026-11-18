"""記憶：禁區、已清掃區域、最近的指令。

- **禁區**：玩家說「不准進臥室」會被規則式偵測寫入（也可在關卡預設）。
- **已清掃區域**、**最近幾句指令與結果**：每次組 Prompt 時帶入，讓行為跨指令保持一致。
"""
import re
from collections import Counter, deque

from ..world.constants import KNOWN_ROOMS, QUIET_EVENTS, ROOM_ALIASES

OP_TEXT = {"turn_left": "左轉", "turn_right": "右轉", "suck": "吸", "return_home": "回充", "stop": "停"}


def actions_to_text(actions):
    return "、".join(f"前進{a['n']}格" if a["op"] == "forward" else OP_TEXT[a["op"]] for a in actions) or "（沒動）"


def events_to_text(events):
    msgs = [e["msg"] for e in events if e["type"] not in QUIET_EVENTS]
    return "；".join(msgs[:4]) if msgs else "順利完成，沒有意外。"


class Memory:
    def __init__(self, max_recent=4):
        self.recent = deque(maxlen=max_recent)

    def remember_turn(self, command, actions, events):
        self.recent.append({"cmd": command, "plan": actions_to_text(actions), "result": events_to_text(events)})

    def to_text(self, game):
        forb = "、".join(sorted(game.forbidden)) or "（無）"
        by_room = Counter(game.room_of(p) for p in game.cleaned)
        cleaned = "、".join(f"{r} {n} 坨" for r, n in by_room.items()) or "還沒有"
        lines = [f"- 禁區：{forb}（絕對不能進去）",
                 f"- 已清掃：{game.n_cleaned} 坨（{cleaned}），還剩 {len(game.dirt)} 坨"]
        if self.recent:
            lines.append("- 最近的指令：")
            for r in self.recent:
                lines.append(f"  ·「{r['cmd']}」→ 你做了：{r['plan']} → 結果：{r['result']}")
        return "\n".join(lines)


_ROOM_RE = "|".join(sorted(set(KNOWN_ROOMS) | set(ROOM_ALIASES), key=len, reverse=True))
FORBID_RE = re.compile(rf"(不准|不準|不要|別|禁止|不可以|不能|不許)\s*再?\s*(進入|進去|跑進|跑去|靠近|進|去|到)?\s*(?P<room>{_ROOM_RE})")
ALLOW_RE = re.compile(rf"(?<!不)(可以|准|允許)\s*(進入|進去|進|去)\s*(?P<room>{_ROOM_RE})")


def update_rules_from_text(game, text):
    """從玩家的話更新禁區（寫入記憶）。回傳變更說明。"""
    notes = []
    for m in FORBID_RE.finditer(text):
        room = ROOM_ALIASES.get(m.group("room"), m.group("room"))
        if room in game.room_names() and room not in game.forbidden:
            game.forbidden.add(room)
            notes.append(f"📝 記住了：「{room}」是禁區")
    if not notes:
        for m in ALLOW_RE.finditer(text):
            room = ROOM_ALIASES.get(m.group("room"), m.group("room"))
            if room in game.forbidden:
                game.forbidden.discard(room)
                notes.append(f"📝 解除禁區：「{room}」")
    return notes
