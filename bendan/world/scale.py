"""v6：把關卡地圖放大（預設每格 → 2×2，面積約 4 倍），並把灰塵加倍。

為什麼用程式放大、不直接重畫地圖？關卡（牆、房間、門、障礙物的相對位置）都是實測調過的，
放大後玩法不變，只是格子變小、房子變大——配合「一直往前開、喊停才停」的連續移動。

規則：
- 牆壁「線條」維持 1 格厚：一整欄（列）大部分都是牆的（外牆、房間隔間）只放大成 1 格寬，其它欄（列）放大 k 倍。
  → 門口從 1 格變成 k 格寬，連續移動時比較好開進去。
- 地板、牆壁：整塊照抄。灰塵、充電座、起點、貓狗、樂高……：放在那塊的左上角，其它是地板。
- 每坨原本的灰塵旁邊（同一個房間、3 格內、走得到）再多一坨 → 灰塵數量加倍。
- 依放大倍數一起調整：房間範圍、步數上限 ×2.5、標準句數與指令上限 ×1.5、停電燈光與視野 ×k、
  寵物亂跑的間隔 ×k、每步機率 ÷k，以及介紹文字裡的「N 坨」「走 N 步」。
"""
import math
import random
import re
from collections import deque

MAP_SCALE = 2
SPECIAL = set("DH^>v<CGLSWPO")
BLOCK = set("#CG")


def _sizes(rows, k):
    h, w = len(rows), len(rows[0])
    cols = [1 if sum(r[x] == "#" for r in rows) * 2 >= h else k for x in range(w)]
    lines = [1 if r.count("#") * 2 >= w else k for r in rows]
    return cols, lines


def _offsets(sizes):
    out, acc = [], 0
    for s in sizes:
        out.append(acc)
        acc += s
    return out, acc


def _room_of(rooms, p):
    for name, (x0, y0, x1, y1) in rooms.items():
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            return name
    return "客廳"


def _reach(grid, start, rooms, forbidden):
    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            n = (x + dx, y + dy)
            if (n in seen or not (0 <= n[1] < len(grid) and 0 <= n[0] < len(grid[0]))
                    or grid[n[1]][n[0]] in BLOCK or _room_of(rooms, n) in forbidden):
                continue
            seen.add(n)
            q.append(n)
    return seen


def _round10(v):
    return int(math.ceil(v / 10.0) * 10)


def scale_level(cfg, k=MAP_SCALE, seed=0):
    """回傳放大後的新關卡設定（不改原本的 dict）。k=1 原樣回傳。"""
    if k <= 1:
        return cfg
    rows = cfg["map"]
    cols, lines = _sizes(rows, k)
    xo, W = _offsets(cols)
    yo, H = _offsets(lines)
    grid = [["." for _ in range(W)] for _ in range(H)]
    start, dirt = None, []
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            for dy in range(lines[y]):
                for dx in range(cols[x]):
                    grid[yo[y] + dy][xo[x] + dx] = "#" if ch == "#" else "."
            if ch in SPECIAL:
                p = (xo[x], yo[y])
                grid[p[1]][p[0]] = ch
                if ch in "^>v<":
                    start = p
                elif ch == "D":
                    dirt.append(p)
    rooms = {name: (xo[x0], yo[y0], xo[x1] + cols[x1] - 1, yo[y1] + lines[y1] - 1)
             for name, (x0, y0, x1, y1) in cfg.get("rooms", {}).items()}
    forbidden = set(cfg.get("forbidden", []))

    # 灰塵加倍：每坨旁邊再撒一坨（同房間、走得到、不在禁區）
    rng = random.Random(f"scale-{seed}")
    reach = _reach(grid, start, rooms, forbidden) if start else set()
    added = 0
    for p in dirt:
        room = _room_of(rooms, p)
        cands = [(x, y) for y in range(p[1] - 3, p[1] + 4) for x in range(p[0] - 3, p[0] + 4)
                 if (x, y) in reach and grid[y][x] == "." and (x, y) != p and _room_of(rooms, (x, y)) == room
                 and abs(x - p[0]) + abs(y - p[1]) >= 2]
        if cands:
            x, y = rng.choice(sorted(cands))
            grid[y][x] = "D"
            added += 1
    ratio = (len(dirt) + added) / len(dirt) if dirt else 1

    out = dict(cfg, map=["".join(r) for r in grid], rooms=rooms, scale=k)
    if cfg.get("step_limit"):
        out["step_limit"] = _round10(cfg["step_limit"] * 2.5)
    for key in ("par", "command_limit"):
        if cfg.get(key):
            out[key] = int(round(cfg[key] * 1.5))
    for key in ("dark", "vision"):
        if cfg.get(key):
            out[key] = cfg[key] * k
    incidents = []
    for spec in cfg.get("incidents", []):
        spec = dict(spec)
        if "every" in spec:
            spec["every"] = spec["every"] * k
        if "chance" in spec:
            spec["chance"] = spec["chance"] / k
        incidents.append(spec)
    out["incidents"] = incidents

    def fix_text(s):
        s = re.sub(r"(\d+) 坨", lambda m: f"{round(int(m.group(1)) * ratio)} 坨", s)
        if out.get("step_limit"):
            s = re.sub(r"走 \d+ 步", f"走 {out['step_limit']} 步", s)
        if out.get("command_limit"):
            s = re.sub(r"(\d+) 句", lambda m: f"{out['command_limit']} 句" if int(m.group(1)) == cfg.get(
                "command_limit") else m.group(0), s)
        return s
    for key in ("intro", "new", "tip"):
        if isinstance(out.get(key), str):
            out[key] = fix_text(out[key])
    if out.get("vision") and isinstance(out.get("new"), str):
        out["new"] = out["new"].replace(f"{cfg['vision']} 格", f"{out['vision']} 格")
    if out.get("vision") and isinstance(out.get("tip"), str):
        out["tip"] = out["tip"].replace(f"{cfg['vision']} 格", f"{out['vision']} 格")
    return out
