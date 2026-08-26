#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 0:30:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-02-baseline-cycles
#SBATCH --output=talk-02-baseline-cycles-%j.out
"""Slide 5 (per-core cycle-count imbalance): VTune hardware-event counters,
original OnePredict / StaticFor, 72 threads, short (3-timestep) run.

Branch: figures/baseline-instrumented, base d1005c27 (see ../REPRODUCTION.md).
Usage: sbatch 02_baseline_core_cycles.py /path/to/that/build/DP3
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


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: sbatch 02_baseline_core_cycles.py /path/to/build/DP3")
    dp3_exe = sys.argv[1]
    env = common.sourced_env(vtune=True)

    with tempfile.TemporaryDirectory() as tmp:
        result_dir = Path(tmp) / "result"
        common.run(
            [
                "vtune", "-collect", "threading",
                "-knob", "sampling-and-waits=hw", "-knob", "sampling-interval=10",
                "-data-limit=4000", "-r", str(result_dir), "--",
                dp3_exe, str(common.PSET),
                "numthreads=72", "msin.ntimes=3", "solve1.usefastpredict=false",
                "solve1.useoriginalpredict=true", "solve1.debuglevel=1",
                *common.h5parm_args(Path(tmp) / "h5out"),
            ],
            env=env,
        )

        report = common.run(
            [
                "vtune", "-report", "hw-events", "-r", str(result_dir),
                "-group-by=core", "-format=csv", "-csv-delimiter=comma",
            ],
            env=env,
        )

    out_csv = common.DATA_DIR / "baseline_core_cycles.csv"
    lines = [l for l in report.splitlines() if l.startswith("core_") or l.startswith("Physical Core")]
    out_csv.write_text("\n".join(lines) + "\n")
    print(f"wrote {out_csv} ({len(lines) - 1} cores)")


if __name__ == "__main__":
    main()
