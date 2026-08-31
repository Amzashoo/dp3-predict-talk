"""Shared setup for every script in this directory. Import, don't run.

This repo (dp3-predict-talk) is independent of the DP3 checkout, but every
script here still needs one - to build the branches/commits named in its
own header comment (see ../REPRODUCTION.md), and to reuse DP3's
setup_env.sh / measures-data fix. Point DP3_REPO at it; defaults to a
sibling checkout next to this repo (../DP3), which is where it happened to
live when this repo was split out.

Every script here assumes:
  - it runs from a git worktree checked out at the commit/branch named in
    its own header comment
  - it runs on a SCITAS-style SLURM cluster node with --exclusive, one job
    per node, 72 cores (2x Intel Xeon Platinum 8360Y, Ice Lake-SP)
  - intel-oneapi-vtune is available via `module load` where a script needs
    it (see sourced_env(vtune=True))

None of these scripts are wired into slides.qmd automatically - they
regenerate the CSVs under ../data/, which the qmd reads.
"""
from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TALK_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = TALK_DIR / "data"

_dp3_repo_env = os.environ.get("DP3_REPO")
DP3_REPO = Path(_dp3_repo_env) if _dp3_repo_env else (TALK_DIR.parent / "DP3")
if not DP3_REPO.is_dir():
    sys.exit(
        f"DP3_REPO not found at {DP3_REPO}. Set DP3_REPO=/path/to/DP3 "
        "or check out DP3 as a sibling of this repo."
    )
PSET = DP3_REPO / "params_compare.pset"

NCORES = 72


def sourced_env(vtune: bool = False) -> dict:
    """The environment after sourcing DP3's setup_env.sh (and, if vtune,
    `module load intel-oneapi-vtune`) - so subprocess calls see the same
    spack/module environment the original bash scripts did. Shells out
    once and diffs os.environ, since Python can't source a bash script
    in-process."""
    shell_cmd = f"source {DP3_REPO}/setup_env.sh"
    if vtune:
        shell_cmd += " && module load intel-oneapi-vtune"
    shell_cmd += " && env -0"

    result = subprocess.run(
        ["bash", "-c", shell_cmd], capture_output=True, check=True
    )
    env = dict(os.environ)
    for entry in result.stdout.split(b"\0"):
        if b"=" in entry:
            key, _, value = entry.decode().partition("=")
            env[key] = value
    env["CASARCFILES"] = str(DP3_REPO / "presentation_data" / "measures.casarc")
    return env


def run(cmd: list[str], env: dict, log_path: Path | None = None) -> str:
    """Runs `cmd`, returns combined stdout+stderr as text. Raises on a
    nonzero exit UNLESS check=False is what you want - callers that expect
    a nonzero exit (e.g. vtune -duration killing the target on purpose)
    should call subprocess.run directly instead."""
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
    text = result.stdout + result.stderr
    if log_path:
        log_path.write_text(text)
    return text


def parse_predict_times(text: str) -> tuple[list[float], list[float]]:
    """Returns (normal_times, beam_times). The 2 largest 'Predict time:'
    values in a debuglevel>=1 log are the beam-recompute timesteps, same
    convention used throughout this project's data."""
    times = [float(x) for x in re.findall(r"Predict time:\s*([\d.]+)", text)]
    srt = sorted(times)
    return srt[:-2], srt[-2:]


def write_scaling_row(csv_path: Path, threads: int, normal: list[float], beam: list[float]):
    """Appends one row to a scaling-table CSV, creating it with a header
    if it doesn't exist yet."""
    is_new = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["threads", "n_normal", "normal_mean_s", "n_beam", "beam_mean_s", "predict_agg_s"])
        w.writerow([
            threads, len(normal), f"{sum(normal)/len(normal):.4f}",
            len(beam), f"{sum(beam)/len(beam):.4f}", f"{sum(normal)+sum(beam):.4f}",
        ])


def parse_per_thread_blocks(text: str, stage: str = "worker.simulate") -> list[dict]:
    """Every PER-THREAD block in a debuglevel=2 log, as a list (one entry
    per timestep) of {thread_id: (items, seconds)}.

    Shared by 03_baseline_histogram.py and 08_tbb_histogram.py so the two
    builds are always summarised the same way - they are compared directly
    on slides 6 and 9, and a difference in parsing would show up as a
    difference in the scheduler.
    """
    blocks = [b.get(stage, {}) for b in parse_all_stages(text)]
    blocks = [b for b in blocks if b]
    if not blocks:
        raise RuntimeError(f"no PER-THREAD rows for stage {stage!r} - "
                           "was debuglevel=2 set, and does this build have "
                           "that timer?")
    return blocks


def parse_all_stages(text: str) -> list[dict]:
    """Every PER-THREAD block, as {stage: {thread_id: (items, seconds)}}.

    Parses all stages rather than one, so callers can check what fraction
    of a thread's work each timer actually covers instead of assuming.
    """
    blocks = []
    for block in re.findall(
        r"PER-THREAD BEGIN ===\n.*?thread;stage;.*?\n(.*?)=== PER-THREAD END",
        text, re.S,
    ):
        stages: dict = {}
        for line in block.strip().splitlines():
            line = re.sub(r"^\[\s*[\d.]+\]\s*", "", line.strip())
            parts = line.rstrip(";").split(";")
            if len(parts) < 9:
                continue
            try:
                thread, count, total_ms = int(parts[0]), int(parts[2]), float(parts[3])
            except ValueError:
                continue  # header or malformed row
            stages.setdefault(parts[1], {})[thread] = (count, total_ms / 1000.0)
        if stages:
            blocks.append(stages)
    if not blocks:
        raise RuntimeError("no PER-THREAD blocks found - was debuglevel=2 set?")
    return blocks


def predict_timestep_times(text: str) -> list[float]:
    """The per-timestep "Predict time:" values (s), used to check that the
    whole-range timer actually covers the predict phase rather than some
    inner slice of it."""
    return [float(x) for x in re.findall(r"Predict time:\s*([\d.]+)", text)]


def balance_stats(blocks: list[dict]) -> dict:
    """Load-balance summary over per-timestep blocks.

    Computed per timestep and then averaged - NOT over per-thread averages.
    Averaging each thread across timesteps first would hide the very thing
    this measures for a work-stealing scheduler: its assignment is random
    per timestep, so a thread that is unlucky once and lucky the next
    averages out to looking perfectly balanced, while the static split (the
    same assignment every timestep) has no such variance to average away.
    That asymmetry would flatter whichever build is nondeterministic.

    `utilization` is mean/max thread busy time within a timestep: the
    fraction of the makespan an average thread actually spent working, so
    100% is perfect balance and lower means threads sat idle waiting for a
    straggler. It is the metric that maps to lost wall time; `spread` (the
    min-to-max range) is reported too but is a single-outlier metric.
    """
    per_ts = []
    for rows in blocks:
        times = [t for _, t in rows.values()]
        mean, hi, lo = sum(times) / len(times), max(times), min(times)
        per_ts.append({
            "utilization_pct": mean / hi * 100,
            "spread_pct": (hi - lo) / mean * 100,
            "makespan_s": hi,
            "busy_mean_s": mean,
        })

    def avg(k):
        return sum(p[k] for p in per_ts) / len(per_ts)

    return {
        "timesteps": len(per_ts),
        "threads": len(blocks[0]),
        "utilization_pct": f"{avg('utilization_pct'):.1f}",
        "spread_pct": f"{avg('spread_pct'):.1f}",
        "makespan_s": f"{avg('makespan_s'):.3f}",
        "busy_mean_s": f"{avg('busy_mean_s'):.3f}",
        "idle_s": f"{avg('makespan_s') - avg('busy_mean_s'):.3f}",
    }


def accounting_report(text: str, outer: str = "worker.range",
                      inner: str = "worker.simulate") -> dict:
    """Check what the timers actually account for, per timestep.

    Three things get verified, because each has already produced a wrong
    answer at least once:

    1. `coverage` - outer-timer makespan against the timestep's own
       "Predict time:". Near 1.0 means the outer timer really does span the
       parallel phase; well under 1.0 means it is timing an inner slice and
       any balance number taken from it describes that slice, not the
       phase.
    2. `inner_share` - what fraction of the outer timer the inner one is.
       This is the trap that made work stealing look broken: simulate() is
       ~60% of a thread's work, so a thread doing more of the uncounted
       remainder shows *less* counted time, which reads as imbalance
       exactly when the scheduler is balancing well.
    3. `negative_residual` - threads where inner > outer, which would mean
       the timers don't nest and the whole decomposition is wrong.
    """
    blocks = parse_all_stages(text)
    predict_times = predict_timestep_times(text)
    per_ts = []
    for i, stages in enumerate(blocks):
        if outer not in stages:
            continue
        out_rows = stages[outer]
        in_rows = stages.get(inner, {})
        makespan = max(t for _, t in out_rows.values())
        out_total = sum(t for _, t in out_rows.values())
        in_total = sum(t for _, t in in_rows.values())
        negatives = sum(
            1 for th, (_, t) in in_rows.items()
            if th in out_rows and t > out_rows[th][1] + 1e-6
        )
        entry = {
            "makespan_s": makespan,
            "outer_total_s": out_total,
            "inner_total_s": in_total,
            "inner_share": in_total / out_total if out_total else 0.0,
            "negative_residual": negatives,
        }
        if i < len(predict_times) and predict_times[i] > 0:
            entry["predict_s"] = predict_times[i]
            entry["coverage"] = makespan / predict_times[i]
        per_ts.append(entry)

    if not per_ts:
        raise RuntimeError(f"stage {outer!r} not present - old binary?")

    def avg(k):
        vals = [p[k] for p in per_ts if k in p]
        return sum(vals) / len(vals) if vals else None

    return {
        "timesteps": len(per_ts),
        "stages_seen": sorted({s for b in blocks for s in b}),
        "coverage": avg("coverage"),
        "inner_share": avg("inner_share"),
        "negative_residual": sum(p["negative_residual"] for p in per_ts),
    }


def balance_from_log(text: str, stage: str = "worker.range") -> tuple:
    """(stats, blocks, indices) for the timesteps this build actually
    instruments end to end.

    The two beam-recompute timesteps are excluded. Where the beam is
    computed decides whether the timer sees it: the static split computes
    beams inside the dispatch (so `stage` covers 100% of those timesteps),
    while the TBB and tiled builds precompute them in a separate
    parallel_for that sits outside it - coverage there drops to 17% and 2%
    respectively. Averaging all 30 would mix a measured phase for one build
    with an unmeasured one for the others. On the 28 normal timesteps
    coverage is 95-100% for all three, which is the like-for-like set.
    It barely moves the answer (static 68.5%->64.2% spread, TBB and tiled
    unchanged) - the point is that the number is now of something all three
    builds actually measured.
    """
    blocks = parse_all_stages(text)
    predict = predict_timestep_times(text)
    idx = [i for i, b in enumerate(blocks) if stage in b and i < len(predict)]
    if not idx:
        raise RuntimeError(f"stage {stage!r} not present - old binary?")
    beam = set(sorted(idx, key=lambda i: -predict[i])[:2])
    normal = [i for i in idx if i not in beam] or idx

    rows = [blocks[i][stage] for i in normal]
    coverage = sum(
        max(t for _, t in blocks[i][stage].values()) / predict[i]
        for i in normal
    ) / len(normal)
    stats = {"stage": stage, "coverage_pct": f"{coverage * 100:.0f}",
             **balance_stats(rows)}
    return stats, rows, normal


def _median_utilization_index(blocks: list[dict]) -> int:
    """Index of the timestep whose utilization is the median.

    The per-thread bar charts show one timestep, so it has to be picked
    without favouring either build: TBB's dispatch is random per timestep,
    so "the first" or "the fullest" block is that run's luck.
    """
    def util(rows):
        times = [t for _, t in rows.values()]
        return (sum(times) / len(times)) / max(times)

    order = sorted(range(len(blocks)), key=lambda i: util(blocks[i]))
    return order[len(order) // 2]


def representative_block(blocks: list[dict]) -> dict:
    """The timestep whose utilization is the median across timesteps.

    The per-thread bar charts show one timestep, so that timestep has to be
    picked without favouring either build: TBB's dispatch is random per
    timestep, so "the first" or "the fullest" block is that run's luck.
    The median-utilization block is representative by construction, and for
    the static split every block is near-identical anyway.
    """
    ranked = sorted(
        blocks,
        key=lambda rows: (
            sum(t for _, t in rows.values()) / len(rows)
        ) / max(t for _, t in rows.values()),
    )
    return ranked[len(ranked) // 2]


def write_balance_row(implementation: str, stats: dict):
    """Upserts one implementation's row in data/load_balance.csv."""
    fields = ["implementation", "stage", "coverage_pct", "timesteps",
              "threads", "utilization_pct", "spread_pct", "makespan_s",
              "busy_mean_s", "idle_s"]
    path = DATA_DIR / "load_balance.csv"
    rows = {}
    if path.exists():
        with open(path) as f:
            rows = {r["implementation"]: r for r in csv.DictReader(f)}
    rows[implementation] = {"implementation": implementation, **stats}
    order = ["static_baseline", "tbb", "tiled_final"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for key in order:
            if key in rows:
                w.writerow(rows[key])
    return path


def run_histogram(dp3_exe: str, implementation: str, csv_name: str,
                  use_original: bool, ntimes: int = 30):
    """The whole per-thread-histogram measurement, shared by scripts 03, 08
    and 09 so the three builds they compare can't drift apart in method.

    They are read side by side on slides 6 and 9, so everything except the
    binary and the predict flag has to be identical: same node (each
    caller pins the same --nodelist), same ntimes, same parsing, same
    representative-timestep rule, same balance metric. The bug this guards
    against already happened once - two copies of the parser sampled a
    single timestep differently and made work stealing look twice as
    imbalanced as the static split.

    Writes the representative timestep to data/<csv_name> for the bar
    chart, and the per-timestep balance stats to data/load_balance.csv.
    """
    env = sourced_env()
    with tempfile.TemporaryDirectory() as tmp:
        log = run(
            [
                dp3_exe, str(PSET),
                "numthreads=72", f"msin.ntimes={ntimes}", "solve1.debuglevel=2",
                "solve1.usefastpredict=false",
                f"solve1.useoriginalpredict={'true' if use_original else 'false'}",
                "msout=",
                *h5parm_args(Path(tmp)),
            ],
            env=env,
        )

    log_path = TALK_DIR / "scripts" / f"talk-hist-{implementation}-{os.environ.get('SLURM_JOB_ID','local')}.log"
    log_path.write_text(log)

    audit = accounting_report(log)
    print(f"accounting: stages={audit['stages_seen']} timesteps={audit['timesteps']}")
    print(f"  worker.range covers {audit['coverage']:.1%} of the reported "
          f"predict time; worker.simulate is {audit['inner_share']:.1%} of it")
    if audit["negative_residual"]:
        raise RuntimeError(
            f"{audit['negative_residual']} thread-timesteps have "
            "worker.simulate > worker.range - the timers don't nest, so the "
            "per-thread breakdown is wrong; fix before using these numbers")
    if audit["coverage"] is not None and audit["coverage"] < 0.9:
        print(f"  WARNING: worker.range covers only {audit['coverage']:.1%} of "
              "the predict phase - balance measured from it describes that "
              "slice, not the phase")

    # worker.range, not worker.simulate: simulate() is only ~60% of a
    # thread's work, and measuring the counted part alone inverts the answer.
    stats, range_blocks, normal_idx = balance_from_log(log)
    blocks = parse_all_stages(log)
    sim_blocks = [blocks[i].get("worker.simulate", {}) for i in normal_idx]

    # The bar chart carries both, so nothing is hidden: `items` and
    # simulate_s show how the sources were distributed, range_s the thread's
    # whole work, other_s the beam-apply remainder between them.
    rep_index = _median_utilization_index(range_blocks)
    rep_sim, rep_range = sim_blocks[rep_index], range_blocks[rep_index]

    out_csv = DATA_DIR / csv_name
    with open(out_csv, "w") as f:
        f.write("thread_id,items,simulate_s,range_s,other_s\n")
        for t in sorted(rep_range):
            items, sim_s = rep_sim.get(t, (0, 0.0))
            _, range_s = rep_range[t]
            f.write(f"{t},{items},{sim_s:.4f},{range_s:.4f},{range_s - sim_s:.4f}\n")

    bal = write_balance_row(implementation, stats)
    print(f"wrote {out_csv} ({len(rep_range)} threads, representative of "
          f"{len(range_blocks)} non-beam timesteps)")
    print(f"wrote {bal}: stage=worker.range coverage={stats['coverage_pct']}% "
          f"utilization={stats['utilization_pct']}% "
          f"spread={stats['spread_pct']}% makespan={stats['makespan_s']}s")
    print(f"  raw log kept at {log_path.name}")


def h5parm_args(h5dir: Path) -> list[str]:
    """DP3 needs distinct h5parm output paths per run, or concurrent jobs
    silently collide on a shared default path and stall (found the hard
    way - see git history of scripts/collect_cpuutil_generic.sh in the
    main DP3 repo's presentation_data/ for the postmortem)."""
    h5dir.mkdir(parents=True, exist_ok=True)
    return [f"solve{i}.h5parm={h5dir / f'solve{i}.h5parm'}" for i in (1, 2, 3, 4)]
