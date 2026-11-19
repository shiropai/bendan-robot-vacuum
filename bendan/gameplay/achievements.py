"""成就系統。每個成就是一個檢查函式，讀「這一關的統計」和「累積存檔」。

stats（單關）欄位：
    events: Counter（這關各種事件發生幾次）  tones: Counter（玩家語氣標籤）
    result: 結算 dict（見 scoring.finalize）  mood: Mood  bp: BloodPressure  level_id
totals（存檔累積）：Counter（跨關卡的事件總數）
"""

ACHIEVEMENTS = [
    {"id": "first_clear", "icon": "🎓", "name": "第一次上工", "desc": "第一次通關",
     "check": lambda s, t: s["result"]["cleared"]},
    {"id": "three_stars", "icon": "🌟", "name": "完美主人", "desc": "任一關拿到三顆星",
     "check": lambda s, t: s["result"]["stars"] == 3},
    {"id": "gentle", "icon": "🌸", "name": "溫柔的主人", "desc": "通關，而且全程沒罵過笨笨、也沒催它",
     "check": lambda s, t: s["result"]["cleared"] and not (s["tones"]["罵人"] or s["tones"]["催促"])},
    {"id": "coaxer", "icon": "🍬", "name": "哄哄就好", "desc": "把鬧彆扭的笨笨哄回開心",
     "check": lambda s, t: s["mood"].recovered_from_sulk},
    {"id": "one_liner", "icon": "🗣️", "name": "一句搞定", "desc": "只用 2 句以內的指令通關（至少 2 坨灰塵的關卡）",
     "check": lambda s, t: s["result"]["cleared"] and s["result"]["n_commands"] <= 2 and s["total_dirt"] >= 2},
    {"id": "combo3", "icon": "🔥", "name": "三連吸", "desc": "連擊達到 x3",
     "check": lambda s, t: s["result"]["best_combo"] >= 3},
    {"id": "cat_vacuum", "icon": "🐱", "name": "吸貓大師", "desc": "同一關吸到貓 2 次",
     "check": lambda s, t: s["events"]["sucked_cat"] >= 2},
    {"id": "lego_victim", "icon": "🧱", "name": "樂高受害者", "desc": "累積踩到 5 次樂高",
     "check": lambda s, t: t["lego"] >= 5},
    {"id": "poop_artist", "icon": "💩", "name": "抽象畫家", "desc": "把狗便便抹得滿地都是",
     "check": lambda s, t: s["events"]["smeared"] >= 1},
    {"id": "bp_max", "icon": "🤯", "name": "血壓爆表", "desc": "主人氣到昏倒",
     "check": lambda s, t: s["result"]["failed"] == "owner_faint"},
    {"id": "dead_battery", "icon": "🪫", "name": "沒電了啦", "desc": "電量歸零",
     "check": lambda s, t: s["result"]["failed"] == "out_of_battery"},
    {"id": "rebel", "icon": "🙅", "name": "叛逆期", "desc": "同一關被笨笨拒絕 3 次",
     "check": lambda s, t: s["events"]["refused"] >= 3},
    {"id": "daily", "icon": "📅", "name": "每日挑戰者", "desc": "通關「今日挑戰」",
     "check": lambda s, t: s["result"]["cleared"] and s["level_id"] == "daily"},
    {"id": "mother_in_law", "icon": "👵", "name": "婆婆滿意", "desc": "通關第 6 關「婆婆十分鐘後到」",
     "check": lambda s, t: s["result"]["cleared"] and s["level_id"] == 6},
    {"id": "tamer", "icon": "🦁", "name": "叛逆期馴獸師", "desc": "通關第 7 關「叛逆期」",
     "check": lambda s, t: s["result"]["cleared"] and s["level_id"] == 7},
    {"id": "goldfish", "icon": "🐟", "name": "金魚腦訓練師", "desc": "通關第 8 關「記憶體不足」",
     "check": lambda s, t: s["result"]["cleared"] and s["level_id"] == 8},
    {"id": "blackout", "icon": "🔦", "name": "摸黑掃地", "desc": "通關第 9 關「颱風夜停電」",
     "check": lambda s, t: s["result"]["cleared"] and s["level_id"] == 9},
    {"id": "graduate", "icon": "🏆", "name": "笨笨畢業了", "desc": "通關第 10 關「除夕大掃除」",
     "check": lambda s, t: s["result"]["cleared"] and s["level_id"] == 10},
    {"id": "quirk_veteran", "icon": "🙃", "name": "見怪不怪", "desc": "累積遇到 10 次笨笨恍神",
     "check": lambda s, t: t["quirk"] >= 10},
    # v8
    {"id": "boom", "icon": "💥", "name": "煙火秀", "desc": "笨笨爆炸了",
     "check": lambda s, t: s["result"]["failed"] == "exploded"},
    {"id": "unscathed", "icon": "🛡️", "name": "毫髮無傷", "desc": "第 3 關以後的關卡通關，而且笨笨一次都沒受損",
     "check": lambda s, t: (s["result"]["cleared"] and s["events"]["damaged"] == 0
                            and isinstance(s["level_id"], int) and s["level_id"] >= 3)},
    {"id": "pothole", "icon": "🕳️", "name": "掉坑專家", "desc": "掉進地洞",
     "check": lambda s, t: s["events"]["fell"] >= 1},
    {"id": "roach_hunter", "icon": "🪳", "name": "小強剋星", "desc": "吸到小強",
     "check": lambda s, t: s["events"]["caught_roach"] >= 1},
    {"id": "cat_taxi", "icon": "🚕", "name": "貓咪計程車", "desc": "載貓咪兜風",
     "check": lambda s, t: s["events"]["cat_ride"] >= 1},
    {"id": "mechanic", "icon": "🔧", "name": "黑手笨笨", "desc": "冒煙後撿維修包修好自己",
     "check": lambda s, t: s["events"]["repaired"] >= 1},
    {"id": "clutch_stop", "icon": "✋", "name": "神之煞車", "desc": "同一關按「停」3 次以上，而且通關",
     "check": lambda s, t: s["result"]["cleared"] and s["events"]["stopped"] >= 3},
]
BY_ID = {a["id"]: a for a in ACHIEVEMENTS}


def check_achievements(stats, totals, already=()):
    """回傳這次新解鎖的成就清單。"""
    new = []
    for a in ACHIEVEMENTS:
        if a["id"] in already:
            continue
        try:
            ok = a["check"](stats, totals)
        except (KeyError, TypeError):
            ok = False
        if ok:
            new.append(a)
    return new
