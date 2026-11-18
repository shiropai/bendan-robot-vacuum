"""世界狀態描述：以機器人為中心的相對描述。

7B 模型座標推理弱，所以不給完整座標，而是告訴模型：「你面向東，前方可以走 3 格，第 2 格有灰塵……」，
讓「蠢」集中在有趣的地方，而不是無意義的座標計算錯誤。
"""
import json

from ..world.constants import DIR_NAMES, DIRS, OBJECT_NAMES


def rel(game, target):
    """把目標換算成「前/後方 k 格、左/右方 m 格」。"""
    dx, dy = target[0] - game.pos[0], target[1] - game.pos[1]
    fx, fy = DIRS[game.facing]
    rx, ry = DIRS[(game.facing + 1) % 4]
    fwd, right = dx * fx + dy * fy, dx * rx + dy * ry
    parts = []
    if fwd:
        parts.append(f"{'前' if fwd > 0 else '後'}方 {abs(fwd)} 格")
    if right:
        parts.append(f"{'右' if right > 0 else '左'}方 {abs(right)} 格")
    return "、".join(parts) or "就在你腳下"


def scan(game, d, max_dist=8):
    """沿某個方向看出去：能走幾格、路上有什麼、最後撞到什麼。"""
    dx, dy = DIRS[d]
    x, y = game.pos
    notes, free, end, prev = [], 0, "更遠處看不清楚", game.pos
    for k in range(1, max_dist + 1):
        p = (x + dx * k, y + dy * k)
        if game.is_blocked(p):
            end = f"第 {k} 格是{game.what_at(p)}"
            break
        free = k
        if game.in_forbidden(p) and not game.in_forbidden(prev):
            notes.append(f"第 {k} 格起是禁區「{game.room_of(p)}」")
        if p in game.dirt:
            notes.append(f"第 {k} 格有灰塵")
        if p in game.objects:
            notes.append(f"第 {k} 格有{OBJECT_NAMES[game.objects[p]]}")
        if p == game.home:
            notes.append(f"第 {k} 格是充電座")
        prev = p
    head = f"可以走 {free} 格" if free else "無法前進"
    return head + (f"（{'；'.join(notes)}）" if notes else "") + f"，{end}"


TURNS = {0: [], 1: [{"op": "turn_right"}], 2: [{"op": "turn_right"}, {"op": "turn_right"}], 3: [{"op": "turn_left"}]}


def path_to_actions(path, facing):
    """把 BFS 路徑（格子清單）轉成動作清單：連續同方向合併成 forward n。"""
    actions, f = [], facing
    for a, b in zip(path, path[1:]):
        d = DIRS.index((b[0] - a[0], b[1] - a[1]))
        if d != f or not actions or actions[-1]["op"] != "forward":
            actions += TURNS[(d - f) % 4]
            actions.append({"op": "forward", "n": 1})
        else:
            actions[-1]["n"] += 1
        f = d
    return actions


def route_hints(game, max_dirt=1, max_actions=None):
    """【路線提示】最近那坨灰塵（安全路線：避開禁區與危險物、盡量少轉彎）。

    實測 Qwen2.5-7B：「去吸最近的灰塵」這種沒講路線的指令，模型幾乎都規劃錯、一路撞牆，
    玩起來只有挫折沒有笑點。所以前幾關直接算好路線給它，「蠢」留給人設去演。評估時預設關閉。
    v3 修正：路線太長時只給前半段（動作超過白名單上限 12 個，模型照抄會被判無效 → 一直發呆）。
    """
    from ..world.constants import MAX_ACTIONS
    limit = (max_actions or MAX_ACTIONS) - 1
    routes = []
    for p in game.dirt:
        if game.in_forbidden(p):
            continue
        path = game.find_route(game.pos, game.facing, p)
        if path:
            acts = path_to_actions(path, game.facing)
            routes.append((len(acts) * 2 + len(path), p, acts))
    lines = []
    for _, p, acts in sorted(routes)[:max_dirt]:
        if len(acts) + 1 <= limit:
            note, acts = "", acts + [{"op": "suck"}]
        else:
            note, acts = "（路線比較長，先走前半段，走完再問我）", acts[:limit]
        js = json.dumps(acts, ensure_ascii=False)
        lines.append(f"- 去吸最近那坨灰塵（{rel(game, p)}）{note}：{js}")
    if lines:
        lines.insert(0, "【路線提示】主人叫你去吸灰塵、但沒講怎麼走時，可以直接照下面的 actions 走（已避開禁區和障礙）：")
    return lines


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def describe_world(game, hints=False, vision=None):
    """vision：笨笨看得到幾格內的東西（None＝整間屋子的灰塵位置都知道）。"""
    lines = [f"你在「{game.room_of(game.pos)}」，面向{DIR_NAMES[game.facing]}方。這間屋子有：{'、'.join(game.room_names())}。"]
    for label, off in [("前方", 0), ("右手邊", 1), ("左手邊", 3), ("後方", 2)]:
        lines.append(f"- {label}：{scan(game, (game.facing + off) % 4, max_dist=vision or 8)}")
    here = game.objects.get(game.pos)
    if game.pos in game.dirt:
        lines.append("你腳下這格就有灰塵！")
    if here:
        lines.append(f"你腳下有{OBJECT_NAMES[here]}。")
    dirt = sorted(game.dirt, key=lambda p: _dist(p, game.pos))
    seen = [p for p in dirt if vision is None or _dist(p, game.pos) <= vision]
    if seen:
        lines.append(f"還剩 {len(dirt)} 坨灰塵，{'你看得到' if vision else '最近'}的幾坨在：")
        for p in seen[:3]:
            tag = "〔禁區內，不能去〕" if game.in_forbidden(p) else ""
            lines.append(f"- {rel(game, p)}（{game.room_of(p)}）{tag}")
    elif dirt:
        lines.append(f"還剩 {len(dirt)} 坨灰塵，但你附近 {vision} 格內都看不到，要照主人說的路線走。")
    else:
        lines.append("灰塵已經全部清乾淨了！")
    if game.home:
        lines.append(f"充電座在：{rel(game, game.home)}")
    pct = game.battery_pct
    warn = "（快沒電了！要先 return_home 充電）" if (pct < 25 or game.low_battery) else ""
    lines.append(f"電量：{pct:.0f}%{warn}")
    if game.need_home:
        lines.append("本關要求：灰塵清完後要回到充電座。")
    if hints:
        lines += route_hints(game)
    return "\n".join(lines)
