"""畫面：SVG 遊戲畫面（2.5D／俯視，v3 起的主要畫面）、HUD（HTML）、純文字／emoji 地圖、matplotlib PNG（報告用）。

SVG 畫面不需要 matplotlib，任何 Kernel 都能玩；`render_png` 只在有 matplotlib 時可用（評估報告、存圖）。
"""
from .ascii import map_html, render_ascii
from .board import direction_aids, facing_text, render_svg
from .hud import (EVENT_ICON, achievements_html, bubble_html, difficulty_html, event_line, history_html, hud_html, levels_html,
                  meters_html, modifiers_html, result_html, side_html)

try:
    from .iso import CJK_FONT, FONT, L, render_png
    HAS_MPL = True
except ImportError:          # 沒有 matplotlib
    HAS_MPL = False
    CJK_FONT, FONT, render_png = None, "sans-serif", None

    def L(zh, en):
        return zh


def show(game, view="iso", **kw):
    """在 Notebook 裡畫出目前的世界（SVG）。"""
    from IPython.display import HTML, display
    kw.pop("frame", None)
    display(HTML(render_svg(game, view=view, **kw)))


__all__ = ["CJK_FONT", "EVENT_ICON", "FONT", "HAS_MPL", "L", "achievements_html", "bubble_html", "difficulty_html", "direction_aids",
           "event_line", "facing_text", "history_html", "hud_html", "levels_html", "map_html", "meters_html",
           "modifiers_html", "render_ascii", "render_png", "render_svg", "result_html", "show", "side_html"]
