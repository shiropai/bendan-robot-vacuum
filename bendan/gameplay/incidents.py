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
