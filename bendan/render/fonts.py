"""matplotlib 圖表（評估報告）用的中文字型：伺服器有中文字型就用中文標籤，否則自動改用英文（避免豆腐字）。"""
from matplotlib import font_manager


def _pick_cjk_font():
    wanted = ["Noto Sans CJK TC", "Noto Sans TC", "Noto Sans CJK JP", "Noto Sans CJK SC", "PingFang TC",
              "Heiti TC", "Microsoft JhengHei", "Arial Unicode MS", "WenQuanYi Zen Hei", "Droid Sans Fallback"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    return next((n for n in wanted if n in have), None)


CJK_FONT = _pick_cjk_font()
FONT = CJK_FONT or "DejaVu Sans"


def L(zh, en):
    return zh if CJK_FONT else en
