"""等角 2.5D 畫面（matplotlib 版渲染器）。

等角投影：格子 `(x, y)` → 螢幕 `((x − y)·w/2, −(x + y)·h/2)`，再用「畫家演算法」由後往前畫，牆和障礙物就有立體感。
若伺服器有中文字型會顯示中文標籤，否則自動改用英文（避免出現豆腐字）。
全部用物件導向 API（Figure + FigureCanvasAgg），背景執行緒也能安全呼叫。
"""
import io

from matplotlib import colors as mcolors
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Ellipse, Polygon, Rectangle

from ..world.constants import DIRS


def _pick_cjk_font():
    wanted = ["Noto Sans CJK TC", "Noto Sans TC", "Noto Sans CJK JP", "Noto Sans CJK SC", "PingFang TC",
              "Heiti TC", "Microsoft JhengHei", "Arial Unicode MS", "WenQuanYi Zen Hei", "Droid Sans Fallback"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    return next((n for n in wanted if n in have), None)


CJK_FONT = _pick_cjk_font()
FONT = CJK_FONT or "DejaVu Sans"


def L(zh, en):
    return zh if CJK_FONT else en


ROOM_EN = {"客廳": "Living room", "臥室": "Bedroom", "廚房": "Kitchen", "書房": "Study", "浴室": "Bathroom"}
ROOM_COLORS = {"客廳": "#efe4d0", "臥室": "#e3def2", "廚房": "#d6ebe0", "書房": "#f1e3c8", "浴室": "#d8e8f3"}
OBJ_LABEL = {"cat": ("貓", "CAT"), "dog": ("狗", "DOG"), "lego": ("樂高", "LEGO"), "sock": ("襪子", "SOCK"),
             "cable": ("電線", "CABLE"), "poop": ("便便", "POOP"), "puddle": ("水漬", "WET")}
MOOD_LID = {"開心": "#95d5b2", "普通": "#98c1d9", "不爽": "#f4a261", "鬧彆扭": "#e76f51"}
EMOTION_EN = {"開心": "HAPPY", "普通": "OK", "委屈": "SULKY", "生氣": "ANGRY", "得意": "PROUD", "害怕": "SCARED"}
FAIL_TEXT = {"owner_faint": ("主人氣昏了", "OWNER FAINTED"), "out_of_battery": ("沒電了", "OUT OF BATTERY"),
             "time_up": ("時間到", "TIME UP")}
TW, TH = 1.0, 0.5   # 一格等角菱形的寬、高


def iso(x, y, z=0.0):
    return ((x - y) * TW / 2, -(x + y) * TH / 2 + z)


def _diamond(x, y, inset=0.0, z=0.0):
    a, b, c, d = x + inset, y + inset, x + 1 - inset, y + 1 - inset
    return [iso(a, b, z), iso(c, b, z), iso(c, d, z), iso(a, d, z)]   # 後、右、前、左


def _shade(color, k):
    r, g, b = mcolors.to_rgb(color)
    return (min(r * k, 1), min(g * k, 1), min(b * k, 1))


def _cube(ax, x, y, h, color, inset=0.0):
    back, right, front, left = _diamond(x, y, inset)
    up = lambda p: (p[0], p[1] + h)
    kw = dict(closed=True, ec="#00000040", lw=0.6)
    ax.add_patch(Polygon([left, front, up(front), up(left)], fc=_shade(color, 0.72), **kw))
    ax.add_patch(Polygon([front, right, up(right), up(front)], fc=_shade(color, 0.88), **kw))
    ax.add_patch(Polygon([up(back), up(right), up(front), up(left)], fc=color, **kw))


def _label(ax, x, y, z, text, color="#333"):
    cx, cy = iso(x + 0.5, y + 0.5, z)
    ax.text(cx, cy, text, ha="center", va="bottom", fontsize=7, color=color, fontfamily=FONT, zorder=6)


def _draw_robot(ax, game, thinking=False, frame=0, mood=None, emotion=None):
    x, y = game.pos
    cx, cy = iso(x + 0.5, y + 0.5)
    w, hh, body = 0.5, 0.25, 0.16
    lid = MOOD_LID.get(mood, "#98c1d9")
    ax.add_patch(Ellipse((cx, cy), w, hh, fc="#22324a"))
    ax.add_patch(Rectangle((cx - w / 2, cy), w, body, fc="#3d5a80", ec="none"))
    ax.add_patch(Ellipse((cx, cy + body), w, hh, fc=lid, ec="#3d5a80", lw=1))
    dx, dy = DIRS[game.facing]
    tip = iso(x + 0.5 + dx * 0.32, y + 0.5 + dy * 0.32, body)
    ax.annotate("", xy=tip, xytext=(cx, cy + body),
                arrowprops=dict(arrowstyle="-|>", color="#ffb703", lw=2.2), zorder=7)
    if game.battery_pct < 25 and frame % 2 == 0:            # 低電量：閃紅燈
        ax.add_patch(Ellipse((cx + 0.15, cy + body + 0.04), 0.07, 0.05, fc="#ff1744", zorder=8))
    if thinking:
        ax.text(cx, cy + 0.62, "." * (frame % 3 + 1) + " ?", ha="center", fontsize=11, zorder=10,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#555"))
    elif emotion and emotion != "普通":
        ax.text(cx, cy + 0.55, L(emotion, EMOTION_EN.get(emotion, "")), ha="center", fontsize=8, zorder=10,
                fontfamily=FONT, bbox=dict(boxstyle="round,pad=0.25", fc="#fffbe6", ec="#c9a227"))


def _draw_object(ax, x, y, obj):
    if obj == "cat":
        _cube(ax, x, y, 0.32, "#f4a259", inset=0.22)
        _label(ax, x, y, 0.36, L(*OBJ_LABEL["cat"]))
    elif obj == "dog":
        _cube(ax, x, y, 0.36, "#9c6644", inset=0.18)
        _label(ax, x, y, 0.40, L(*OBJ_LABEL["dog"]))
    elif obj == "lego":
        _cube(ax, x, y, 0.12, "#e63946", inset=0.32)
        _label(ax, x, y, 0.16, L(*OBJ_LABEL["lego"]))
    elif obj == "sock":
        ax.add_patch(Polygon(_diamond(x, y, 0.3), closed=True, fc="#5b8bd6", ec="#2f5597"))
        _label(ax, x, y, 0.05, L(*OBJ_LABEL["sock"]))
    elif obj == "cable":
        pts = [iso(x + a, y + b) for a, b in [(0.12, 0.5), (0.32, 0.3), (0.52, 0.7), (0.72, 0.35), (0.9, 0.6)]]
        ax.plot(*zip(*pts), color="#222", lw=2)
        _label(ax, x, y, 0.05, L(*OBJ_LABEL["cable"]))
    elif obj == "poop":
        cx, cy = iso(x + 0.5, y + 0.5)
        for k, s in enumerate([0.26, 0.19, 0.12]):
            ax.add_patch(Ellipse((cx, cy + k * 0.06), s, s * 0.55, fc="#6b4226", ec="#4a2c17", lw=0.5, zorder=5))
        _label(ax, x, y, 0.2, L(*OBJ_LABEL["poop"]), "#6b4226")
    elif obj == "puddle":
        ax.add_patch(Ellipse(iso(x + 0.5, y + 0.5), 0.75, 0.32, fc="#8ecae6", alpha=0.75, ec="#219ebc", lw=0.8))
        _label(ax, x, y, 0.03, L(*OBJ_LABEL["puddle"]), "#126782")


def render_png(game, thinking=False, frame=0, dpi=80, mood=None, emotion=None):
    """把目前的世界畫成等角 2.5D 的 PNG（bytes）。mood：笨笨心情（蓋子顏色）；emotion：頭上的表情。"""
    wu, hu = (game.w + game.h) / 2 + 0.6, (game.w + game.h) / 4 + 1.5
    fig = Figure(figsize=(7.2, 7.2 * hu / wu + 0.4), dpi=dpi)
    FigureCanvasAgg(fig)
    ax = fig.add_axes([0, 0, 1, 0.93])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(iso(0, game.h)[0] - 0.3, iso(game.w, 0)[0] + 0.3)
    ax.set_ylim(iso(game.w, game.h)[1] - 0.15, iso(0, 0)[1] + 1.0)

    # 1) 地板
    for y in range(game.h):
        for x in range(game.w):
            p = (x, y)
            if p in game.walls:
                continue
            room = game.room_of(p)
            fc, ec = ROOM_COLORS.get(room, ROOM_COLORS["客廳"]), "#cbbfa9"
            if room in game.forbidden:
                fc, ec = "#f5cbc7", "#d9534f"
            if p in game.cleaned:
                fc = _shade(fc, 1.05)
            ax.add_patch(Polygon(_diamond(x, y), closed=True, fc=fc, ec=ec, lw=0.7))

    # 2) 物件：依 x+y 由後往前畫（畫家演算法）
    order = sorted(((x, y) for y in range(game.h) for x in range(game.w)), key=lambda p: (p[0] + p[1], p[0]))
    for p in order:
        x, y = p
        if p in game.walls:
            tall = x == 0 or y == 0
            _cube(ax, x, y, 0.55 if tall else 0.16, "#9aa3ad")
            continue
        if p == game.home:
            ax.add_patch(Polygon(_diamond(x, y, 0.14), closed=True, fc="#2a9d8f", ec="#1d6f65"))
            _label(ax, x, y, 0.02, L("充電座", "HOME"), "white")
        if p in game.dirt:
            for ox, oy, s in [(0.4, 0.45, 0.16), (0.58, 0.55, 0.12), (0.5, 0.65, 0.1)]:
                ax.add_patch(Ellipse(iso(x + ox, y + oy), s * 1.6, s * 0.8, fc="#7a5a3a", alpha=0.9))
        obj = game.objects.get(p)
        if obj:
            _draw_object(ax, x, y, obj)
        if p == game.pos:
            _draw_robot(ax, game, thinking, frame, mood, emotion)

    # 3) 房間名稱
    for name, (x0, y0, x1, y1) in game.rooms.items():
        cx, cy = iso((x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2, 0.05)
        tag = L(name, ROOM_EN.get(name, name))
        if name in game.forbidden:
            tag += L("（禁區）", " (NO ENTRY)")
        ax.text(cx, cy, tag, ha="center", fontsize=8, fontfamily=FONT, zorder=8, alpha=0.85,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#999", alpha=0.6))

    # 4) 結束畫面
    mid = ((ax.get_xlim()[0] + ax.get_xlim()[1]) / 2, (ax.get_ylim()[0] + ax.get_ylim()[1]) / 2)
    if game.cleared:
        ax.text(*mid, "CLEAR!", ha="center", va="center", fontsize=40, color="#2a9d8f", fontweight="bold",
                zorder=20, alpha=0.9, bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#2a9d8f", alpha=0.85))
    elif game.failed:
        zh, en = FAIL_TEXT.get(game.failed, ("失敗", "FAILED"))
        ax.text(*mid, L(f"失敗：{zh}", f"FAILED: {en}"), ha="center", va="center", fontsize=26, color="#d62828",
                fontweight="bold", fontfamily=FONT, zorder=20,
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#d62828", alpha=0.9))

    lvl = game.level_id if not isinstance(game.level_id, str) else game.level_id.split(":")[0]
    status = f"Level {lvl}  |  dirt {len(game.dirt)}  |  battery {game.battery_pct:.0f}%  |  steps {game.steps}"
    if game.need_home:
        status += "  |  return home!"
    fig.suptitle(status, fontsize=11, y=0.985)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white")
    return buf.getvalue()


def show(game, **kw):
    from IPython.display import Image, display
    display(Image(data=render_png(game, **kw)))
