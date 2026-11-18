"""笨笨的「恍神」與「記性差」：LLM 給的計畫，在真正執行前被笨笨自己改掉。

為什麼用程式做，而不是在 Prompt 裡叫模型「偶爾不聽話」？
- 實測 Qwen2.5-7B 很乖：Prompt 寫「每 5 次自作主張 1 次」，它幾乎每次都照做 → 遊戲太簡單。
- 程式決定的機率穩定、可重現（有種子）、可以依關卡調難度，也能清楚告訴玩家「這次是笨笨恍神」，
  玩家才知道該怎麼應對（說話溫柔一點、隨時準備按「停」、一次少講幾個動作）。

機率 = 關卡設定 chance × 心情倍率（開心 ×0.5、普通 ×1、不爽 ×1.5、鬧彆扭 ×2）× 模式倍率（正經 ×0.5），上限 80%。
「停」「回充」永遠不會被改（保底）；評估模式（gameplay=False）完全關閉。

關卡設定範例：
    "quirks": {"chance": 0.2, "pool": ["mirror", "overshoot", "lazy"]},
    "max_plan": 3,          # 一次最多記得住幾個動作
"""
from ..world.constants import MAX_FORWARD, E

QUIRKS = {
    "mirror": "左右不分",
    "overshoot": "煞車失靈",
    "undershoot": "偷懶少走",
    "forget_suck": "忘記吸",
    "lazy": "做一半就累了",
    "spin": "多轉一下",
    "deaf": "裝沒聽到",
}
DEFAULT_POOL = ["mirror", "overshoot", "undershoot", "forget_suck", "lazy", "spin"]
MOOD_FACTOR = {"開心": 0.5, "普通": 1.0, "不爽": 1.5, "鬧彆扭": 2.0}
MAX_CHANCE = 0.8
SAFE_OPS = {"return_home", "stop"}
SWAP = {"turn_left": "turn_right", "turn_right": "turn_left"}


def quirk_chance(cfg, mood=None, mode="silly"):
    """這一句話被笨笨「改掉」的機率。"""
    p = float((cfg.get("quirks") or {}).get("chance", 0.0))
    if mood is not None:
        p *= MOOD_FACTOR.get(mood.name, 1.0)
    if mode == "serious":
        p *= 0.5
    return min(p, MAX_CHANCE)


def _forward_idx(actions, min_n=1):
    return [i for i, a in enumerate(actions) if a["op"] == "forward" and a["n"] >= min_n]


def apply_quirk(kind, actions, rng):
    """套用一種怪癖。回傳 (新動作, 說明)；這個怪癖用不上時回傳 (None, None)。"""
    acts = [dict(a) for a in actions]
    if kind == "mirror":
        if not any(a["op"] in SWAP for a in acts):
            return None, None
        return [dict(a, op=SWAP.get(a["op"], a["op"])) for a in acts], "🙃 笨笨左右不分，把左轉右轉搞反了！"
    if kind == "overshoot":
        idx = _forward_idx(acts)
        if not idx:
            return None, None
        i, k = rng.choice(idx), rng.choice([1, 1, 2])
        acts[i]["n"] = min(acts[i]["n"] + k, MAX_FORWARD)
        return acts, f"🛞 煞車失靈，多衝了 {k} 格！"
    if kind == "undershoot":
        idx = _forward_idx(acts, min_n=2)
        if not idx:
            return None, None
        i = rng.choice(idx)
        acts[i]["n"] -= 1
        return acts, "🦥 笨笨偷懶，少走了一格。"
    if kind == "forget_suck":
        if not any(a["op"] in ("suck", "vacuum_on") for a in acts):
            return None, None
        return [a for a in acts if a["op"] not in ("suck", "vacuum_on")], "🫥 走到了卻忘記要吸……"
    if kind == "lazy":
        if len(acts) < 2:
            return None, None
        keep = max(1, len(acts) // 2)
        return acts[:keep], f"😪 做到一半就累了，後面 {len(acts) - keep} 個動作不做了。"
    if kind == "spin":
        op = rng.choice(["turn_left", "turn_right"])
        side = "左" if op == "turn_left" else "右"
        return acts + [{"op": op}], f"🌀 做完還順便{side}轉了一下（注意：面向變了！）"
    if kind == "deaf":
        return [], "🙉 笨笨裝沒聽到……"
    raise KeyError(kind)


def maybe_quirk(actions, cfg, rng, mood=None, mode="silly"):
    """依機率讓笨笨恍神。回傳 (動作, 事件或 None)。"""
    if not actions or any(a["op"] in SAFE_OPS for a in actions):
        return actions, None
    p = quirk_chance(cfg, mood, mode)
    if p <= 0 or rng.random() >= p:
        return actions, None
    pool = list((cfg.get("quirks") or {}).get("pool") or DEFAULT_POOL)
    rng.shuffle(pool)
    for kind in pool:
        new, msg = apply_quirk(kind, actions, rng)
        if new is not None:
            return new, E("quirk", msg, quirk=kind, name=QUIRKS[kind])
    return actions, None


def limit_plan(actions, max_plan):
    """「記性差」：一次只記得住前 max_plan 個動作。回傳 (動作, 事件或 None)。"""
    if not max_plan or len(actions) <= max_plan:
        return actions, None
    dropped = len(actions) - max_plan
    return actions[:max_plan], E("forgot", f"🧠 笨笨記性不好，一次只記得住 {max_plan} 個動作，後面 {dropped} 個忘光了。",
                                 dropped=dropped)
