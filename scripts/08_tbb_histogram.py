#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 1:00:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-08-tbb-histogram
#SBATCH --output=talk-08-tbb-histogram-%j.out
"""Slide 9 (per-thread load, TBB): the direct counterpart to slide 6's
static split, dispatched through tbb::parallel_for instead.

The measurement itself is common.run_histogram(), shared with 03
(baseline) and 09 (tiled final). Sampling method matters more here than
anywhere else in the deck: TBB's dispatch is random per timestep, so a
rule that picks one block by "first" or "fullest" reports that run's luck.
An earlier version did exactly that and showed a 99% spread against the
static split's 52%, reading as work stealing making balance twice as bad;
measured per timestep over 30 timesteps the two are close.

Branch: TODO - not committed yet, see ../REPRODUCTION.md. The TBB dispatch
lives in OnePredict.cc (useoriginalpredict=true), uncommitted in the
rebase-onto-upstream working tree; build/ is that build.
Usage: sbatch 08_tbb_histogram.py /path/to/that/build/DP3
"""
import os
import sys

sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: sbatch 08_tbb_histogram.py /path/to/build/DP3")
    common.run_histogram(
        sys.argv[1], implementation="tbb",
        csv_name="tbb_histogram.csv", use_original=True,
    )
