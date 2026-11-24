#!/usr/bin/env python3
"""輸出格式實驗：純 Prompt vs 結構化輸出（json_schema），三個課程模型各跑一次 30 句指令＋6 句禁區記憶測試。

同一個模型、同一組 seed，只換「要不要用 response_format json_schema」，所以差別只來自輸出格式。

    python scripts/compare_formats.py                          # 三個模型同時跑（各一個子行程），約 3–5 分鐘
    python scripts/compare_formats.py --models qwen2.5:7b      # 只跑一個
    python scripts/compare_formats.py --one qwen2.5:7b --out /tmp/q.json   # 給上面那行呼叫用

要在連得到課程 LLM 的地方跑（課程 JupyterHub，有 OPENAI_BASE_URL／OPENAI_API_KEY）。
"""
import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bendan import llm  # noqa: E402
from bendan.evaluation.metrics import run_eval  # noqa: E402


def one(model, modes):
    llm.connect(model=model, verbose=False)
    rows = []
    for label, on in (("純 Prompt", False), ("json_schema", True)):
        formats = Counter()
        real_chat = llm.chat

        def counting_chat(*a, **kw):
            out = real_chat(*a, **kw)
            formats[llm.STATE.last_format] += 1
            return out
        llm.chat = counting_chat
        try:
            with llm.structured_output(on):
                df = run_eval(modes=modes, models=[model], verbose=False, save=False)
        finally:
            llm.chat = real_chat
        ins, mem = df[df.type == "instruction"], df[df.type == "memory"]
        lat = [float(x) for x in df.latency_s]
        rows.append({"model": model, "format": label, "used": dict(formats), "n": int(len(df)),
                     "format_rate": float(df.format_ok.mean()), "parse_rate": float(df.parse_ok.mean()),
                     "follow_rate": float(ins.follow.mean()),
                     "memory_violation_rate": float(mem.violated.mean()) if len(mem) else None,
                     "latency_avg": statistics.fmean(lat), "latency_p50": statistics.median(lat)})
        print(f"  {model}｜{label}：格式 {rows[-1]['format_rate']:.0%}、照做 {rows[-1]['follow_rate']:.0%}、"
              f"延遲 {rows[-1]['latency_avg']:.2f} 秒（實際格式 {dict(formats)}）", flush=True)
    return rows


def table(rows):
    lines = ["| 模型 | 輸出格式 | 格式正確率 | 照做率 | 闖禁區率 | 平均延遲 |", "|---|---|---|---|---|---|"]
    for r in rows:
        mem = "—" if r["memory_violation_rate"] is None else f"{r['memory_violation_rate']:.0%}"
        lines.append(f"| {r['model']} | {r['format']} | {r['format_rate']:.0%} | {r['follow_rate']:.0%} | {mem} | "
                     f"{r['latency_avg']:.2f} 秒 |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(llm.COURSE_MODELS))
    ap.add_argument("--modes", default="silly")
    ap.add_argument("--one", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    if args.one:
        rows = one(args.one, modes)
        Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        return
    tmp = Path(tempfile.mkdtemp(prefix="formats-"))
    procs = []
    for m in [x.strip() for x in args.models.split(",") if x.strip()]:
        out = tmp / (m.replace(":", "_") + ".json")
        procs.append((m, out, subprocess.Popen([sys.executable, "-u", __file__, "--one", m, "--out", str(out),
                                                "--modes", args.modes])))
    rows = []
    for m, out, p in procs:
        p.wait()
        if p.returncode == 0 and out.exists():
            rows += json.loads(out.read_text(encoding="utf-8"))
        else:
            print(f"❌ {m} 失敗", flush=True)
    data = {"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "modes": list(modes), "rows": rows}
    out = Path(args.out) if args.out else ROOT / "logs" / "format_comparison.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(table(rows))
    print(f"存到 {out}")


if __name__ == "__main__":
    main()
