"""SVG 遊戲畫面：2.5D 等角／俯視兩種視角。

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
EMOJI = {"cat": "🐱", "dog": "🐶", "lego": "🧱", "sock": "🧦", "cable": "➰", "poop": "💩", "puddle": "💧"}
MOOD_LID = {"開心": "#95d5b2", "普通": "#98c1d9", "不爽": "#f4a261", "鬧彆扭": "#e76f51"}
EMOTION_ICON = {"開心": "😄", "委屈": "🥺", "生氣": "😠", "得意": "😎", "害怕": "😱"}
FAIL_TEXT = {"owner_faint": "主人氣昏了", "out_of_battery": "沒電了", "time_up": "時間到"}
FONT = "'PingFang TC','Noto Sans TC','Microsoft JhengHei',sans-serif"
EMOJI_FONT = "'Apple Color Emoji','Segoe UI Emoji','Noto Color Emoji',sans-serif"
FOG = "#23263a"
ARROW = "#ffb703"

TW, TH = 56, 28          # 等角：一格菱形的寬、高（px）
WALL_TALL, WALL_LOW = 30, 12
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


# ---------- 2.5D 等角 ----------
def _iso_svg(game, thinking, mood, emotion, robot=True):
    pad, top = 16, WALL_TALL + 46
    W = (game.w + game.h) * TW / 2 + pad * 2
    H = (game.w + game.h) * TH / 2 + top + pad + 8
    ox, oy = game.h * TW / 2 + pad, top

    def P(x, y, z=0.0):
        return (ox + (x - y) * TW / 2, oy + (x + y) * TH / 2 - z)

    def diamond(x, y, inset=0.0, z=0.0):
        a, b, c, d = x + inset, y + inset, x + 1 - inset, y + 1 - inset
        return [P(a, b, z), P(c, b, z), P(c, d, z), P(a, d, z)]

    def cube(x, y, h, color, edge="#00000030"):
        back, right, front, left = diamond(x, y)
        up = lambda q: (q[0], q[1] - h)    # noqa: E731
        svg.poly([left, front, up(front), up(left)], _shade(color, 0.75), edge)
        svg.poly([front, right, up(right), up(front)], _shade(color, 0.88), edge)
        svg.poly([up(back), up(right), up(front), up(left)], color, edge)

    svg = _Svg()
    tiles = sorted(((x, y) for y in range(game.h) for x in range(game.w)), key=lambda p: (p[0] + p[1], p[0]))

    def near_seen(p):
        return any(game.visible((p[0] + a, p[1] + b)) for a, b in DIRS)

    # 1) 地板（停電關：沒看過的地方是一整片平的黑色）
    for p in tiles:
        if not game.visible(p):
            if p not in game.walls or not near_seen(p):
                svg.poly(diamond(*p), FOG, "#2c3048", 0.6)
            continue
        if p in game.walls:
            continue
        svg.poly(diamond(*p), _floor_color(game, p), "#d9534f" if game.in_forbidden(p) else "#cbbfa9")

    # 2) 地上的東西（灰塵、充電座、方向標示）
    for p in tiles:
        if p in game.walls or not game.visible(p):
            continue
        x, y = p
        cx, cy = P(x + 0.5, y + 0.5)
        if p == game.home:
            svg.poly(diamond(x, y, 0.16), "#2a9d8f", "#1d6f65")
            svg.text(cx, cy, "🔋", size=15, emoji=True)
        if p in game.dirt:
            for ox_, oy_, r in ((-7, -1, 7), (6, 2, 5.5), (0, 5, 4.5)):
                svg.add(f"<ellipse cx='{_f(cx + ox_)}' cy='{_f(cy + oy_)}' rx='{_f(r * 1.5)}' ry='{_f(r * 0.75)}' "
                        f"fill='#7a5a3a' fill-opacity='0.9'/>")

    # 3) 牆、物件、機器人（畫家演算法：由後往前）
    for p in tiles:
        x, y = p
        if p in game.walls:
            if game.visible(p) or near_seen(p):       # 看得到的牆（或剛好在光線邊緣）才畫立體
                cube(x, y, WALL_TALL if (x == 0 or y == 0) else WALL_LOW, "#9aa3ad")
            continue
        if not game.visible(p):
            continue
        cx, cy = P(x + 0.5, y + 0.5)
        obj = game.objects.get(p)
        if obj:
            if obj == "puddle":
                svg.add(f"<ellipse cx='{_f(cx)}' cy='{_f(cy)}' rx='21' ry='9' fill='#8ecae6' fill-opacity='0.8' "
                        "stroke='#219ebc'/>")
                svg.text(cx, cy - 4, EMOJI[obj], size=14, emoji=True)
            else:
                big = obj in ("cat", "dog")
                svg.add(f"<ellipse cx='{_f(cx)}' cy='{_f(cy + 2)}' rx='{14 if big else 10}' ry='{6 if big else 4}' "
                        "fill='#000' fill-opacity='0.15'/>")
                svg.text(cx, cy - (13 if big else 8), EMOJI[obj], size=26 if big else 19, emoji=True)
        if robot and p == game.pos:
            _iso_robot(svg, game, P, cx, cy, thinking, mood, emotion)
    if not robot:
        svg.add("<g class='bd-botlayer'></g>")    # 遊戲視窗：笨笨由前端畫在這一層，一格分 30 幀連續移動

    # 4) 房間名稱、指北針、結束畫面
    for name, (x0, y0, x1, y1) in game.rooms.items():
        if game.dark and not any(game.visible((x, y)) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)):
            continue
        cx, cy = P((x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2)
        if name in game.forbidden:
            svg.label(cx, cy - 18, f"🚫 {name}（禁區）", color="#c1121f", border="#d9534f")
        else:
            svg.label(cx, cy - 18, name, color="#555")
    _compass(svg, 48, 52, game.facing, lambda d: (P(*DIRS[d])[0] - P(0, 0)[0], P(*DIRS[d])[1] - P(0, 0)[1]))
    _end_banner(svg, game, W, H)
    return W, H, svg, {"proj": "iso", "ox": ox, "oy": oy, "tw": TW, "th": TH}


def _iso_robot(svg, game, P, cx, cy, thinking, mood, emotion):
    body, rx, ry = 11, 17, 8.5
    lid = MOOD_LID.get(mood, "#98c1d9")
    svg.add(f"<ellipse cx='{_f(cx)}' cy='{_f(cy + 2)}' rx='{rx + 3}' ry='{ry + 2}' fill='#000' fill-opacity='0.18'/>")
    svg.add(f"<ellipse cx='{_f(cx)}' cy='{_f(cy)}' rx='{rx}' ry='{ry}' fill='#22324a'/>")
    svg.add(f"<rect x='{_f(cx - rx)}' y='{_f(cy - body)}' width='{rx * 2}' height='{body}' fill='#3d5a80'/>")
    svg.add(f"<ellipse cx='{_f(cx)}' cy='{_f(cy - body)}' rx='{rx}' ry='{ry}' fill='{lid}' stroke='#3d5a80' "
            "stroke-width='1.5'/>")
    # 前進方向的大箭頭
    x, y = game.pos
    dx, dy = DIRS[game.facing]
    tx, ty = P(x + 0.5 + dx, y + 0.5 + dy)
    vx, vy = tx - cx, ty - cy
    n = math.hypot(vx, vy)
    vx, vy = vx / n, vy / n
    _arrow(svg, cx, cy - body, vx, vy, length=30, width=9)
    if game.battery_pct < 25:
        svg.add(f"<circle cx='{_f(cx + 9)}' cy='{_f(cy - body - 2)}' r='3.5' fill='#ff1744' class='bd-blink'/>")
    if thinking:
        svg.label(cx, cy - body - 30, "🤔 …", size=13, border="#555")
    elif emotion in EMOTION_ICON:
        svg.text(cx, cy - body - 28, EMOTION_ICON[emotion], size=20, emoji=True)


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


def _shade(color, k):
    c = color.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (min(int(r * k), 255), min(int(g * k), 255), min(int(b * k), 255))


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


def render_svg(game, view="iso", thinking=False, mood=None, emotion=None, max_width=760, robot=True):
    """把目前的世界畫成 SVG 字串。view："iso"（2.5D）或 "top"（俯視）。

    robot=False：不畫笨笨，只留一個空的 `.bd-botlayer` 和投影參數（data-*），
    遊戲視窗的前端會把笨笨畫在那一層，每移動一格分成 30 幀播放（連續移動）。
    """
    W, H, svg, proj = (_top_svg if view == "top" else _iso_svg)(game, thinking, mood, emotion, robot=robot)
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
