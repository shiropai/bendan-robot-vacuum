"""SVG 地圖（俯視）：文字模式、Notebook 說明圖、報告用。v8 起遊戲視窗只用 3D，2.5D 等角視角已移除。

為什麼改用 SVG（v3）？
- 不需要 matplotlib：任何 Kernel 都能玩；字串組出來的 SVG 比 matplotlib 畫 PNG 快很多，即時模式更順。
- 瀏覽器直接畫 emoji，貓狗樂高看起來更像遊戲。

方向輔助（玩家回饋：「看不出笨笨面向哪裡」）：
- 笨笨頭上的大黃箭頭＝正前方，前方那一格整格發亮
- 「前方雷射」：前方每一格標上 1、2、3……，一路標到會撞到的東西為止 → 直接看出「往前走幾格」
- 笨笨的左手邊、右手邊、後方標「左」「右」「後」（笨笨的左右，不是螢幕的左右）
- 指北針：笨笨面向的方位會亮黃色（等角視角下東西南北是斜的，看指北針最清楚）
- 停電關（`dark`）：沒看過的格子是黑的
"""
import html
import math

from ..world.constants import DIR_NAMES, DIRS

ROOM_COLORS = {"客廳": "#efe4d0", "臥室": "#e3def2", "廚房": "#d6ebe0", "書房": "#f1e3c8", "浴室": "#d8e8f3"}
FORBIDDEN_FILL = "#f6c9c4"
EMOJI = {"cat": "🐱", "dog": "🐶", "lego": "🧱", "sock": "🧦", "cable": "➰", "poop": "💩", "puddle": "💧",
         "hole": "🕳️", "banana": "🍌", "toolbox": "🧰", "roach": "🪳"}
MOOD_LID = {"開心": "#95d5b2", "普通": "#98c1d9", "不爽": "#f4a261", "鬧彆扭": "#e76f51"}
EMOTION_ICON = {"開心": "😄", "委屈": "🥺", "生氣": "😠", "得意": "😎", "害怕": "😱"}
FAIL_TEXT = {"owner_faint": "主人氣昏了", "out_of_battery": "沒電了", "time_up": "時間到", "exploded": "笨笨爆炸了"}
FONT = "'PingFang TC','Noto Sans TC','Microsoft JhengHei',sans-serif"
EMOJI_FONT = "'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',sans-serif"
FOG = "#23263a"
ARROW = "#ffb703"

FURN_ICON = {"sofa": "🛋️", "armchair": "🛋️", "tv": "📺", "bookcase": "📚", "shelf": "📚", "plant": "🪴", "lamp": "💡",
             "speaker": "🔊", "bed": "🛏️", "wardrobe": "🚪", "nightstand": "🗄️", "fridge": "🧊", "stove": "🍳",
             "sink": "🚰", "counter": "🗄️", "counter2": "🗄️", "desk": "🖥️", "toilet": "🚽", "basin": "🚰",
             "washer": "🫧", "bathcab": "🗄️"}
CELL = 42                # 俯視：一格的邊長（px）


def _f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _pts(points):
    return " ".join(f"{_f(x)},{_f(y)}" for x, y in points)


def _esc(s):
    return html.escape(str(s), quote=True)


class _Svg:
    def __init__(self):
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def poly(self, points, fill, stroke="none", sw=0.8, extra=""):
        self.add(f"<polygon points='{_pts(points)}' fill='{fill}' stroke='{stroke}' stroke-width='{sw}' {extra}/>")

    def text(self, x, y, s, size=12, fill="#333", weight="normal", emoji=False, anchor="middle", extra=""):
        fam = EMOJI_FONT if emoji else FONT
        self.add(f"<text x='{_f(x)}' y='{_f(y)}' font-size='{size}' fill='{fill}' font-weight='{weight}' "
                 f"text-anchor='{anchor}' dominant-baseline='central' font-family=\"{fam}\" {extra}>{_esc(s)}</text>")

    def badge(self, x, y, s, fill, color="white", r=9, size=11):
        self.add(f"<circle cx='{_f(x)}' cy='{_f(y)}' r='{r}' fill='{fill}' stroke='white' stroke-width='1.5'/>")
        self.text(x, y + 0.5, s, size=size, fill=color, weight="bold")

    def label(self, x, y, s, color="#333", bg="white", size=11, border="#999"):
        w = 8 + size * sum(1.0 if ord(c) > 255 else 0.6 for c in s)
        self.add(f"<rect x='{_f(x - w / 2)}' y='{_f(y - size * 0.8)}' width='{_f(w)}' height='{_f(size * 1.6)}' "
                 f"rx='6' fill='{bg}' fill-opacity='0.82' stroke='{border}' stroke-width='0.8'/>")
        self.text(x, y, s, size=size, fill=color, weight="bold")


def _floor_color(game, p):
    room = game.room_of(p)
    return FORBIDDEN_FILL if room in game.forbidden else ROOM_COLORS.get(room, ROOM_COLORS["客廳"])


def _end_banner(svg, game, W, H):
    if not (game.cleared or game.failed):
        return
    text = "🎉 CLEAR!" if game.cleared else f"💀 失敗：{FAIL_TEXT.get(game.failed, game.failed)}"
    color = "#2a9d8f" if game.cleared else "#d62828"
    svg.add(f"<rect x='0' y='{_f(H / 2 - 34)}' width='{_f(W)}' height='68' fill='white' fill-opacity='0.88'/>")
    svg.text(W / 2, H / 2, text, size=34, fill=color, weight="bold")


# ---------- 共用 ----------
def _arrow(svg, x, y, vx, vy, length=30, width=9):
    """從 (x, y) 沿 (vx, vy) 畫一支粗箭頭。"""
    px, py = -vy, vx
    shaft = length * 0.55
    tip = (x + vx * length, y + vy * length)
    base = (x + vx * shaft, y + vy * shaft)
    pts = [(x + px * width * 0.35, y + py * width * 0.35), (base[0] + px * width * 0.35, base[1] + py * width * 0.35),
           (base[0] + px * width, base[1] + py * width), tip,
           (base[0] - px * width, base[1] - py * width), (base[0] - px * width * 0.35, base[1] - py * width * 0.35),
           (x - px * width * 0.35, y - py * width * 0.35)]
    svg.poly(pts, ARROW, "#5c4100", 1.4)


def _compass(svg, cx, cy, facing, vec):
    svg.add(f"<circle cx='{cx}' cy='{cy}' r='38' fill='white' fill-opacity='0.85' stroke='#bbb'/>")
    for d in range(4):
        vx, vy = vec(d)
        n = math.hypot(vx, vy)
        vx, vy = vx / n, vy / n
        on = d == facing
        color = ARROW if on else "#adb5bd"
        svg.add(f"<line x1='{cx}' y1='{cy}' x2='{_f(cx + vx * 20)}' y2='{_f(cy + vy * 20)}' stroke='{color}' "
                f"stroke-width='{4 if on else 2}' stroke-linecap='round'/>")
        svg.text(cx + vx * 30, cy + vy * 30, DIR_NAMES[d], size=13 if on else 11,
                 fill="#b5651d" if on else "#6c757d", weight="bold" if on else "normal")
    svg.add(f"<circle cx='{cx}' cy='{cy}' r='3' fill='#555'/>")


# ---------- 俯視 ----------
def _top_svg(game, thinking, mood, emotion, robot=True):
    pad, side = 12, 96
    W, H = game.w * CELL + pad * 2 + side, game.h * CELL + pad * 2
    svg = _Svg()

    def C(x, y):
        return pad + x * CELL, pad + y * CELL

    for y in range(game.h):
        for x in range(game.w):
            p = (x, y)
            X, Y = C(x, y)
            if not game.visible(p):
                svg.add(f"<rect x='{X}' y='{Y}' width='{CELL}' height='{CELL}' fill='{FOG}'/>")
                continue
            if p in game.furniture:          # v8：家具（擋路，跟牆一樣）
                svg.add(f"<rect x='{X}' y='{Y}' width='{CELL}' height='{CELL}' fill='{_floor_color(game, p)}'/>"
                        f"<rect x='{X + 3}' y='{Y + 3}' width='{CELL - 6}' height='{CELL - 6}' rx='5' fill='#b08968' "
                        "stroke='#7f5539'/>")
                svg.text(X + CELL / 2, Y + CELL / 2, FURN_ICON.get(game.furniture[p]["key"], "🪑"), size=18, emoji=True)
                continue
            if p in game.walls:
                svg.add(f"<rect x='{X}' y='{Y}' width='{CELL}' height='{CELL}' fill='#6c757d' stroke='#5a6268'/>")
                continue
            fill = _floor_color(game, p)
            svg.add(f"<rect x='{X}' y='{Y}' width='{CELL}' height='{CELL}' fill='{fill}' stroke='#d6ccb8'/>")
            mx, my = X + CELL / 2, Y + CELL / 2
            if p == game.home:
                svg.add(f"<rect x='{X + 5}' y='{Y + 5}' width='{CELL - 10}' height='{CELL - 10}' rx='6' fill='#2a9d8f'/>")
                svg.text(mx, my, "🔋", size=18, emoji=True)
            if p in game.dirt:
                for ox_, oy_, r in ((-6, -3, 7), (6, 2, 6), (-1, 8, 4.5)):
                    svg.add(f"<circle cx='{_f(mx + ox_)}' cy='{_f(my + oy_)}' r='{r}' fill='#7a5a3a' fill-opacity='0.9'/>")
            obj = game.objects.get(p)
            if obj:
                svg.text(mx, my, EMOJI[obj], size=24 if obj in ("cat", "dog") else 20, emoji=True)
    for name, (x0, y0, x1, y1) in game.rooms.items():
        if game.dark and not any(game.visible((x, y)) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)):
            continue
        cx, cy = C((x0 + x1 + 1) / 2, y0 + 0.2)
        if name in game.forbidden:
            svg.label(cx, cy, f"🚫 {name}（禁區）", color="#c1121f", border="#d9534f", size=10)
        else:
            svg.label(cx, cy, name, color="#555", size=10)
    # 機器人（遊戲視窗裡由前端畫，才能連續移動）
    if robot:
        x, y = game.pos
        X, Y = C(x, y)
        cx, cy = X + CELL / 2, Y + CELL / 2
        svg.add(f"<circle cx='{_f(cx)}' cy='{_f(cy)}' r='{CELL * 0.4:.1f}' fill='{MOOD_LID.get(mood, '#98c1d9')}' "
                "stroke='#22324a' stroke-width='3'/>")
        dx, dy = DIRS[game.facing]
        _arrow(svg, cx - dx * 6, cy - dy * 6, dx, dy, length=30, width=9)
        if thinking:
            svg.label(cx, Y - 6, "🤔 …", size=12, border="#555")
        elif emotion in EMOTION_ICON:
            svg.text(cx + 16, Y + 2, EMOTION_ICON[emotion], size=16, emoji=True)
    else:
        svg.add("<g class='bd-botlayer'></g>")
    _compass(svg, W - side / 2, 56, game.facing, lambda d: DIRS[d])
    _end_banner(svg, game, W - side, H)
    return W, H, svg, {"proj": "top", "pad": pad, "cell": CELL}


def render_svg(game, view="top", thinking=False, mood=None, emotion=None, max_width=760, robot=True):
    """把目前的世界畫成俯視 SVG 字串（view 參數保留相容，v8 起只有俯視）。robot=False：不畫笨笨。"""
    W, H, svg, proj = _top_svg(game, thinking, mood, emotion, robot=robot)
    body = "".join(svg.parts)
    data = " ".join(f"data-{k}='{v}'" for k, v in proj.items())
    return (f"<svg class='bendan-board' {data} viewBox='0 0 {_f(W)} {_f(H)}' xmlns='http://www.w3.org/2000/svg' "
            f"style='width:100%;max-width:{max_width}px;height:auto;display:block;margin:0 auto'>"
            f"<rect width='100%' height='100%' fill='#fbf8f2' rx='12'/>{body}</svg>")


def facing_text(game):
    """「面向東 ➡｜前方是牆壁」這類文字（HUD 用）。v7 不再顯示格數（連續移動用不到），只在快撞到時提醒。"""
    from ..world.constants import DIR_ARROWS
    x, y = game.pos
    dx, dy = DIRS[game.facing]
    k = 0
    while not game.is_blocked((x + dx * (k + 1), y + dy * (k + 1))) and k < 60:
        k += 1
    what = game.what_at((x + dx * (k + 1), y + dy * (k + 1)))
    near = "（快撞到了！）" if k <= 1 else ""
    state = ("｜🚗 前進中，喊「停」才會停" if game.driving else "") + ("｜🌀 吸塵中" if game.vacuum else "")
    return f"面向{DIR_NAMES[game.facing]} {DIR_ARROWS[game.facing]}｜前方是{what}{near}{state}"
