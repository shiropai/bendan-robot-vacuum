"""主人血壓計（靈感：《教妹妹開車》的宣傳詞「挑戰副駕哥哥的血壓極限」）。

每次笨笨出包，主人的血壓就往上飆；清乾淨會稍微降一點。血壓爆表 = 主人氣到昏倒 = 這關失敗。
內部用 0–100 的數值，顯示時換算成 115–200 mmHg 比較有臨場感。
"""

EVENT_BP = {
    "collision": 5, "lego": 9, "tangled": 7, "jammed": 9, "sucked_cat": 14, "sucked_dog": 12,
    "entered_forbidden": 18, "smeared": 25, "slip": 3, "suck_water": 12, "doorbell": 4,
    "out_of_battery": 20, "no_path": 4, "dazed": 6, "refused": 5, "suck_empty": 1, "quirk": 4, "forgot": 3,
    "leak": 2,
    # v8
    "damaged": 10, "exploded": 25, "fell": 10, "banana": 4, "sucked_bad": 6, "quake": 6, "roach": 8,
    "banana_drop": 1, "caught_roach": -15, "popcorn": 3, "coin": -2, "cat_ride": -4, "repaired": -6, "toolbox": -2,
    "cleaned": -4, "charged": -2, "level_clear": -20,
    # v8.1
    "dock_repair": -6,
}

LABELS = [(85, "快爆血管 🤯"), (60, "青筋浮現 😡"), (30, "有點火 😤"), (0, "冷靜 😌")]


class BloodPressure:
    MAX = 100.0

    def __init__(self, value=10):
        self.value = float(value)
        self.peak = self.value

    @property
    def mmhg(self):
        return int(round(115 + self.value * 0.85))

    @property
    def label(self):
        return next(lbl for th, lbl in LABELS if self.value >= th)

    @property
    def maxed(self):
        return self.value >= self.MAX

    def add(self, delta):
        self.value = max(0.0, min(self.MAX, self.value + delta))
        self.peak = max(self.peak, self.value)

    def apply_events(self, events):
        for e in events:
            d = EVENT_BP.get(e["type"])
            if d:
                self.add(d)
