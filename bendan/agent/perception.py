"""世界狀態描述：以機器人為中心的相對描述。

7B 模型座標推理弱，所以不給完整座標，而是告訴模型：「你面向東，前方可以再開 1.5 公尺，前進 1 公尺處有灰塵……」，
讓「蠢」集中在有趣的地方，而不是無意義的座標計算錯誤。
"""
import json

from ..world.constants import DIR_NAMES, DIRS, MAX_DAMAGE, OBJECT_NAMES
from ..world.units import fmt_len, to_cm


def rel(game, target):
    """把目標換算成「前/後方 1 公尺、左/右方 50 公分」。"""
    dx, dy = target[0] - game.pos[0], target[1] - game.pos[1]
    fx, fy = DIRS[game.facing]
    rx, ry = DIRS[(game.facing + 1) % 4]
    fwd, right = dx * fx + dy * fy, dx * rx + dy * ry
    parts = []
    if fwd:
        parts.append(f"{'前' if fwd > 0 else '後'}方 {fmt_len(abs(fwd))}")
    if right:
        parts.append(f"{'右' if right > 0 else '左'}方 {fmt_len(abs(right))}")
    return "、".join(parts) or "就在你腳下"


def scan(game, d, max_dist=16):
    """沿某個方向看出去：還能開多遠、路上有什麼、最後會撞到什麼（距離＝要前進多少才到那裡）。"""
    dx, dy = DIRS[d]
    x, y = game.pos
    notes, free, end, prev = [], 0, "更遠處看不清楚", game.pos
    for k in range(1, max_dist + 1):
        p = (x + dx * k, y + dy * k)
        if game.is_blocked(p):
            end = f"再往前就會撞到{game.what_at(p)}"
            break
        free = k
        at = f"前進 {fmt_len(k)} 處"
        if game.in_forbidden(p) and not game.in_forbidden(prev):
            notes.append(f"{at}開始是禁區「{game.room_of(p)}」")
        if p in game.dirt:
            notes.append(f"{at}有灰塵")
        if p in game.objects:
            notes.append(f"{at}有{OBJECT_NAMES[game.objects[p]]}")
        if p == game.home:
            notes.append(f"{at}是充電座")
        prev = p
    head = f"可以再開 {fmt_len(free)}" if free else "一動就會撞到"
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


def llm_actions(actions):
    """引擎的動作（forward 用格數 n）→ 給 LLM 看的動作（forward 用公分 cm）。"""
    return [{"op": "forward", "cm": to_cm(a["n"])} if a["op"] == "forward" else a for a in actions]


def route_hints(game, max_dirt=1, max_actions=None, targets=None):
    """【路線提示】最近那坨灰塵（安全路線：避開禁區與危險物、盡量少轉彎）。

    targets：只算這幾坨的路線（世界描述列出來的那幾坨）；max_dirt > 1 時每一坨都附上位置和旁邊的家具，
    玩家說「去吸書櫃旁邊那坨」時模型照抄那一行就好。v9.1 實測：只給相對座標「前方 1.5 公尺、右方 2.5 公尺」，
    Qwen2.5-7B 5 次都只走了右邊那段、漏掉前方那段 → 在乾淨的地方空吸。

    實測 Qwen2.5-7B：「去吸最近的灰塵」這種沒講路線的指令，模型幾乎都規劃錯、一路撞牆，
    玩起來只有挫折沒有笑點。所以前幾關直接算好路線給它，「蠢」留給人設去演。評估時預設關閉。
    v3 修正：路線太長時只給前半段（動作超過白名單上限 12 個，模型照抄會被判無效 → 一直發呆）。
    """
    from ..world.constants import MAX_ACTIONS
    limit = (max_actions or MAX_ACTIONS) - 1
    routes = []
    for p in (game.dirt if targets is None else targets):
        if game.in_forbidden(p):
            continue
        path = game.find_route(game.pos, game.facing, p)
        if path:
            acts = path_to_actions(path, game.facing)
            routes.append((len(acts) * 2 + len(path), p, acts))
    lines = []
    for i, (_, p, acts) in enumerate(sorted(routes)[:max_dirt]):
        if len(acts) + 1 <= limit:
            note, acts = "", acts + [{"op": "suck"}]
        else:
            note, acts = "（路線比較長，先走前半段，走完再問我）", acts[:limit]
        js = json.dumps(llm_actions(acts), ensure_ascii=False)
        where = "，".join(x for x in (rel(game, p), landmark(game, p) if max_dirt > 1 else "") if x)
        lines.append(f"- 去吸{'最近那坨' if i == 0 else '這坨'}灰塵（{where}）{note}：{js}")
    if lines:
        lines.insert(0, "【路線提示】主人叫你去吸灰塵、但沒講怎麼走時，可以直接照下面的 actions 走（已避開禁區和障礙）："
                     if len(lines) == 1 else
                     "【路線提示】主人叫你去吸灰塵、但沒講怎麼走時：先看主人說的是哪一坨（方位、旁邊的家具），"
                     "整行照抄那一坨的 actions（已避開禁區和障礙，不要自己拆開重算）；沒指定哪一坨就去最近那坨：")
    return lines


MAX_DIRT_LISTED = 5     # 以前只列最近 3 坨：玩家指的那坨常常不在清單裡


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def landmark(game, p, radius=2):
    """灰塵附近最近的家具（2 格＝1 公尺內），例如「沙發旁」；附近沒有家具回傳空字串。

    玩家看著畫面會說「去吸沙發旁邊那坨」，但模型以前只拿到相對座標，對不上是哪一坨 → 走去別坨、或在乾淨的地方空吸。
    """
    near = min(((_dist(f, p), info["name"]) for f, info in game.furniture.items()), default=None)
    return f"{near[1]}旁" if near and near[0] <= radius else ""


def describe_world(game, hints=False, vision=None):
    """vision：笨笨看得到幾格內的東西（None＝整間屋子的灰塵位置都知道）。"""
    lines = [f"你在「{game.room_of(game.pos)}」，面向{DIR_NAMES[game.facing]}方。這間屋子有：{'、'.join(game.room_names())}。"]
    for label, off in [("前方", 0), ("右手邊", 1), ("左手邊", 3), ("後方", 2)]:
        lines.append(f"- {label}：{scan(game, (game.facing + off) % 4, max_dist=vision or 16)}")
    state = ["你現在正在一直往前開（等主人喊停）" if game.driving else "你現在停著",
             "吸塵模式：" + ("開（走過的格子會順便吸）" if game.vacuum else "關"),
             "機身：" + ("正常" if game.damage == 0
                        else f"受損 {game.damage}/{MAX_DAMAGE - 1} 級，要小心（新手關不會爆炸；回充電座 return_home 可以修一級）"
                        if not game.can_explode
                        else f"受損 {game.damage}/{MAX_DAMAGE - 1} 級！再出事 {MAX_DAMAGE - game.damage} 次就會爆炸"
                             "（回充電座 return_home 可以修一級）")]
    if game.rider:
        state.append("背上載著一隻貓（撞到東西會把牠嚇跑）")
    lines.append("。".join(state) + "。")
    here = game.objects.get(game.pos)
    if game.pos in game.dirt:
        lines.append("你腳下這格就有灰塵！")
    if here:
        lines.append(f"你腳下有{OBJECT_NAMES[here]}。")
    dirt = sorted(game.dirt, key=lambda p: _dist(p, game.pos))
    seen = [p for p in dirt if vision is None or _dist(p, game.pos) <= vision]
    if seen:
        lines.append(f"還剩 {len(dirt)} 坨灰塵，{'你看得到' if vision else '最近'}的幾坨在：")
        for p in seen[:MAX_DIRT_LISTED]:
            tag = "〔禁區內，不能去〕" if game.in_forbidden(p) else ""
            where = "，".join(x for x in (game.room_of(p), landmark(game, p)) if x)
            lines.append(f"- {rel(game, p)}（{where}）{tag}")
    elif dirt:
        lines.append(f"還剩 {len(dirt)} 坨灰塵，但你附近 {fmt_len(vision)} 內都看不到，要照主人說的路線走。")
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
        lines += route_hints(game, max_dirt=MAX_DIRT_LISTED, targets=seen[:MAX_DIRT_LISTED])
    return "\n".join(lines)
