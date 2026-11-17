"""評估圖表（matplotlib 物件導向 API，回傳 PNG bytes；在 Notebook 裡會直接顯示）。"""
import io

PALETTE = ["#4895ef", "#2a9d8f", "#f4a261", "#e63946"]


def _new_figure(size):
    """延後載入 matplotlib：沒有 matplotlib 的 Kernel 也能 import 評估模組（只是不能畫圖）。"""
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError as exc:
        raise ImportError("畫圖需要 matplotlib：請把 Kernel 換成「Python 3 (ipykernel)」") from exc
    fig = Figure(figsize=size, dpi=90)
    FigureCanvasAgg(fig)
    return fig


def _font():
    from ..render import FONT, L
    return FONT, L


def _finish(fig, show):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    png = buf.getvalue()
    if show:
        try:
            from IPython.display import Image, display
            display(Image(data=png))
        except ImportError:
            pass
    return png


def plot_summary(summary, show=True):
    """正經 vs 賣蠢：格式正確率、照做率、記憶遵守率。"""
    metrics = [("格式正確率", "format OK"), ("照做率", "follow rate"), ("記憶遵守率", "memory compliance"),
               ("記憶遵守率_加護欄", "memory + guardrail")]
    metrics = [m for m in metrics if m[0] in summary.columns]
    FONT, L = _font()
    fig = _new_figure((8, 4))
    ax = fig.add_subplot()
    labels = [f"{m}\n{mode}" for m, mode in summary.index]
    width = 0.8 / len(metrics)
    for i, (col, en) in enumerate(metrics):
        xs = [k + i * width for k in range(len(summary))]
        bars = ax.bar(xs, summary[col], width, label=L(col, en), color=PALETTE[i])
        for b, v in zip(bars, summary[col]):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.0%}", ha="center", fontsize=8)
    ax.set_xticks([k + width for k in range(len(summary))])
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("rate")
    ax.set_title("Serious vs Silly mode")
    ax.legend(prop={"family": FONT, "size": 8})
    ax.spines[["top", "right"]].set_visible(False)
    for t in ax.get_xticklabels() + [ax.title]:
        t.set_fontfamily(FONT)
    return _finish(fig, show)


MOOD_EN = {"開心": "happy", "普通": "neutral", "不爽": "annoyed", "鬧彆扭": "sulking"}


def plot_mood_eval(mood_summary, show=True):
    """心情 vs 照做率。"""
    FONT, L = _font()
    fig = _new_figure((6, 3.6))
    ax = fig.add_subplot()
    names = list(mood_summary.index)
    vals = list(mood_summary["照做率"])
    bars = ax.bar([L(n, MOOD_EN.get(n, n)) for n in names], vals, color=PALETTE[:len(names)])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.0%}", ha="center", fontsize=9)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel(L("照做率", "follow rate"), fontfamily=FONT)
    ax.set_title(L("笨笨的心情 vs 照做率", "Robot mood vs follow rate"), fontfamily=FONT)
    ax.spines[["top", "right"]].set_visible(False)
    for t in ax.get_xticklabels():
        t.set_fontfamily(FONT)
    return _finish(fig, show)
