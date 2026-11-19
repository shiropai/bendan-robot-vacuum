"""真實單位：遊戲邏輯仍然用格子算（碰撞、導航、灰塵都在格子上），但玩家和 LLM 看到的一律是公分／公尺。

尺寸（盡量貼近現實）：
- 1 格 = 50 公分（笨笨每走一步 50 公分；第 0 關的客廳約 7 × 5 公尺，第 10 關整間房子約 14 × 9.5 公尺）
- 笨笨直徑約 36 公分、高約 10 公分（3D 模型），牆高 2.4 公尺、門高 2 公尺
"""
import re

CELL_CM = 50


def to_cm(cells):
    return int(round(cells * CELL_CM))


def fmt_len(cells):
    """格數 → 「50 公分」「1 公尺」「1.5 公尺」。"""
    cm = to_cm(cells)
    if cm < 100:
        return f"{cm} 公分"
    m = cm / 100
    return f"{m:g} 公尺"


def cells_from_cm(cm):
    """公分 → 格數（四捨五入到 50 公分；正的距離至少走 1 步）。不合法回傳 None。"""
    try:
        cm = float(cm)
    except (TypeError, ValueError):
        return None
    if cm != cm or cm <= 0:
        return None
    return max(1, int(round(cm / CELL_CM)))


CN_DIGITS = {"零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_number(s):
    """「三」「十五」「1.5」「一百五十」→ 數字；認不得回傳 None。"""
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        pass
    if not s or any(c not in CN_DIGITS and c not in "十百點半" for c in s):
        return None
    total, cur = 0, 0
    frac = 0.0
    if "點" in s:
        s, dec = s.split("點", 1)
        frac = float("0." + "".join(str(CN_DIGITS.get(c, 0)) for c in dec)) if dec else 0.0
    if s.endswith("半"):
        frac, s = 0.5, s[:-1]
    for c in s:
        if c in CN_DIGITS:
            cur = CN_DIGITS[c]
        elif c == "十":
            total += (cur or 1) * 10
            cur = 0
        elif c == "百":
            total += (cur or 1) * 100
            cur = 0
    return total + cur + frac


LEN_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?|[零一二兩三四五六七八九十百點]+半?)\s*(公尺|米|公分|厘米|cm|m|格|步)", re.I)


def parse_length_cells(text):
    """從玩家的話抓距離 → 格數（「1.5 公尺」→3、「五十公分」→1、「三格」→3）。找不到回傳 None。"""
    m = LEN_RE.search(text)
    if not m:
        return None
    v = cn_number(m.group(1))
    if v is None:
        return None
    unit = m.group(2).lower()
    if unit in ("公尺", "米", "m"):
        return cells_from_cm(v * 100)
    if unit in ("公分", "厘米", "cm"):
        return cells_from_cm(v)
    return max(1, int(round(v)))          # 格、步：一步 = 50 公分
