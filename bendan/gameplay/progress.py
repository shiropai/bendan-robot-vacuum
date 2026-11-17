"""存檔：每關最佳星數／分數、已解鎖成就、累積事件數。存在 `saves/progress.json`。

關卡依序解鎖：第 0、1 關一開始就能玩，通關第 n 關才能玩第 n+1 關；「今日挑戰」隨時可以玩。
"""
import json
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path

from .. import config
from ..world.levels import CAMPAIGN


class Progress:
    def __init__(self, path=None, unlock_all=False):
        self.path = Path(path) if path else config.SAVE_DIR / "progress.json"
        self.unlock_all = unlock_all
        self._lock = threading.Lock()
        self.data = {"levels": {}, "achievements": {}, "totals": {}}
        self.load()

    # ---------- 讀寫 ----------
    def load(self):
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self.data.update({k: loaded.get(k, v) for k, v in self.data.items()})
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self):
        self.data = {"levels": {}, "achievements": {}, "totals": {}}
        self.save()

    # ---------- 查詢 ----------
    def level(self, level_id):
        return self.data["levels"].get(str(level_id), {})

    def stars(self, level_id):
        return self.level(level_id).get("stars", 0)

    def is_unlocked(self, level_id):
        if self.unlock_all or not isinstance(level_id, int) or level_id <= 1:
            return True
        prev = CAMPAIGN[CAMPAIGN.index(level_id) - 1] if level_id in CAMPAIGN else level_id - 1
        return self.level(prev).get("clears", 0) > 0

    @property
    def totals(self):
        return Counter(self.data["totals"])

    @property
    def unlocked_achievements(self):
        return set(self.data["achievements"])

    @property
    def total_stars(self):
        return sum(v.get("stars", 0) for k, v in self.data["levels"].items() if k.isdigit())

    # ---------- 更新 ----------
    def record(self, result, event_counts=(), new_achievements=()):
        key = str(result["level"])
        entry = self.data["levels"].setdefault(key, {"stars": 0, "best_score": 0, "clears": 0, "plays": 0})
        entry["plays"] += 1
        if result["cleared"]:
            entry["clears"] += 1
            entry["stars"] = max(entry["stars"], result["stars"])
            entry["best_score"] = max(entry["best_score"], result["score"])
            if entry.get("best_commands") is None or result["n_commands"] < entry["best_commands"]:
                entry["best_commands"] = result["n_commands"]
        totals = Counter(self.data["totals"])
        totals.update(dict(event_counts))
        self.data["totals"] = dict(totals)
        now = datetime.now().isoformat(timespec="seconds")
        for a in new_achievements:
            self.data["achievements"].setdefault(a["id"], now)
        self.save()
