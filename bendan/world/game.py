"""遊戲世界：地圖、機器人、障礙物、電量、動作佇列執行器與事件系統。完全不依賴 LLM。

- `set_plan(actions)`：把驗證過的動作展開成「微步驟」放進佇列（新指令會**取代**還沒做完的舊計畫）。
- `step()`：執行一個微步驟（走一格／轉一次／吸一次），回傳這一步發生的**事件**。
- `return_home` 用 BFS 找路，會盡量避開禁區與危險物。
- 進階關卡：`step_limit`（步數上限 = 時間限制）、`dark`（停電：只看得到笨笨附近、走過的地方才會亮）。
- v6 連續移動：`drive`＝一直往前開，直到「停」、撞到東西或被事件打斷（佇列裡的 ("drive",) 不會被消耗）；
  `vacuum_on/off`＝吸塵模式，開著的時候走過的格子會順便吸（每格多耗一點電，吸到襪子、水漬一樣出事）。
- v8 受損：撞到牆／家具／寵物、吸到不該吸的（襪子、水、樂高、電線、便便）、掉進地洞 → `damage` +1；
  第一次冒煙，第二次爆炸（這關失敗）。撿到維修包可以修好一次。家具（地圖 'F'）跟牆一樣擋路，但有名字。
- v8 畫面特效：`fx` 記錄最近發生的「要播動畫的事」（撞擊、冒煙、爆炸、掉洞……），3D 畫面看編號播一次。
"""
import copy
import heapq
import itertools
import random
from collections import deque

from .constants import (AVOID_OBJECTS, BATTERY_COST, BLOCKING_OBJECTS, DIRS, LOW_BATTERY_RATIO, MAX_DAMAGE,
                        OBJECT_CHARS, OBJECT_NAMES, START_FACING, SUCK_BAD, E)
from .levels import get_level

_GAME_IDS = itertools.count(1)


class Game:
    def __init__(self, level_id=1, seed=None, scale=None):
        self.rng = random.Random(seed)
        self.scale = scale
        self.load(level_id)

    def load(self, level_id):
        cfg = get_level(level_id, getattr(self, "scale", None))
        self.uid = next(_GAME_IDS)          # 每次載入（換關、重來）都不一樣：3D 畫面用來判斷要不要把笨笨組回去
        rows = cfg["map"]
        self.level_id, self.cfg = level_id, cfg
        self.h, self.w = len(rows), len(rows[0])
        assert all(len(r) == self.w for r in rows), "地圖每一列長度必須相同"
        self.walls, self.objects, self.dirt = set(), {}, set()
        self.furniture = {(f["x"], f["y"]): f for f in cfg.get("furniture", [])}
        self.home = self.pos = None
        self.facing = 1
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                p = (x, y)
                if ch in "#F":
                    self.walls.add(p)
                    if ch == "F" and p not in self.furniture:
                        self.furniture[p] = {"x": x, "y": y, "key": "cabinet", "name": "櫃子", "back": 0, "span": 1,
                                             "part": 0, "sx": 1, "sy": 0}
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
        self.vacuum = False           # 吸塵模式（v6）：開著的時候走過的格子會順便吸
        self.violations = 0
        self.steps = 0
        self.battery_max = float(cfg.get("battery", 100))
        self.battery = self.battery_max
        self._low_warned = False
        self.cleared = False
        self.failed = None            # 失敗原因（字串）；None = 還沒失敗
        self.step_limit = cfg.get("step_limit")      # 走超過這麼多步 = 時間到
        self.dark = cfg.get("dark")                  # 停電關：燈光半徑（格）；None = 全亮
        self.seen = set()                            # 停電關：看過的格子（畫面只顯示這些）
        self.fragile = cfg.get("fragile", True)      # v8：會不會受損（評估場景關掉）
        self.damage = 0                              # 0 正常、1 冒煙、2 爆炸
        self.rider = None                            # v8：背上載著的貓 {"left": 還要載幾步}
        self.fx, self.fx_n = [], 0                   # v8：畫面特效（[編號, 種類, x, y, 朝向, 附加]）
        self.reveal()

    # ---------- 狀態 ----------
    @property
    def over(self):
        return self.cleared or self.failed is not None

    @property
    def driving(self):
        """正在「一直往前開」（等主人喊停）。"""
        return bool(self.queue) and self.queue[0][0] == "drive"

    @property
    def steps_left(self):
        return None if not self.step_limit else max(self.step_limit - self.steps, 0)

    def reveal(self):
        """停電關：把笨笨附近（曼哈頓距離 ≤ dark）的格子加進「看過」。"""
        if not self.dark:
            return
        r = int(self.dark)
        x0, y0 = self.pos
        for y in range(y0 - r, y0 + r + 1):
            for x in range(x0 - r, x0 + r + 1):
                if abs(x - x0) + abs(y - y0) <= r and self.in_bounds((x, y)):
                    self.seen.add((x, y))

    def visible(self, p):
        """畫面上看不看得到這一格（停電關才會有看不到的）。"""
        return not self.dark or p in self.seen

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
        if p in self.furniture:
            return self.furniture[p]["name"]
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
            elif op == "drive":
                self.queue.append(("drive",))
            elif op in ("vacuum_on", "vacuum_off"):
                self.queue.append(("vac", op == "vacuum_on"))
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
        if self.queue[0][0] == "vac":           # 開關吸塵不花時間
            on = self.queue.popleft()[1]
            if on == self.vacuum:
                return []
            self.vacuum = on
            return [E("vacuum", "🌀 吸塵模式開啟：走過的地方會順便吸。" if on else "吸塵模式關閉。", on=on)]
        kind, *arg = self.queue[0] if self.queue[0][0] == "drive" else self.queue.popleft()
        self.steps += 1
        events = []
        if kind == "drive":
            events += self._move()
        elif kind == "turn":
            self.facing = (self.facing + arg[0]) % 4
            self.battery -= BATTERY_COST["turn"]
        elif kind == "move":
            events += self._move()
        elif kind == "suck":
            self.battery -= BATTERY_COST["suck"]
            events += self._suck()
        elif kind == "home":
            events += self._plan_home()
        if self.rider and not self.over:
            events += self._rider_tick()
        events += self._battery_check()
        self.reveal()
        if not self.failed and not self.dirt and (not self.need_home or self.pos == self.home):
            self.cleared = True
            self.queue.clear()
            self._fx("clear")
            events.append(E("level_clear", "🎉 過關！"))
        elif self.step_limit and self.steps >= self.step_limit:
            events += self.fail("time_up", self.cfg.get("fail_text", "⏱️ 時間到！地板還沒掃完……"))
        return events

    # ---------- 微步驟的實作 ----------
    def _move(self):
        nxt = self.front()
        if self.is_blocked(nxt):
            self.queue.clear()   # 途中碰撞 → 中斷整串動作
            what = self.what_at(nxt)
            self._fx("bump", what=what)
            events = [E("collision", f"撞到{what}了，動作中斷！", target=what)]
            if self.rider:
                events += self._rider_off("被撞得嚇一跳")
            return events + self._hurt(f"撞到{what}")
        self.battery -= BATTERY_COST["move"] + (BATTERY_COST["vacuum"] if self.vacuum else 0.0)
        prev, self.pos = self.pos, nxt
        here = self.objects.get(nxt)
        if self.vacuum and here in SUCK_BAD | {"roach"}:
            # 吸塵模式開著直接開過去 → 東西被吸進去（不是踩過去）
            events = self._enter(nxt, prev, effects=False)
            if here != "roach":
                self.vacuum = False
            return events + self._suck()
        events = self._enter(nxt, prev)
        if self.vacuum and not self.over:
            events += self._vacuum_here()
        return events

    def _vacuum_here(self):
        """吸塵模式：走到哪吸到哪（不該吸的東西在 _move 就處理了）。"""
        if self.pos in self.dirt:
            return self._suck()
        return []

    # ---------- v8：受損、特效、搭便車的貓 ----------
    def _fx(self, kind, **extra):
        self.fx_n += 1
        self.fx.append([self.fx_n, kind, self.pos[0], self.pos[1], self.facing, extra])
        del self.fx[:-10]

    def _hurt(self, cause):
        """受損一次：第一次冒煙，第二次爆炸（這關失敗）。"""
        if not self.fragile or self.over:
            return []
        self.damage = min(self.damage + 1, MAX_DAMAGE)
        self.queue.clear()
        if self.damage >= MAX_DAMAGE:
            self.vacuum = False
            self._fx("boom", cause=cause)
            return ([E("exploded", f"💥 轟！{cause}，笨笨整台炸開了……", cause=cause)]
                    + self.fail("exploded", "💥 笨笨爆炸了，這關失敗。"))
        self._fx("smoke", cause=cause)
        return [E("damaged", f"💨 {cause}，笨笨開始冒煙了！再出一次事就會爆炸！", cause=cause)]

    def repair(self):
        if self.damage <= 0:
            return False
        self.damage -= 1
        self._fx("repair")
        return True

    def free_neighbors(self, p):
        return [n for n in ((p[0] + dx, p[1] + dy) for dx, dy in DIRS)
                if self.in_bounds(n) and n not in self.walls and n not in self.objects and n != self.pos
                and n != self.home]

    def ride(self, cat_pos, steps):
        """貓跳上笨笨的背（從地圖上拿掉）。"""
        del self.objects[cat_pos]
        self.rider = {"left": steps}
        self._fx("ride_on", frm=list(cat_pos))

    def _rider_off(self, why="跳下來了"):
        spots = self.free_neighbors(self.pos) or [n for n in self.free_neighbors(self.pos)]
        self.rider = None
        if not spots:
            spot = self.random_free_tile(min_dist=1)
            if spot is None:
                return []
        else:
            spot = self.rng.choice(spots)
        self.objects[spot] = "cat"
        self._fx("ride_off", to=list(spot))
        return [E("cat_off", f"🐱 貓咪{why}，從笨笨背上跳下去了。")]

    def _rider_tick(self):
        self.rider["left"] -= 1
        return self._rider_off("坐膩了") if self.rider["left"] <= 0 else []

    def _enter(self, p, prev, depth=0, effects=True):
        """機器人進到格子 p 時發生的事。"""
        events = []
        if self.in_forbidden(p) and not self.in_forbidden(prev):
            self.violations += 1
            events.append(E("entered_forbidden", f"闖進了禁區「{self.room_of(p)}」！"))
        obj = self.objects.get(p) if effects else None
        if obj == "hole":
            return events + self._fall(p, prev)
        if obj == "banana" and depth < 6:
            del self.objects[p]
            self.queue.clear()
            self.facing = self.rng.randrange(4)
            self._fx("spin")
            events.append(E("banana", "🍌 踩到香蕉皮！轉了好幾圈，動作中斷。"))
            slide = self.front()
            if not self.is_blocked(slide):
                self.pos = slide
                events += self._enter(slide, p, depth + 1)
            return events
        if obj == "toolbox":
            del self.objects[p]
            if self.repair():
                events.append(E("repaired", "🔧 撿到維修包！敲敲打打，修好了，不冒煙了。"))
            else:
                self._fx("repair")
                events.append(E("toolbox", "🔧 撿到維修包！先收著，下次壞掉時用得到……其實已經自動拿去保養了。"))
        elif obj == "roach":
            spots = self.free_neighbors(p)
            del self.objects[p]
            if spots:
                self.objects[self.rng.choice(spots)] = "roach"
                events.append(E("roach_moved", "蟑螂被嚇得跑開了！"))
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

    def _fall(self, p, prev):
        """v8：掉進地洞 → 受損一次；沒炸掉的話主人把它撈起來放回充電座（沒有充電座就放回起點）。"""
        self.queue.clear()
        self.vacuum = False
        events = []
        if self.rider:                    # 貓在掉下去之前跳開
            self.rider = None
            if prev not in self.objects and prev != self.home:
                self.objects[prev] = "cat"
            events.append(E("cat_off", "🐱 貓咪在最後一刻跳開了！"))
        self._fx("fall")
        events.append(E("fell", "🕳️ 掉進地洞了！咚咚咚——", at=p))
        events += self._hurt("摔進地洞")
        if not self.over:
            back, f = (self.home, self.facing) if self.home else self.start
            self.pos, self.facing = back, f
            self._fx("rescue")
            events.append(E("rescued", "主人把笨笨從洞裡撈出來，放回" + ("充電座。" if self.home else "起點。")))
        return events

    def _charge(self):
        if self.battery < self.battery_max - 0.5:
            self.battery = self.battery_max
            self._low_warned = False
            return [E("charged", "🔋 充飽電了！")]
        return []

    @property
    def low_battery(self):
        """已經發出低電量警告（充電後會重置）。"""
        return self._low_warned

    def home_distance(self):
        path = self.find_path(self.pos, self.home) if self.home else None
        return len(path) - 1 if path else None

    def _battery_check(self):
        if self.battery <= 0:
            self.battery = 0.0
            return [E("out_of_battery", "🪫 電量歸零……笨笨倒在地上不動了。")] + \
                self.fail("out_of_battery", "電量歸零，這關失敗了。")
        if self._low_warned:
            return []
        pct = self.battery_pct
        if pct < LOW_BATTERY_RATIO * 100:
            self._low_warned = True
            return [E("low_battery", f"⚠️ 電量剩 {pct:.0f}%，快回充電座！")]
        if pct < 60:
            # 實測第 5 關（電池 60）：等到 25% 才警告，離充電座 17 格的角落根本走不回去 → 改成「只夠走回家」就先警告
            d = self.home_distance()
            if d is not None and self.battery <= d * BATTERY_COST["move"] + 6:
                self._low_warned = True
                return [E("low_battery", f"⚠️ 電量剩 {pct:.0f}%，只夠走回充電座了（離充電座 {d} 格）！")]
        return []

    def _suck(self):
        p = self.pos
        if p in self.dirt:
            self.dirt.remove(p)
            self.cleaned.add(p)
            self.n_cleaned += 1
            events = [E("cleaned", f"吸乾淨了！（剩 {len(self.dirt)} 坨）")]
            # v8 彩蛋：家具旁邊的灰塵裡偶爾藏著零錢（叮！不會壞，還加分）
            near = [self.furniture[n]["name"] for n in ((p[0] + dx, p[1] + dy) for dx, dy in DIRS) if n in self.furniture]
            if near and self.rng.random() < 0.25:
                self._fx("coin")
                events.append(E("coin", f"💰 叮！在{near[0]}底下吸到一枚 10 元硬幣！"))
            return events
        here = self.objects.get(p)
        if here == "sock":
            del self.objects[p]
            self.queue.clear()
            return [E("jammed", "把襪子吸進去了，刷子卡住！動作中斷。")] + self._hurt("吸到襪子")
        if here == "puddle":
            del self.objects[p]
            self.queue.clear()
            self.battery -= 10
            return [E("suck_water", "吸到水了，滋滋短路！電量 −10，動作中斷。")] + self._hurt("吸到水")
        if here in ("lego", "cable", "poop"):
            del self.objects[p]
            self.queue.clear()
            msg = {"lego": "把樂高吸進去了，喀啦喀啦卡在吸口！", "cable": "電線捲進滾刷，越捲越緊！",
                   "poop": "把狗便便吸進去了……整台機器都是味道，還抹得到處都是！"}[here]
            events = [E("sucked_bad", msg + "動作中斷。", what=here)]
            if here == "poop":
                for s in [p] + self.free_neighbors(p)[:2]:
                    self.add_dirt(s)
            name = OBJECT_NAMES[here]
            return events + self._hurt(f"吸到{name}")
        front = self.front()
        for spot in (p, front):
            if self.objects.get(spot) == "roach":
                del self.objects[spot]
                self._fx("gulp")
                return [E("caught_roach", "🪳 吸到小強了！主人感動到想哭。")]
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
                    if (n in prev or self.is_blocked(n) or (n != goal and avoid(n))
                            or (n != goal and self.objects.get(n) == "hole")):
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

    def find_route(self, start, facing, goal, avoid_hazards=True, turn_cost=2):
        """「少轉彎」的路線（Dijkstra，狀態＝位置＋朝向；前進成本 1、轉向成本 turn_cost）。

        BFS 的最短路常常走成鋸齒狀，轉成動作清單會超過 12 個（白名單上限）→ 模型照抄就被判無效。
        這裡讓轉彎比較貴，路線就會盡量走直線、動作比較少。一律不進禁區；找不到回傳 None。
        """
        def avoid(n):
            return self.in_forbidden(n) or (avoid_hazards and self.objects.get(n) in AVOID_OBJECTS)

        start_state = (start, facing)
        best, prev, tie = {start_state: 0}, {start_state: None}, 0
        pq = [(0, 0, start, facing)]
        while pq:
            d, _, p, f = heapq.heappop(pq)
            if d > best.get((p, f), float("inf")):
                continue
            if p == goal:
                path, st = [p], (p, f)
                while prev[st] is not None:
                    st = prev[st]
                    if st[0] != path[-1]:
                        path.append(st[0])
                return path[::-1]
            dx, dy = DIRS[f]
            n = (p[0] + dx, p[1] + dy)
            moves = [((p, (f + 1) % 4), turn_cost), ((p, (f - 1) % 4), turn_cost)]
            if not self.is_blocked(n) and (n == goal or (not avoid(n) and self.objects.get(n) != "hole")):
                moves.append(((n, f), 1))
            for state, c in moves:
                if d + c < best.get(state, float("inf")):
                    best[state], prev[state] = d + c, (p, f)
                    tie += 1
                    heapq.heappush(pq, (d + c, tie, state[0], state[1]))
        if avoid_hazards:
            return self.find_route(start, facing, goal, avoid_hazards=False, turn_cost=turn_cost)
        return None


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
