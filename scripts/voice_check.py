#!/usr/bin/env python3
"""檢查本機 Whisper 能不能用、準不準、多快。

    python scripts/voice_check.py                 # Mac：用系統的台灣中文語音（美佳）念 8 句遊戲指令來測
    python scripts/voice_check.py a.wav b.wav     # 測自己錄的 WAV（16-bit PCM）
    BENDAN_WHISPER_MODEL=mlx-community/whisper-small-mlx python scripts/voice_check.py   # 換小模型比較

印出每一句的原始辨識、清理後的指令、是否完全正確、辨識秒數。
"""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bendan import voice  # noqa: E402

SENTENCES = ["請往前走三格，然後吸", "右轉，往前走兩格，再左轉", "不准進臥室", "笨笨你好棒，對不起剛剛太兇了",
             "停", "請回充電座", "向後轉，前進五格，吸兩次", "繞過那隻貓，去廚房吸灰塵"]


def norm(t):
    return "".join(ch for ch in t if ch not in "，。,.！!？? ")


def synth(folder):
    """用 macOS 的 say（美佳，台灣中文）把測試句念成 16 kHz WAV。"""
    if not (shutil.which("say") and shutil.which("afconvert")):
        sys.exit("這台電腦沒有 say／afconvert（不是 Mac）：請自己錄幾個 WAV，當參數傳進來。")
    files = []
    for i, text in enumerate(SENTENCES, 1):
        aiff, wav = folder / f"c{i}.aiff", folder / f"c{i}.wav"
        subprocess.run(["say", "-v", "Meijia", "-o", str(aiff), text], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
        files.append((wav, text))
    return files


def main():
    be = voice.connect_stt(warmup=False)
    if be is None:
        sys.exit(1)
    t0 = time.perf_counter()
    be.warmup()
    print(f"模型載入（第一次會下載）：{time.perf_counter() - t0:.1f} 秒\n")
    with tempfile.TemporaryDirectory() as tmp:
        cases = [(Path(f), None) for f in sys.argv[1:]] or synth(Path(tmp))
        ok = total_lat = 0
        for wav, expected in cases:
            tr = voice.transcribe(wav.read_bytes(), backend=be)
            hit = expected is not None and norm(tr.text) == norm(expected)
            ok += hit
            total_lat += tr.latency
            mark = "" if expected is None else ("✅" if hit else "❌")
            print(f"{mark} {tr.seconds:4.1f}s 錄音 → {tr.latency:4.2f}s 辨識｜原始：{tr.raw.strip()!r}")
            print(f"      指令：{tr.text or '（' + tr.note + '）'}" + (f"｜應該是：{expected}" if expected and not hit else ""))
        n = len(cases)
        print(f"\n{be.label}：平均辨識 {total_lat / n:.2f} 秒" +
              (f"，完全正確 {ok}/{n}" if all(e for _, e in cases) else ""))


if __name__ == "__main__":
    main()
