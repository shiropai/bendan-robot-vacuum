"""語音轉文字（Speech-to-Text）：Whisper，三種跑法自動挑一種。

| 後端 | 什麼時候用 | 安裝 |
|---|---|---|
| `api`   | 設了 `BENDAN_STT_URL`（OpenAI 相容的 `/v1/audio/transcriptions`，例如自架的 Whisper 服務） | `openai` |
| `mlx`   | Apple Silicon Mac（M1～M4），最快 | `pip install mlx-whisper` |
| `faster`| 其他電腦（Windows／Linux／Intel Mac），CPU 也能跑 | `pip install faster-whisper` |

    from bendan import voice
    voice.connect_stt()                       # 自動挑後端（找不到就回傳 None → 遊戲改用瀏覽器語音辨識或電腦聽寫）
    voice.transcribe(wav_bytes)              # → Transcript(text="請往前走三格然後吸", shout=False, ...)

環境變數：
- `BENDAN_STT_URL`、`BENDAN_STT_KEY`（沒設就用 `OPENAI_API_KEY`）、`BENDAN_STT_MODEL`（預設 whisper-1）
- `BENDAN_WHISPER_MODEL`：本機模型。Apple Silicon 預設 `mlx-community/whisper-large-v3-turbo`（約 1.6 GB，中文準、M 系列晶片一句不到 1 秒）；
  記憶體小可改 `mlx-community/whisper-small-mlx`。faster-whisper 預設 `small`。
- `BENDAN_STT=off` 關掉語音。
"""
import os
import platform
import threading
import time
from dataclasses import dataclass, field

from .audio import decode_wav
from .textfix import clean_transcript

# 給 Whisper 的提示句：用繁體中文、而且是遊戲常用詞 → 輸出比較會是繁體、也比較會選對同音字
INITIAL_PROMPT = ("以下是對掃地機器人笨笨下的中文指令：請往前走一公尺，往前五十公分，左轉，右轉，向後轉，然後吸。停！回充電座。"
                  "不准進臥室、廚房、書房。繞過那隻貓。對不起，你好棒，謝謝。")


@dataclass
class Transcript:
    text: str                       # 清理後的指令（空字串＝沒聽到有意義的話）
    raw: str = ""                   # Whisper 原始輸出
    shout: bool = False             # 用吼的
    seconds: float = 0.0            # 錄音長度
    latency: float = 0.0            # 辨識花了幾秒
    backend: str = ""
    note: str = ""                  # 沒有結果時的原因（太短、太小聲……）
    meta: dict = field(default_factory=dict)


def _prefer_plain_download():
    """第一次下載模型時用一般 HTTP，不用 Hugging Face 新的 Xet 傳輸。

    實測（2026-11）：Xet 的 CDN 連不上時會直接報 `CAS Client Error`、模型下載失敗；一般 HTTP 下載沒問題。
    要在 huggingface_hub 被 import 之前設定才有效；使用者自己設過就不動。
    """
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")


class _Backend:
    name = "?"
    label = "?"

    def warmup(self):
        pass

    def run(self, clip):            # → 原始文字
        raise NotImplementedError


class APIBackend(_Backend):
    name = "api"

    def __init__(self, base_url, api_key, model="whisper-1"):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key or "none", timeout=60.0)
        self.model = model
        self.label = f"Whisper API（{model}）"

    def run(self, clip):
        r = self.client.audio.transcriptions.create(model=self.model, file=("speech.wav", clip.to_wav_bytes()),
                                                    language="zh", prompt=INITIAL_PROMPT)
        return r.text


class MLXBackend(_Backend):
    name = "mlx"
    DEFAULT = "mlx-community/whisper-large-v3-turbo"

    def __init__(self, model=None):
        _prefer_plain_download()
        import mlx_whisper
        self.mlx_whisper = mlx_whisper
        self.model = model or os.getenv("BENDAN_WHISPER_MODEL") or self.DEFAULT
        self.label = f"Whisper（本機 MLX：{self.model.split('/')[-1]}）"

    def warmup(self):                # 第一次會下載模型；先跑一次 0.5 秒的靜音
        import numpy as np
        self.mlx_whisper.transcribe(np.zeros(8000, dtype=np.float32), path_or_hf_repo=self.model, language="zh")

    def run(self, clip):
        out = self.mlx_whisper.transcribe(clip.to_float32(), path_or_hf_repo=self.model, language="zh",
                                          initial_prompt=INITIAL_PROMPT, condition_on_previous_text=False,
                                          temperature=0.0)
        return out.get("text", "")


class FasterWhisperBackend(_Backend):
    name = "faster"

    def __init__(self, model=None):
        _prefer_plain_download()
        from faster_whisper import WhisperModel
        self.model_name = model or os.getenv("BENDAN_WHISPER_MODEL") or "small"
        self.model = WhisperModel(self.model_name, device="auto", compute_type="int8")
        self.label = f"Whisper（本機 faster-whisper：{self.model_name}）"

    def run(self, clip):
        segments, _ = self.model.transcribe(clip.to_float32(), language="zh", initial_prompt=INITIAL_PROMPT,
                                            vad_filter=True, beam_size=5, temperature=0.0)
        return "".join(s.text for s in segments)


class FakeBackend(_Backend):
    """測試用：不管聽到什麼都回傳固定文字（或依序回傳清單）。"""
    name = "fake"
    label = "FakeSTT（測試）"

    def __init__(self, replies=("請往前走三格然後吸",)):
        self.replies = list(replies)
        self.i = 0

    def run(self, clip):
        text = self.replies[min(self.i, len(self.replies) - 1)]
        self.i += 1
        return text


class STTState:
    def __init__(self):
        self.backend = None
        self.error = ""
        self.ready = threading.Event()
        self.lock = threading.Lock()


STATE = STTState()


def _is_apple_silicon():
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def connect_stt(backend="auto", model=None, warmup=True, verbose=True):
    """挑一個語音辨識後端。回傳後端物件；都沒有就回傳 None（遊戲會改用瀏覽器語音辨識或電腦內建聽寫）。

    backend："auto"、"api"、"mlx"、"faster"、"off"，或直接給一個後端物件（測試用）。
    warmup=True 會在背景執行緒先載入模型（第一次要下載），不會卡住 Notebook。
    """
    STATE.backend, STATE.error = None, ""
    STATE.ready.clear()
    if not isinstance(backend, str):
        STATE.backend = backend
        STATE.ready.set()
        return backend
    choice = os.getenv("BENDAN_STT", backend) if backend == "auto" else backend
    tried = []
    if choice in ("auto", "api") and os.getenv("BENDAN_STT_URL"):
        try:
            STATE.backend = APIBackend(os.getenv("BENDAN_STT_URL"),
                                       os.getenv("BENDAN_STT_KEY") or os.getenv("OPENAI_API_KEY"),
                                       os.getenv("BENDAN_STT_MODEL", "whisper-1"))
        except Exception as exc:     # noqa: BLE001
            tried.append(f"api：{type(exc).__name__}")
    if STATE.backend is None and choice in ("auto", "mlx") and (choice == "mlx" or _is_apple_silicon()):
        try:
            STATE.backend = MLXBackend(model)
        except ImportError:
            tried.append("mlx：沒有安裝 mlx-whisper")
    if STATE.backend is None and choice in ("auto", "faster"):
        try:
            STATE.backend = FasterWhisperBackend(model)
        except ImportError:
            tried.append("faster：沒有安裝 faster-whisper")
        except Exception as exc:     # noqa: BLE001
            tried.append(f"faster：{type(exc).__name__}")
    if STATE.backend is None:
        STATE.error = "；".join(tried) or "語音已關閉"
        if verbose and choice != "off":
            print("🎤 找不到 Whisper：", STATE.error)
            print("   Apple Silicon：pip install mlx-whisper｜其他電腦：pip install faster-whisper")
        return None
    if verbose:
        print("🎤 語音辨識：", STATE.backend.label)
    if warmup:
        def _warm():
            try:
                STATE.backend.warmup()
            except Exception as exc:  # noqa: BLE001 — 載入失敗就在辨識時再報錯
                STATE.error = f"模型載入失敗：{type(exc).__name__}: {str(exc)[:120]}"
            finally:
                STATE.ready.set()
        threading.Thread(target=_warm, daemon=True).start()
    else:
        STATE.ready.set()
    return STATE.backend


def stt_label():
    return STATE.backend.label if STATE.backend else ""


def transcribe(audio, backend=None):
    """WAV bytes／base64 → Transcript。太短、太小聲、幻覺句都會回傳空字串並寫明原因。"""
    be = backend or STATE.backend
    clip = decode_wav(audio)
    tr = Transcript(text="", shout=clip.shout, seconds=clip.seconds, backend=be.name if be else "",
                    meta={"rms_dbfs": round(clip.rms_dbfs, 1), "peak_dbfs": round(clip.peak_dbfs, 1)})
    if be is None:
        tr.note = "沒有語音辨識後端"
        return tr
    if clip.too_short:
        tr.note = "按太短了，按住 🎤 講完再放開"
        return tr
    if clip.silent:
        tr.note = "沒聽到聲音（麥克風有開嗎？）"
        return tr
    if backend is None:
        STATE.ready.wait(timeout=600)          # 模型還在下載／載入就等它
    t0 = time.perf_counter()
    with STATE.lock:                           # 一次只辨識一段，避免同時佔用 GPU／CPU
        tr.raw = be.run(clip)
    tr.latency = time.perf_counter() - t0
    tr.text = clean_transcript(tr.raw)
    if not tr.text:
        tr.note = "沒聽清楚，再說一次？"
    return tr
