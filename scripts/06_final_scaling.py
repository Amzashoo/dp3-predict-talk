#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 2:00:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-06-final-scaling
#SBATCH --output=talk-06-final-scaling-%j.out
"""Slide 17 (final scaling): predict time vs. thread count, 30-timestep
sweep, tiled OnePredictNew, current HEAD.

Branch: rebase-onto-upstream, current HEAD. Usage:
    sbatch 06_final_scaling.py /path/to/build/DP3
(the normal build/ directory at the DP3 repo root is fine - no separate
worktree needed, this is HEAD)
"""
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
        sys.exit("usage: sbatch 06_final_scaling.py /path/to/build/DP3")
    dp3_exe = sys.argv[1]
    env = common.sourced_env()

    out_csv = common.DATA_DIR / "final_scaling.csv"
    out_csv.unlink(missing_ok=True)

    for threads in THREAD_COUNTS:
        with tempfile.TemporaryDirectory() as tmp:
            log = common.run(
                [
                    dp3_exe, str(common.PSET),
                    f"numthreads={threads}", "msin.ntimes=30", "solve1.debuglevel=1",
                    "solve1.usefastpredict=false", "solve1.useoriginalpredict=false", "msout=",
                    *common.h5parm_args(Path(tmp)),
                ],
                env=env,
            )
        normal, beam = common.parse_predict_times(log)
        common.write_scaling_row(out_csv, threads, normal, beam)
        print(f"threads={threads}: normal_mean={sum(normal)/len(normal):.4f}s "
              f"beam_mean={sum(beam)/len(beam):.3f}s")

    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
