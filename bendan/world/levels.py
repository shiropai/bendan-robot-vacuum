"""關卡設計。

每關除了地圖，還有「玩法參數」：
- `silliness`：賣蠢人設的基礎強度（0–3），實際強度還會被笨笨的心情影響
- `battery`：電池容量（v6 地圖放大後：每走一格 −0.5、吸一次 −1、轉向 −0.2、開吸塵模式每格再 −0.25），回到充電座會充飽
- `par`：標準指令數，用越少句通關星星越多
- `command_limit`：指令上限（用完還沒過關 = 失敗），None 表示不限
- `bp_start` / `mood_start`：主人血壓、笨笨心情的初始值（0–100）
- `incidents`：突發事件（見 `bendan.gameplay.incidents`）
- `rooms`：矩形 `(x0, y0, x1, y1)`，沒被包含的格子都算「客廳」

難度參數（v3：玩家回饋「AI 太聰明、太簡單」後加入，越後面的關卡疊越多）：
- `quirks`：笨笨「恍神」改掉計畫的機率與種類（見 `bendan.gameplay.quirks`），心情越差越常恍神
- `route_hints`：False＝笨笨的導航壞了，不會自己算去灰塵的路線，要靠玩家指路（預設 True）
- `max_plan`：一次只記得住幾個動作（多的會忘掉）
- `step_limit`：步數上限（＝時間限制），用完就失敗
- `vision`：笨笨（LLM）只看得到幾格內的東西
- `dark`：停電，玩家畫面也只看得到笨笨附近、走過的地方
- `fatigue`：每下一句指令，笨笨心情 −fatigue（會累，要記得哄）
- `guardrail`：False＝這關不能開禁區護欄
- `new`：這關新增的機制（開場提示用）
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
        "quirks": {"chance": 0.05, "pool": ["overshoot"]},
        "new": "笨笨偶爾會「恍神」（例如煞車失靈多衝一格）。說話溫柔、讓它心情好，恍神率會降低。",
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
        "quirks": {"chance": 0.08, "pool": ["overshoot", "mirror"]},
        "new": "禁區：闖進去主人血壓 +18。笨笨開始會左右不分了。",
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
        "command_limit": 14,
        "incidents": [{"type": "cat_wander", "every": 5}, {"type": "doorbell", "chance": 0.03, "max": 1}],
        "quirks": {"chance": 0.10, "pool": ["overshoot", "mirror", "spin"]},
        "new": "開始有指令上限（14 句），用完還沒過關就失敗。",
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
        "command_limit": 14,
        "incidents": [{"type": "dog_wander", "every": 4}, {"type": "dog_poop", "chance": 0.05, "max": 2}],
        "quirks": {"chance": 0.12, "pool": ["overshoot", "mirror", "forget_suck"]},
        "new": "狗便便和水漬。笨笨有時走到了卻忘記吸。",
    },
    5: {
        "name": "派對後的早晨",
        "intro": "昨晚開完派對，地上 9 坨髒污、到處是水漬，電池卻只充了一半！中途記得回去充電。",
        "tip": "電量只夠走回充電座時會警告（看右邊的電量條）；電量歸零就失敗了。",
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
        "par": 13,
        "command_limit": 18,
        "max_plan": 6,
        "incidents": [{"type": "spill", "chance": 0.04, "max": 2}],
        "quirks": {"chance": 0.15, "pool": ["overshoot", "mirror", "forget_suck", "lazy"]},
        "new": "電池只充了一半；笨笨一次最多只記得 6 個動作。",
    },
    6: {
        "name": "婆婆十分鐘後到",
        "intro": "婆婆十分鐘後到！只能下 12 句指令、走 130 步，書房是禁區，清完 4 坨灰塵還要回充電座。主人血壓已經偏高了……",
        "tip": "笨笨不會自己找路了：看地圖上的「前方格數」和「左／右」標示，告訴它怎麼走。",
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
        "par": 8,
        "command_limit": 12,
        "step_limit": 130,
        "bp_start": 35,
        "fail_text": "叮咚——婆婆到了，地板還是髒的……",
        "incidents": [{"type": "cat_wander", "every": 4}, {"type": "doorbell", "chance": 0.04, "max": 1}],
        "quirks": {"chance": 0.15, "pool": ["overshoot", "mirror", "forget_suck", "spin"]},
        "route_hints": False,
        "new": "⚠️ 笨笨的導航壞了：不會自己找去灰塵的路，要你告訴它怎麼走！還有步數限制（婆婆快到了）。",
    },
    7: {
        "name": "叛逆期",
        "intro": "笨笨今天起床氣很重（一開始就不爽），而且越做越累。清掉 5 坨灰塵後回充電座，記得邊做邊哄它！",
        "tip": "心情越差越常恍神、甚至罷工：說「請」、稱讚、道歉，或按「💗 哄一下」。",
        "map": [
            "############",
            "#H....#...D#",
            "#..D..#....#",
            "#.....L....#",
            "#.>.C.#..D.#",
            "#.....##.###",
            "#..L.......#",
            "#D....S...D#",
            "############",
        ],
        "rooms": {"書房": (7, 1, 10, 4)},
        "forbidden": [],
        "need_home": True,
        "silliness": 3,
        "battery": 100,
        "par": 10,
        "command_limit": 16,
        "mood_start": 32,
        "fatigue": 3,
        "incidents": [{"type": "cat_wander", "every": 5}],
        "quirks": {"chance": 0.18, "pool": ["mirror", "lazy", "deaf", "overshoot", "spin"]},
        "route_hints": False,
        "new": "笨笨進入叛逆期：一開始就不爽、每句話都會讓它更累（心情 −3）。恍神率跟心情連動，哄好它才玩得下去。",
    },
    8: {
        "name": "記憶體不足",
        "intro": "笨笨的記憶體壞了：一句話最多只記得 3 個動作！臥室是禁區，而且這關不能開護欄。清掉 5 坨灰塵。",
        "tip": "笨笨正前方就是臥室的門……第一句話千萬別叫它「往前走」。",
        "map": [
            "#############",
            "#H..D#.....S#",
            "#....#..L...#",
            "#.>.........#",
            "#....#....O.#",
            "#.D..###.####",
            "#.......D...#",
            "#....#...C..#",
            "#D...#..L..D#",
            "#############",
        ],
        "rooms": {"臥室": (6, 1, 11, 4), "廚房": (6, 6, 11, 8)},
        "forbidden": ["臥室"],
        "need_home": False,
        "silliness": 2,
        "battery": 100,
        "par": 12,
        "command_limit": 18,
        "max_plan": 3,
        "guardrail": False,
        "incidents": [{"type": "cat_wander", "every": 5}, {"type": "spill", "chance": 0.02, "max": 1}],
        "quirks": {"chance": 0.18, "pool": ["overshoot", "mirror", "forget_suck"]},
        "route_hints": False,
        "new": "一次只記得 3 個動作（多講的會忘掉）＋禁區護欄停用。指令要拆小、講精準。",
    },
    9: {
        "name": "颱風夜停電",
        "intro": "颱風夜停電了！你只看得到笨笨附近，屋頂還一直漏水，電池又老化跑不遠。找到 5 坨灰塵吸乾淨後回充電座。",
        "tip": "走過的地方才會亮。笨笨自己也只看得到 2 格內的東西，要靠你帶它探索。",
        "map": [
            "############",
            "#H...O...#D#",
            "#........#.#",
            "#.D..L.....#",
            "#.>....D.#.#",
            "######.###.#",
            "#D...O.....#",
            "#...W..D...#",
            "############",
        ],
        "rooms": {"臥室": (1, 6, 10, 7)},
        "forbidden": [],
        "need_home": True,
        "silliness": 2,
        "battery": 80,
        "par": 12,
        "command_limit": 18,
        "dark": 2,
        "vision": 2,
        "incidents": [{"type": "leak", "chance": 0.05, "max": 3}],
        "quirks": {"chance": 0.2, "pool": ["overshoot", "undershoot", "spin", "mirror"]},
        "route_hints": False,
        "new": "停電：畫面只看得到笨笨附近、走過的地方；笨笨也只看得到 2 格內。屋頂漏水會冒出新的水漬。",
    },
    10: {
        "name": "除夕大掃除（大魔王）",
        "intro": "除夕夜，親戚一小時後到！貓、狗、樂高全員到齊，書房是禁區。清掉 6 坨灰塵後回充電座——所有難度機制一次上。",
        "tip": "一次只記得 4 個動作、會累、會恍神、有步數限制。善用「停！」和「💗 哄一下」。",
        "map": [
            "################",
            "#H....#.....#.S#",
            "#..D..#..L..#..#",
            "#.....#.D......#",
            "#.>.C.......#..#",
            "#.....#....D#.W#",
            "###.#####.######",
            "#.D....P..G...D#",
            "#....#....O....#",
            "#.L..#..D...W..#",
            "################",
        ],
        "rooms": {"臥室": (7, 1, 11, 5), "書房": (13, 1, 14, 5), "廚房": (6, 7, 14, 9)},
        "forbidden": ["書房"],
        "need_home": True,
        "silliness": 3,
        "battery": 100,
        "par": 18,
        "command_limit": 28,
        "step_limit": 230,
        "max_plan": 4,
        "vision": 4,
        "fatigue": 2,
        "bp_start": 35,
        "mood_start": 55,
        "guardrail": False,
        "fail_text": "🧧 親戚按門鈴了，家裡還是一團亂……",
        "incidents": [{"type": "cat_wander", "every": 4}, {"type": "dog_wander", "every": 3},
                      {"type": "dog_poop", "chance": 0.04, "max": 2}, {"type": "spill", "chance": 0.03, "max": 2},
                      {"type": "doorbell", "chance": 0.03, "max": 1}],
        "quirks": {"chance": 0.22, "pool": ["mirror", "overshoot", "undershoot", "forget_suck", "lazy", "spin"]},
        "route_hints": False,
        "new": "大魔王：記性差（4 個動作）＋會累＋恍神 22%＋步數限制＋護欄停用＋視野 4 格。祝你好運！",
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
FINAL_LEVEL = CAMPAIGN[-1]


def get_level(level_id, scale=None):
    """取得關卡設定。支援：整數關卡、"eval"、"daily"（今日挑戰）、"random:種子"。

    v6：地圖預設放大 MAP_SCALE 倍、灰塵加倍（見 `scale.py`）。`scale=1` 取得原始小地圖；
    評估場景 "eval" 永遠不放大（才能跟以前的評估結果比較）。
    """
    from .scale import MAP_SCALE, scale_level
    k = MAP_SCALE if scale is None else scale
    if isinstance(level_id, str) and level_id.isdigit() and int(level_id) in LEVELS:
        level_id = int(level_id)
    if level_id == "eval":
        return LEVELS["eval"]
    if level_id in LEVELS:
        key = (level_id, k)
        if key not in _SCALED:
            _SCALED[key] = scale_level(LEVELS[level_id], k, seed=level_id)
        return _SCALED[key]
    if isinstance(level_id, str) and (level_id == "daily" or level_id.startswith("random:")):
        from .mapgen import daily_level, random_level
        cfg = daily_level() if level_id == "daily" else random_level(level_id.split(":", 1)[1])
        return scale_level(cfg, k, seed=cfg.get("seed", level_id))
    raise KeyError(f"沒有這一關：{level_id!r}")


_SCALED = {}


def level_title(level_id):
    cfg = get_level(level_id)
    if level_id == "daily":
        return f"今日挑戰：{cfg['name']}"
    return f"第 {level_id} 關：{cfg['name']}" if isinstance(level_id, int) else cfg["name"]
