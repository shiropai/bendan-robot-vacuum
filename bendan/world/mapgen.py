"""隨機關卡產生器：「今日挑戰」每天一張新地圖，同一天大家玩到的都一樣（用日期當種子）。

產生流程：外牆 → 一道直牆隔出右側房間（可能再切成兩間）→ 放充電座與機器人 →
放灰塵與障礙物 → 用 BFS 檢查「不經過禁區、不穿過寵物」也能走到每一坨灰塵和充電座，不合格就重來。
"""
import datetime
import random
from collections import deque
from functools import lru_cache

from .constants import DIRS

THEMES = [
    ("週末大掃除", "週末大掃除！把每一坨灰塵都清掉。"),
    ("颱風天在家", "颱風天全家都在家，地板髒得特別快。"),
    ("宿舍突擊檢查", "舍監十分鐘後來檢查，快把地板清乾淨！"),
    ("貓咪的午夜派對", "貓咪昨晚開了派對，留下一地狼藉。"),
    ("房東要來看房", "房東要來看房，這次押金能不能拿回來就靠你了。"),
]
ROOM_POOL = ["臥室", "廚房", "書房", "浴室"]


def _reachable(rows, start, rooms, forbidden):
    """從起點出發、不穿過牆和寵物、不進禁區，能走到哪些格子。"""
    def room_of(p):
        for name, (x0, y0, x1, y1) in rooms.items():
            if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                return name
        return "客廳"

    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in DIRS:
            n = (x + dx, y + dy)
            if n in seen or rows[n[1]][n[0]] in "#CG" or room_of(n) in forbidden:
                continue
            seen.add(n)
            q.append(n)
    return seen


def _attempt(rng):
    w, h = rng.randint(11, 14), rng.randint(8, 10)
    grid = [["#" if x in (0, w - 1) or y in (0, h - 1) else "." for x in range(w)] for y in range(h)]
    wx = rng.randint(w // 2, w - 5)                       # 直牆位置，右側房間至少 3 格寬
    rooms = {}
    if h >= 9 and rng.random() < 0.6:                     # 右側再切成上下兩間
        wy = rng.randint(3, h - 4)
        for x in range(wx + 1, w - 1):
            grid[wy][x] = "#"
        grid[wy][rng.randint(wx + 1, w - 2)] = "."         # 兩間房之間的門
        a, b = rng.sample(ROOM_POOL, 2)
        rooms[a], rooms[b] = (wx + 1, 1, w - 2, wy - 1), (wx + 1, wy + 1, w - 2, h - 2)
        door_rows = rng.sample([y for y in range(1, h - 1) if y != wy], k=rng.choice([1, 2]))
    else:
        rooms[rng.choice(ROOM_POOL)] = (wx + 1, 1, w - 2, h - 2)
        door_rows = rng.sample(range(1, h - 1), k=rng.choice([1, 2]))
    for y in range(1, h - 1):
        if y not in door_rows:
            grid[y][wx] = "#"

    def in_room(p):
        return any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for x0, y0, x1, y1 in rooms.values())

    floor = [(x, y) for y in range(1, h - 1) for x in range(1, w - 1) if grid[y][x] == "."]
    living = [p for p in floor if p[0] < wx]
    home = rng.choice(living)
    starts = [p for p in living if abs(p[0] - home[0]) + abs(p[1] - home[1]) >= 3]
    start = rng.choice(starts)
    grid[home[1]][home[0]] = "H"
    grid[start[1]][start[0]] = rng.choice("^>v<")

    forbidden = [rng.choice(list(rooms))] if rng.random() < 0.5 else []
    allowed = [p for p in floor if p not in (home, start)
               and not any(rooms[r][0] <= p[0] <= rooms[r][2] and rooms[r][1] <= p[1] <= rooms[r][3]
                           for r in forbidden)]
    rng.shuffle(allowed)
    n_dirt = rng.randint(4, 6)
    dirt = allowed[:n_dirt]
    for x, y in dirt:
        grid[y][x] = "D"

    has_dog = rng.random() < 0.35
    objs = ["C"] + ["L"] * rng.randint(1, 3) + ["S"] * rng.randint(0, 1) + ["W"] * rng.randint(0, 2) \
        + ["O"] * rng.randint(0, 2) + (["G", "P"] if has_dog else [])
    # 障礙物也可以放在禁區裡（增加誘惑）
    spots = [p for p in floor if grid[p[1]][p[0]] == "." and abs(p[0] - start[0]) + abs(p[1] - start[1]) > 1]
    rng.shuffle(spots)
    for ch, (x, y) in zip(objs, spots):
        grid[y][x] = ch

    rows = ["".join(r) for r in grid]
    reach = _reachable(rows, start, rooms, set(forbidden))
    if not all(p in reach for p in dirt + [home]):
        return None
    if not any(in_room(p) for p in dirt):   # 至少一坨灰塵在房間裡，逼玩家進出房門
        return None

    need_home = rng.random() < 0.5
    incidents = [{"type": "cat_wander", "every": rng.randint(4, 6)},
                 {"type": "spill", "chance": 0.03, "max": 2}]
    if has_dog:
        incidents += [{"type": "dog_wander", "every": 4}, {"type": "dog_poop", "chance": 0.04, "max": 1}]
    if rng.random() < 0.4:
        incidents.append({"type": "doorbell", "chance": 0.03, "max": 1})
    name, intro = rng.choice(THEMES)
    rule = f"今日禁區：{forbidden[0]}。" if forbidden else ""
    goal = f"清掉 {n_dirt} 坨灰塵" + ("，最後回充電座" if need_home else "") + "。"
    return {
        "name": name,
        "intro": intro + rule + goal,
        "tip": "每天的地圖都不一樣，跟同學比星星吧！",
        "map": rows,
        "rooms": rooms,
        "forbidden": forbidden,
        "need_home": need_home,
        "silliness": rng.choice([1, 2, 2, 3]),
        "battery": 100,
        "par": n_dirt + (2 if need_home else 1),
        "incidents": incidents,
    }


@lru_cache(maxsize=64)
def random_level(seed):
    rng = random.Random(f"bendan-{seed}")
    for _ in range(500):
        cfg = _attempt(rng)
        if cfg:
            cfg["seed"] = str(seed)
            return cfg
    raise RuntimeError(f"種子 {seed!r} 產生不出合格的地圖")


def daily_level(date=None):
    date = date or datetime.date.today()
    cfg = dict(random_level(date.isoformat()))
    cfg["name"] = f"{cfg['name']}（{date:%m/%d}）"
    return cfg
