"""v8：沿著牆擺家具（真的會擋路、會撞到），以及在地板上挖地洞。

以前 3D 畫面的家具是「畫在牆那一格裡」的裝飾，牆面離笨笨還有一整格 → 撞牆時看起來中間有空隙。
v8 改成：牆壁＝整格實心（牆面就在格子邊界上），家具改成地圖上真的障礙物（地圖字元 'F'），
LLM 看得到（「前方第 3 格是沙發」），撞到一樣會受損。

規則（只在放大地圖時做，k ≥ 2）：
- 家具貼著牆擺（背後是牆），前面至少要留 2 格地板；門口附近 2 格內、起點、充電座旁邊不擺；不放在灰塵、物件上。
- 每擺一件都用 BFS 檢查：其它走得到的格子還是全部走得到（不會把房間或走道堵死）。
- 兩格寬的家具（沙發、床、書桌……）沿著牆佔兩格。
- 地洞（'U'）：關卡設定 "holes": N 時隨機挖 N 個，一樣不能把路堵死（導航會繞開地洞）。
"""
from collections import deque

DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))

# 每個房間會出現的家具：(代號, 中文名稱, 佔幾格)。3D 模型對照在 bendan/ui/scene3d.js 的 FURN_MODELS
CATALOG = {
    "客廳": [("sofa", "沙發", 2), ("tv", "電視櫃", 2), ("bookcase", "書櫃", 1), ("armchair", "單人沙發", 1),
            ("plant", "盆栽", 1), ("lamp", "立燈", 1), ("speaker", "音響", 1)],
    "臥室": [("bed", "床", 2), ("wardrobe", "衣櫃", 1), ("nightstand", "床頭櫃", 1), ("lamp", "立燈", 1),
            ("plant", "盆栽", 1)],
    "廚房": [("fridge", "冰箱", 1), ("stove", "瓦斯爐", 1), ("sink", "流理台", 1), ("counter", "櫥櫃", 1),
            ("counter2", "櫥櫃", 1)],
    "書房": [("desk", "書桌", 2), ("shelf", "書櫃", 2), ("bookcase", "書櫃", 1), ("plant", "盆栽", 1)],
    "浴室": [("toilet", "馬桶", 1), ("basin", "洗手台", 1), ("washer", "洗衣機", 1), ("bathcab", "浴櫃", 1)],
}
NAMES = {key: name for items in CATALOG.values() for key, name, _ in items}
BLOCKING = set("#FCG")


def room_of(rooms, p):
    for name, (x0, y0, x1, y1) in rooms.items():
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            return name
    return "客廳"


def _reach(grid, start, rooms, forbidden):
    """從起點走得到的格子（不進禁區；地洞當作走不過去）。"""
    H, W = len(grid), len(grid[0])
    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in DIRS:
            n = (x + dx, y + dy)
            if (n in seen or not (0 <= n[0] < W and 0 <= n[1] < H) or grid[n[1]][n[0]] in BLOCKING
                    or grid[n[1]][n[0]] == "U" or room_of(rooms, n) in forbidden):
                continue
            seen.add(n)
            q.append(n)
    return seen


def _doors(grid):
    """門口：落在「牆線」（大部分是牆的整欄／整列）上的地板格。"""
    H, W = len(grid), len(grid[0])
    cols = {x for x in range(W) if sum(grid[y][x] == "#" for y in range(H)) * 2 >= H}
    rows = {y for y in range(H) if sum(c == "#" for c in grid[y]) * 2 >= W}
    return {(x, y) for y in range(H) for x in range(W) if grid[y][x] != "#" and (x in cols or y in rows)}


def _near(p, cells, r):
    return any(abs(p[0] - q[0]) <= r and abs(p[1] - q[1]) <= r for q in cells)


def _safe_to_block(grid, cells, start, rooms, forbidden, reach):
    """把 cells 擋起來之後，其它原本走得到的格子是不是都還走得到。"""
    saved = [grid[y][x] for x, y in cells]
    for x, y in cells:
        grid[y][x] = "F"
    ok = _reach(grid, start, rooms, forbidden) == reach - set(cells)
    for (x, y), ch in zip(cells, saved):
        grid[y][x] = ch
    return ok


def furnish(grid, rooms, forbidden, start, rng, holes=0):
    """直接改 grid（list of list），回傳家具清單 [{x, y, key, name, back, span, part, sx, sy}, ...]。"""
    H, W = len(grid), len(grid[0])
    if start is None:
        return []
    doors = _doors(grid)
    keep = [start] + [(x, y) for y in range(H) for x in range(W) if grid[y][x] == "H"]
    reach = _reach(grid, start, rooms, forbidden)

    def wall(x, y):
        return not (0 <= x < W and 0 <= y < H) or grid[y][x] == "#"

    def free(x, y):
        return 0 <= x < W and 0 <= y < H and grid[y][x] == "."

    def candidate(p, b):
        x, y = p
        bx, by = DIRS[b]
        return (free(x, y) and wall(x + bx, y + by) and free(x - bx, y - by) and free(x - 2 * bx, y - 2 * by)
                and not _near(p, doors, 2) and not _near(p, keep, 1))

    spots = {}
    for y in range(H):
        for x in range(W):
            for b in range(4):
                if candidate((x, y), b):
                    spots.setdefault(room_of(rooms, (x, y)), []).append(((x, y), b))
    placed = []
    for room in sorted(spots):
        cands = sorted(spots[room])
        rng.shuffle(cands)
        catalog = CATALOG.get(room, CATALOG["客廳"])
        want = max(1, len(cands) // 6)
        items = [catalog[i % len(catalog)] for i in range(want)]
        rng.shuffle(items)
        for key, name, span in items:
            for (x, y), b in cands:
                if grid[y][x] != ".":
                    continue
                bx, by = DIRS[b]
                cells = [(x, y)]
                sx, sy = by, -bx                    # 沿著牆的方向
                if span == 2:
                    nx, ny = x + sx, y + sy
                    if not ((0 <= nx < W and 0 <= ny < H) and candidate((nx, ny), b)):
                        sx, sy = -sx, -sy
                        nx, ny = x + sx, y + sy
                        if not ((0 <= nx < W and 0 <= ny < H) and candidate((nx, ny), b)):
                            continue
                    cells.append((nx, ny))
                # 家具彼此之間至少隔一格（不要擠成一排擋住牆邊）
                if any(grid[cy + dy][cx + dx] == "F" for cx, cy in cells for dx, dy in DIRS
                       if 0 <= cx + dx < W and 0 <= cy + dy < H and (cx + dx, cy + dy) not in cells):
                    continue
                if not _safe_to_block(grid, cells, start, rooms, forbidden, reach):
                    continue
                for i, (cx, cy) in enumerate(cells):
                    grid[cy][cx] = "F"
                    placed.append({"x": cx, "y": cy, "key": key, "name": name, "back": b, "span": span, "part": i,
                                   "sx": sx, "sy": sy})
                reach -= set(cells)
                break
    # 地洞：不在禁區、離起點／充電座 3 格以上、不在門口附近，而且不能把路堵死
    if holes:
        cands = [(x, y) for y in range(H) for x in range(W) if grid[y][x] == "." and (x, y) in reach
                 and not _near((x, y), doors, 1) and not _near((x, y), keep, 3)
                 and room_of(rooms, (x, y)) not in forbidden]
        rng.shuffle(cands)
        dug = 0
        for x, y in cands:
            if dug >= holes:
                break
            if any(grid[y + dy][x + dx] in "UF" for dx, dy in DIRS):
                continue
            if _safe_to_block(grid, [(x, y)], start, rooms, forbidden, reach):
                grid[y][x] = "U"
                reach.discard((x, y))
                dug += 1
    return placed
