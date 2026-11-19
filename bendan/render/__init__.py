"""畫面：3D 遊戲畫面的世界狀態（scene.py → 前端 Three.js）、俯視 SVG 地圖（文字模式、說明圖）、HUD（HTML）、純文字地圖。

v8：2.5D 等角視角（SVG 與 matplotlib 版）全部移除，遊戲視窗只有 3D。俯視 SVG 不需要 matplotlib，任何 Kernel 都能用。
"""
from .ascii import map_html, render_ascii
from .board import facing_text, render_svg
from .hud import (EVENT_ICON, achievements_html, bubble_html, difficulty_html, event_line, history_html, hud_html, levels_html,
                  meters_html, modifiers_html, result_html, side_html)

try:
    from .fonts import CJK_FONT, FONT, L        # 評估圖表用
    HAS_MPL = True
except ImportError:          # 沒有 matplotlib
    HAS_MPL = False
    CJK_FONT, FONT = None, "sans-serif"

    def L(zh, en):
        return zh


def show(game, view="top", **kw):
    """在 Notebook 裡畫出目前的世界（俯視 SVG）。"""
    from IPython.display import HTML, display
    kw.pop("frame", None)
    display(HTML(render_svg(game, view=view, **kw)))


__all__ = ["CJK_FONT", "EVENT_ICON", "FONT", "HAS_MPL", "L", "achievements_html", "bubble_html", "difficulty_html",
           "event_line", "facing_text", "history_html", "hud_html", "levels_html", "map_html", "meters_html",
           "modifiers_html", "render_ascii", "render_svg", "result_html", "show", "side_html"]
