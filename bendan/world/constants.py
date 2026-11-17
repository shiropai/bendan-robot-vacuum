"""方向、地圖字元、物件分類與動作白名單。"""

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]        # 北、東、南、西（地圖 y 向下 = 南）
DIR_NAMES = ["北", "東", "南", "西"]
START_FACING = {"^": 0, ">": 1, "v": 2, "<": 3}

# 地圖字元：
#   '#' 牆   '.' 地板   'D' 灰塵   'H' 充電座   '^ > v <' 機器人起點與朝向
#   'C' 貓（擋路、會亂跑）   'G' 狗（擋路、會亂跑、會大便）
#   'L' 樂高（踩到會痛）     'S' 襪子（吸到會卡住）   'W' 充電線（會纏住）
#   'P' 狗便便（輾過會抹得滿地都是）   'O' 水漬（踩到會滑一格；吸到會短路）
OBJECT_CHARS = {"C": "cat", "G": "dog", "L": "lego", "S": "sock", "W": "cable", "P": "poop", "O": "puddle"}
OBJECT_NAMES = {"cat": "貓", "dog": "狗", "lego": "樂高", "sock": "襪子", "cable": "充電線",
                "poop": "狗便便", "puddle": "水漬"}
PETS = {"cat", "dog"}
BLOCKING_OBJECTS = {"cat", "dog"}                       # 走不過去
HAZARD_OBJECTS = {"lego", "cable", "poop", "puddle"}    # 走得過去，但會出事
AVOID_OBJECTS = HAZARD_OBJECTS | {"sock"}               # 自動導航時盡量避開

ACTION_WHITELIST = {"forward", "turn_left", "turn_right", "stop", "suck", "return_home"}
MAX_FORWARD = 30     # 「三格走成三十格」仍是合法格式，只是不聽話
MAX_ACTIONS = 12     # 一次最多幾個動作

# 電量消耗（每個微步驟）
BATTERY_COST = {"move": 1.0, "turn": 0.2, "suck": 2.0, "home": 0.0}
LOW_BATTERY_RATIO = 0.25

# 會讓動作中斷、需要回報給 LLM 的事件
INTERRUPT_EVENTS = {"collision", "lego", "tangled", "jammed", "sucked_cat", "sucked_dog", "entered_forbidden",
                    "no_path", "smeared", "suck_water", "doorbell", "out_of_battery"}

# 不顯示在事件列表的「安靜事件」（例如寵物換位置）
QUIET_EVENTS = {"pet_moved", "navigating"}

KNOWN_ROOMS = ["客廳", "臥室", "廚房", "書房", "浴室"]
ROOM_ALIASES = {"房間": "臥室", "臥房": "臥室", "睡房": "臥室", "灶腳": "廚房", "工作室": "書房",
                "廁所": "浴室", "洗手間": "浴室"}


def E(type_, msg, **extra):
    """建立一個事件（遊戲端 → Agent / 玩法系統 的結構化回報）。"""
    return {"type": type_, "msg": msg, **extra}
