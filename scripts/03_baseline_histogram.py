#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 1:00:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-03-baseline-histogram
#SBATCH --output=talk-03-baseline-histogram-%j.out
"""Slide 6 (per-thread load): worker.simulate items and cumulative time
per thread for the static schaapcommon::StaticFor split.

The measurement itself is common.run_histogram(), shared with 08 (TBB) and
09 (tiled final) so the three builds compared on slides 6 and 9 can't
drift apart in method.

Branch: figures/baseline-instrumented, base d1005c27 (see ../REPRODUCTION.md).
Build: presentation_data/baseline_analysis/build (StaticFor, -O3 -march=native).
Usage: sbatch 03_baseline_histogram.py /path/to/that/build/DP3
"""
import os
import sys

sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: sbatch 03_baseline_histogram.py /path/to/build/DP3")
    common.run_histogram(
        sys.argv[1], implementation="static_baseline",
        csv_name="baseline_histogram.csv", use_original=True,
    )
