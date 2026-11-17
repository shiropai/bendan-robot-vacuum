"""計分、連擊與星級評價。

- 每吸掉一坨灰塵 +100；**連擊**（中間沒出包）每多一段再 +50
- 出包（碰撞、踩樂高……）會中斷連擊並扣分；闖禁區、輾便便扣更多
- 過關獎勵：基本分 + 剩餘電量 + 低於標準指令數（par）的獎勵 + 笨笨心情好的獎勵

星級：⭐ 過關；⭐⭐ 指令數 ≤ par；⭐⭐⭐ 再加上零違規且主人血壓沒超過 60。
"""
from collections import Counter

from ..world.constants import INTERRUPT_EVENTS

PENALTY = {"entered_forbidden": -100, "smeared": -80, "sucked_cat": -50, "sucked_dog": -40}
DEFAULT_PENALTY = -30


class Scoreboard:
    def __init__(self):
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.breakdown = Counter()

    def _add(self, key, pts):
        self.score += pts
        self.breakdown[key] += pts

    def on_events(self, events):
        out = []
        for e in events:
            t = e["type"]
            if t == "cleaned":
                self.combo += 1
                self.best_combo = max(self.best_combo, self.combo)
                self._add("清掃", 100)
                if self.combo >= 2:
                    bonus = 50 * (self.combo - 1)
                    self._add("連擊", bonus)
                    out.append({"type": "combo", "msg": f"🔥 連擊 x{self.combo}！+{100 + bonus}", "combo": self.combo})
            elif t in INTERRUPT_EVENTS or t in PENALTY:
                if self.combo >= 2:
                    out.append({"type": "combo_break", "msg": f"連擊中斷（最高 x{self.combo}）"})
                self.combo = 0
                self._add("出包", PENALTY.get(t, DEFAULT_PENALTY))
        return out

    def finalize(self, game, n_commands, bp, mood):
        """關卡結束時的結算。回傳 dict（星級、分數、明細）。"""
        par = game.cfg.get("par")
        cleared = game.cleared
        if cleared:
            self._add("過關", 300)
            self._add("剩餘電量", int(game.battery_pct * 2))
            if par and n_commands < par:
                self._add("指令精簡", 40 * (par - n_commands))
            if mood.name == "開心":
                self._add("笨笨很開心", 100)
        stars = 0
        if cleared:
            stars = 1
            if par is None or n_commands <= par:
                stars = 2
                if game.violations == 0 and bp.peak < 60:
                    stars = 3
        return {
            "level": game.level_id, "level_name": game.cfg["name"], "cleared": cleared, "failed": game.failed,
            "stars": stars, "score": max(self.score, 0), "breakdown": dict(self.breakdown),
            "n_commands": n_commands, "par": par, "violations": game.violations, "best_combo": self.best_combo,
            "bp_peak_mmhg": int(round(115 + bp.peak * 0.85)), "mood_end": mood.name, "battery_pct": game.battery_pct,
            "steps": game.steps,
        }


def stars_text(n, total=3):
    return "⭐" * n + "☆" * (total - n)
