"""笨笨掃地機 — 以 LLM 為大腦、會「賣蠢」的 2.5D 掃地機器人指令遊戲。

套件結構（遊戲端與 Agent 只透過結構化資料溝通：Agent 給「動作清單」，遊戲回「事件清單」）：

    bendan/
    ├── config.py        路徑與設定
    ├── llm/             課程 API client、離線 FakeLLM
    ├── world/           遊戲世界：地圖、引擎、關卡、隨機地圖
    ├── agent/           大腦：Prompt、世界描述、記憶、JSON 解析驗證
    ├── gameplay/        玩法：心情、血壓、計分、突發事件、成就、存檔
    ├── session.py       Agent 迴圈＋玩法系統＋非同步＋Log
    ├── render/          等角 2.5D 畫面、HUD、純文字地圖
    ├── ui/              文字模式、即時模式（ipywidgets）
    └── evaluation/      照做率、格式正確率、記憶遵守率、心情實驗

最快開始：
    from bendan import llm, play
    llm.connect()
    play(level=0)
"""
from . import config, llm
from .session import Session

__version__ = "2.0.0"


PACKAGES = {"openai": "連線課程 LLM", "matplotlib": "2.5D 畫面、評估圖表", "pandas": "評估",
            "ipywidgets": "即時模式"}


def check_env(verbose=True):
    """檢查這個 Kernel 有沒有需要的套件和 API 設定。

    實測課程 JupyterHub：「Python (Lab 1)」只有 openai，沒有 matplotlib／pandas／ipywidgets；
    「Python 3 (ipykernel)」全部都有 → 建議用 Python 3 (ipykernel)。
    """
    import importlib.util
    import os
    missing = [m for m in PACKAGES if importlib.util.find_spec(m) is None]
    api = bool(os.getenv("OPENAI_BASE_URL") and os.getenv("OPENAI_API_KEY"))
    if verbose:
        for m, use in PACKAGES.items():
            print(f"{'✅' if m not in missing else '❌'} {m:<11} {use}")
        print(f"{'✅' if api else '⚠️'} API 設定    {'已找到 OPENAI_BASE_URL / OPENAI_API_KEY' if api else '找不到 → 會改用離線 FakeLLM'}")
        if missing:
            print("\n👉 缺少套件：在課程 JupyterHub 請把 Kernel 換成「Python 3 (ipykernel)」"
                  "（右上角的 Kernel 名稱 → 選擇），它已經裝好全部套件。"
                  + ("沒有 matplotlib 時遊戲會改用 emoji 文字地圖。" if "matplotlib" in missing else ""))
    return {"missing": missing, "api": api}


def play(*args, **kwargs):
    from .ui import play as _play
    return _play(*args, **kwargs)


def play_widgets(*args, **kwargs):
    from .ui import play_widgets as _pw
    return _pw(*args, **kwargs)


__all__ = ["Session", "check_env", "config", "llm", "play", "play_widgets"]
