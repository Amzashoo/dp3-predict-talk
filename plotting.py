"""Figures for slides.qmd, kept out of the qmd itself so each slide's code
cell is a couple of lines instead of 20-30 lines of matplotlib. One
function per chart; each reads its own CSV from `data/`, draws the figure,
calls plt.show(), and returns a dict of any numbers the slide's markdown
text needs afterwards (empty dict if none).

Import as `import plotting` from slides.qmd (run from the repo root, so
`data/` resolves the same way here as it does there).
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown

DATA = Path("data")

# Palette: red = baseline, ochre = intermediate attempts, green = final /
# validated solution - so a chart warms up where it shows the problem and
# cools down where it shows the result. Reused consistently across every chart
# in this talk, and the same three hues custom.scss sets the deck in.
# The names are the roles, not the hues: BLUE/ORANGE/TEAL are what these three
# series have been called since the deck was dark, and every figure below and
# every skin in STYLE_VARIANTS/ keys off them.
BLUE = "#b23b30"     # baseline
ORANGE = "#a87a1e"   # intermediate attempts
TEAL = "#0f766e"     # final / validated
INK = "#14171a"
INK2 = "#4d545a"
INK3 = "#868d93"

plt.rcParams.update({
    "font.family": "sans-serif",
    "figure.facecolor": "none",
    "axes.facecolor": "none",
    "savefig.facecolor": "none",
    "axes.edgecolor": "#969ea4",
    "axes.labelcolor": INK2,
    "text.color": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    # No gridlines anywhere: they compete with the bars and lines instead of
    # helping read values off them, and every chart here is read for its shape
    # rather than off the axis.
    "axes.grid": False,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 12,
    "legend.labelcolor": INK,
    "axes.linewidth": 1.2,
})

# Legends sit inside the axes on most of these charts, which on light stock
# puts the labels over a filled bar. matplotlib's default is an unframed
# legend, so every call site below passes this instead.
LEGEND = dict(frameon=True, facecolor="#f7f8f6", edgecolor=INK3,
              framealpha=0.95)


NBSP = " "


def fmt_int(value) -> str:
    """Integer with digits grouped by a non-breaking space above 999."""
    return f"{int(round(float(value))):,}".replace(",", NBSP)


def fmt_int_html(value) -> str:
    """fmt_int for inline `{python}` expressions in the qmd, which escape any
    non-ASCII output to its Python repr ("1\\xa0161"). The entity survives."""
    return f"{int(round(float(value))):,}".replace(",", "&nbsp;")


def ncores() -> int:
    """Core count, parsed from the machine description in
    reference_workload.csv rather than hardcoded here.

    Every parallelism figure in the talk is quoted against this as its
    ideal, so it has to be the same number the configuration table on
    slide 3 shows - a constant duplicated in this file would drift from it
    silently the first time the talk is re-run on another machine.
    """
    ref = pd.read_csv(DATA / "reference_workload.csv").set_index("quantity")
    machine = str(ref.loc["machine", "value"])
    match = re.search(r"(\d+)\s+cores", machine)
    if not match:
        raise ValueError(f"no core count in machine description: {machine!r}")
    return int(match.group(1))


def scaling_efficiency(csv_name: str) -> dict:
    """Speedup and efficiency over a scaling sweep's full thread range,
    with the ideal stated. "50% efficiency" alone doesn't say 50% of what,
    and the two sweeps in this talk don't start at the same thread count.
    """
    df = pd.read_csv(DATA / csv_name).set_index("threads")
    lo, hi = int(df.index.min()), int(df.index.max())
    speedup = df.loc[lo, "predict_agg_s"] / df.loc[hi, "predict_agg_s"]
    ideal = hi / lo
    return {"lo": lo, "hi": hi, "speedup": speedup, "ideal": ideal,
            "efficiency_pct": speedup / ideal * 100}


# ---------------------------------------------------------------- slide 2 --
def predict_share() -> dict:
    """Stacked bar: predict's share of total baseline pipeline time."""
    df = pd.read_csv(DATA / "predict_share.csv")
    total = df["seconds"].sum()
    predict = df.loc[df.component == "predict", "seconds"].iloc[0]
    rest = total - predict

    fig, ax = plt.subplots(figsize=(3, 4.2))
    ax.bar(0, predict, color=BLUE, width=0.6)
    ax.bar(0, rest, bottom=predict, color="#b5bcc0", width=0.6)
    ax.set_ylim(0, total)
    ax.set_xticks([])
    ax.set_xlim(-0.6, 0.6)
    ax.set_ylabel("seconds, baseline run")
    ax.text(0, predict / 2, f"predict\n{fmt_int(predict)}s\n({predict/total*100:.0f}%)",
            ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    ax.text(0, predict + rest / 2, "rest of\npipeline", ha="center", va="center",
            color=INK2, fontsize=9)
    plt.tight_layout()
    plt.show()
    return {"predict": predict, "total": total}


# ---------------------------------------------------------------- slide 3 --
def reference_workload_table() -> Markdown:
    """The CSV's keys are snake_case and its counts are bare digits, both of
    which render as-is on the slide (`sky_components`, `25085`). Relabel and
    group here rather than in the CSV, which stays machine-readable."""
    df = pd.read_csv(DATA / "reference_workload.csv").copy()
    df["quantity"] = df["quantity"].str.replace("_", " ")

    def value(v):
        try:
            return fmt_int(v)
        except ValueError:
            return v

    df["value"] = df["value"].map(value)
    return Markdown(
        "Test configuration used for benchmarking in this talk\n\n"
        + df.to_markdown(index=False, headers=["quantity", "value"],
                         colalign=("left", "right"))
    )


# ---------------------------------------------------------------- slide 4 --
def baseline_headline_table() -> Markdown:
    """Vertical (metric, value) table for the right-hand column of the
    'Original work distribution' slide."""
    df = pd.read_csv(DATA / "baseline_headline.csv").set_index("metric")
    predict, wall, cpu, par = (df.loc[m, "value"] for m in
                                ["predict", "wall", "user_cpu", "mean_parallelism"])
    cores = ncores()
    return Markdown(f"""
| metric | value |
|---|---:|
| predict | {fmt_int(predict)} s |
| wall | {fmt_int(wall)} s |
| user CPU | {fmt_int(cpu)} s |
| mean parallelism | {par:.1f}× of {cores} ({par / cores * 100:.0f}%) |
""")


# ---------------------------------------------------------------- slide 5 --
def core_imbalance() -> dict:
    """Binned histogram of cycles per thread: x is cycles, y is how many of
    the 72 threads fall in each bin.

    A balanced run is one narrow spike; this one is spread across the whole
    range, which is the imbalance the slide is about.
    """
    cores = pd.read_csv(DATA / "baseline_core_cycles.csv")
    vals = cores["Hardware Event Count:CPU_CLK_UNHALTED.THREAD"] / 1e9

    fig, ax = plt.subplots(figsize=(5.4, 3.5))
    bins = [80 + 5 * i for i in range(49)]  # 80..320 Gcycles, 5 G wide
    ax.hist(vals, bins=bins, color=BLUE, linewidth=0)

    ax.set_xlabel("CPU cycles per thread (billions)")
    ax.set_ylabel("threads")
    ax.set_xticks([80 + 40 * i for i in range(7)])
    ax.yaxis.get_major_locator().set_params(integer=True)

    spread = vals.max() / vals.min()
    ax.set_title(f"{spread:.2f}x spread, busiest vs. idlest thread",
                 loc="left", fontsize=11)
    plt.tight_layout()
    plt.show()
    return {"spread": spread, "cores": len(vals)}


def baseline_utilization_stats() -> Markdown:
    df = pd.read_csv(DATA / "baseline_headline.csv").set_index("metric")
    # Labelled: this sits beside "41.3x of 72 (57%)" on the same slide, and
    # the two only reconcile once you know VTune discounts spin.
    util = df.loc["effective_cpu_utilization", "value"]
    cores = ncores()
    return Markdown(
        f"- **{util:.1f}%** effective CPU utilization — {util / 100 * cores:.1f} "
        f"of {cores} cores (VTune, spin and overhead discounted)\n"
        f"- **{df.loc['cycle_spread_ratio', 'value']:.2f}x** cycle-count spread, busiest vs. idlest core"
    )


def baseline_scaling_plot() -> dict:
    """Predict time against thread count for the static baseline, with the
    ideal-scaling line drawn in.

    The measured curve alone says "it gets faster with more threads", which
    is not the point; the widening gap against perfect scaling from the
    first measured point is. Log-log so ideal scaling is a straight line
    and the shortfall is readable as a vertical distance, and to match the
    two other scaling charts in the talk.
    """
    df = pd.read_csv(DATA / "baseline_scaling.csv")
    threads = df["threads"].tolist()
    measured = df["predict_agg_s"].tolist()
    ideal = [measured[0] * threads[0] / t for t in threads]

    fig, ax = plt.subplots(figsize=(5, 3.1))
    ax.plot(threads, ideal, "--", color=INK3, linewidth=1.2, label="ideal")
    ax.plot(threads, measured, "o-", color=BLUE, markersize=5, label="measured")

    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(threads)
    ax.set_xticklabels([str(t) for t in threads], fontsize=9)
    # Headroom on the right so the shortfall arrow at the last point isn't
    # drawn on the axis line.
    ax.set_xlim(threads[0] * 0.88, threads[-1] * 1.18)
    # Log decades give a single 10^3 tick over this range; label the round
    # values instead so the axis is readable as seconds.
    yticks = [300, 500, 1000, 2000, 3000]
    ax.set_yticks(yticks)
    ax.set_yticklabels([fmt_int(y) for y in yticks], fontsize=9)
    ax.minorticks_off()
    ax.set_xlabel("threads")
    ax.set_ylabel("predict time, s")
    ax.legend(fontsize=9, **LEGEND)

    # Call out the shortfall where it is widest, at the full thread count.
    ax.annotate("", xy=(threads[-1], measured[-1]), xytext=(threads[-1], ideal[-1]),
                arrowprops=dict(arrowstyle="<->", color=ORANGE, lw=1.2))
    ax.text(threads[-1] * 0.94, (measured[-1] * ideal[-1]) ** 0.5,
            f"{measured[-1] / ideal[-1]:.1f}x", color=ORANGE, fontsize=9.5,
            ha="right", va="center")

    plt.tight_layout()
    plt.show()
    return {"threads": threads, "measured": measured, "ideal": ideal}


# ---------------------------------------------------------------- slide 6 --
def _per_thread_load(csv_name: str, color: str, pending_hint: str,
                     items_label: str = "sources simulated") -> dict:
    """Items and time per thread for one build, one representative timestep.

    The time panel is stacked so the whole thread's work is visible:
    simulate() plus the beam-apply remainder that sits outside it. Showing
    simulate() alone reads as large imbalance even when threads finish
    together, because a thread doing more beam applies necessarily does
    less simulate in the same wall time - the total is what the scheduler
    balances. Slides 6 and 9 read these side by side, so both go through
    this one function; two near-copies is how they drifted apart before.
    """
    csv_path = DATA / csv_name
    if not csv_path.exists():
        fig, ax = plt.subplots(figsize=(10, 1))
        ax.axis("off")
        ax.text(0.5, 0.5, f"({pending_hint})", ha="center", va="center",
                fontsize=11, color=INK3)
        plt.show()
        return {}

    hist = pd.read_csv(csv_path)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    ax1.bar(hist["thread_id"], hist["items"], color=color, width=0.8)
    ax1.set_xlabel("thread")
    ax1.set_ylabel(items_label)
    ax1.set_title(f"{items_label.capitalize()} per thread", loc="left", fontsize=11)

    ax2.bar(hist["thread_id"], hist["simulate_s"], color=color, width=0.8,
            label="simulate()")
    ax2.bar(hist["thread_id"], hist["other_s"], bottom=hist["simulate_s"],
            color=INK3, alpha=0.45, width=0.8, label="beam apply + rest")
    total = hist["range_s"]
    mean_t = total.mean()
    ax2.set_xlabel("thread")
    ax2.set_ylabel("thread busy time, s")
    # Below the panels rather than inside ax2: at "lower right" the labels
    # sit on top of the bars and are unreadable on the dark slide.
    fig.legend(*ax2.get_legend_handles_labels(), fontsize=8.5, **LEGEND,
               ncol=2, loc="lower center", bbox_to_anchor=(0.5, -0.03))
    spread = (total.max() - total.min()) / mean_t * 100
    ax2.set_title(f"Time per thread (total spread {spread:.0f}%)",
                  loc="left", fontsize=11)

    plt.tight_layout()
    plt.show()
    sim_spread = ((hist["simulate_s"].max() - hist["simulate_s"].min())
                  / hist["simulate_s"].mean() * 100)
    return {
        "spread_pct": spread,
        "simulate_spread_pct": sim_spread,
        "simulate_share_pct": hist["simulate_s"].sum() / total.sum() * 100,
        "items_min": int(hist["items"].min()),
        "items_max": int(hist["items"].max()),
    }


def per_thread_load() -> dict:
    """Slide 6: the static (StaticFor) split."""
    return _per_thread_load("baseline_histogram.csv", BLUE,
                            "baseline per-thread histogram pending - run 03")


def tbb_per_thread_load() -> dict:
    """Slide 9: the TBB work-stealing build, the counterpart to slide 6."""
    return _per_thread_load("tbb_histogram.csv", TEAL,
                            "TBB per-thread histogram pending - run 08")


def final_per_thread_load() -> dict:
    """The tiled build, the counterpart to slides 6 and 9.

    `items` here counts simulate() calls, not sources: the tiled dispatch
    splits each source across channel slabs, so the count is sources x
    slabs. Labelled accordingly rather than reusing "sources simulated",
    which would read as 9x more work than the other two builds do.
    """
    return _per_thread_load("final_histogram.csv", TEAL,
                            "final per-thread histogram pending - run 09",
                            items_label="simulate() calls")


def load_balance_stats() -> dict:
    """{implementation: utilization_pct} for inline references in the
    slides, so no balance number is typed by hand twice."""
    path = DATA / "load_balance.csv"
    if not path.exists():
        return {}
    bal = pd.read_csv(path).set_index("implementation")
    return {k: float(bal.loc[k, "utilization_pct"]) for k in bal.index}


def load_balance_table() -> Markdown | None:
    """The three dispatch strategies side by side on load balance.

    The per-thread bar charts show one timestep each; this is the metric
    measured over all 30, so it's what the claim should rest on.
    `utilization` is the average thread's busy time as a fraction of the
    timestep's makespan - 100% means every thread worked until the last
    one finished, lower means threads idled waiting on a straggler.
    """
    path = DATA / "load_balance.csv"
    if not path.exists():
        return None
    bal = pd.read_csv(path).set_index("implementation")
    names = {"static_baseline": "static split", "tbb": "TBB stealing",
             "tiled_final": "tiled (final)"}
    present = [k for k in names if k in bal.index]
    if not present:
        return None

    # Every column must come from the same timer, or rows measured with
    # different ones read as a difference between implementations.
    stages = {str(bal.loc[k, "stage"]) if "stage" in bal.columns else ""
              for k in present}
    if len(stages) > 1:
        return Markdown(
            "*(load-balance rows were measured with different timers "
            f"({', '.join(sorted(s or '?' for s in stages))}) and are not "
            "comparable - re-run scripts 03, 08 and 09 against builds that "
            "all have the worker.range timer.)*"
        )
    stage = stages.pop() or "worker.simulate"

    header = "| metric | " + " | ".join(names[k] for k in present) + " |\n"
    header += "|---" + "|---:" * len(present) + "|\n"
    # One decimal, not zero: 99.6% renders as "100%" at .0f, which reads as
    # perfect balance rather than near-perfect, and 0.6% spread as "1%".
    rows = [
        ("thread utilization", "utilization_pct", "{:.1f}%"),
        ("time spread", "spread_pct", "{:.1f}%"),
        ("idle, per timestep", "idle_s", "{:.2f}s"),
    ]
    body = "\n".join(
        f"| {label} | " + " | ".join(fmt.format(bal.loc[k, col]) for k in present) + " |"
        for label, col, fmt in rows
    )
    n = int(bal.loc[present[0], "timesteps"])
    scope = ("a thread's whole work" if stage == "worker.range"
             else f"`{stage}` only")
    return Markdown(
        header + body
        + f"\n\nOver {scope}, per timestep, averaged over {n}."
    )


def dispatch_work_totals() -> dict:
    """What fine-grained stealing costs in total work, static vs. TBB.

    Both histograms are one representative timestep of the same workload on
    the same node, so their per-thread times sum to comparable
    thread-seconds. The point is that the TBB column is *larger*: stealing
    removed the idle time by adding work, because addBeamToData fires once
    per patch per dispatched range (OnePredict.cc, PredictSourceRange) and
    stealing needs many ranges.
    """
    out = {}
    for key, name in (("static", "baseline_histogram.csv"),
                      ("tbb", "tbb_histogram.csv"),
                      ("tiled", "final_histogram.csv")):
        path = DATA / name
        if not path.exists():
            return {}
        hist = pd.read_csv(path)
        out[f"{key}_total_s"] = hist["range_s"].sum()
        out[f"{key}_beam_s"] = hist["other_s"].sum()
        out[f"{key}_makespan_s"] = hist["range_s"].max()
    out["work_growth_pct"] = (out["tbb_total_s"] / out["static_total_s"] - 1) * 100
    out["beam_growth_pct"] = (out["tbb_beam_s"] / out["static_beam_s"] - 1) * 100
    out["makespan_gain_pct"] = (
        1 - out["tbb_makespan_s"] / out["static_makespan_s"]) * 100
    return out


def tile_granularity() -> dict:
    """Why the tiled build balances to ~95% and not the ~100% work stealing
    reaches: its work units are coarse (16 per thread by default), so the
    residual idle is one last unit finishing alone, not a scheduler failure.

    A DP3_PREDICT_SOURCE_BLOCKS sweep confirms it - idle roughly halves with
    every doubling of the unit count - and also shows it isn't worth fixing:
    past ~32 units/thread the extra per-block accumulators and the
    sum_source_blocks reduction cost more than the tail they remove.
    Returns the default row and the finest one swept.
    """
    path = DATA / "tile_granularity.csv"
    if not path.exists():
        return {}
    sweep = pd.read_csv(path).sort_values("units_per_thread")
    lo, hi = sweep.iloc[0], sweep.iloc[-1]
    return {
        "units_lo": float(lo["units_per_thread"]),
        "units_hi": float(hi["units_per_thread"]),
        "idle_lo_ms": float(lo["idle_ms"]),
        "idle_hi_ms": float(hi["idle_ms"]),
        "spread_lo_pct": float(lo["spread_pct"]),
        "spread_hi_pct": float(hi["spread_pct"]),
        "predict_lo_s": float(lo["normal_predict_s"]),
        "predict_hi_s": float(hi["normal_predict_s"]),
        "cost_pct": (float(hi["normal_predict_s"]) / float(lo["normal_predict_s"]) - 1) * 100,
    }


# Beam applies vary in cost, and that variance is the problem being drawn.
# Fixed pattern, not random, so the figure redraws identically.
_APPLY_WIDTHS = [1.0, 2.6, 0.6, 1.8, 0.8, 3.0, 1.3, 0.7, 2.2, 1.5,
                 0.9, 2.8, 1.1, 0.6, 2.0, 1.6, 0.8, 2.4, 1.2, 0.7]
_APPLY_BASE = 0.07


def dispatch_variants_diagram() -> None:
    """The four dispatch schemes behind slide 10, side by side.

    Each panel is three threads on a time axis. Bar length is how long that
    thread works, the notch marks along a bar are beam applies, and the
    hatched tail is idle time waiting on the slowest thread. Read across,
    the panels show that every attempt to cut the applies (the notches) pays
    for it somewhere else - in idle time, in memory, or in complexity.

    Schematic: the bar lengths and notch counts are drawn to show the
    mechanism, not measured. The numbers that *are* measured live on slides
    9 and 10's text.
    """
    fig, axes = plt.subplots(1, 4, figsize=(11.5, 3.4))
    y_rows = [6.6, 5.0, 3.4]
    height = 1.15
    x0 = 0.4

    def frame(ax, title, verdict):
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.axis("off")
        ax.set_title(title, loc="left", fontsize=10, color=INK)
        ax.text(0.4, 1.6, verdict, fontsize=8.5, color=INK2, va="top", wrap=True)

    def panel(ax, title, lengths, notches, verdict, colour=BLUE):
        """One solid work bar per thread, with the beam applies marked on it."""
        frame(ax, title, verdict)
        span = max(lengths)
        for y, length, n in zip(y_rows, lengths, notches):
            ax.add_patch(mpatches.Rectangle((x0, y), length, height,
                                            facecolor=colour, alpha=0.85))
            if length < span:  # idle tail, waiting on the slowest thread
                ax.add_patch(mpatches.Rectangle(
                    (x0 + length, y), span - length, height, facecolor="none",
                    edgecolor=INK3, hatch="////", linewidth=0.7))
            for k in range(n):
                w = _APPLY_BASE * _APPLY_WIDTHS[k % len(_APPLY_WIDTHS)]
                centre = x0 + length * (k + 0.5) / n
                ax.add_patch(mpatches.Rectangle(
                    (centre - w / 2, y), w, height,
                    facecolor=ORANGE, alpha=0.95, linewidth=0))

    def pipeline_panel(ax, title, verdict):
        """A pipeline graph rather than a thread timeline: sources feed a
        simulate stage, a patch's beam apply is queued the instant that
        patch's last source lands, and any worker pulls from either stage."""
        frame(ax, title, verdict)
        box = dict(alpha=0.85, linewidth=0)
        ax.add_patch(mpatches.Rectangle((0.5, 7.0), 3.6, 1.3, facecolor=BLUE, **box))
        ax.text(2.3, 7.65, "simulate\nsources", ha="center", va="center",
                fontsize=8, color="white")
        ax.add_patch(mpatches.Rectangle((5.9, 7.0), 3.6, 1.3, facecolor=ORANGE, **box))
        ax.text(7.7, 7.65, "beam\napply", ha="center", va="center",
                fontsize=8, color=INK)
        ax.annotate("", xy=(5.8, 7.65), xytext=(4.2, 7.65),
                    arrowprops=dict(arrowstyle="->", color=INK2, lw=1.4))
        ax.text(5.0, 8.5, "patch\ncomplete", ha="center", fontsize=7,
                color=INK3, va="bottom")

        # Worker pool below, pulling from either stage.
        for i, cx in enumerate((2.0, 5.0, 8.0)):
            ax.add_patch(mpatches.Rectangle((cx - 0.75, 4.2), 1.5, 0.95,
                                            facecolor="#b5bcc0", linewidth=0))
            ax.text(cx, 4.68, f"T{i + 1}", ha="center", va="center",
                    fontsize=8, color=INK)
            for target in (2.3, 7.7):
                ax.annotate("", xy=(target, 6.9), xytext=(cx, 5.25),
                            arrowprops=dict(arrowstyle="->", color=TEAL, lw=0.8,
                                            alpha=0.55))
        ax.text(5.0, 3.4, "any worker pulls either stage", ha="center",
                fontsize=7.5, color=INK3)

    # One line each: the slide's bullets carry the reasoning.
    # The apply counts are the point of the first two panels: a patch split
    # across many small ranges is re-applied once per range, so per-source
    # stealing pays several times what patch-parallel does.
    panel(axes[0], "per-source stealing", [8.4, 8.4, 8.4], [20, 20, 20],
          "balanced — but applies everywhere")
    panel(axes[1], "patch-parallel", [8.4, 5.6, 6.8], [4, 3, 4],
          "fewest applies — but threads idle")
    panel(axes[2], "per-patch accumulators", [8.0, 8.0, 8.0], [4, 4, 4],
          "applies deferred — but 218 GB of buffers")
    pipeline_panel(axes[3], "pipeline",
                   "balanced, few applies — but bandwidth-bound")

    # Panel 3: the buffer stack that makes it a memory problem.
    for i in range(7):
        axes[2].add_patch(mpatches.Rectangle((8.7, 3.4 + i * 0.55), 0.9, 0.42,
                                             facecolor=ORANGE, alpha=0.5))
    axes[2].text(9.15, 7.6, "1 buffer\nper patch", fontsize=7.5, color="#8a5a0f",
                 ha="center", va="bottom")

    legend = [
        mpatches.Patch(facecolor=BLUE, alpha=0.85, label="simulating sources"),
        mpatches.Patch(facecolor=ORANGE, alpha=0.95, label="beam apply"),
        mpatches.Patch(facecolor="none", edgecolor=INK3, hatch="////", label="idle"),
    ]
    fig.legend(handles=legend, fontsize=8.5, ncol=3, **LEGEND,
               loc="lower center", bbox_to_anchor=(0.5, -0.04))
    plt.tight_layout()
    plt.show()


def patch_accumulator_cost() -> dict:
    """Why the beam applies can't simply be deferred to a second pass.

    One patch accumulator is n_baselines x n_channels x 1 complex<double>
    (stokes-I here) - `patch_model_data` in OnePredict.cc. Today that is one
    buffer per *thread*, reused and zeroed at each patch boundary. Holding
    every patch's contribution until a second pass needs one per *patch*
    instead, which is what turns the deferred variant into a
    memory-bandwidth problem rather than a scheduling one.
    """
    ref = pd.read_csv(DATA / "reference_workload.csv").set_index("quantity")
    baselines = int(ref.loc["baselines", "value"])
    channels = int(ref.loc["channels", "value"])
    patches = int(ref.loc["patches", "value"])
    buffer_bytes = baselines * channels * 16  # complex<double>, 1 correlation
    return {
        "buffer_mb": buffer_bytes / 1e6,
        "patches": patches,
        "total_gb": buffer_bytes * patches / 1e9,
    }


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
    ax.legend(**LEGEND)
    plt.tight_layout()
    plt.show()

    pct = 100 * (sc_ok["baseline_predict_agg_s"] - sc_ok["tbb_predict_agg_s"]) / sc_ok["baseline_predict_agg_s"]
    pending = [int(t) for t in sc[sc["status"] == "pending"]["threads"]]
    note = ""
    if pending:
        counts = ", ".join(str(t) for t in pending)
        note = f" (not measured at {counts} thread{'s' if pending[-1] != 1 else ''})"

    # Don't fold a regression into the "X-Y% faster" range - a negative
    # min renders as "-75-24% faster", which reads as a typo rather than
    # as the result it is. Report the two directions separately.
    gain, loss = pct[pct > 0], pct[pct <= 0]
    if loss.empty:
        lead = (f"**{gain.min():.0f}–{gain.max():.0f}% faster** than the static "
                f"baseline at every measured thread count{note}")
    else:
        slow = ", ".join(str(int(t)) for t in sc_ok.loc[loss.index, "threads"])
        lead = (f"**{gain.min():.0f}–{gain.max():.0f}% faster** at "
                f"{len(gain)} of {len(pct)} thread counts{note}, but "
                f"**{abs(loss.min()):.0f}% slower** at {slow}")
    return Markdown(
        lead + ". Still far short of what the profiling budget suggested "
        "was available."
    )


# --------------------------------------------------------------- slide 11 --
# Slide 11's comparison: the tiled build has not been introduced yet there.
_MEM_PAIR = {"static_baseline": ("static split", BLUE),
             "tbb_fixed": ("TBB stealing", ORANGE)}


def memory_traffic_bars() -> Markdown | None:
    """Where the stalls are, static baseline vs. TBB. Slide 11 sits before
    the tiled build exists in the story, so it compares only those two."""
    mem = pd.read_csv(DATA / "memory_traffic.csv")
    mem = mem[mem["status"] == "confirmed"].set_index("implementation")
    pair = [k for k in _MEM_PAIR if k in mem.index]
    if len(pair) < 2:
        return Markdown(f"*(memory-access measurement pending for "
                        f"{', '.join(k for k in _MEM_PAIR if k not in mem.index)})*")

    categories = ["l1_bound_pct", "l2_bound_pct", "l3_bound_pct",
                  "dram_bound_pct", "store_bound_pct"]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    x = range(len(categories))
    width = 0.35
    for i, key in enumerate(pair):
        offset = (i - (len(pair) - 1) / 2) * width
        ax.bar([xi + offset for xi in x], [mem.loc[key, c] for c in categories],
               width=width, color=_MEM_PAIR[key][1], label=_MEM_PAIR[key][0])
    ax.set_xticks(list(x))
    ax.set_xticklabels(["L1", "L2", "L3", "DRAM", "Store"])
    ax.set_ylabel("% of clockticks stalled")
    ax.legend(**LEGEND)
    plt.tight_layout()
    plt.show()
    return None


def memory_traffic_table() -> Markdown | None:
    """Raw counts behind the bars: what actually moved, baseline vs. TBB."""
    mem = pd.read_csv(DATA / "memory_traffic.csv")
    mem = mem[mem["status"] == "confirmed"].set_index("implementation")
    if any(k not in mem.index for k in _MEM_PAIR):
        return None
    base, tbb = (mem.loc[k] for k in _MEM_PAIR)

    def fmt(n):
        n = float(n)
        for scale, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
            if n >= scale:
                return f"{n / scale:.1f}{suffix}"
        return f"{n:.0f}"

    # Load/store counts are instructions, so SIMD deflates them without
    # moving fewer bytes; LLC misses are cache-line events and carry the
    # traffic claim.
    rows = [
        ("Memory Bound", f"{base['memory_bound_pct']:.0f}%", f"{tbb['memory_bound_pct']:.0f}%"),
        ("L3 Bound", f"{base['l3_bound_pct']:.1f}%", f"{tbb['l3_bound_pct']:.1f}%"),
        ("DRAM Bound", f"{base['dram_bound_pct']:.1f}%", f"{tbb['dram_bound_pct']:.1f}%"),
        ("Load ops", fmt(base["loads"]), fmt(tbb["loads"])),
        ("LLC misses", fmt(base["llc_miss_count"]), fmt(tbb["llc_miss_count"])),
    ]
    table = ("| metric | static | TBB |\n|---|---:|---:|\n"
             + "\n".join(f"| {n} | {a} | {b} |" for n, a, b in rows))

    delta = float(tbb["llc_miss_count"]) / float(base["llc_miss_count"]) - 1
    note = (f"\n\nWork stealing moves **{delta:+.0%} LLC misses** in our test case.")
    return Markdown(table + note)


# --------------------------------------------------------------- slide 12 --
def tiling_diagram() -> None:
    """Traversal order over the channel x source grid, before and after.

    Axes are labelled because the point is which axis is swept innermost:
    per-source dispatch crosses all channels for one source and evicts the
    slab before the next source can reuse it; tiling holds one channel slab
    and runs every source in the block against it.
    """
    ref = pd.read_csv(DATA / "reference_workload.csv").set_index("quantity")
    n_chan = int(ref.loc["channels", "value"])
    slab = 53
    n_slabs = 4
    n_src = 6

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))

    def frame(ax, title):
        ax.set_xlim(0, 10)
        ax.set_ylim(0, n_src)
        ax.set_title(title, loc="left", fontsize=12, color=INK, pad=16)
        ax.set_xlabel(f"channels  →   ({fmt_int(n_chan)} total)", fontsize=10)
        ax.set_ylabel("sources", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ("left", "bottom"):
            ax.spines[spine].set_visible(True)
        ax.add_patch(mpatches.Rectangle((0, 0), 10, n_src, fill=False,
                                        edgecolor=INK3, linewidth=1))

    # ---- left: one source at a time, across every channel
    ax = axes[0]
    frame(ax, "Per-source dispatch")
    for i in range(n_src):
        y = n_src - 0.5 - i
        ax.annotate("", xy=(9.7, y), xytext=(0.3, y),
                    arrowprops=dict(arrowstyle="->", color=ORANGE, lw=2))
        ax.text(0.25, y, str(i + 1), fontsize=8, color=ORANGE,
                ha="right", va="center")
    ax.add_patch(mpatches.Rectangle((0, 0), 10 * slab / n_chan, n_src,
                                    facecolor=TEAL, alpha=0.16,
                                    edgecolor=TEAL, linestyle="dashed", linewidth=1.2))
    ax.text(10 * slab / n_chan + 0.25, n_src + 0.12,
            f"only ~{slab} channels fit in L2", fontsize=9, color=TEAL, va="bottom")
    ax.text(5, -1.05, "each source re-crosses the whole row —\nthe slab is evicted before the next one reuses it",
            fontsize=9.5, color=ORANGE, ha="center", va="top")

    # ---- right: one channel slab at a time, across every source
    ax = axes[1]
    frame(ax, "Channel × source tiling")
    w = 10 / n_slabs
    for k in range(1, n_slabs):
        ax.plot([k * w] * 2, [0, n_src], color=INK3, linewidth=0.8, linestyle="dotted")
    ax.add_patch(mpatches.Rectangle((0, 0), w, n_src, facecolor=TEAL, alpha=0.16,
                                    edgecolor=TEAL, linewidth=1.4))
    for i in range(n_src):
        y = n_src - 0.5 - i
        ax.annotate("", xy=(w - 0.25, y), xytext=(0.25, y),
                    arrowprops=dict(arrowstyle="->", color=TEAL, lw=2))
        ax.text(0.25, y, str(i + 1), fontsize=8, color=TEAL, ha="right", va="center")
    ax.annotate("", xy=(w + 0.9, n_src / 2), xytext=(w + 0.1, n_src / 2),
                arrowprops=dict(arrowstyle="->", color=INK2, lw=1.6))
    ax.text(w + 1.15, n_src / 2, "then the\nnext slab", fontsize=8.5,
            color=INK2, ha="left", va="center")
    ax.text(w / 2, n_src + 0.12, f"{slab} channels", fontsize=9, color=TEAL, ha="center")
    ax.text(5, -1.05, "the slab stays in L2 while every source uses it",
            fontsize=9.5, color=TEAL, ha="center", va="top")

    plt.tight_layout()
    plt.show()


# ------------------------------------------------------------ slides 13-14 --
STAGE_LABELS = {
    "upstream_original": "upstream",
    "tiled_layout": "tiled\nlayout",
    "split_planes": "split\nplanes",
    "slab_rounding": "slab\nrounding",
    "simd_sincos": "SIMD\nsincos",
}


def loop_progression() -> dict:
    """The three inner-loop changes taken together, measured on a normal
    (non-beam) timestep - the work they actually touch."""
    prog = pd.read_csv(DATA / "progression.csv").set_index("stage")
    before, after = prog.loc["tiled_layout"], prog.loc["simd_sincos"]
    return {"before": before["normal_timestep_s"], "after": after["normal_timestep_s"],
            "speedup": before["normal_timestep_s"] / after["normal_timestep_s"],
            "total_before": before["predict_s"], "total_after": after["predict_s"],
            "total_speedup": before["predict_s"] / after["predict_s"]}


def loop_progression_bars() -> None:
    """Normal-timestep time across the three inner-loop commits."""
    prog = pd.read_csv(DATA / "progression.csv").set_index("stage")
    stages = ["tiled_layout", "split_planes", "slab_rounding", "simd_sincos"]
    labels = ["tiled\nlayout", "split\nplanes", "slab\nrounding", "SIMD\nsincos"]
    vals = [prog.loc[st, "normal_timestep_s"] for st in stages]

    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    ax.bar(range(len(vals)), vals, color=["#b5bcc0"] * 3 + [TEAL], width=0.62)
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("normal timestep, s")
    ax.set_ylim(0, max(vals) * 1.2)
    for i, v in enumerate(vals):
        ax.text(i, v + max(vals) * 0.03, f"{v:.2f}s", ha="center", fontsize=9)
    plt.tight_layout()
    plt.show()


def inner_loop_diagram() -> None:
    """The three inner-loop changes, before -> after, one row each.

    The SIMD row is drawn against a vertical time axis: scalar work occupies
    eight time slots, the vectorised form occupies one.
    """
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 5.0),
                             gridspec_kw={"height_ratios": [1, 1, 2.6]})
    for ax in axes[:2]:
        ax.set_xlim(0, 20)
        ax.set_ylim(-0.6, 1.3)
        ax.axis("off")

    def arrow(ax, y=0.35):
        ax.annotate("", xy=(11.2, y), xytext=(9.2, y),
                    arrowprops=dict(arrowstyle="->", color=INK2, lw=1.6))

    # 1. interleaved complex<double> -> two float planes
    ax = axes[0]
    ax.text(0, 1.0, "interleaved complex → split real/imag float planes",
            fontsize=9.5, color=INK)
    for i in range(8):
        ax.add_patch(mpatches.Rectangle((i, 0.1), 0.85, 0.55,
                                        facecolor=BLUE if i % 2 == 0 else ORANGE, alpha=0.85))
    arrow(ax)
    for i in range(8):
        ax.add_patch(mpatches.Rectangle((11.8 + i * 0.5, 0.42), 0.42, 0.25,
                                        facecolor=BLUE, alpha=0.85))
        ax.add_patch(mpatches.Rectangle((11.8 + i * 0.5, 0.08), 0.42, 0.25,
                                        facecolor=ORANGE, alpha=0.85))

    # 2. 53 channels (ragged epilogue) -> 48 (whole vector widths)
    ax = axes[1]
    ax.text(0, 1.0, "53 channels → 48, a whole multiple of the vector width",
            fontsize=9.5, color=INK)
    for st in range(0, 53, 8):
        n = min(8, 53 - st)
        ax.add_patch(mpatches.Rectangle((st * 0.16, 0.1), n * 0.16 - 0.04, 0.55,
                                        facecolor=ORANGE if n < 8 else BLUE, alpha=0.85))
    arrow(ax)
    for st in range(0, 48, 8):
        ax.add_patch(mpatches.Rectangle((11.8 + st * 0.16, 0.1), 8 * 0.16 - 0.04, 0.55,
                                        facecolor=TEAL, alpha=0.85))

    # 3. scalar: one lane per time slot; vectorised: eight lanes in one slot
    ax = axes[2]
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.text(0, 9.4, "scalar sin/cos/exp → 8 lanes per instruction",
            fontsize=9.5, color=INK)

    top, h, gap = 8.4, 0.82, 0.18
    ax.annotate("", xy=(0.5, top - 8 * (h + gap) - 0.1), xytext=(0.5, top + h),
                arrowprops=dict(arrowstyle="->", color=INK3, lw=1.4))
    ax.text(0.15, top - 4 * (h + gap), "time", fontsize=9, color=INK3,
            rotation=90, ha="right", va="center")

    for i in range(8):  # scalar: eight slots, one block each
        ax.add_patch(mpatches.Rectangle((1.4, top - i * (h + gap)), 1.1, h,
                                        facecolor=ORANGE, alpha=0.85))
    ax.text(1.95, top - 8 * (h + gap) - 0.35, "8 iterations", fontsize=8.5,
            color=ORANGE, ha="center", va="top")

    arrow(ax, y=top - 3.5 * (h + gap))

    for i in range(8):  # vectorised: one slot, eight lanes
        ax.add_patch(mpatches.Rectangle((11.8 + i * 1.0, top), 0.85, h,
                                        facecolor=TEAL, alpha=0.85))
    ax.text(15.8, top - 0.35, "1 iteration", fontsize=8.5, color=TEAL,
            ha="center", va="top")

    plt.tight_layout()
    plt.show()


def progression_bars(up_to_stage: str) -> dict:
    """Cumulative bar chart: predict time per optimization stage, from
    upstream through up_to_stage. Slide 13 calls it; the per-commit
    breakdown it used to feed on slides 14-16 is now loop_progression_bars()
    on the merged slide 14."""
    prog = pd.read_csv(DATA / "progression.csv").set_index("stage")
    stages = list(STAGE_LABELS)
    stages = stages[: stages.index(up_to_stage) + 1]
    values = prog.loc[stages, "predict_s"]
    upstream = prog.loc["upstream_original", "predict_s"]

    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    colors = ["#b5bcc0"] * (len(stages) - 1) + [TEAL]
    ax.bar(range(len(stages)), values, color=colors, width=0.6)
    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels([STAGE_LABELS[s] for s in stages], fontsize=9)
    ax.set_ylabel("predict step, s")
    ax.set_ylim(0, upstream * 1.15)
    for i, v in enumerate(values):
        ax.text(i, v + upstream * 0.02, f"{fmt_int(v)}s", ha="center", fontsize=9)
    plt.tight_layout()
    plt.show()
    current = values.iloc[-1]
    out = {"before": upstream, "after": current, "speedup": upstream / current}

    # Step gain on a normal (non-beam) timestep as well as on total predict
    # time. The totals are diluted by the two beam-recompute timesteps, which
    # none of these optimisations touch.
    col = prog["normal_timestep_s"]
    if len(stages) > 1 and pd.notna(col.get(stages[-1])) and pd.notna(col.get(stages[-2])):
        before, after = col[stages[-2]], col[stages[-1]]
        out.update({"normal_before": before, "normal_after": after,
                    "normal_speedup": before / after,
                    "step_speedup": values.iloc[-2] / current})
    return out


# --------------------------------------------------------------- slide 15 --
def amdahl_split() -> dict:
    """Predict time at full thread count split into the two beam-recompute
    timesteps and the 28 normal ones, baseline vs. final.

    Everything on slides 12-14 acts on the normal timesteps; the beam calls
    are EveryBeam and untouched, so they set the floor on total speedup.
    """
    rows = {}
    for key, name in (("baseline", "baseline_scaling.csv"),
                      ("final", "final_scaling.csv")):
        df = pd.read_csv(DATA / name).set_index("threads")
        hi = df.index.max()
        rows[key] = (df.loc[hi, "n_normal"] * df.loc[hi, "normal_mean_s"],
                     df.loc[hi, "n_beam"] * df.loc[hi, "beam_mean_s"])
    (bn, bb), (fn, fb) = rows["baseline"], rows["final"]

    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    x = [0, 1]
    ax.bar(x, [bn, fn], color=TEAL, width=0.55, label="everything else")
    ax.bar(x, [bb, fb], bottom=[bn, fn], color=ORANGE, width=0.55,
           label="beam recompute (EveryBeam)")
    ax.set_xticks(x)
    ax.set_xticklabels(["baseline", "final"])
    ax.set_ylabel("predict step, s")
    ax.legend(fontsize=9, **LEGEND)
    for xi, (n, b) in zip(x, ((bn, bb), (fn, fb))):
        ax.text(xi, n + b + 8, f"{fmt_int(n + b)}s", ha="center", fontsize=9)
    plt.tight_layout()
    plt.show()

    return {"base_normal": bn, "base_beam": bb, "final_normal": fn,
            "final_beam": fb, "normal_speedup": bn / fn,
            "beam_speedup": bb / fb,
            "beam_share_pct": fb / (fn + fb) * 100}


# --------------------------------------------------------------- slide 17 --
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
    ax.legend(**LEGEND)
    plt.tight_layout()
    plt.show()

    prog = pd.read_csv(DATA / "progression.csv").set_index("stage")
    upstream = prog.loc["upstream_original", "predict_s"]
    final_100ts = prog.loc["simd_sincos", "predict_s"]

    # Same thread range for both, or the comparison is rigged: efficiency
    # decays over a wider range and the two sweeps start at 2 and 4.
    lo = max(final["threads"].min(), baseline["threads"].min())
    f_lo, f_hi = final.set_index("threads").loc[[lo, 72], "predict_agg_s"]
    b_lo, b_hi = baseline.set_index("threads").loc[[lo, 72], "predict_agg_s"]
    ideal = 72 / lo

    return {
        "upstream": upstream,
        "final_100ts": final_100ts,
        "speedup": upstream / final_100ts,
        "scaling_speedup": f_lo / f_hi,
        "baseline_scaling_speedup": b_lo / b_hi,
        "ideal_speedup": ideal,
        "efficiency_pct": (f_lo / f_hi) / ideal * 100,
        "baseline_efficiency_pct": (b_lo / b_hi) / ideal * 100,
        "efficiency_from_threads": int(lo),
    }
