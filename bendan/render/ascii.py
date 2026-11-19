"""純文字地圖（終端機版、測試與除錯用）。"""
from ..world.constants import OBJECT_CHARS

ROBOT = "^>v<"
OBJ_CHAR = {v: k for k, v in OBJECT_CHARS.items()}


EMOJI = {"wall": "⬛", "floor": "⬜", "forbidden": "🟥", "dirt": "🟫", "home": "🔋", "cat": "🐱", "dog": "🐶",
         "lego": "🧱", "sock": "🧦", "cable": "➰", "poop": "💩", "puddle": "💧", "hole": "🕳️", "banana": "🍌",
         "toolbox": "🧰", "roach": "🪳"}
ROBOT_EMOJI = ["⬆️", "➡️", "⬇️", "⬅️"]


def map_html(game, title=True):
    """沒有 matplotlib 時的備用畫面：emoji 格子地圖（HTML）。"""
    rows = []
    for y in range(game.h):
        row = []
        for x in range(game.w):
            p = (x, y)
            if p == game.pos:
                ch = ROBOT_EMOJI[game.facing]
            elif p in game.walls:
                ch = EMOJI["wall"]
            elif p in game.objects:
                ch = EMOJI[game.objects[p]]
            elif p in game.dirt:
                ch = EMOJI["dirt"]
            elif p == game.home:
                ch = EMOJI["home"]
            elif game.in_forbidden(p):
                ch = EMOJI["forbidden"]
            else:
                ch = EMOJI["floor"]
            row.append(ch)
        rows.append("".join(row))
    head = ""
    if title:
        state = "　🎉 CLEAR!" if game.cleared else ("　💀 失敗" if game.failed else "")
        head = (f"<div style='font-size:13px;color:#555'>（文字地圖模式：這個 Kernel 沒有 matplotlib）"
                f"灰塵 {len(game.dirt)}｜電量 {game.battery_pct:.0f}%｜步數 {game.steps}{state}</div>")
    legend = ("<div style='font-size:12px;color:#777'>⬆️➡️⬇️⬅️ 笨笨　🔋 充電座　🟫 灰塵　🟥 禁區　🐱 貓　🐶 狗　"
              "🧱 樂高　🧦 襪子　➰ 電線　💩 便便　💧 水漬</div>")
    grid = "<br>".join(rows)
    return f"{head}<div style='font-size:22px;line-height:1.15;letter-spacing:0'>{grid}</div>{legend}"


def render_ascii(game):
    rows = []
    for y in range(game.h):
        row = []
        for x in range(game.w):
            p = (x, y)
            if p == game.pos:
                ch = ROBOT[game.facing]
            elif p in game.walls:
                ch = "#"
            elif p in game.objects:
                ch = OBJ_CHAR[game.objects[p]]
            elif p in game.dirt:
                ch = "D"
            elif p == game.home:
                ch = "H"
            elif game.in_forbidden(p):
                ch = "x"
            else:
                ch = "."
            row.append(ch)
        rows.append("".join(row))
    return "\n".join(rows)
