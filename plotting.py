"""Figures for slides.qmd, kept out of the qmd itself so each slide's code
cell is a couple of lines instead of 20-30 lines of matplotlib. One
function per chart; each reads its own CSV from `data/`, draws the figure,
calls plt.show(), and returns a dict of any numbers the slide's markdown
text needs afterwards (empty dict if none).

Import as `import plotting` from slides.qmd (run from the repo root, so
`data/` resolves the same way here as it does there).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown

DATA = Path("data")

# Palette: blue = baseline, orange = intermediate attempts, teal = final /
# validated solution. Reused consistently across every chart in this talk.
# Brightened relative to a light-slide version of this palette so they still
# pop against the dark slide background used by custom.scss.
BLUE = "#4c8fe0"
ORANGE = "#f08a4b"
TEAL = "#2bd0a0"
INK = "#e7e9ee"
INK2 = "#aab2c0"
INK3 = "#77808f"
GRID = "#333c4d"

plt.rcParams.update({
    "font.family": "sans-serif",
    "figure.facecolor": "none",
    "axes.facecolor": "none",
    "savefig.facecolor": "none",
    "axes.edgecolor": "#4a5468",
    "axes.labelcolor": INK2,
    "text.color": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 12,
    "legend.labelcolor": INK,
})


def show_table(df: pd.DataFrame, **kwargs) -> Markdown:
    return Markdown(df.to_markdown(index=False, **kwargs))


# ---------------------------------------------------------------- slide 2 --
def predict_share() -> dict:
    """Stacked bar: predict's share of total baseline pipeline time."""
    df = pd.read_csv(DATA / "predict_share.csv")
    total = df["seconds"].sum()
    predict = df.loc[df.component == "predict", "seconds"].iloc[0]
    rest = total - predict

    fig, ax = plt.subplots(figsize=(3, 4.2))
    ax.bar(0, predict, color=BLUE, width=0.6)
    ax.bar(0, rest, bottom=predict, color="#d8d6cc", width=0.6)
    ax.set_ylim(0, total)
    ax.set_xticks([])
    ax.set_xlim(-0.6, 0.6)
    ax.grid(False)
    ax.set_ylabel("seconds, baseline run")
    ax.text(0, predict / 2, f"predict\n{predict:.0f}s\n({predict/total*100:.0f}%)",
            ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    ax.text(0, predict + rest / 2, "rest of\npipeline", ha="center", va="center",
            color=INK2, fontsize=9)
    plt.tight_layout()
    plt.show()
    return {"predict": predict, "total": total}


# ---------------------------------------------------------------- slide 3 --
def reference_workload_table() -> Markdown:
    df = pd.read_csv(DATA / "reference_workload.csv")
    return show_table(df, headers=["quantity", "value"])


# ---------------------------------------------------------------- slide 4 --
def baseline_headline_table() -> Markdown:
    """Vertical (metric, value) table for the right-hand column of the
    'Original work distribution' slide."""
    df = pd.read_csv(DATA / "baseline_headline.csv").set_index("metric")
    predict, wall, cpu, par = (df.loc[m, "value"] for m in
                                ["predict", "wall", "user_cpu", "mean_parallelism"])
    return Markdown(f"""
| metric | value |
|---|---|
| predict | {predict:.0f} s |
| wall | {wall:.0f} s |
| user CPU | {cpu:.0f} s |
| mean parallelism (user CPU ÷ wall) | {par:.1f}x |
""")


# ---------------------------------------------------------------- slide 5 --
def core_imbalance() -> dict:
    """Bar chart: per-core CPU cycles, 10 of 72 cores sampled busiest to
    idlest, showing the spread a static equal-count split leaves behind."""
    cores = pd.read_csv(DATA / "baseline_core_cycles.csv")
    cores = cores.sort_values(
        "Hardware Event Count:CPU_CLK_UNHALTED.THREAD", ascending=False
    ).reset_index(drop=True)
    sample_idx = [0, 7, 14, 21, 28, 35, 42, 49, 57, 71]
    sample = cores.iloc[sample_idx]
    vals = sample["Hardware Event Count:CPU_CLK_UNHALTED.THREAD"] / 1e9

    fig, ax = plt.subplots(figsize=(5, 3.5))
    colors = [BLUE] * (len(vals) - 1) + [ORANGE]
    ax.bar(range(len(vals)), vals, color=colors)
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels([f"#{i+1}" for i in sample_idx], fontsize=8)
    ax.set_ylabel("CPU cycles (billions)")
    ax.set_xlabel("core rank (busiest → idlest)")
    spread = vals.iloc[0] / vals.iloc[-1]
    ax.set_title(f"{spread:.2f}x spread", loc="left", fontsize=11)
    plt.tight_layout()
    plt.show()
    return {"spread": spread}


def baseline_utilization_stats() -> Markdown:
    df = pd.read_csv(DATA / "baseline_headline.csv").set_index("metric")
    return Markdown(
        f"- **{df.loc['effective_cpu_utilization', 'value']:.1f}%** effective CPU utilization\n"
        f"- **{df.loc['cycle_spread_ratio', 'value']:.2f}x** cycle-count spread, busiest vs. idlest core"
    )


def baseline_scaling_table() -> Markdown:
    df = pd.read_csv(DATA / "baseline_scaling.csv")[["threads", "predict_agg_s"]]
    df = df.rename(columns={"predict_agg_s": "predict, s"})
    df["predict, s"] = df["predict, s"].round(0).astype(int)
    return show_table(df)


# ---------------------------------------------------------------- slide 6 --
def per_thread_load() -> dict:
    """Two bar charts: work-item count and cumulative time per thread, one
    representative timestep of the static baseline split."""
    hist = pd.read_csv(DATA / "baseline_histogram.csv")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    ax1.bar(hist["thread_id"], hist["items"], color=BLUE, width=0.8)
    ax1.set_xlabel("thread")
    ax1.set_ylabel("work items")
    ax1.set_title("Items per thread", loc="left", fontsize=11)

    ax2.bar(hist["thread_id"], hist["total_time_s"], color=BLUE, width=0.8)
    mean_t = hist["total_time_s"].mean()
    ax2.axhline(mean_t, color=INK3, linestyle="--", linewidth=1)
    ax2.set_xlabel("thread")
    ax2.set_ylabel("total simulate() time, s")
    spread = (hist["total_time_s"].max() - hist["total_time_s"].min()) / mean_t * 100
    ax2.set_title(f"Time per thread (spread {spread:.0f}%)", loc="left", fontsize=11)

    plt.tight_layout()
    plt.show()
    return {"spread_pct": spread}


def tbb_per_thread_load() -> dict:
    """Same two charts as per_thread_load(), against the TBB dispatch build
    instead of the static baseline - the direct visual counterpart to
    slide 6, showing what work stealing does to the imbalance."""
    csv_path = DATA / "tbb_histogram.csv"
    if not csv_path.exists():
        fig, ax = plt.subplots(figsize=(10, 1))
        ax.axis("off")
        ax.text(0.5, 0.5, "(TBB per-thread histogram pending - see 08_tbb_histogram.py)",
                ha="center", va="center", fontsize=11, color=INK3)
        plt.show()
        return {"spread_pct": None}
    hist = pd.read_csv(csv_path)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    ax1.bar(hist["thread_id"], hist["items"], color=TEAL, width=0.8)
    ax1.set_xlabel("thread")
    ax1.set_ylabel("work items")
    ax1.set_title("Items per thread", loc="left", fontsize=11)

    ax2.bar(hist["thread_id"], hist["total_time_s"], color=TEAL, width=0.8)
    mean_t = hist["total_time_s"].mean()
    ax2.axhline(mean_t, color=INK3, linestyle="--", linewidth=1)
    ax2.set_xlabel("thread")
    ax2.set_ylabel("total simulate() time, s")
    spread = (hist["total_time_s"].max() - hist["total_time_s"].min()) / mean_t * 100
    ax2.set_title(f"Time per thread (spread {spread:.0f}%)", loc="left", fontsize=11)

    plt.tight_layout()
    plt.show()
    return {"spread_pct": spread}


# ---------------------------------------------------------------- slide 7 --
def work_stealing_diagram() -> None:
    """Static equal split leaves one thread idle once its slice is done
    while another is still working through a longer one; TBB's queue lets
    the idle thread steal a remaining task off the busy thread's queue."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    tasks = {
        0: [1.0, 0.9, 1.1],
        1: [0.5],
        2: [0.8, 0.7, 0.6],
        3: [1.2, 1.3, 0.9, 0.6],
    }
    width = 0.8
    x_pos = {i: 0.6 + i * 1.15 for i in tasks}

    def draw_stack(ax, heights, x, color, y0=0.3):
        y = y0
        for h in heights:
            ax.add_patch(mpatches.Rectangle((x, y), width, h - 0.06, facecolor=color, alpha=0.85))
            y += h
        return y

    def base(ax, title):
        ax.set_xlim(0, 5.2)
        ax.set_ylim(0, 5.4)
        ax.set_title(title, loc="left", fontsize=11)
        ax.axis("off")
        for i in tasks:
            ax.text(x_pos[i] + width / 2, -0.25, f"T{i}", ha="center", fontsize=9, color=INK2)

    # left: static split - T1's slice is short, it idles once done
    ax = axes[0]
    base(ax, "Static equal split")
    tops = {i: draw_stack(ax, tasks[i], x_pos[i], BLUE) for i in tasks}
    busiest, top_max = max(tops.items(), key=lambda kv: kv[1])
    idle_from = tops[1]
    ax.add_patch(mpatches.Rectangle((x_pos[1], idle_from), width, top_max - idle_from,
                                     facecolor="none", edgecolor=INK3, hatch="////", linewidth=0.8))
    ax.text(x_pos[1] + width / 2, (idle_from + top_max) / 2, "idle", rotation=90,
            ha="center", va="center", fontsize=8, color=INK3)
    ax.text(x_pos[busiest] + width / 2, top_max + 0.15, "still working", ha="center",
            fontsize=8, color=ORANGE)

    # right: work stealing - T1 steals T3's last remaining task
    ax = axes[1]
    base(ax, "TBB work stealing")
    stolen = tasks[3][-1]
    remaining3 = tasks[3][:-1]
    draw_stack(ax, tasks[0], x_pos[0], BLUE)
    draw_stack(ax, tasks[1], x_pos[1], BLUE)
    draw_stack(ax, tasks[2], x_pos[2], BLUE)
    top3 = draw_stack(ax, remaining3, x_pos[3], BLUE)
    y1_before = 0.3 + sum(tasks[1])
    ax.add_patch(mpatches.Rectangle((x_pos[1], y1_before), width, stolen - 0.06,
                                     facecolor=TEAL, alpha=0.9))
    ax.annotate("steal", xy=(x_pos[1] + width / 2, y1_before + stolen / 2),
                xytext=(x_pos[3] + width / 2, top3 + stolen / 2),
                arrowprops=dict(arrowstyle="->", color=TEAL, lw=1.6, connectionstyle="arc3,rad=-0.3"),
                fontsize=8, color=TEAL, ha="center", va="center")

    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------- slide 8 --
def tbb_vs_baseline_scaling() -> Markdown:
    """Log-log scaling comparison, plus the faster-by-% summary line."""
    sc = pd.read_csv(DATA / "tbb_vs_baseline_scaling.csv")
    sc_ok = sc.dropna(subset=["baseline_predict_agg_s", "tbb_predict_agg_s"])

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(sc_ok["threads"], sc_ok["baseline_predict_agg_s"], "o-", color=BLUE, label="baseline")
    ax.plot(sc_ok["threads"], sc_ok["tbb_predict_agg_s"], "s-", color=ORANGE, label="TBB, fixed")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(sc_ok["threads"])
    ax.set_xticklabels(sc_ok["threads"].astype(int))
    ax.set_xlabel("threads")
    ax.set_ylabel("aggregate predict time, s")
    ax.legend(frameon=False)
    plt.tight_layout()
    plt.show()

    pct = 100 * (sc_ok["baseline_predict_agg_s"] - sc_ok["tbb_predict_agg_s"]) / sc_ok["baseline_predict_agg_s"]
    pending = sc[sc["status"] == "pending"]["threads"].tolist()
    note = f" ({len(pending)} thread count(s) still pending: {pending})" if pending else ""
    return Markdown(
        f"**{pct.min():.0f}–{pct.max():.0f}% faster** than the static baseline, "
        f"every confirmed thread count{note}. Still far short of what the "
        f"profiling budget suggested was available."
    )


def cpu_utilization_timeline() -> None:
    """CPU utilization over time, baseline vs. TBB, same 6s bins, same
    -duration=180 bound so the two are directly comparable. Both static and
    dynamic dispatch hit the same near-idle setup phase; TBB reaches
    saturation a few seconds sooner once compute starts."""
    df = pd.read_csv(DATA / "cpu_utilization_timeline.csv")
    mid = (df["bin_start_s"] + df["bin_end_s"]) / 2

    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(mid, df["baseline_utilization_pct"], "o-", color=BLUE, markersize=4, label="baseline")
    ax.plot(mid, df["tbb_utilization_pct"], "s-", color=ORANGE, markersize=4, label="TBB")
    ax.set_ylim(0, 105)
    ax.set_xlabel("seconds into the run")
    ax.set_ylabel("CPU utilization, % of 72 cores")
    ax.legend(frameon=False)
    plt.tight_layout()
    plt.show()


# ---------------------------------------------------------------- slide 9 --
def memory_traffic_bars() -> Markdown | None:
    """Grouped bar chart: % of clockticks stalled per cache level, one
    group per implementation that's been measured so far."""
    mem = pd.read_csv(DATA / "memory_traffic.csv")
    mem_ok = mem[mem["status"] == "confirmed"]
    categories = ["l1_bound_pct", "l2_bound_pct", "l3_bound_pct", "dram_bound_pct", "store_bound_pct"]
    labels = ["L1", "L2", "L3", "DRAM", "Store"]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    x = range(len(categories))
    width = 0.35
    colors = {"tbb_fixed": ORANGE, "tiled_final": TEAL}
    for i, (_, row) in enumerate(mem_ok.iterrows()):
        vals = [row[c] for c in categories]
        offset = (i - (len(mem_ok) - 1) / 2) * width
        ax.bar([xi + offset for xi in x], vals, width=width,
               color=colors.get(row["implementation"], INK3), label=row["implementation"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("% of clockticks stalled")
    ax.legend(frameon=False)
    plt.tight_layout()
    plt.show()

    if "tiled_final" not in mem_ok["implementation"].values:
        return Markdown(
            "*(final-implementation memory-access measurement pending, and "
            "the tbb-only number above needs a matched-window remeasurement "
            "- see 05_memory_traffic.py's docstring.)*"
        )
    return None


def memory_traffic_table() -> Markdown | None:
    """Raw-number companion to memory_traffic_bars(): loads/stores/LLC
    misses side by side, plus the headline reduction factor - the % bound
    figures above say where time went, this says what actually moved."""
    mem = pd.read_csv(DATA / "memory_traffic.csv")
    mem_ok = mem[mem["status"] == "confirmed"].set_index("implementation")
    if "tbb_fixed" not in mem_ok.index or "tiled_final" not in mem_ok.index:
        return None

    tbb, final = mem_ok.loc["tbb_fixed"], mem_ok.loc["tiled_final"]

    def fmt(n):
        n = float(n)
        if n >= 1e9:
            return f"{n / 1e9:.1f}B"
        if n >= 1e6:
            return f"{n / 1e6:.1f}M"
        return f"{n:.0f}"

    rows = [
        ("Memory Bound", f"{tbb['memory_bound_pct']:.0f}%", f"{final['memory_bound_pct']:.0f}%"),
        ("L3 Bound", f"{tbb['l3_bound_pct']:.1f}%", f"{final['l3_bound_pct']:.1f}%"),
        ("Loads", fmt(tbb["loads"]), fmt(final["loads"])),
        ("Stores", fmt(tbb["stores"]), fmt(final["stores"])),
        ("LLC misses", fmt(tbb["llc_miss_count"]), fmt(final["llc_miss_count"])),
    ]
    table = "| metric | TBB | tiled (final) |\n|---|---|---|\n"
    table += "\n".join(f"| {name} | {t} | {f} |" for name, t, f in rows)

    llc_factor = float(tbb["llc_miss_count"]) / float(final["llc_miss_count"])
    return Markdown(table + f"\n\n**{llc_factor:.0f}x fewer LLC misses.**")


# --------------------------------------------------------------- slide 10 --
def tiling_diagram() -> None:
    """Side-by-side: a per-source sweep re-crossing the full channel range
    each time, vs. a channel x source tile sized to stay inside L2."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    def draw_sweep(ax, tiled, title):
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 6)
        ax.set_title(title, loc="left", fontsize=11)
        ax.axis("off")
        if tiled:
            ax.add_patch(mpatches.Rectangle((0.3, 0.3), 3, 5, facecolor=TEAL, alpha=0.15,
                                             edgecolor=TEAL, linewidth=1.4))
            ax.text(1.8, 5.6, "tile fits in L2", color=TEAL, ha="center", fontsize=9, fontweight="bold")
            for y in [1, 2, 3, 4, 5]:
                ax.annotate("", xy=(3.2, y), xytext=(0.4, y),
                            arrowprops=dict(arrowstyle="->", color=TEAL, lw=1.6))
            ax.annotate("", xy=(9.6, 0.3), xytext=(3.4, 0.3),
                        arrowprops=dict(arrowstyle="->", color=INK3, lw=1, linestyle="dashed"))
            ax.text(6.5, 0.05, "next slab, once", ha="center", fontsize=8, color=INK3)
        else:
            for y in [1, 2, 3, 4, 5]:
                ax.annotate("", xy=(9.6, y), xytext=(0.4, y),
                            arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.6))
            ax.add_patch(mpatches.Rectangle((0.3, 0.3), 0.9, 5, facecolor=TEAL, alpha=0.12,
                                             edgecolor=TEAL, linestyle="dashed", linewidth=1))
            ax.text(0.75, 5.6, "L2", color=TEAL, ha="center", fontsize=8)
            ax.text(5, -0.3, "every source re-crosses the full row", ha="center",
                    fontsize=8, color=ORANGE)
        ax.add_patch(mpatches.Rectangle((0.2, 0.2), 9.6, 5.2, fill=False, edgecolor=INK3, linewidth=0.8))

    draw_sweep(axes[0], False, "Per-source dispatch")
    draw_sweep(axes[1], True, "Channel × source tiling")
    plt.tight_layout()
    plt.show()


# --------------------------------------------------------------- slide 11 --
STAGE_LABELS = {
    "upstream_original": "upstream",
    "tiled_layout": "tiled\nlayout",
    "split_planes": "split\nplanes",
    "slab_rounding": "slab\nrounding",
    "simd_sincos": "SIMD\nsincos",
}


def progression_bars(up_to_stage: str) -> dict:
    """Cumulative bar chart: predict time per optimization stage, from
    upstream through up_to_stage. Shared by slides 13-16, one column
    added each time, same y-axis throughout so each slide reads as the
    last one plus a column."""
    prog = pd.read_csv(DATA / "progression.csv").set_index("stage")
    stages = list(STAGE_LABELS)
    stages = stages[: stages.index(up_to_stage) + 1]
    values = prog.loc[stages, "predict_s"]
    upstream = prog.loc["upstream_original", "predict_s"]

    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    colors = ["#c9c7bd"] * (len(stages) - 1) + [TEAL]
    ax.bar(range(len(stages)), values, color=colors, width=0.6)
    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels([STAGE_LABELS[s] for s in stages], fontsize=9)
    ax.set_ylabel("predict step, s")
    ax.set_ylim(0, upstream * 1.15)
    for i, v in enumerate(values):
        ax.text(i, v + upstream * 0.02, f"{v:.0f}s", ha="center", fontsize=9)
    plt.tight_layout()
    plt.show()
    current = values.iloc[-1]
    return {"before": upstream, "after": current, "speedup": upstream / current}


# --------------------------------------------------------------- slide 12 --
def split_planes_diagram() -> None:
    """Interleaved complex<double> vs. two split float planes (SoA)."""
    fig, ax = plt.subplots(figsize=(8, 2.2))
    n = 8
    for i in range(n):
        color = BLUE if i % 2 == 0 else ORANGE
        ax.add_patch(mpatches.Rectangle((i, 1.3), 0.9, 0.8, facecolor=color, alpha=0.85))
    ax.text(-0.6, 1.7, "interleaved", ha="right", va="center", fontsize=9)
    for i in range(n):
        ax.add_patch(mpatches.Rectangle((i * 0.5, 0.1), 0.45, 0.4, facecolor=BLUE, alpha=0.85))
    for i in range(n):
        ax.add_patch(mpatches.Rectangle((i * 0.5, -0.5), 0.45, 0.4, facecolor=ORANGE, alpha=0.85))
    ax.text(-0.6, 0.1, "real plane", ha="right", va="center", fontsize=9)
    ax.text(-0.6, -0.5, "imag plane", ha="right", va="center", fontsize=9)
    ax.set_xlim(-2.2, n)
    ax.set_ylim(-0.8, 2.3)
    ax.axis("off")
    plt.tight_layout()
    plt.show()


# --------------------------------------------------------------- slide 13 --
def slab_sizing_diagram() -> None:
    """53 channels (a prime, ragged last group) vs. 48 (divides evenly)."""
    fig, axes = plt.subplots(2, 1, figsize=(8, 2.4))
    for ax, n, title, ragged in [(axes[0], 53, "53 channels", True), (axes[1], 48, "48 channels", False)]:
        ax.set_xlim(0, 56)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.text(-2, 0.5, title, ha="right", va="center", fontsize=9)
        for block_start in range(0, n, 8):
            block_len = min(8, n - block_start)
            color = ORANGE if (ragged and block_len < 8) else BLUE
            ax.add_patch(mpatches.Rectangle((block_start, 0.1), block_len - 0.15, 0.8,
                                             facecolor=color, alpha=0.85))
    plt.tight_layout()
    plt.show()


# --------------------------------------------------------------- slide 14 --
def simd_lanes_diagram() -> None:
    """Scalar (1 lane) vs. vectorized (8 lanes) side by side."""
    fig, axes = plt.subplots(1, 2, figsize=(9, 2.2))
    for ax, n, title in [(axes[0], 1, "scalar: 1 at a time"), (axes[1], 8, "vectorized: 8 at a time")]:
        ax.set_xlim(0, 8)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.set_title(title, fontsize=10)
        for i in range(n):
            ax.add_patch(mpatches.Rectangle((i, 0.2), 0.8, 0.6,
                                             facecolor=TEAL if n == 8 else ORANGE, alpha=0.85))
    plt.tight_layout()
    plt.show()


# --------------------------------------------------------------- slide 15 --
def final_scaling() -> dict:
    """Log-log scaling comparison, baseline vs. final tiled implementation,
    plus the headline speedup/efficiency numbers."""
    final = pd.read_csv(DATA / "final_scaling.csv")
    baseline = pd.read_csv(DATA / "baseline_scaling.csv")

    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(baseline["threads"], baseline["predict_agg_s"], "o-", color=BLUE, label="baseline")
    ax.plot(final["threads"], final["predict_agg_s"], "^-", color=TEAL, label="final (tiled)")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("threads")
    ax.set_ylabel("aggregate predict time, s")
    ax.legend(frameon=False)
    plt.tight_layout()
    plt.show()

    prog = pd.read_csv(DATA / "progression.csv").set_index("stage")
    upstream = prog.loc["upstream_original", "predict_s"]
    final_100ts = prog.loc["simd_sincos", "predict_s"]
    f2, f72 = final.set_index("threads").loc[[2, 72], "predict_agg_s"]
    eff = (f2 / f72) / (72 / 2) * 100

    return {
        "upstream": upstream,
        "final_100ts": final_100ts,
        "speedup": upstream / final_100ts,
        "efficiency_pct": eff,
    }
