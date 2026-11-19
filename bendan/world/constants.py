"""方向、地圖字元、物件分類與動作白名單。"""

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]        # 北、東、南、西（地圖 y 向下 = 南）
DIR_NAMES = ["北", "東", "南", "西"]
DIR_ARROWS = ["⬆", "➡", "⬇", "⬅"]                # 俯視圖上的方向（地圖上方 = 北）
START_FACING = {"^": 0, ">": 1, "v": 2, "<": 3}

# 地圖字元：
#   '#' 牆   '.' 地板   'D' 灰塵   'H' 充電座   '^ > v <' 機器人起點與朝向
#   'C' 貓（擋路、會亂跑）   'G' 狗（擋路、會亂跑、會大便）
#   'L' 樂高（踩到會痛）     'S' 襪子（吸到會卡住）   'W' 充電線（會纏住）
#   'P' 狗便便（輾過會抹得滿地都是）   'O' 水漬（踩到會滑一格；吸到會短路）
#   v8：'U' 地洞（掉下去會摔壞）  'B' 香蕉皮（踩到會打滑轉圈）  'K' 維修包（修好一次損傷）  'R' 蟑螂（會亂跑，吸到有獎勵）
#       'F' 家具（放大地圖時沿著牆擺，跟牆一樣擋路；名字在關卡設定的 "furniture"）
OBJECT_CHARS = {"C": "cat", "G": "dog", "L": "lego", "S": "sock", "W": "cable", "P": "poop", "O": "puddle",
                "U": "hole", "B": "banana", "K": "toolbox", "R": "roach"}
OBJECT_NAMES = {"cat": "貓", "dog": "狗", "lego": "樂高", "sock": "襪子", "cable": "充電線",
                "poop": "狗便便", "puddle": "水漬", "hole": "地洞", "banana": "香蕉皮", "toolbox": "維修包",
                "roach": "蟑螂"}
PETS = {"cat", "dog"}
BLOCKING_OBJECTS = {"cat", "dog"}                       # 走不過去
HAZARD_OBJECTS = {"lego", "cable", "poop", "puddle", "hole", "banana"}    # 走得過去，但會出事
AVOID_OBJECTS = HAZARD_OBJECTS | {"sock"}               # 自動導航時盡量避開
SUCK_BAD = {"sock", "puddle", "lego", "cable", "poop"}  # v8：吸到會受損
MAX_DAMAGE = 2       # v8：受損兩次＝爆炸（第一次冒煙）

ACTION_WHITELIST = {"forward", "drive", "turn_left", "turn_right", "stop", "suck", "vacuum_on", "vacuum_off",
                    "return_home"}
MAX_FORWARD = 60     # 「三格走成三十格」仍是合法格式，只是不聽話（v6 地圖放大 → 上限跟著加倍）
MOVE_OPS = {"forward", "drive", "return_home", "stop"}   # 會改變「要不要繼續開」的動作
MAX_ACTIONS = 12     # 一次最多幾個動作

# 電量消耗（每個微步驟）。v6 格子變小（地圖放大 2 倍）→ 走一格、吸一次的耗電減半
BATTERY_COST = {"move": 0.5, "turn": 0.2, "suck": 1.0, "vacuum": 0.25, "home": 0.0}
LOW_BATTERY_RATIO = 0.25

# 會讓動作中斷、需要回報給 LLM 的事件
INTERRUPT_EVENTS = {"collision", "lego", "tangled", "jammed", "sucked_cat", "sucked_dog", "entered_forbidden",
                    "no_path", "smeared", "suck_water", "doorbell", "out_of_battery", "damaged", "fell", "banana",
                    "sucked_bad", "quake"}

# 不顯示在事件列表的「安靜事件」（例如寵物換位置）
QUIET_EVENTS = {"pet_moved", "navigating", "roach_moved"}

KNOWN_ROOMS = ["客廳", "臥室", "廚房", "書房", "浴室"]
ROOM_ALIASES = {"房間": "臥室", "臥房": "臥室", "睡房": "臥室", "灶腳": "廚房", "工作室": "書房",
                "廁所": "浴室", "洗手間": "浴室"}


def E(type_, msg, **extra):
    """建立一個事件（遊戲端 → Agent / 玩法系統 的結構化回報）。"""
    return {"type": type_, "msg": msg, **extra}
