"""三個模型的跑分：同一套題目、同一支腳本玩家，在課程伺服器上比較 qwen2.5:7b、llama3.1:8b、qwen3-14b。

兩部分：
1. 指令測試（`run_eval`，賣蠢模式、評估場景）：30 句照做測試＋6 句禁區記憶測試 → 格式正確率、照做率、延遲、闖禁區率。
2. 實際玩（`scripts/difficulty_probe.py` 的腳本玩家）：第 0–6 關，偷懶＋精準兩種玩家 → 過關率、平均指令數、爆炸次數。

跑法（課程 JupyterHub 上，約 15–30 分鐘；三個模型同時跑）：

    python scripts/benchmark_models.py                 # → bendan/assets/benchmarks.json

結果會出現在遊戲主畫面的「📊 模型跑分」。
"""
import html
import importlib.util
import json
import statistics
import tempfile
import time
from pathlib import Path

from .. import llm

BENCH_FILE = Path(__file__).resolve().parent.parent / "assets" / "benchmarks.json"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _probe_module():
    spec = importlib.util.spec_from_file_location("difficulty_probe", PROJECT_ROOT / "scripts" / "difficulty_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_model_benchmark(model, levels=range(0, 7), runs=1, verbose=True):
    """一個模型的完整跑分，回傳 dict（可以直接存成 JSON）。"""
    from ..session import NullLogger
    from .metrics import run_eval
    t0 = time.time()
    llm.set_model(model)
    df = run_eval(modes=("silly",), models=[model], verbose=verbose, save=False)
    ins, mem = df[df.type == "instruction"], df[df.type == "memory"]
    lat = [float(x) for x in df.latency_s]
    probe = _probe_module()
    games = []
    with tempfile.TemporaryDirectory() as tmp:
        for lv in levels:
            for st in ("lazy", "precise"):
                for run in range(runs):
                    row = probe.play_one(lv, st, run, NullLogger(), tmp)
                    games.append({k: row[k] for k in ("level", "strategy", "run", "cleared", "failed", "n_commands",
                                                      "quirks", "collisions", "seconds")})
                    if verbose:
                        print(f"  {model} L{lv} {st} run{run}: {'過關' if row['cleared'] else row['failed']}", flush=True)
    per_level = {}
    for g in games:
        per_level.setdefault(str(g["level"]), []).append(g["cleared"])
    return {
        "model": model, "label": llm.COURSE_MODELS.get(model, model),
        "eval": {"n": int(len(ins)), "format_rate": float(df.format_ok.mean()), "follow_rate": float(ins.follow.mean()),
                 "memory_violation_rate": float(mem.violated.mean()) if len(mem) else None,
                 "latency_avg": statistics.fmean(lat), "latency_p50": statistics.median(lat)},
        "play": {"levels": [int(x) for x in levels], "runs": runs, "games": games,
                 "pass_rate": sum(g["cleared"] for g in games) / len(games),
                 "per_level": {k: sum(v) / len(v) for k, v in per_level.items()},
                 "avg_commands": statistics.fmean(g["n_commands"] for g in games),
                 "explosions": sum(g["failed"] == "exploded" for g in games)},
        "minutes": round((time.time() - t0) / 60, 1),
    }


def load_benchmarks(path=BENCH_FILE):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pct(x):
    return "—" if x is None else f"{x * 100:.0f}%"


def bench_html(data=None):
    """主畫面「📊 模型跑分」的內容。"""
    data = data if data is not None else load_benchmarks()
    if not data or not data.get("models"):
        return ("<div class='bd-bench'><h3>📊 模型跑分</h3><p>還沒有跑分資料。在課程 JupyterHub 的終端機執行 "
                "<code>python scripts/benchmark_models.py</code>（約 15–30 分鐘）。</p></div>")
    ms = data["models"]
    rows = [
        ("格式正確率", "回覆第一次就是合法 JSON、動作都在選單內", [m["eval"]["format_rate"] for m in ms], _pct, True),
        ("照做率", "30 句指令測試，動作跟標準答案一樣", [m["eval"]["follow_rate"] for m in ms], _pct, True),
        ("闖禁區率", "說了「不准進臥室」之後還闖進去（越低越好）", [m["eval"]["memory_violation_rate"] for m in ms], _pct,
         False),
        ("平均延遲", "每句指令從送出到回覆（秒，越低越好）", [m["eval"]["latency_avg"] for m in ms], lambda x: f"{x:.2f} 秒",
         False),
        ("過關率", f"腳本玩家實際玩第 {ms[0]['play']['levels'][0]}–{ms[0]['play']['levels'][-1]} 關",
         [m["play"]["pass_rate"] for m in ms], _pct, True),
        ("平均指令數", "每局用了幾句話（越低越好）", [m["play"]["avg_commands"] for m in ms], lambda x: f"{x:.1f}", False),
        ("爆炸次數", "實際玩時笨笨炸掉幾次", [m["play"]["explosions"] for m in ms], lambda x: f"{x}", False),
    ]
    head = "".join(f"<th>{html.escape(m['label'])}<br><code>{html.escape(m['model'])}</code></th>" for m in ms)
    body = []
    for name, tip, vals, fmt, higher in rows:
        ok = [v for v in vals if v is not None]
        best = (max(ok) if higher else min(ok)) if ok else None
        top = max(ok) if ok else 1
        cells = []
        for v in vals:
            bar = "" if v is None or not top else (f"<div class='bd-bar' style='width:{max(4, 100 * v / top):.0f}%'></div>")
            cls = " class='bd-best'" if v is not None and v == best and len(ok) > 1 else ""
            cells.append(f"<td{cls}>{fmt(v) if v is not None else '—'}{bar}</td>")
        body.append(f"<tr><th title='{html.escape(tip)}'>{name}<div class='bd-tip'>{html.escape(tip)}</div></th>{''.join(cells)}</tr>")
    levels = ms[0]["play"]["levels"]
    lv_rows = "".join(
        f"<tr><th>第 {lv} 關</th>" + "".join(f"<td>{_pct(m['play']['per_level'].get(str(lv)))}</td>" for m in ms) + "</tr>"
        for lv in levels)
    note = html.escape(data.get("note", ""))
    return (f"<div class='bd-bench'><h3>📊 三個模型的跑分</h3>"
            f"<p class='bd-benchmeta'>{html.escape(data.get('date', ''))}｜{html.escape(data.get('server', ''))}｜{note}</p>"
            f"<table><tr><th></th>{head}</tr>{''.join(body)}</table>"
            f"<details><summary>每一關的過關率</summary><table><tr><th></th>{head}</tr>{lv_rows}</table></details>"
            "<p class='bd-benchmeta'>⭐ 綠色＝這一項最好。每格樣本數少（指令測試 30 句、每關 2 局），數字只能看趨勢。</p></div>")
