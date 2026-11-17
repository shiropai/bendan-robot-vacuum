"""離線測試用的規則式假模型 FakeLLM。

只看得懂簡單中文；賣蠢模式下會隨機左右顛倒、多走十倍、或吐出壞掉的 JSON。
也會「演」心情：鬧彆扭時頂嘴、被哄會撒嬌，讓沒有 API 的時候也能測完整的玩法。
"""
import json
import random
import re
import time

MAX_FORWARD = 30
CN_DIGITS = {"零": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
NUM_RE = r"([0-9]+|[一二兩三四五六七八九十]+)"


def cn_to_int(s):
    if s.isdigit():
        return int(s)
    if "十" in s:
        a, _, b = s.partition("十")
        return CN_DIGITS.get(a, 1) * 10 + CN_DIGITS.get(b, 0)
    return CN_DIGITS.get(s, 1)


def parse_simple_command(cmd):
    """超簡易中文指令解析（真正的理解交給 LLM）。"""
    acts = []
    for c in re.split(r"[，,。、；;！!]|然後|接著|之後|再", cmd):
        c = c.strip()
        if not c:
            continue
        if re.search(r"停|不要動|別動", c):
            acts.append({"op": "stop"})
        times = re.search(NUM_RE + r"\s*次", c)
        k = cn_to_int(times.group(1)) if times else 1
        if "吸" in c and not re.search(r"走|前進", c):
            acts += [{"op": "suck"}] * k
        if re.search(r"回充|充電|回家|回去", c):
            acts.append({"op": "return_home"})
            continue
        if re.search(r"向後轉|掉頭|迴轉|轉身|往後|向後|後退", c):
            acts += [{"op": "turn_right"}] * 2
        elif "左" in c:
            acts += [{"op": "turn_left"}] * (k if "轉" in c else 1)
        elif "右" in c:
            acts += [{"op": "turn_right"}] * (k if "轉" in c else 1)
        n = re.search(NUM_RE + r"\s*(格|步)", c)
        if n or re.search(r"前進|往前|走", c):
            acts.append({"op": "forward", "n": min(cn_to_int(n.group(1)) if n else 1, MAX_FORWARD)})
    return acts


class FakeLLM:
    SILLY = ["收到！不過我覺得那隻貓比地板還髒。", "好啦好啦，你說了算。", "先聲明，撞到不是我的錯。",
             "這個方向我有不同看法，但還是照做。", "掃地是我的天命！", "我覺得那邊比較髒。"]
    HAPPY = ["主人最好了～馬上去！", "嘿嘿，交給我！", "今天心情超好，地板會亮到反光！"]
    GRUMPY = ["……做就做嘛，兇什麼。", "哼，好啦。", "你剛剛那樣講我很受傷欸。"]
    REFUSE = ["哼！你說「請」我才要做。", "我不要。除非你跟我道歉。", "罷工中，請稍後再試。", "你剛剛罵我，我現在不想動。"]
    SWEET = ["嘿嘿，被誇了～", "好啦原諒你了！", "主人人真好 >///<"]
    SERIOUS = ["收到，開始執行。", "了解。", "好的。"]
    OOPS = ["哎呀，這不在我的計畫內……", "是那個東西先擋我的！", "沒事沒事，小意外。"]

    def __init__(self, seed=42, think_time=(0.3, 0.9)):
        self.rng = random.Random(seed)
        self.think_time = think_time

    def chat(self, messages, temperature=0.5):
        if self.think_time:
            time.sleep(self.rng.uniform(*self.think_time))      # 假裝在思考
        system = messages[0]["content"]
        silly = "笨笨" in system
        last = messages[-1]["content"]
        first = next(m["content"] for m in messages if m["role"] == "user")
        mood = re.search(r"【你的心情】\s*(\S+?)（", first)
        mood = mood.group(1) if mood else "普通"

        if "【執行結果】" in last:
            return self._out([], self.rng.choice(self.OOPS), "委屈")
        if "【你的決定】" in first:
            return self._out([], self.rng.choice(self.REFUSE), "生氣")

        m = re.search(r"【主人指令】\s*(.+)", first, re.S)
        cmd = m.group(1).strip() if m else first
        actions = parse_simple_command(cmd)
        if silly:
            pool = {"開心": self.HAPPY, "不爽": self.GRUMPY, "鬧彆扭": self.GRUMPY}.get(mood, self.SILLY)
            emotion = {"開心": "開心", "不爽": "委屈", "鬧彆扭": "生氣"}.get(mood, "得意")
        else:
            pool, emotion = self.SERIOUS, "普通"
        say = self.rng.choice(pool)
        if not actions and re.search(r"棒|乖|厲害|對不起|抱歉|謝謝|愛你", cmd):
            return self._out([], self.rng.choice(self.SWEET) if silly else "謝謝主人。", "開心")

        if silly and not last.startswith("你的回覆不符合格式"):
            r = self.rng.random()
            chaos = {"開心": 0.5, "不爽": 1.3, "鬧彆扭": 1.6}.get(mood, 1.0)   # 心情越差越容易出錯
            if r < 0.08 * chaos:
                return '嗯……我覺得應該先 {"actions": [{"op": "dance"}], "say": "跳支舞'   # 壞掉的 JSON
            if r < 0.20 * chaos:   # 左右搞反
                swap = {"turn_left": "turn_right", "turn_right": "turn_left"}
                if any(a["op"] in swap for a in actions):
                    actions = [dict(a, op=swap.get(a["op"], a["op"])) for a in actions]
                    say = "左右是相對的嘛～"
            elif r < 0.27 * chaos:  # 三格走成三十格
                if any(a["op"] == "forward" for a in actions):
                    actions = [dict(a, n=min(a["n"] * 10, MAX_FORWARD)) if a["op"] == "forward" else a
                               for a in actions]
                    say = "多走一點比較乾淨！"
        return self._out(actions, say, emotion)

    @staticmethod
    def _out(actions, say, emotion):
        return json.dumps({"actions": actions, "say": say, "emotion": emotion}, ensure_ascii=False)
