"""遊戲世界：地圖、機器人、障礙物、電量、動作佇列執行器與事件系統。完全不依賴 LLM。

- `set_plan(actions)`：把驗證過的動作展開成「微步驟」放進佇列（新指令會**取代**還沒做完的舊計畫）。
- `step()`：執行一個微步驟（走一格／轉一次／吸一次），回傳這一步發生的**事件**。
- `return_home` 用 BFS 找路，會盡量避開禁區與危險物。
"""
import copy
import random
from collections import deque

from .constants import (AVOID_OBJECTS, BATTERY_COST, BLOCKING_OBJECTS, DIRS, LOW_BATTERY_RATIO, OBJECT_CHARS,
                        OBJECT_NAMES, START_FACING, E)
from .levels import get_level


class Game:
    def __init__(self, level_id=1, seed=None):
        self.rng = random.Random(seed)
        self.load(level_id)

    def load(self, level_id):
        cfg = get_level(level_id)
        rows = cfg["map"]
        self.level_id, self.cfg = level_id, cfg
        self.h, self.w = len(rows), len(rows[0])
        assert all(len(r) == self.w for r in rows), "地圖每一列長度必須相同"
        self.walls, self.objects, self.dirt = set(), {}, set()
        self.home = self.pos = None
        self.facing = 1
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                p = (x, y)
                if ch == "#":
                    self.walls.add(p)
                elif ch == "D":
                    self.dirt.add(p)
                elif ch == "H":
                    self.home = p
                elif ch in START_FACING:
                    self.pos, self.facing = p, START_FACING[ch]
                elif ch in OBJECT_CHARS:
                    self.objects[p] = OBJECT_CHARS[ch]
        assert self.pos is not None, "地圖需要機器人起點 (^ > v <)"
        self.start = (self.pos, self.facing)
        self.rooms = dict(cfg.get("rooms", {}))
        self.forbidden = set(cfg.get("forbidden", []))   # 禁區清單（記憶的一部分）
        self.need_home = cfg.get("need_home", False)
        self.total_dirt = len(self.dirt)
        self.cleaned = set()          # 清過的格子（畫面用）
        self.n_cleaned = 0            # 清掉的坨數（灰塵可能會重新出現，所以分開算）
        self.queue = deque()
        self.violations = 0
        self.steps = 0
        self.battery_max = float(cfg.get("battery", 100))
        self.battery = self.battery_max
        self._low_warned = False
        self.cleared = False
        self.failed = None            # 失敗原因（字串）；None = 還沒失敗

    # ---------- 狀態 ----------
    @property
    def over(self):
        return self.cleared or self.failed is not None

    @property
    def battery_pct(self):
        return 100.0 * self.battery / self.battery_max if self.battery_max else 0.0

    def fail(self, reason, msg):
        """讓這一關失敗（只會觸發一次）。"""
        if self.over:
            return []
        self.failed = reason
        self.queue.clear()
        return [E("level_fail", msg, reason=reason)]

    # ---------- 查詢 ----------
    def in_bounds(self, p):
        return 0 <= p[0] < self.w and 0 <= p[1] < self.h

    def room_of(self, p):
        for name, (x0, y0, x1, y1) in self.rooms.items():
            if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                return name
        return "客廳"

    def room_names(self):
        return ["客廳"] + [r for r in self.rooms if r != "客廳"]

    def in_forbidden(self, p):
        return self.room_of(p) in self.forbidden

    def is_blocked(self, p):
        return (not self.in_bounds(p)) or p in self.walls or self.objects.get(p) in BLOCKING_OBJECTS

    def what_at(self, p):
        if not self.in_bounds(p) or p in self.walls:
            return "牆壁"
        return OBJECT_NAMES.get(self.objects.get(p), "地板")

    def front(self, pos=None, facing=None):
        pos = self.pos if pos is None else pos
        dx, dy = DIRS[self.facing if facing is None else facing]
        return (pos[0] + dx, pos[1] + dy)

    def floor_tiles(self):
        return [(x, y) for y in range(self.h) for x in range(self.w) if (x, y) not in self.walls]

    def random_free_tile(self, rng=None, min_dist=0, avoid_forbidden=True, exclude=()):
        """隨機挑一格「空地」（沒有物件、灰塵、機器人、充電座）。找不到回傳 None。"""
        rng = rng or self.rng
        cands = [p for p in self.floor_tiles()
                 if p not in self.objects and p not in self.dirt and p not in (self.pos, self.home)
                 and p not in exclude and not (avoid_forbidden and self.in_forbidden(p))
                 and abs(p[0] - self.pos[0]) + abs(p[1] - self.pos[1]) >= min_dist]
        return rng.choice(cands) if cands else None

    def add_dirt(self, p):
        if p in self.dirt or p in self.walls:
            return False
        self.dirt.add(p)
        self.total_dirt += 1
        return True

    def pets(self, kind=None):
        return [p for p, o in self.objects.items() if (o == kind if kind else o in ("cat", "dog"))]

    # ---------- 動作佇列 ----------
    def set_plan(self, actions):
        """把驗證過的動作清單展開成微步驟（取代尚未執行完的舊計畫）。"""
        self.queue.clear()
        for a in actions:
            op = a["op"]
            if op == "forward":
                self.queue.extend([("move",)] * a["n"])
            elif op == "turn_left":
                self.queue.append(("turn", -1))
            elif op == "turn_right":
                self.queue.append(("turn", 1))
            elif op == "suck":
                self.queue.append(("suck",))
            elif op == "return_home":
                self.queue.append(("home",))
            elif op == "stop":
                self.queue.clear()

    def step(self):
        """執行一個微步驟，回傳事件清單。"""
        if self.over:
            self.queue.clear()
            return []
        if not self.queue:
            return []
        kind, *arg = self.queue.popleft()
        self.steps += 1
        events = []
        if kind == "turn":
            self.facing = (self.facing + arg[0]) % 4
            self.battery -= BATTERY_COST["turn"]
        elif kind == "move":
            events += self._move()
        elif kind == "suck":
            self.battery -= BATTERY_COST["suck"]
            events += self._suck()
        elif kind == "home":
            events += self._plan_home()
        events += self._battery_check()
        if not self.failed and not self.dirt and (not self.need_home or self.pos == self.home):
            self.cleared = True
            self.queue.clear()
            events.append(E("level_clear", "🎉 過關！"))
        return events

    # ---------- 微步驟的實作 ----------
    def _move(self):
        nxt = self.front()
        if self.is_blocked(nxt):
            self.queue.clear()   # 途中碰撞 → 中斷整串動作
            what = self.what_at(nxt)
            return [E("collision", f"撞到{what}了，動作中斷！", target=what)]
        self.battery -= BATTERY_COST["move"]
        prev, self.pos = self.pos, nxt
        return self._enter(nxt, prev)

    def _enter(self, p, prev, depth=0):
        """機器人進到格子 p 時發生的事。"""
        events = []
        if self.in_forbidden(p) and not self.in_forbidden(prev):
            self.violations += 1
            events.append(E("entered_forbidden", f"闖進了禁區「{self.room_of(p)}」！"))
        obj = self.objects.get(p)
        if obj == "lego":
            del self.objects[p]
            self.queue.clear()
            self.facing = (self.facing + self.rng.choice([-1, 1])) % 4
            events.append(E("lego", "踩到樂高！痛到原地亂轉，動作中斷。"))
        elif obj == "cable":
            del self.objects[p]
            self.queue.clear()
            events.append(E("tangled", "被充電線纏住了，動作中斷！（線被拖走了）"))
        elif obj == "poop":
            del self.objects[p]
            self.queue.clear()
            around = [n for n in ((p[0] + dx, p[1] + dy) for dx, dy in DIRS)
                      if self.in_bounds(n) and n not in self.walls and n not in self.objects and n != self.home]
            self.rng.shuffle(around)
            added = sum(self.add_dirt(s) for s in [p] + around[:3])
            events.append(E("smeared", f"💩 輾過狗便便！抹得到處都是（多了 {added} 坨髒污），動作中斷。"))
        elif obj == "puddle" and depth < 6:
            slide = self.front()
            if self.is_blocked(slide):
                events.append(E("slip", f"踩到水漬腳底一滑，差點撞上{self.what_at(slide)}！"))
            else:
                self.pos = slide
                events.append(E("slip", "踩到水漬，滑了一格！"))
                events += self._enter(slide, p, depth + 1)
        if p == self.home:
            events.append(E("docked", "回到充電座了。"))
            events += self._charge()
        return events

    def _charge(self):
        if self.battery < self.battery_max - 0.5:
            self.battery = self.battery_max
            self._low_warned = False
            return [E("charged", "🔋 充飽電了！")]
        return []

    def _battery_check(self):
        if self.battery <= 0:
            self.battery = 0.0
            return [E("out_of_battery", "🪫 電量歸零……笨笨倒在地上不動了。")] + \
                self.fail("out_of_battery", "電量歸零，這關失敗了。")
        if not self._low_warned and self.battery_pct < LOW_BATTERY_RATIO * 100:
            self._low_warned = True
            return [E("low_battery", f"⚠️ 電量剩 {self.battery_pct:.0f}%，快回充電座！")]
        return []

    def _suck(self):
        p = self.pos
        if p in self.dirt:
            self.dirt.remove(p)
            self.cleaned.add(p)
            self.n_cleaned += 1
            return [E("cleaned", f"吸乾淨了！（剩 {len(self.dirt)} 坨）")]
        here = self.objects.get(p)
        if here == "sock":
            del self.objects[p]
            self.queue.clear()
            return [E("jammed", "把襪子吸進去了，刷子卡住！動作中斷。")]
        if here == "puddle":
            del self.objects[p]
            self.queue.clear()
            self.battery -= 10
            return [E("suck_water", "吸到水了，滋滋冒煙！電量 −10，動作中斷。")]
        front = self.front()
        pet = self.objects.get(front)
        if pet == "cat":
            spot = self.random_free_tile(min_dist=3)
            if spot:
                del self.objects[front]
                self.objects[spot] = "cat"
            self.queue.clear()
            return [E("sucked_cat", "吸到貓尾巴！貓尖叫著跑走了……")]
        if pet == "dog":
            self.queue.clear()
            self.facing = (self.facing + 2) % 4
            return [E("sucked_dog", "吸到狗耳朵！狗狗狂吠，笨笨嚇得轉身就跑。")]
        return [E("suck_empty", "這格本來就很乾淨，空吸了一下。")]

    def _plan_home(self):
        path = self.find_path(self.pos, self.home)
        if path is None:
            return [E("no_path", "找不到回充電座的路……")]
        if len(path) == 1:
            return [E("docked", "已經在充電座上了。")] + self._charge()
        micro, f = [], self.facing
        for a, b in zip(path, path[1:]):
            d = DIRS.index((b[0] - a[0], b[1] - a[1]))
            micro += {0: [], 1: [("turn", 1)], 2: [("turn", 1), ("turn", 1)], 3: [("turn", -1)]}[(d - f) % 4]
            micro.append(("move",))
            f = d
        self.queue.extendleft(reversed(micro))
        return [E("navigating", f"自動導航回充電座（{len(path) - 1} 格）。")]

    def find_path(self, start, goal, careful=True):
        """BFS：先試著避開禁區與危險物，找不到再放寬。"""
        def bfs(avoid):
            prev, q = {start: None}, deque([start])
            while q:
                p = q.popleft()
                if p == goal:
                    break
                for dx, dy in DIRS:
                    n = (p[0] + dx, p[1] + dy)
                    if n in prev or self.is_blocked(n) or (n != goal and avoid(n)):
                        continue
                    prev[n] = p
                    q.append(n)
            if goal not in prev:
                return None
            path = [goal]
            while prev[path[-1]] is not None:
                path.append(prev[path[-1]])
            return path[::-1]

        cautious = lambda n: self.in_forbidden(n) or self.objects.get(n) in AVOID_OBJECTS
        if careful:
            return bfs(cautious) or bfs(lambda n: False)
        return bfs(lambda n: False)


def run_to_end(game, max_steps=400):
    """一次把佇列跑完（不需要動畫時使用）。"""
    events = []
    for _ in range(max_steps):
        if not game.queue:
            break
        events += game.step()
    return events


def simulate(game, actions):
    """在複製的世界裡試跑動作，不影響原本的遊戲（評估用）。"""
    g = copy.deepcopy(game)
    g.set_plan(actions)
    return g, run_to_end(g)


def check_level(level_id):
    """檢查一個關卡：灰塵與充電座都走得到（不經過禁區）。回傳問題清單，空的代表 OK。"""
    g = Game(level_id)
    problems = []
    for target in sorted(g.dirt) + [g.home]:
        path = g.find_path(g.pos, target)
        if path is None:
            problems.append(f"走不到 {target}")
        elif any(g.in_forbidden(p) for p in path) and not g.in_forbidden(target):
            # 只有在「必須穿過禁區」時才算問題
            g2 = copy.deepcopy(g)
            g2.objects = {p: o for p, o in g2.objects.items() if o in BLOCKING_OBJECTS}
            if any(g2.in_forbidden(p) for p in g2.find_path(g2.pos, target)):
                problems.append(f"{target} 必須穿過禁區才到得了")
        if g.in_forbidden(target) and target != g.home:
            problems.append(f"灰塵 {target} 在預設禁區裡")
    return problems
