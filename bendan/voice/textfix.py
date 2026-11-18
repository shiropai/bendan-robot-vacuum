"""語音辨識結果的清理：簡轉繁、遊戲用語的同音字修正、過濾 Whisper 的幻覺句。

Whisper 對中文常見的問題：
- 輸出簡體字（就算指定 language="zh"）→ 有 OpenCC 就用 s2twp（台灣用語），沒有就用內建小對照表
- 同音字：「做轉」「有轉」「往錢」「然後西」→ 依遊戲用語修正（只修在指令裡幾乎不可能是原意的組合）
- 沒講話或雜音時會「幻覺」出影片字幕常見句（「請不吝點贊訂閱」「謝謝觀看」）→ 整句丟掉
"""
import re

from ..agent.parsing import to_traditional

try:                                     # 選用：pip install opencc-python-reimplemented
    from opencc import OpenCC
    _OPENCC = OpenCC("s2twp")
except Exception:                        # noqa: BLE001 — 沒裝就用內建對照表
    _OPENCC = None

# 內建對照表不夠時補的常用字（遊戲指令會用到的）
_EXTRA_S2T = str.maketrans(dict(zip("转进后吸厅卧厨书禁准尘脏猫狗乐积袜线门铃脑笨乱冲坐别让请谢对现处还边转马给",
                                     "轉進後吸廳臥廚書禁准塵髒貓狗樂積襪線門鈴腦笨亂沖坐別讓請謝對現處還邊轉馬給")))

HOMOPHONES = [
    (r"[做作佐坐]轉", "左轉"),
    (r"[有又幼祐]轉", "右轉"),
    (r"往[錢潛乾]", "往前"),
    (r"[前錢][盡近晉]", "前進"),
    (r"(然後|再|去|就|開|幫我|順便|過去|馬上)[西洗息惜溪]", r"\1吸"),
    (r"回[沖衝]", "回充"),
    (r"充電[做作坐]", "充電座"),
    (r"[本奔][本奔笨]|笨[本奔]", "笨笨"),
    (r"臥[式是事適]", "臥室"),
    (r"進入室(?!內|外)", "進臥室"),                 # 實測：大吼時聲音爆掉，「臥室」常被聽成「入室」
    (r"[停聽亭]下來", "停下來"),
    # 實測：Whisper 原本就輸出「不准」，OpenCC（s2twp）卻把「准」轉成「準」→ 禁區規則就認不出來了
    (r"(不|批|允)準", r"\1准"),
    (r"準(許|進|你)", r"准\1"),
]

HALLUCINATIONS = ["點贊", "點讚", "訂閱", "字幕", "謝謝觀看", "感謝觀看", "感謝收看", "明鏡與點點", "Amara",
                  "thank you for watching", "優優獨播", "請不吝"]


def to_trad(text):
    if _OPENCC is not None:
        return _OPENCC.convert(text)
    return to_traditional(text).translate(_EXTRA_S2T)


def is_hallucination(text):
    low = text.lower()
    return any(h.lower() in low for h in HALLUCINATIONS)


def clean_transcript(text):
    """回傳清理後的指令文字；空字串代表「沒聽到有意義的話」。"""
    t = to_trad((text or "").strip())
    t = re.sub(r"\s+", "", t)                      # 中文不需要空白（Whisper 常在詞之間加空格）
    if not t or is_hallucination(t):
        return ""
    for pat, rep in HOMOPHONES:
        t = re.sub(pat, rep, t)
    return t.strip("。.，, ")
