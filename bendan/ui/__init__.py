"""遊玩介面：文字模式 play()、即時模式 play_widgets()、終端機模式（scripts/play_cli.py）。"""
from .commands import COAX_LINES, HELP, change_level, handle_slash, next_level
from .text_mode import NotebookView, play, run_turn
from .widget_mode import WidgetGame, play_widgets

__all__ = ["COAX_LINES", "HELP", "NotebookView", "WidgetGame", "change_level", "handle_slash", "next_level", "play",
           "play_widgets", "run_turn"]
