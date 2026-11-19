"""突發事件導演（靈感：《教妹妹開車》路上的突發狀況——行人、其他車輛、意外）。

事件依「機器人走了幾步」觸發，而不是真實時間：LLM 思考時世界是暫停的，
避免「模型想太久 → 被事件連環爆」這種不公平的情況。

關卡設定範例：
    "incidents": [
        {"type": "cat_wander", "every": 5},              # 每 5 步，貓隨機走一格
        {"type": "dog_wander", "every": 4},
        {"type": "spill", "chance": 0.04, "max": 2},     # 每步 4% 機率：小孩打翻果汁 → 多一坨髒污
        {"type": "dog_poop", "chance": 0.05, "max": 2},  # 狗狗在旁邊留下便便
        {"type": "doorbell", "chance": 0.03, "max": 1},  # 門鈴響 → 笨笨分心，動作被打斷
        {"type": "leak", "chance": 0.04, "max": 3},      # 颱風天屋頂漏水 → 多一灘水漬
        # v8
        {"type": "quake", "chance": 0.01, "max": 1},     # 地震：笨笨被晃得轉向、東西掉滿地、地板可能裂出地洞
        {"type": "roach", "chance": 0.02, "max": 1},     # 小強出現：每一步都會亂跑，吸到有獎勵（主人血壓下降）
        {"type": "banana", "chance": 0.03, "max": 1},    # 小孩丟香蕉皮：踩到會轉圈打滑
        {"type": "cat_ride", "chance": 0.08, "max": 1},  # 貓咪在笨笨旁邊時，可能跳上來搭便車
        {"type": "toolbox", "chance": 0.12, "max": 1},   # 笨笨冒煙時，爸爸把維修包忘在地上
        {"type": "popcorn", "chance": 0.02, "max": 1},   # 爆米花打翻：一小堆擠在一起的髒污（連擊機會）
    ]
"""
import random
from collections import Counter

from ..world.constants import DIRS, E

SPILL_TEXT = ["👶 小孩在{room}打翻了果汁！", "🍜 有人在{room}把泡麵湯灑出來了！", "🪴 {room}的盆栽倒了，土撒了一地！",
              "🍪 餅乾屑掉滿{room}的地板！"]


class IncidentDirector:
    def __init__(self, specs=(), rng=None):
        self.specs = [dict(s) for s in specs]
        self.rng = rng or random.Random()
        self.counts = Counter()

    def on_step(self, game):
        """機器人每走一個微步驟呼叫一次，回傳突發事件清單。"""
        events = []
        for s in self.specs:
            t = s["type"]
            if t in ("cat_wander", "dog_wander"):
                if game.steps % max(1, s.get("every", 5)) == 0:
                    events += self._wander(game, "cat" if t == "cat_wander" else "dog")
                continue
            if t == "roach":                     # 小強每一步都會跑（跑離笨笨）
                events += self._roach_run(game)
            if self.counts[t] >= s.get("max", 10 ** 9) or self.rng.random() >= s.get("chance", 0.0):
                continue
            ev = getattr(self, "_" + t)(game)
            if ev:
                self.counts[t] += 1
                events += ev
        return events

    # ---------- 各種事件 ----------
    def _wander(self, game, kind):
        events = []
        robot_front = game.front()
        for p in game.pets(kind):
            options = []
            for dx, dy in DIRS:
                n = (p[0] + dx, p[1] + dy)
                if (game.in_bounds(n) and n not in game.walls and n not in game.objects and n != game.pos
                        and n != game.home and n not in game.dirt):
                    options.append(n)
            if not options or self.rng.random() < 0.3:      # 有時候寵物懶得動
                continue
            n = self.rng.choice(options)
            game.objects[n] = game.objects.pop(p)
            name = "貓" if kind == "cat" else "狗"
            note = "（跑到你正前方了！）" if n == robot_front else ""
            events.append(E("pet_moved", f"{name}換了個位置{note}", pet=kind, to=n))
        return events

    def _spill(self, game):
        p = game.random_free_tile(self.rng, min_dist=2)
        if p is None:
            return []
        game.add_dirt(p)
        msg = self.rng.choice(SPILL_TEXT).format(room=game.room_of(p))
        return [E("spill", msg + f"（多了一坨髒污，現在剩 {len(game.dirt)} 坨）", at=p)]

    def _leak(self, game):
        p = game.random_free_tile(self.rng, min_dist=2)
        if p is None:
            return []
        game.objects[p] = "puddle"
        return [E("leak", f"💧 屋頂漏水了！{game.room_of(p)}多了一灘水，小心滑倒。", at=p)]

    def _dog_poop(self, game):
        dogs = game.pets("dog")
        if not dogs:
            return []
        d = self.rng.choice(dogs)
        spots = [(d[0] + dx, d[1] + dy) for dx, dy in DIRS]
        spots = [p for p in spots if game.in_bounds(p) and p not in game.walls and p not in game.objects
                 and p not in game.dirt and p not in (game.pos, game.home)]
        if not spots:
            return []
        p = self.rng.choice(spots)
        game.objects[p] = "poop"
        return [E("dog_poop", f"🐶 狗狗在{game.room_of(p)}留下了一份「驚喜」……小心別輾過去！", at=p)]

    def _doorbell(self, game):
        if not game.queue:          # 只有在笨笨正在做事時才會被打斷
            return []
        game.queue.clear()
        game.queue.extend([("turn", self.rng.choice([-1, 1])), ("move",)])
        return [E("doorbell", "🔔 叮咚！門鈴響了，笨笨分心衝去看門口，原本的動作被打斷！")]

    # ---------- v8 ----------
    def _quake(self, game):
        """🌏 地震：笨笨被晃得轉向、動作中斷；櫃子上的東西掉下來（多 1～2 坨髒污）；一半機率地板裂出地洞。"""
        game.queue.clear()
        game.facing = (game.facing + self.rng.choice([-1, 1, 2])) % 4
        game._fx("quake")
        added = 0
        for _ in range(self.rng.choice([1, 2])):
            p = game.random_free_tile(self.rng, min_dist=2)
            if p is not None and game.add_dirt(p):
                added += 1
        msg = f"🌏 地震！笨笨被晃得轉了方向，櫃子上的東西掉下來（多了 {added} 坨髒污）"
        if self.rng.random() < 0.5:
            hole = self._safe_hole(game)
            if hole:
                msg += f"，{game.room_of(hole)}的地板裂開一個洞！"
        return [E("quake", msg + "。", at=list(game.pos))]

    def _safe_hole(self, game):
        """找一格挖地洞：不能讓灰塵或充電座變成走不到。"""
        for _ in range(12):
            p = game.random_free_tile(self.rng, min_dist=3)
            if p is None:
                return None
            game.objects[p] = "hole"
            targets = list(game.dirt) + ([game.home] if game.home else [])
            if all(game.find_path(game.pos, t, careful=False) for t in targets):
                return p
            del game.objects[p]
        return None

    def _roach(self, game):
        if game.pets("roach") or any(o == "roach" for o in game.objects.values()):
            return []
        p = game.random_free_tile(self.rng, min_dist=4)
        if p is None:
            return []
        game.objects[p] = "roach"
        return [E("roach", f"🪳 {game.room_of(p)}出現一隻小強！主人尖叫中——快吸掉牠（吸到有獎勵）！", at=p)]

    def _roach_run(self, game):
        events = []
        for p, o in list(game.objects.items()):
            if o != "roach" or self.rng.random() < 0.35:
                continue
            opts = [n for n in game.free_neighbors(p) if n not in game.dirt]
            if not opts:
                continue
            far = max(abs(n[0] - game.pos[0]) + abs(n[1] - game.pos[1]) for n in opts)
            opts = [n for n in opts if abs(n[0] - game.pos[0]) + abs(n[1] - game.pos[1]) >= far - 1]
            n = self.rng.choice(opts)
            game.objects[n] = game.objects.pop(p)
            events.append(E("roach_moved", "小強跑來跑去", to=n))
        return events

    def _popcorn(self, game):
        """🍿 爆米花打翻：一次撒出一小堆（3～4 坨擠在一起）→ 連續吸可以拿連擊獎勵。"""
        p = game.random_free_tile(self.rng, min_dist=3)
        if p is None:
            return []
        spots = [p] + [n for n in ((p[0] + dx, p[1] + dy) for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 0), (0, -1)))
                       if game.in_bounds(n) and n not in game.walls and n not in game.objects and n != game.home
                       and n != game.pos]
        added = sum(game.add_dirt(s) for s in spots[:self.rng.choice([3, 4])])
        return [E("popcorn", f"🍿 有人在{game.room_of(p)}打翻了一整桶爆米花！一口氣多了 {added} 坨（連續吸可以拿連擊！）", at=p)]

    def _banana(self, game):
        p = game.random_free_tile(self.rng, min_dist=3)
        if p is None:
            return []
        game.objects[p] = "banana"
        return [E("banana_drop", f"🍌 小孩在{game.room_of(p)}丟了一塊香蕉皮！踩到會打滑轉圈。", at=p)]

    def _cat_ride(self, game):
        if game.rider or game.over:
            return []
        cats = [n for n in ((game.pos[0] + dx, game.pos[1] + dy) for dx, dy in DIRS) if game.objects.get(n) == "cat"]
        if not cats:
            return []
        game.ride(cats[0], self.rng.randint(8, 16))
        return [E("cat_ride", "🐱 貓咪跳上笨笨的背，搭起便車了！（撞到東西會把牠嚇跑）")]

    def _toolbox(self, game):
        if game.damage <= 0 or "toolbox" in game.objects.values():
            return []
        p = game.random_free_tile(self.rng, min_dist=4)
        if p is None:
            return []
        game.objects[p] = "toolbox"
        return [E("toolbox_drop", f"🔧 爸爸把維修包忘在{game.room_of(p)}的地上了！開過去撿起來就能修好笨笨。", at=p)]
