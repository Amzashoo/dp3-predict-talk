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
    if len(sys.argv) < 2:
        sys.exit("usage: sbatch 04_tbb_attempt_scaling.py /path/to/build/DP3 [threads ...]")
    dp3_exe = sys.argv[1]
    # Optional thread counts fill in single missing points without
    # re-running the whole sweep; already-measured rows are merged back in
    # below rather than overwritten.
    wanted = [int(a) for a in sys.argv[2:]] or THREAD_COUNTS
    env = common.sourced_env()

    job = os.environ.get("SLURM_JOB_ID", "local")
    tbb = {}
    for threads in wanted:
        # Keep the raw DP3 log: an 8-thread point once came back 75% slower
        # than the baseline and there was no way to tell a bad run from a
        # real effect, because the log had been thrown away. *.log is
        # gitignored.
        # common.TALK_DIR, not __file__: under sbatch, SLURM copies this
        # script to a read-only spool dir, so __file__'s parent isn't
        # writable (and the crash lands *after* the run, losing it).
        log_path = common.TALK_DIR / "scripts" / f"talk-04-t{threads}-{job}.log"
        with tempfile.TemporaryDirectory() as tmp:
            log = common.run(
                [
                    dp3_exe, str(common.PSET),
                    f"numthreads={threads}", "msin.ntimes=30", "solve1.debuglevel=1",
                    "solve1.usefastpredict=false", "solve1.useoriginalpredict=true", "msout=",
                    *common.h5parm_args(Path(tmp)),
                ],
                env=env,
                log_path=log_path,
            )
        normal, beam = common.parse_predict_times(log)
        tbb[threads] = {
            "normal_mean_s": sum(normal) / len(normal),
            "beam_mean_s": sum(beam) / len(beam),
            "predict_agg_s": sum(normal) + sum(beam),
        }
        print(f"threads={threads}: predict_agg={tbb[threads]['predict_agg_s']:.1f}s "
              f"(normal {tbb[threads]['normal_mean_s']:.1f}s x{len(normal)}, "
              f"beam {tbb[threads]['beam_mean_s']:.1f}s x{len(beam)}) log={log_path.name}")

    baseline = {}
    with open(common.DATA_DIR / "baseline_scaling.csv") as f:
        for row in csv.DictReader(f):
            baseline[int(row["threads"])] = float(row["predict_agg_s"])

    out_csv = common.DATA_DIR / "tbb_vs_baseline_scaling.csv"
    if out_csv.exists():  # keep points this run didn't measure
        with open(out_csv) as f:
            for row in csv.DictReader(f):
                t = int(row["threads"])
                if t not in tbb and row["tbb_predict_agg_s"]:
                    tbb[t] = {
                        "predict_agg_s": float(row["tbb_predict_agg_s"]),
                        "normal_mean_s": float(row["tbb_normal_mean_s"]),
                        "beam_mean_s": float(row["tbb_beam_mean_s"]),
                    }

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
