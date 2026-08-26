#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 0:30:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-05-memory-traffic
#SBATCH --output=talk-05-memory-traffic-%j.out
"""Slide 9 (memory traffic / L3 cache misses): VTune memory-access
profile, restricted to the predict phases only.

Bounded by a fixed timestep count (2 beam-recompute + 4 normal), not a
wall-clock -duration - a -duration=90 kill was tried first and produced a
misleading comparison: ~50s fixed DP3 startup left only ~40s of budget,
which isn't enough for TBB to finish even one 47s beam call (its whole
sample was "stuck mid-beam"), while the faster tiled build's 38s beam call
fits, plus a sliver of cheap steady-state. Different phase mix per build,
not a real result. Letting both run the same fixed timestep count to
completion instead keeps the beam:normal phase mix identical regardless of
how fast each build is - -duration=400 below is just a safety net, not
expected to trigger.

That fix still measured the whole collection window, including ~50s of
DP3 startup and the inter-call DDECal solve/calibration phases - not what
was asked for. Both predict implementations (OnePredict.cc,
OnePredictNew.cc) now bracket PredictWithSourceParallelization in an ITT
task ("beam_predict"/"normal_predict") and __itt_resume() a
-start-paused collection on first entry, so setup is skipped entirely.
The actual per-source compute happens inside the nested tbb::parallel_for
call, which TBB's own built-in ITT hooks report as a separate sibling task
"tbb_parallel_for" (confirmed via `grep -rn tbb::parallel_for` that no
other code path - in particular no DDECal/solve code - uses
tbb::parallel_for, so that bucket is exclusively predict work).
`-group-by task` (not `computing-task`, which errors - confirmed via
`-group-by=?`) reports memory metrics per task type; predict-phase-only
numbers are beam_predict + normal_predict + tbb_parallel_for, explicitly
excluding "[Outside any task]" (startup + solve/calibration).

label=tbb:   solve1.useoriginalpredict=true  (OnePredict.cc)
label=final: solve1.useoriginalpredict=false (OnePredictNew.cc, tiled)
Both share one ITT-instrumented binary - build with -DDP3_ENABLE_ITT=ON.

Usage: sbatch 05_memory_traffic.py tbb /path/to/build/DP3
       sbatch 05_memory_traffic.py final /path/to/build/DP3
"""
import csv
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

PREDICT_TASKS = {"beam_predict", "normal_predict", "tbb_parallel_for"}


def parse_task_report(text: str) -> dict:
    """Aggregate the predict-only task rows from a `-group-by task` CSV
    report: raw counts (loads/stores/LLC misses) are summed, percentages
    are averaged weighted by each task's CPU Time (non-overlapping self
    time, so it's a valid weight)."""
    rows = [r for r in csv.DictReader(io.StringIO(text))
            if r["Task Type"] in PREDICT_TASKS]
    if not rows:
        raise RuntimeError("no predict-task rows in vtune -group-by task report - "
                            "was the binary built with -DDP3_ENABLE_ITT=ON?")

    def f(row, col):
        return float(row[col]) if row[col] else 0.0

    total_cpu_time = sum(f(r, "CPU Time") for r in rows)

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


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("tbb", "final"):
        sys.exit("usage: sbatch 05_memory_traffic.py tbb|final /path/to/build/DP3")
    label, dp3_exe = sys.argv[1], sys.argv[2]
    predict_flag = "solve1.useoriginalpredict=" + ("true" if label == "tbb" else "false")

    env = common.sourced_env(vtune=True)

    with tempfile.TemporaryDirectory() as tmp:
        result_dir = Path(tmp) / "result"
        subprocess.run(
            [
                "vtune", "-collect", "memory-access", "-data-limit=60000",
                "-knob", "sampling-interval=20",
                "-knob", "analyze-mem-objects=false",
                "-knob", "analyze-openmp=false",
                "-start-paused", "-duration=400",
                "-r", str(result_dir), "--",
                dp3_exe, str(common.PSET),
                "numthreads=72", "msin.ntimes=6",
                "solve1.usefastpredict=false", predict_flag, "msout=",
                *common.h5parm_args(Path(tmp) / "h5out"),
            ],
            env=env,
        )  # -duration=400 is a safety net, not expected to fire; don't check=True
           # in case it does anyway - collection stays paused (see
           # -start-paused) until the first ScopedPredictTask resumes it,
           # so this is measured from DP3 wall time, not profiled time

        task_report = subprocess.run(
            ["vtune", "-quiet", "-report", "hotspots", "-r", str(result_dir),
             "-group-by", "task", "-format=csv", "-csv-delimiter=comma"],
            env=env, capture_output=True, text=True, check=True,
        ).stdout

    row = {"implementation": "tbb_fixed" if label == "tbb" else "tiled_final",
           **parse_task_report(task_report), "status": "confirmed"}

    fields = ["implementation", "memory_bound_pct", "l1_bound_pct", "l2_bound_pct",
              "l3_bound_pct", "dram_bound_pct", "store_bound_pct", "loads", "stores",
              "llc_miss_count", "status"]
    csv_path = common.DATA_DIR / "memory_traffic.csv"
    rows = {}
    if csv_path.exists():
        with open(csv_path) as f:
            rows = {r["implementation"]: r for r in csv.DictReader(f)}
    rows[row["implementation"]] = row

    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for key in ("tbb_fixed", "tiled_final"):
            if key in rows:
                w.writerow(rows[key])

    print(f"updated {csv_path} for label={label}")
    print(f"  memory_bound={row['memory_bound_pct']}% l3_bound={row['l3_bound_pct']}% "
          f"llc_miss_count={row['llc_miss_count']}")


if __name__ == "__main__":
    main()
