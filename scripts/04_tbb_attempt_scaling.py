#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 2:00:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-04-tbb-scaling
#SBATCH --output=talk-04-tbb-scaling-%j.out
"""Slide 8 (TBB attempt vs. baseline scaling): predict time vs. thread
count, 30-timestep sweep, TBB tbb::parallel_for.

Branch: TODO - not committed yet, see ../REPRODUCTION.md. Build against
whatever branch ends up holding that fix, useoriginalpredict=true.

Usage: sbatch 04_tbb_attempt_scaling.py /path/to/that/build/DP3
Reads ../data/baseline_scaling.csv (run 01 first) and writes
tbb_vs_baseline_scaling.csv, joined on thread count.
"""
import csv
import sys
import tempfile
from pathlib import Path

import os
import sys
sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common

THREAD_COUNTS = [2, 4, 8, 16, 24, 36, 48, 72]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: sbatch 04_tbb_attempt_scaling.py /path/to/build/DP3")
    dp3_exe = sys.argv[1]
    env = common.sourced_env()

    tbb = {}
    for threads in THREAD_COUNTS:
        with tempfile.TemporaryDirectory() as tmp:
            log = common.run(
                [
                    dp3_exe, str(common.PSET),
                    f"numthreads={threads}", "msin.ntimes=30", "solve1.debuglevel=1",
                    "solve1.usefastpredict=false", "solve1.useoriginalpredict=true", "msout=",
                    *common.h5parm_args(Path(tmp)),
                ],
                env=env,
            )
        normal, beam = common.parse_predict_times(log)
        tbb[threads] = {
            "normal_mean_s": sum(normal) / len(normal),
            "beam_mean_s": sum(beam) / len(beam),
            "predict_agg_s": sum(normal) + sum(beam),
        }
        print(f"threads={threads}: predict_agg={tbb[threads]['predict_agg_s']:.1f}s")

    baseline = {}
    with open(common.DATA_DIR / "baseline_scaling.csv") as f:
        for row in csv.DictReader(f):
            baseline[int(row["threads"])] = float(row["predict_agg_s"])

    out_csv = common.DATA_DIR / "tbb_vs_baseline_scaling.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["threads", "baseline_predict_agg_s", "tbb_predict_agg_s",
                    "tbb_normal_mean_s", "tbb_beam_mean_s", "status"])
        for threads in sorted(set(baseline) | set(tbb)):
            b, x = baseline.get(threads), tbb.get(threads)
            w.writerow([
                threads, b if b is not None else "",
                x["predict_agg_s"] if x else "", x["normal_mean_s"] if x else "",
                x["beam_mean_s"] if x else "", "confirmed" if x else "pending",
            ])
    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
