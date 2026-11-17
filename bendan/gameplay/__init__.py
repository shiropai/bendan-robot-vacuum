"""玩法系統：讓「指揮笨笨」從技術展示變成真正的遊戲。

| 模組 | 玩法 |
|---|---|
| mood | 笨笨的心情：語氣會影響它聽不聽話、會不會頂嘴或拒絕 |
| pressure | 主人血壓計：出包會飆血壓，爆表就失敗 |
| scoring | 分數、連擊、星級評價 |
| incidents | 突發事件：寵物亂跑、打翻果汁、狗便便、門鈴 |
| achievements | 成就 |
| progress | 存檔與關卡解鎖 |
"""
from .achievements import ACHIEVEMENTS, check_achievements
from .incidents import IncidentDirector
from .mood import Mood, Tone, analyze_tone
from .pressure import BloodPressure
from .progress import Progress
from .scoring import Scoreboard, stars_text

__all__ = ["ACHIEVEMENTS", "BloodPressure", "IncidentDirector", "Mood", "Progress", "Scoreboard", "Tone",
           "analyze_tone", "check_achievements", "stars_text"]
