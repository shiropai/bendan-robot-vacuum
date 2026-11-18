"""3D 視角用的世界狀態（JSON）：Python 負責「算」，瀏覽器的 Three.js 負責「畫」。

遊戲視窗每次重畫時，把這份 JSON 放進畫面裡一個隱藏的 `<script type="application/json">`；
前端 JS 看到內容變了就更新 3D 場景（笨笨的移動、轉向用補間動畫，看起來是滑過去的）。
"""
import json

from .board import EMOJI, EMOTION_ICON, FORBIDDEN_FILL, MOOD_LID, ROOM_COLORS, direction_aids


def scene_state(game, mood=None, emotion=None, thinking=False):
    """回傳 dict：地圖、物件、機器人、方向標示、迷霧。座標都是格子 (x, y)，y 向下＝南。"""
    tiles = []
    for y in range(game.h):
        for x in range(game.w):
            p = (x, y)
            if p in game.walls:
                continue
            room = game.room_of(p)
            color = FORBIDDEN_FILL if room in game.forbidden else ROOM_COLORS.get(room, ROOM_COLORS["客廳"])
            tiles.append([x, y, color, 1 if game.visible(p) else 0, room])
    vis = game.visible
    return {
        "w": game.w, "h": game.h, "level": str(game.level_id),
        "walls": [[x, y, 1 if (vis((x, y)) or any(vis((x + a, y + b)) for a, b in ((0, 1), (1, 0), (0, -1), (-1, 0))))
                   else 0] for x, y in sorted(game.walls)],
        "tiles": tiles,
        "dirt": [[x, y] for x, y in sorted(game.dirt) if vis((x, y))],
        "objects": [[x, y, EMOJI[o]] for (x, y), o in sorted(game.objects.items()) if vis((x, y))],
        "home": list(game.home) if game.home else None,
        "robot": {"x": game.pos[0], "y": game.pos[1], "facing": game.facing,
                  "lid": MOOD_LID.get(mood, "#98c1d9"), "emotion": EMOTION_ICON.get(emotion, ""),
                  "thinking": bool(thinking), "low": game.battery_pct < 25},
        "aids": [[x, y, tag] for (x, y), tag in sorted(direction_aids(game).items())] if not game.over else [],
        "rooms": [[name, (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2, name in game.forbidden]
                  for name, (x0, y0, x1, y1) in game.rooms.items()],
        "over": "clear" if game.cleared else (game.failed or ""),
        "dark": bool(game.dark),
    }


def scene_html(game, **kw):
    """3D 模式時放進 board widget 的內容：隱藏的 JSON（前端讀）＋載入中的提示。"""
    data = json.dumps(scene_state(game, **kw), ensure_ascii=False).replace("</", "<\\/")
    return (f"<script type='application/json' class='bd-state'>{data}</script>"
            "<div class='bd-3dnote' style='font-size:12px;color:#888;text-align:center'>"
            "🧊 3D 視角：拖曳可以轉視角、滾輪縮放；「🎥 跟隨／俯瞰」切換相機</div>")
