"""語音輸入：瀏覽器錄音 → Whisper 語音轉文字 → 清理 → 當成玩家指令。

只有在「安全來源」（https 或 localhost）瀏覽器才給麥克風；課程 JupyterHub 是 http，所以這個功能要在自己電腦上跑
（見 docs/voice_input.md）。
"""
from .audio import Clip, decode_wav, make_wav
from .stt import (INITIAL_PROMPT, STATE, APIBackend, FakeBackend, Transcript, connect_stt, stt_label,
                  transcribe)
from .textfix import clean_transcript

__all__ = ["APIBackend", "Clip", "FakeBackend", "INITIAL_PROMPT", "STATE", "Transcript", "clean_transcript",
           "connect_stt", "decode_wav", "make_wav", "stt_label", "transcribe"]
