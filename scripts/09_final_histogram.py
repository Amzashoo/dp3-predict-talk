#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 1:00:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-09-final-histogram
#SBATCH --output=talk-09-final-histogram-%j.out
"""Per-thread load for the tiled OnePredictNew, completing the three-way
load-balance comparison in data/load_balance.csv.

Slides 6 and 9 show the static split and the TBB attempt; this is the row
that says what the tiled layout did to load balance. It matters because
the deck's conclusion is that reordering memory access, not scheduling,
was the real win - and balance is the metric the scheduling attempt was
supposed to move.

The measurement itself is common.run_histogram(), shared with 03 and 08.
Keep --nodelist in step with those two.

Branch: rebase-onto-upstream, current HEAD + uncommitted working tree.
Usage: sbatch 09_final_histogram.py /path/to/build/DP3
"""
import os
import sys

sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: sbatch 09_final_histogram.py /path/to/build/DP3")
    common.run_histogram(
        sys.argv[1], implementation="tiled_final",
        csv_name="final_histogram.csv", use_original=False,
    )
