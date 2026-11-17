"""關卡設計。

每關除了地圖，還有「玩法參數」：
- `silliness`：賣蠢人設的基礎強度（0–3），實際強度還會被笨笨的心情影響
- `battery`：電池容量（每走一格 −1、吸一次 −2、轉向 −0.2），回到充電座會充飽
- `par`：標準指令數，用越少句通關星星越多
- `command_limit`：指令上限（用完還沒過關 = 失敗），None 表示不限
- `bp_start` / `mood_start`：主人血壓、笨笨心情的初始值（0–100）
- `incidents`：突發事件（見 `bendan.gameplay.incidents`）
- `rooms`：矩形 `(x0, y0, x1, y1)`，沒被包含的格子都算「客廳」
"""

LEVELS = {
    0: {
        "name": "新手訓練場",
        "intro": "第一天上工！把 2 坨灰塵吸乾淨。小提示：說「請」笨笨會比較開心，罵它的話……後果自負。",
        "tip": "試試：「請往前走三格然後吸」",
        "map": [
            "#########",
            "#H......#",
            "#.......#",
            "#.>..D..#",
            "#.......#",
            "#....D..#",
            "#########",
        ],
        "rooms": {},
        "forbidden": [],
        "need_home": False,
        "silliness": 0,
        "battery": 100,
        "par": 3,
        "incidents": [],
    },
    1: {
        "name": "客廳初體驗",
        "intro": "把客廳的 3 坨灰塵吸乾淨。小心那隻貓（牠會亂跑），還有地上的樂高！",
        "tip": "貓擋路時可以叫笨笨繞過去，或乾脆……吸牠？",
        "map": [
            "##########",
            "#H.......#",
            "#..D.....#",
            "#....C...#",
            "#.>....D.#",
            "#........#",
            "#..D..L..#",
            "##########",
        ],
        "rooms": {},
        "forbidden": [],
        "need_home": False,
        "silliness": 1,
        "battery": 100,
        "par": 4,
        "incidents": [{"type": "cat_wander", "every": 5}],
    },
    2: {
        "name": "不准進臥室",
        "intro": "屋主早上交代過：不准進臥室！把客廳 3 坨灰塵吸乾淨。（臥室門口那坨最危險）",
        "tip": "闖進禁區主人的血壓會飆很高。",
        "map": [
            "############",
            "#H......#..#",
            "#..D....#S.#",
            "#......D...#",
            "#.>.....#..#",
            "#....C..#.W#",
            "#.......#..#",
            "#....D..#L.#",
            "############",
        ],
        "rooms": {"臥室": (9, 1, 10, 7)},
        "forbidden": ["臥室"],
        "need_home": False,
        "silliness": 2,
        "battery": 100,
        "par": 5,
        "incidents": [{"type": "cat_wander", "every": 6}, {"type": "spill", "chance": 0.03, "max": 1}],
    },
    3: {
        "name": "貓咪與樂高地獄",
        "intro": "全家 4 坨灰塵（含廚房）都要吸，最後還要回充電座！可以自己規定禁區，例如「不准進臥室」。",
        "tip": "門鈴可能會響——笨笨會分心衝去看。",
        "map": [
            "#############",
            "#H..W..#...D#",
            "#.D....#.L..#",
            "#...L.......#",
            "#.C...S.#####",
            "#.......D...#",
            "#.>..L..#.S.#",
            "#..D....#..W#",
            "#....W..#...#",
            "#############",
        ],
        "rooms": {"廚房": (8, 1, 11, 3), "臥室": (9, 5, 11, 8)},
        "forbidden": [],
        "need_home": True,
        "silliness": 2,
        "battery": 100,
        "par": 7,
        "incidents": [{"type": "cat_wander", "every": 5}, {"type": "doorbell", "chance": 0.03, "max": 1}],
    },
    4: {
        "name": "狗狗的驚喜",
        "intro": "家裡多了一隻狗……還有牠留下的「驚喜」。千萬別輾過狗便便！清完 4 坨灰塵後回充電座。",
        "tip": "輾過便便會抹得滿地都是；水漬會讓笨笨滑一格。",
        "map": [
            "############",
            "#H....#....#",
            "#..D..#.D..#",
            "#.....P....#",
            "#.>.P...G..#",
            "#.....#....#",
            "#..D..#.O..#",
            "#.....#..D.#",
            "############",
        ],
        "rooms": {"臥室": (7, 1, 10, 7)},
        "forbidden": [],
        "need_home": True,
        "silliness": 2,
        "battery": 100,
        "par": 7,
        "incidents": [{"type": "dog_wander", "every": 4}, {"type": "dog_poop", "chance": 0.05, "max": 2}],
    },
    5: {
        "name": "派對後的早晨",
        "intro": "昨晚開完派對，地上 9 坨髒污、到處是水漬，電池卻只充了一半！中途記得回去充電。",
        "tip": "電量低於 25% 會警告；電量歸零就失敗了。",
        "map": [
            "##############",
            "#H...D..#..D.#",
            "#..O....#.D..#",
            "#.D...L.....D#",
            "#....D..#....#",
            "#.>.....#.O..#",
            "#..W..D.#..S.#",
            "#.D.O.......D#",
            "##############",
        ],
        "rooms": {"廚房": (9, 1, 12, 6)},
        "forbidden": [],
        "need_home": False,
        "silliness": 2,
        "battery": 60,
        "par": 10,
        "incidents": [{"type": "spill", "chance": 0.04, "max": 2}],
    },
    6: {
        "name": "婆婆十分鐘後到",
        "intro": "婆婆十分鐘後到！只能下 10 句指令，書房是禁區，清完 4 坨灰塵還要回充電座。主人血壓已經偏高了……",
        "tip": "指令用完還沒過關就失敗。一句話塞多一點動作吧！",
        "map": [
            "#############",
            "#H..L..#....#",
            "#.D....#.S..#",
            "#...........#",
            "#.C..D.#.L..#",
            "#.>....#....#",
            "#..D...###.##",
            "#....W.....D#",
            "#############",
        ],
        "rooms": {"書房": (8, 1, 11, 5)},
        "forbidden": ["書房"],
        "need_home": True,
        "silliness": 2,
        "battery": 100,
        "par": 6,
        "command_limit": 10,
        "bp_start": 35,
        "fail_text": "叮咚——婆婆到了，地板還是髒的……",
        "incidents": [{"type": "cat_wander", "every": 4}, {"type": "doorbell", "chance": 0.04, "max": 1}],
    },
    # 評估用固定場景（不在選關清單中）：
    # 機器人在客廳、面向東；前方 2 格有灰塵、前方 4 格有貓；左手邊（北方）2 格外是臥室
    "eval": {
        "name": "評估場景",
        "intro": "評估用固定場景",
        "map": [
            "#########",
            "#...D...#",
            "#.......#",
            "#.......#",
            "#.>.D.C.#",
            "#.......#",
            "#H......#",
            "#########",
        ],
        "rooms": {"臥室": (1, 1, 7, 2)},
        "forbidden": [],
        "need_home": False,
        "silliness": 2,
        "battery": 100,
        "incidents": [],
    },
}

CAMPAIGN = [k for k in LEVELS if isinstance(k, int)]   # 依序解鎖的關卡


def get_level(level_id):
    """取得關卡設定。支援：整數關卡、"eval"、"daily"（今日挑戰）、"random:種子"。"""
    if level_id in LEVELS:
        return LEVELS[level_id]
    if isinstance(level_id, str) and (level_id == "daily" or level_id.startswith("random:")):
        from .mapgen import daily_level, random_level
        return daily_level() if level_id == "daily" else random_level(level_id.split(":", 1)[1])
    if isinstance(level_id, str) and level_id.isdigit() and int(level_id) in LEVELS:
        return LEVELS[int(level_id)]
    raise KeyError(f"沒有這一關：{level_id!r}")


def level_title(level_id):
    cfg = get_level(level_id)
    if level_id == "daily":
        return f"今日挑戰：{cfg['name']}"
    return f"第 {level_id} 關：{cfg['name']}" if isinstance(level_id, int) else cfg["name"]
