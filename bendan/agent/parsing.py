"""輸出解析與白名單驗證。

就算模型多講廢話、包了 ```json，也盡量把 JSON 挖出來；但**動作必須完全在選單內**，否則整份輸出視為無效。
"""
import json
import re

from ..world.constants import ACTION_WHITELIST, MAX_ACTIONS, MAX_FORWARD
from .prompts import EMOTIONS


REPEATABLE = {"turn_left": 4, "turn_right": 4, "suck": 5}   # 這些動作可以帶 n（重複次數上限）

# 實測 Qwen2.5-7B 偶爾回簡體（約 1–2%，例如「我觉得这里比较脏」），Prompt 規定繁體也壓不到 0，
# 所以 say 顯示前再用小對照表轉一次。只收「一對一、不會轉錯」的常用字（像 里／后／发 這種有歧義的不轉）。
_S2T = dict(zip(
    "这们说个么吗还没为时样对来过请让会给话觉脏气语见听写难开关门边间问题东车实现经动当欢应该电机扫尘头声线较",
    "這們說個麼嗎還沒為時樣對來過請讓會給話覺髒氣語見聽寫難開關門邊間問題東車實現經動當歡應該電機掃塵頭聲線較"))
_S2T_PHRASES = {"干嘛": "幹嘛", "干什么": "幹什麼"}


def to_traditional(text):
    for s, t in _S2T_PHRASES.items():
        text = text.replace(s, t)
    return text.translate(str.maketrans(_S2T))


def _as_int(n):
    if isinstance(n, bool):
        return None
    if isinstance(n, str) and n.strip().isdigit():
        return int(n)
    if isinstance(n, float) and n.is_integer():
        return int(n)
    return n if isinstance(n, int) else None


def extract_json(text):
    if not text or not text.strip():
        raise ValueError("空白回覆")
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e <= s:
        raise ValueError("找不到 JSON 物件")
    return json.loads(t[s:e + 1])


def validate_output(obj):
    """回傳 (plan, errors)。plan = {"actions": [...], "say": "...", "emotion": ...}；只要有錯 plan 就是 None。"""
    if not isinstance(obj, dict):
        return None, ["最外層不是 JSON 物件"]
    acts = obj.get("actions")
    if not isinstance(acts, list):
        return None, ["缺少 actions 陣列"]
    errors, clean = [], []
    if len(acts) > MAX_ACTIONS:
        errors.append(f"動作太多（{len(acts)} > {MAX_ACTIONS}）")
    for i, a in enumerate(acts, 1):
        if not isinstance(a, dict) or "op" not in a:
            errors.append(f"第 {i} 個動作格式錯誤：{a!r}")
            continue
        op = a["op"]
        if op not in ACTION_WHITELIST:
            errors.append(f"不在選單內的動作：{op!r}")
            continue
        if op == "forward":
            n = _as_int(a.get("n"))
            if n is None or not 1 <= n <= MAX_FORWARD:
                errors.append(f"forward 的 n 不合法：{a.get('n')!r}")
                continue
            clean.append({"op": "forward", "n": n})
        elif op in REPEATABLE and "n" in a:
            # 實測 Qwen2.5-7B 常寫 {"op": "turn_right", "n": 2} 表示「轉兩次」。
            # 以前會默默丟掉 n（只轉一次），造成「向後轉」「往後走」大量失敗；意圖很明確，所以展開成重複動作。
            n = _as_int(a.get("n"))
            if n is None or not 1 <= n <= REPEATABLE[op]:
                errors.append(f"{op} 的 n 不合法：{a.get('n')!r}")
                continue
            clean += [{"op": op}] * n
        else:
            clean.append({"op": op})
    if errors:
        return None, errors
    say = obj.get("say", "")
    say = say if isinstance(say, str) else str(say)
    emotion = obj.get("emotion")
    emotion = emotion if emotion in EMOTIONS else None     # emotion 是選填，亂寫就忽略，不算格式錯誤
    return {"actions": clean, "say": to_traditional(say.strip()[:120]), "emotion": emotion}, []


def parse_reply(raw):
    """extract + validate；回傳 (plan, errors)。"""
    try:
        return validate_output(extract_json(raw))
    except (ValueError, json.JSONDecodeError) as exc:
        return None, [f"JSON 解析失敗：{exc}"]
