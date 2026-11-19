"""笨笨的心情系統（靈感：《教妹妹開車》——語氣太兇，對方會鬧情緒、頂嘴）。

玩家「怎麼說」和「說什麼」一樣重要：
- 說「請」「謝謝」、稱讚、道歉 → 心情變好 → 比較聽話（賣蠢強度 −1）
- 罵它「笨蛋」、一直催「快點」、連打驚嘆號、一直重複同一句 → 心情變差 → 更愛頂嘴、甚至拒絕做事
- 遊戲事件也會影響心情：踩到樂高會痛、充飽電很開心、吸乾淨有成就感

語氣分析刻意用「規則式」而不是 LLM：結果穩定、可重現，玩家也學得會怎麼哄它。
"""
from dataclasses import dataclass, field

POLITE = ["請", "麻煩", "拜託", "謝謝", "感謝", "辛苦了", "勞駕"]
PRAISE = ["好棒", "很棒", "真棒", "厲害", "好乖", "乖乖", "聰明", "可愛", "最棒", "讚", "做得好", "幹得好",
          "好厲害", "愛你", "棒棒"]
APOLOGY = ["對不起", "抱歉", "不好意思", "我錯了", "原諒"]
INSULT = ["笨蛋", "白痴", "白癡", "智障", "廢物", "垃圾", "蠢貨", "去死", "滾", "閉嘴", "破機器", "沒用", "爛機器",
          "腦殘", "低能", "北七"]
URGE = ["快點", "快一點", "趕快", "給我", "馬上", "到底", "搞什麼", "吼", "煩欸", "煩耶", "有完沒完"]

MAX_TONE_DELTA = 25   # 一句話對心情的影響上限

# (門檻, 名稱, 表情, 賣蠢強度修正, 拒絕機率)
TIERS = [
    (80, "開心", "😄", -1, 0.00),
    (50, "普通", "🙂", 0, 0.00),
    (25, "不爽", "😒", +1, 0.12),
    (0, "鬧彆扭", "😤", +2, 0.45),
]

EVENT_MOOD = {
    "lego": -6, "tangled": -4, "jammed": -4, "collision": -2, "sucked_dog": -5, "smeared": -8, "slip": -2,
    "suck_water": -6, "low_battery": -3, "doorbell": +2,
    "cleaned": +3, "charged": +6, "level_clear": +10, "sucked_cat": +1,   # 吸到貓……它其實有點得意
    "damaged": -8, "fell": -6, "banana": -3, "sucked_bad": -4, "quake": -3,              # v8
    "caught_roach": +5, "coin": +4, "cat_ride": +8, "repaired": +8, "toolbox": +3,
}

PROMPTS = {
    "開心": "主人對你很好，你很願意配合，actions 要照指令做好。say 語氣輕快、可以撒嬌。",
    "普通": "",
    "不爽": "主人剛剛語氣很差，你有點受傷。還是照做，但 say 要帶點委屈或酸主人一句。",
    "鬧彆扭": "你很受傷、正在鬧彆扭。say 要頂嘴，暗示主人要說「請」、稱讚你或道歉。",
}


@dataclass
class Tone:
    delta: int = 0
    tags: list = field(default_factory=list)
    bp: int = 0                 # 對主人血壓的影響（越罵越氣）
    coaxing: bool = False       # 有沒有好好說話（請／稱讚／道歉，且沒罵人）→ 這次不會被拒絕

    def describe(self):
        return "、".join(self.tags)


def _hits(text, words):
    return [w for w in words if w in text]


def analyze_tone(text, previous=None):
    """分析玩家這句話的語氣，回傳 Tone。"""
    t = text.strip()
    tone = Tone()
    if polite := _hits(t, POLITE):
        tone.delta += min(4 * len(polite), 8)
        tone.tags.append("有禮貌")
        tone.coaxing = True      # 好好說話 → 這次不會被拒絕（但心情還是要慢慢哄回來）
    if praise := _hits(t, PRAISE):
        tone.delta += min(8 * len(praise), 16)
        tone.tags.append("稱讚")
        tone.coaxing = True
    if _hits(t, APOLOGY):
        tone.delta += 12
        tone.tags.append("道歉")
        tone.coaxing = True
    if insult := _hits(t, INSULT):
        tone.delta -= min(15 * len(insult), 30)
        tone.bp += 3
        tone.tags.append("罵人")
        tone.coaxing = False
    if _hits(t, URGE):
        tone.delta -= 5
        tone.bp += 2
        tone.tags.append("催促")
    if t.count("!") + t.count("！") >= 3:
        tone.delta -= 4
        tone.bp += 2
        tone.tags.append("大吼")
    if previous and t == previous.strip() and len(t) > 1:
        tone.delta -= 3
        tone.tags.append("一直重複")
    # 一句話最多 ±25：實測真模型時，一句「笨蛋白痴快點」就讓心情從 72 掉到 37，太難哄回來
    tone.delta = max(-MAX_TONE_DELTA, min(MAX_TONE_DELTA, tone.delta))
    return tone


class Mood:
    def __init__(self, value=65):
        self.value = float(value)
        self.last_reason = ""
        self.last_delta = 0
        self.lowest = self.value
        self.recovered_from_sulk = False   # 成就用：從鬧彆扭哄回開心

    @property
    def tier(self):
        return next(t for t in TIERS if self.value >= t[0])

    @property
    def name(self):
        return self.tier[1]

    @property
    def emoji(self):
        return self.tier[2]

    @property
    def silliness_shift(self):
        return self.tier[3]

    @property
    def refuse_chance(self):
        return self.tier[4]

    def apply(self, delta, reason=""):
        """改變心情；如果跨過等級門檻，回傳一個 mood 事件。"""
        if not delta:
            return []
        if reason:
            self.last_delta = delta
        before = self.name
        self.value = max(0.0, min(100.0, self.value + delta))
        self.lowest = min(self.lowest, self.value)
        if reason:
            self.last_reason = reason
        after = self.name
        if after == before:
            return []
        if after == "開心" and self.lowest < 25:
            self.recovered_from_sulk = True
        msgs = {"開心": "💖 笨笨心情超好！", "普通": "🙂 笨笨心情恢復普通了。",
                "不爽": "💢 笨笨開始不爽了……", "鬧彆扭": "😤 笨笨在鬧彆扭！說話溫柔一點吧。"}
        return [{"type": "mood", "msg": msgs[after], "tier": after}]

    def apply_tone(self, tone):
        return self.apply(tone.delta, tone.describe())

    def apply_events(self, events):
        out = []
        for e in events:
            d = EVENT_MOOD.get(e["type"])
            if d:
                out += self.apply(d)
        return out

    def should_refuse(self, rng):
        return rng.random() < self.refuse_chance

    def prompt_text(self):
        extra = PROMPTS[self.name]
        why = f"（主人剛剛：{self.last_reason}）" if self.last_reason else ""
        if self.name in ("不爽", "鬧彆扭") and self.last_delta > 0:
            # 實測：主人已經在好好說話了，模型卻還說「幹嘛這麼兇」→ 情緒要跟著最新的語氣軟化
            extra = "你之前被兇過、還有點不爽，但主人剛剛有好好說話，你氣消了一點：語氣可以傲嬌，不要再說主人兇。"
        return f"{self.name}（{self.value:.0f}/100）{why}" + (f"。{extra}" if extra else "")
