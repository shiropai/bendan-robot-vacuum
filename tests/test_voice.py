"""語音輸入：WAV 解碼與音量、辨識結果清理、後端選擇、遊戲視窗的語音流程（全部離線，用 FakeBackend）。"""
import base64
import json
import math
import time

import pytest
from conftest import drive

from bendan import voice
from bendan.voice import FakeBackend, clean_transcript, decode_wav, make_wav, transcribe


def tone(seconds=1.0, amp=0.1, rate=16000, freq=220):
    return make_wav([amp * math.sin(2 * math.pi * freq * i / rate) for i in range(int(seconds * rate))], rate)


def test_decode_wav_measures_length_and_loudness():
    clip = decode_wav(tone(1.0, 0.1))
    assert clip.rate == 16000 and abs(clip.seconds - 1.0) < 1e-6
    assert -26 < clip.rms_dbfs < -21 and not clip.shout and not clip.silent
    assert decode_wav(tone(1.0, 0.9)).shout                     # 很大聲＝大吼
    assert decode_wav(tone(1.0, 0.001)).silent                  # 幾乎沒聲音
    assert decode_wav(base64.b64encode(tone(0.2)).decode()).too_short   # 也吃 base64


def test_resample_to_16k():
    np = pytest.importorskip("numpy")
    x = decode_wav(tone(0.5, 0.1, rate=48000)).to_float32()
    assert isinstance(x, np.ndarray) and len(x) == 8000


@pytest.mark.parametrize("raw, expected", [
    ("请往前走三格然后吸", "請往前走三格然後吸"),               # 簡轉繁
    ("做轉兩次 然後西", "左轉兩次然後吸"),                      # 同音字＋多餘空白
    ("有轉，往錢走5格。", "右轉，往前走5格"),
    ("本本回沖電做", "笨笨回充電座"),
    ("不准進臥式", "不准進臥室"),
    ("不准进卧室", "不准進臥室"),                                # OpenCC 會把「准」轉成「準」→ 要改回來
    ("准你進廚房", "准你進廚房"),
    ("不准進入室！", "不准進臥室！"),
    ("請不吝點贊 訂閱 轉發 打賞支持明鏡與點點欄目", ""),       # Whisper 在靜音時的幻覺
    ("", ""),
])
def test_clean_transcript(raw, expected):
    assert clean_transcript(raw) == expected


def test_transcribe_with_fake_backend():
    be = FakeBackend(["请往前走三格然后吸", "  "])
    tr = transcribe(tone(1.0, 0.1), backend=be)
    assert tr.text == "請往前走三格然後吸" and not tr.shout and tr.backend == "fake"
    assert transcribe(tone(1.0, 0.1), backend=be).note            # 辨識出空白 → 請再說一次
    assert "太短" in transcribe(tone(0.1, 0.1), backend=be).note
    assert "沒聽到" in transcribe(tone(1.0, 0.0005), backend=be).note
    assert transcribe(tone(1.0, 0.9), backend=FakeBackend()).shout


def test_connect_stt_off_and_custom(monkeypatch):
    monkeypatch.setenv("BENDAN_STT", "off")
    assert voice.connect_stt(verbose=False) is None
    be = FakeBackend()
    assert voice.connect_stt(be) is be and voice.stt_label() == be.label
    voice.connect_stt("off", verbose=False)


def test_voice_commands_are_flagged_in_history(session_factory):
    s = session_factory(1, "serious")
    drive_voice = s.preprocess("請往前走兩格", source="voice")
    res = s.think("請往前走兩格")
    s.apply("請往前走兩格", res)
    assert not drive_voice["handled"] and s.history[-1]["flags"][0] == "🎤 語音"
    s.stop()                                                     # 按鈕的「停」不算語音
    assert "🎤 語音" not in s.history[-1]["flags"]
    drive(s, "右轉")
    assert "🎤 語音" not in s.history[-1]["flags"]


def _wait(cond, timeout=5.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_widget_voice_flow(progress):
    pytest.importorskip("ipywidgets")
    from bendan.ui.widget_mode import WidgetGame
    ui = WidgetGame(0, "serious", tick=0.01, progress=progress, seed=0,
                    stt=FakeBackend(["请往前走三格然后吸", "左轉"]))
    try:
        assert "data-stt='whisper'" in ui.mic.value
        wav = base64.b64encode(tone(1.0, 0.9)).decode()          # 大聲 → 大吼
        ui.audio_in.value = json.dumps({"wav": wav, "auto": True, "id": 1})
        assert ui.audio_in.value == "" and ui.say.startswith("🎧")
        assert _wait(lambda: ui.session.history and ui.session.history[0]["cmd"].startswith("請往前走三格然後吸"))
        h = ui.session.history[0]
        assert h["cmd"].endswith("！！！") and h["flags"][0] == "🎤 語音" and "大吼" in h["tone"]
        assert any(e["type"] == "shout" for e in ui.events)
        _wait(lambda: ui.future is None and not ui.session.busy())
        # 取消「自動送出」：只放進輸入框，不會自己送出
        n = len(ui.session.history)
        ui.audio_in.value = json.dumps({"wav": base64.b64encode(tone(1.0, 0.1)).decode(), "auto": False, "id": 2})
        assert _wait(lambda: ui.cmd.value == "左轉")
        time.sleep(0.05)
        assert len(ui.session.history) == n
    finally:
        ui.quit()


def test_widget_without_whisper_uses_browser_mic(progress):
    pytest.importorskip("ipywidgets")
    from bendan.ui.widget_mode import WidgetGame
    ui = WidgetGame(0, "serious", tick=0.01, progress=progress, seed=0)
    try:
        assert "data-stt='browser'" in ui.mic.value
        ui.audio_in.value = json.dumps({"wav": "", "auto": True})
        assert "Whisper" in ui.say
    finally:
        ui.quit()


def test_forbid_rule_accepts_both_spellings(session_factory):
    s = session_factory(2, "serious")
    s.game.forbidden.clear()
    s.preprocess("不準進臥室")
    assert "臥室" in s.game.forbidden


def test_auto_voice_is_silent_when_whisper_is_missing(monkeypatch, capsys, progress):
    """課程伺服器沒有 Whisper：voice="auto" 不能在遊戲上方印「找不到 Whisper」（錄影片會拍到），改寫在 🎤 的提示文字。"""
    pytest.importorskip("ipywidgets")
    from bendan.ui import widget_mode
    from bendan.voice import stt as stt_mod

    def missing(*a, **k):
        raise ImportError("no whisper")
    monkeypatch.setattr(stt_mod, "MLXBackend", missing)
    monkeypatch.setattr(stt_mod, "FasterWhisperBackend", missing)
    monkeypatch.delenv("BENDAN_STT_URL", raising=False)
    monkeypatch.delenv("BENDAN_STT", raising=False)
    monkeypatch.setattr(voice.STATE, "backend", None)
    monkeypatch.setattr(widget_mode, "Progress", lambda *a, **k: progress)
    ui = widget_mode.play_widgets(level=0, mode="serious", seed=0, voice="auto", tts=False)
    try:
        assert "找不到 Whisper" not in capsys.readouterr().out
        assert "data-stt='browser'" in ui.mic.value and "沒有 Whisper" in ui.mic.value
    finally:
        ui.quit()
    voice.connect_stt("faster")                     # 明確指定要 Whisper 卻沒有 → 照樣提醒
    assert "找不到 Whisper" in capsys.readouterr().out
    voice.connect_stt("off", verbose=False)
