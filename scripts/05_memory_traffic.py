#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 3:00:00
#SBATCH --partition=bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-05-memory-traffic
#SBATCH --output=talk-05-memory-traffic-%j.out
"""Slide 11 (memory traffic / L3 cache misses): VTune memory-access
profile, restricted to the predict phases only.

All builds of a comparison run inside ONE job, so the benchmark is
single-node by construction (--nodelist is not needed and only makes it
queue).



label=tbb:   solve1.useoriginalpredict=true  (OnePredict.cc)
label=final: solve1.useoriginalpredict=false (OnePredictNew.cc, tiled)
Both share one ITT-instrumented binary - build with -DDP3_ENABLE_ITT=ON.

Usage: sbatch 05_memory_traffic.py <repeats> label:/path/to/DP3 [label:... ]
       labels: baseline, tbb, final
"""
import csv
import datetime
import io
import subprocess
import sys
import tempfile
from pathlib import Path

import os
import sys
sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common

# An ITT task marks only the thread that opens it, so worker-level tasks are
# needed too: "predict_range" (baseline) and TBB's own "tbb_parallel_for".
PREDICT_TASKS = {"beam_predict", "normal_predict", "tbb_parallel_for",
                 "predict_range"}

# label -> (row name, useoriginalpredict value). `baseline` and `tbb` both
# take true and differ only by which binary is passed - check the path.
LABELS = {
    "baseline": ("static_baseline", "true"),
    "tbb": ("tbb_fixed", "true"),
    "final": ("tiled_final", "false"),
}


def parse_task_report(text: str) -> dict:
    """Aggregate the predict-only task rows from a `-group-by task` CSV
    report: raw counts (loads/stores/LLC misses) are summed, percentages
    are averaged weighted by each task's CPU Time (non-overlapping self
    time, so it's a valid weight)."""
    all_rows = list(csv.DictReader(io.StringIO(text)))
    rows = [r for r in all_rows if r["Task Type"] in PREDICT_TASKS]
    if not rows:
        raise RuntimeError("no predict-task rows in vtune -group-by task report - "
                            "was the binary built with -DDP3_ENABLE_ITT=ON?")

    def f(row, col):
        return float(row[col]) if row[col] else 0.0

    total_cpu_time = sum(f(r, "CPU Time") for r in rows)

    # Guard against uninstrumented workers: an uncaught 0.5%-coverage run
    # produced a complete, plausible, wrong table once. Healthy is 86-87%.
    measured = sum(f(r, "CPU Time") for r in all_rows)
    coverage = total_cpu_time / measured if measured else 0.0
    if coverage < 0.6:
        outside = {r["Task Type"]: round(f(r, "CPU Time"), 1) for r in all_rows
                   if r["Task Type"] not in PREDICT_TASKS}
        raise RuntimeError(
            f"only {coverage:.1%} of CPU time is inside a predict task "
            f"({total_cpu_time:.0f}s of {measured:.0f}s) - the worker threads "
            f"are not instrumented, so these numbers describe a sliver of the "
            f"run. Unattributed: {outside}")

    def weighted_pct(col):
        return sum(f(r, col) * f(r, "CPU Time") for r in rows) / total_cpu_time

    def summed(col):
        return sum(int(float(r[col])) for r in rows if r[col])

    return {
        "memory_bound_pct": f"{weighted_pct('Memory Bound(%)'):.1f}",
        "l1_bound_pct": f"{weighted_pct('Memory Bound:L1 Bound(%)'):.1f}",
        "l2_bound_pct": f"{weighted_pct('Memory Bound:L2 Bound(%)'):.1f}",
        "l3_bound_pct": f"{weighted_pct('Memory Bound:L3 Bound(%)'):.1f}",
        "dram_bound_pct": f"{weighted_pct('Memory Bound:DRAM Bound(%)'):.1f}",
        "store_bound_pct": f"{weighted_pct('Memory Bound:Store Bound(%)'):.1f}",
        "loads": str(summed("Loads")),
        "stores": str(summed("Stores")),
        "llc_miss_count": str(summed("LLC Miss Count")),
    }


RUNS_CSV = common.DATA_DIR / "memory_traffic_runs.csv"
MEDIAN_CSV = common.DATA_DIR / "memory_traffic.csv"

METRICS = ["memory_bound_pct", "l1_bound_pct", "l2_bound_pct", "l3_bound_pct",
           "dram_bound_pct", "store_bound_pct", "loads", "stores", "llc_miss_count"]
RUN_FIELDS = ["implementation", "job_id", "node", "result_dir"] + METRICS


def append_run(row: dict):
    """Appends one measured run to memory_traffic_runs.csv (the raw record,
    one line per run) rather than overwriting a single-value table.

    These numbers move enough between runs to matter - the same tbb build
    measured 37.8% memory-bound on one node and 49.7-51.3% on another - so
    the deck needs the spread visible, not whichever run happened to go
    last. memory_traffic.csv is derived from this file, never edited by
    hand.
    """
    is_new = not RUNS_CSV.exists()
    with open(RUNS_CSV, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RUN_FIELDS)
        if is_new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in RUN_FIELDS})


def write_median_table():
    """Rebuilds memory_traffic.csv as the per-metric median of the runs for
    each implementation, so one outlier run can't set the number on the
    slide. Returns [(implementation, row, n_runs)].

    Only runs from a single node are pooled. Memory-bound%/LLC counts vary
    enough between nodes (37.8% vs 49.7-51.3% for the same binary) that
    mixing them would produce a median describing no machine in
    particular - and the pinned node changes whenever the usual one is
    reserved, so runs from several nodes do accumulate in the raw file.
    The node used is the latest one that has data for *both*
    implementations; if none does, the comparison isn't ready and this
    raises rather than quietly averaging across machines.
    """
    with open(RUNS_CSV) as f:
        runs = list(csv.DictReader(f))

    impls = tuple(name for name, _ in LABELS.values())
    by_node = {}
    for r in runs:
        by_node.setdefault(r["node"], set()).add(r["implementation"])
    # later rows are later runs: take the last node covering both
    # A node qualifies only once it carries every implementation the deck
    # compares. Anything less and the table mixes machines.
    required = set(impls)
    complete = [n for n in dict.fromkeys(r["node"] for r in reversed(runs))
                if required <= by_node.get(n, set())]
    if not complete:
        have = {n: sorted(v & set(impls)) for n, v in by_node.items()}
        raise RuntimeError(
            f"no single node has runs for all of {sorted(required)} yet, so no "
            f"like-for-like median can be built. Have: {have}")
    node = complete[0]
    runs = [r for r in runs if r["node"] == node]

    def median(values):
        v = sorted(float(x) for x in values if x != "")
        n = len(v)
        return (v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2) if v else 0.0

    out, summary = [], []
    for impl in impls:
        mine = [r for r in runs if r["implementation"] == impl]
        if not mine:
            continue
        row = {"implementation": impl, "node": node, "n_runs": len(mine)}
        for m in METRICS:
            med = median([r[m] for r in mine])
            row[m] = f"{med:.1f}" if m.endswith("_pct") else str(int(med))
        row["status"] = "confirmed"
        out.append(row)
        summary.append((impl, row, len(mine)))

    with open(MEDIAN_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["implementation"] + METRICS
                           + ["node", "n_runs", "status"])
        w.writeheader()
        for row in out:
            w.writerow(row)
    return summary


def collect(label: str, dp3_exe: str, env: dict) -> dict:
    """One VTune run of one build, returned as a row for the raw CSV."""
    predict_flag = "solve1.useoriginalpredict=" + LABELS[label][1]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    result_dir = common.DP3_REPO / f"r_membw_{label}_{timestamp}"

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [
                "vtune", "-collect", "memory-access", "-data-limit=60000",
                "-knob", "sampling-interval=20",
                "-knob", "analyze-mem-objects=false",
                "-knob", "analyze-openmp=false",
                "-start-paused", "-duration=600",
                "-r", str(result_dir), "--",
                dp3_exe, str(common.PSET),
                "numthreads=72", "msin.ntimes=6",
                "solve1.usefastpredict=false", predict_flag, "msout=",
                *common.h5parm_args(Path(tmp) / "h5out"),
            ],
            env=env,
        )

    task_report = subprocess.run(
        ["vtune", "-quiet", "-report", "hotspots", "-r", str(result_dir),
         "-group-by", "task", "-format=csv", "-csv-delimiter=comma"],
        env=env, capture_output=True, text=True, check=True,
    ).stdout

    return {
        "implementation": LABELS[label][0],
        "job_id": os.environ.get("SLURM_JOB_ID", ""),
        "node": os.environ.get("SLURMD_NODENAME", ""),
        "result_dir": result_dir.name,
        **parse_task_report(task_report),
    }


def main():
    args = sys.argv[1:]
    if len(args) < 2 or not args[0].isdigit() or any(":" not in a for a in args[1:]):
        sys.exit("usage: sbatch 05_memory_traffic.py <repeats> label:/path/to/DP3 "
                 "[label:/path/to/DP3 ...]\n"
                 f"       labels: {', '.join(LABELS)}")
    repeats = int(args[0])
    pairs = []
    for spec in args[1:]:
        label, _, exe = spec.partition(":")
        if label not in LABELS:
            sys.exit(f"unknown label {label!r}; expected one of {', '.join(LABELS)}")
        if not Path(exe).is_file():
            sys.exit(f"no such binary: {exe}")
        pairs.append((label, exe))

    # Every build of a comparison in ONE job, so the benchmark is single-node
    # by construction: node variance (37.8% vs 51.3% for one binary) swamps
    # the effect. Binaries may repeat; the (binary, flag) pair must not.
    configs = [(exe, LABELS[label][1]) for label, exe in pairs]
    if len(set(configs)) != len(configs):
        sys.exit("two labels resolve to the same (binary, useoriginalpredict) "
                 "pair - that is one configuration measured twice, not a "
                 "comparison")

    env = common.sourced_env(vtune=True)
    for rep in range(repeats):
        for label, exe in pairs:
            print(f"--- repeat {rep + 1}/{repeats}: {label}", flush=True)
            # Skip, don't abort: vtune -report fails intermittently (corrupt
            # trace, killed worker) and one failure used to lose every run
            # still queued behind it.
            try:
                append_run(collect(label, exe, env))
            except (subprocess.CalledProcessError, RuntimeError) as exc:
                print(f"  SKIPPED {label}: {exc}", flush=True)
    median = write_median_table()

    print(f"appended {repeats * len(pairs)} run(s) to {RUNS_CSV.name}, "
          f"rebuilt {MEDIAN_CSV.name}")
    for impl, row, n in median:
        print(f"  median over {n} run(s) {impl}: memory_bound={row['memory_bound_pct']}% "
              f"l3_bound={row['l3_bound_pct']}% llc_miss_count={row['llc_miss_count']}")


if __name__ == "__main__":
    main()
