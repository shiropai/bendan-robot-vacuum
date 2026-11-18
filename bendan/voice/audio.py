"""錄音資料：瀏覽器送來 16 kHz 單聲道 16-bit WAV → 解碼、量音量（偵測「大吼」）。

刻意只用標準函式庫（`wave`、`array`），沒有 numpy 也能量音量；要交給 Whisper 時才轉成 numpy。
"""
import base64
import io
import math
import wave
from array import array
from dataclasses import dataclass

TARGET_RATE = 16000          # Whisper 的取樣率；瀏覽器端錄音時就降到 16 kHz
SHOUT_RMS_DBFS = -15.0       # 平均音量超過這個值就算「大吼」（一般說話約 −35～−22 dBFS）
SHOUT_PEAK_DBFS = -1.0       # 或者有爆音（接近滿格）
MIN_SECONDS = 0.35           # 太短（誤按）就不辨識
SILENCE_RMS_DBFS = -50.0     # 幾乎沒聲音（沒開麥克風、沒講話）就不辨識，避免 Whisper 幻覺


@dataclass
class Clip:
    pcm: array               # int16 樣本
    rate: int
    seconds: float
    rms_dbfs: float
    peak_dbfs: float

    @property
    def shout(self):
        return self.rms_dbfs >= SHOUT_RMS_DBFS or self.peak_dbfs >= SHOUT_PEAK_DBFS

    @property
    def silent(self):
        return self.rms_dbfs <= SILENCE_RMS_DBFS

    @property
    def too_short(self):
        return self.seconds < MIN_SECONDS

    def to_float32(self):
        """給 Whisper 用的 float32 numpy 陣列（−1～1），必要時重新取樣到 16 kHz。"""
        import numpy as np
        x = np.frombuffer(self.pcm.tobytes(), dtype="<i2").astype(np.float32) / 32768.0
        if self.rate != TARGET_RATE and len(x):
            n = int(round(len(x) * TARGET_RATE / self.rate))
            x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
        return x

    def to_wav_bytes(self):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(self.pcm.tobytes())
        return buf.getvalue()


def _dbfs(value):
    return 20 * math.log10(value / 32768.0) if value > 0 else -120.0


def decode_wav(data):
    """WAV bytes（或 base64 字串）→ Clip。支援 16-bit PCM、單聲道或立體聲（立體聲會混成單聲道）。"""
    if isinstance(data, str):
        data = base64.b64decode(data.split(",", 1)[-1])
    with wave.open(io.BytesIO(data), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError("只支援 16-bit PCM WAV")
        channels, rate, frames = w.getnchannels(), w.getframerate(), w.readframes(w.getnframes())
    pcm = array("h")
    pcm.frombytes(frames)
    if channels > 1:
        pcm = array("h", (sum(pcm[i:i + channels]) // channels for i in range(0, len(pcm), channels)))
    n = len(pcm)
    rms = math.sqrt(sum(s * s for s in pcm) / n) if n else 0.0
    peak = max((abs(s) for s in pcm), default=0)
    return Clip(pcm=pcm, rate=rate, seconds=n / rate if rate else 0.0, rms_dbfs=_dbfs(rms), peak_dbfs=_dbfs(peak))


def make_wav(samples, rate=TARGET_RATE):
    """float（−1～1）或 int 樣本 → WAV bytes（測試、範例用）。"""
    pcm = array("h", (max(-32768, min(32767, int(s * 32767) if isinstance(s, float) else int(s))) for s in samples))
    return Clip(pcm, rate, len(pcm) / rate, 0.0, 0.0).to_wav_bytes()
