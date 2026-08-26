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
profile.

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

label=tbb:   branch TODO (see ../REPRODUCTION.md), useoriginalpredict=true
label=final: branch rebase-onto-upstream, current HEAD, useoriginalpredict=false

Usage: sbatch 05_memory_traffic.py tbb /path/to/build/DP3
       sbatch 05_memory_traffic.py final /path/to/build/DP3
"""
import csv
import re
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


def parse_summary(text: str) -> dict:
    def grab(pattern):
        m = re.search(pattern, text)
        return m.group(1).replace(",", "") if m else ""

    return {
        "memory_bound_pct": grab(r"Memory Bound: ([\d.]+)% of Pipeline Slots"),
        "l1_bound_pct": grab(r"L1 Bound: ([\d.]+)% of Clockticks"),
        "l2_bound_pct": grab(r"L2 Bound: ([\d.]+)% of Clockticks"),
        "l3_bound_pct": grab(r"L3 Bound: ([\d.]+)% of Clockticks"),
        "dram_bound_pct": grab(r"DRAM Bound: ([\d.]+)% of Clockticks"),
        "store_bound_pct": grab(r"Store Bound: ([\d.]+)% of Clockticks"),
        "loads": grab(r"Loads: ([\d,]+)"),
        "stores": grab(r"Stores: ([\d,]+)"),
        "llc_miss_count": grab(r"LLC Miss Count: ([\d,]+)"),
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
                "-duration=400",
                "-r", str(result_dir), "--",
                dp3_exe, str(common.PSET),
                "numthreads=72", "msin.ntimes=6",
                "solve1.usefastpredict=false", predict_flag, "msout=",
                *common.h5parm_args(Path(tmp) / "h5out"),
            ],
            env=env,
        )  # -duration=400 is a safety net, not expected to fire; don't check=True
           # in case it does anyway

        summary = subprocess.run(
            ["vtune", "-report", "summary", "-r", str(result_dir),
             "-report-knob", "show-issues=false"],
            env=env, capture_output=True, text=True,
        ).stdout

    row = {"implementation": "tbb_fixed" if label == "tbb" else "tiled_final",
           **parse_summary(summary), "status": "confirmed"}

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
