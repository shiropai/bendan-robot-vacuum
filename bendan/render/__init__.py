"""畫面：等角 2.5D（matplotlib）、HUD（HTML）、純文字／emoji 地圖。

沒有 matplotlib 的 Kernel（例如課程的「Python (Lab 1)」）會自動改用 emoji 地圖，遊戲照樣能玩。
"""
from .ascii import map_html, render_ascii
from .hud import EVENT_ICON, achievements_html, event_line, hud_html, levels_html, meters_html, result_html

try:
    from .iso import CJK_FONT, FONT, L, render_png, show
    HAS_MPL = True
except ImportError:          # 沒有 matplotlib
    HAS_MPL = False
    CJK_FONT, FONT, render_png = None, "sans-serif", None

    def L(zh, en):
        return zh

    def show(game, **kw):
        from IPython.display import HTML, display
        display(HTML(map_html(game)))

__all__ = ["CJK_FONT", "EVENT_ICON", "FONT", "HAS_MPL", "L", "achievements_html", "event_line", "hud_html",
           "levels_html", "map_html", "meters_html", "render_ascii", "render_png", "result_html", "show"]
