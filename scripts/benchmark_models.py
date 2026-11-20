#!/usr/bin/env python3
"""三個課程模型的跑分（qwen2.5:7b、llama3.1:8b、qwen3-14b），結果存到 bendan/assets/benchmarks.json，
遊戲主畫面的「📊 模型跑分」會讀這個檔。

    python scripts/benchmark_models.py                     # 三個模型同時跑（各一個子行程），約 15–30 分鐘
    python scripts/benchmark_models.py --levels 0-3        # 少跑幾關
    python scripts/benchmark_models.py --one qwen3-14b --out /tmp/q3.json   # 只跑一個（給上面那行呼叫用）

要在連得到課程 LLM 的地方跑（課程 JupyterHub，有 OPENAI_BASE_URL／OPENAI_API_KEY）。
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bendan import llm  # noqa: E402
from bendan.evaluation.benchmark import BENCH_FILE, run_model_benchmark  # noqa: E402


def parse_levels(text):
    a, b = text.split("-") if "-" in text else (text, text)
    return list(range(int(a), int(b) + 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(llm.COURSE_MODELS))
    ap.add_argument("--levels", default="0-6")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--one", default=None, help="只跑這一個模型")
    ap.add_argument("--out", default=str(BENCH_FILE))
    args = ap.parse_args()

    if args.one:
        llm.connect(model=args.one, verbose=True)
        res = run_model_benchmark(args.one, parse_levels(args.levels), args.runs)
        Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ {args.one} 完成：{args.out}")
        return

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    tmp = Path(tempfile.mkdtemp(prefix="bench-"))
    procs = []
    for m in models:
        out = tmp / (m.replace(":", "_").replace("/", "_") + ".json")
        log = open(tmp / (out.stem + ".log"), "w")
        procs.append((m, out, log, subprocess.Popen([sys.executable, "-u", __file__, "--one", m, "--out", str(out),
                                                     "--levels", args.levels, "--runs", str(args.runs)],
                                                    stdout=log, stderr=subprocess.STDOUT)))
    print(f"三個模型同時跑中（紀錄在 {tmp}）……", flush=True)
    t0 = time.time()
    results = []
    for m, out, log, p in procs:
        p.wait()
        log.close()
        if p.returncode == 0 and out.exists():
            results.append(json.loads(out.read_text(encoding="utf-8")))
            print(f"✅ {m}（{(time.time() - t0) / 60:.1f} 分鐘）", flush=True)
        else:
            print(f"❌ {m} 失敗，看 {log.name}", flush=True)
    data = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "server": "課程 JupyterHub（vLLM）",
            "note": "賣蠢模式；指令測試 30 句＋記憶 6 句；腳本玩家（偷懶＋精準）每關各 %d 局" % args.runs,
            "models": results}
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"存到 {args.out}")


if __name__ == "__main__":
    main()
