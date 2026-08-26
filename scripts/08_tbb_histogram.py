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
"""TBB per-thread load slide (mirrors slide 6's baseline_histogram): same
worker.simulate item counts and cumulative time per thread, one
representative timestep, but against a build with the TBB dynamic-dispatch
fix instead of the static-split baseline.

Branch: TODO - not committed yet, see ../REPRODUCTION.md (same build used
for 04_tbb_attempt_scaling.py).
Usage: sbatch 08_tbb_histogram.py /path/to/that/build/DP3
"""
import re
import sys
import tempfile
from pathlib import Path

import os
import sys
sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common


def parse_per_thread(text: str, stage: str = "worker.simulate") -> dict[int, dict]:
    """Returns {thread_id: {count, total_ms}} for the most representative
    PER-THREAD block (the one with the most thread rows - avoids picking a
    short/degenerate timestep)."""
    blocks = re.findall(
        r"PER-THREAD BEGIN ===\n.*?thread;stage;.*?\n(.*?)=== PER-THREAD END",
        text, re.S,
    )
    parsed = []
    for block in blocks:
        rows = {}
        for line in block.strip().splitlines():
            line = re.sub(r"^\[\s*[\d.]+\]\s*", "", line.strip())
            parts = line.rstrip(";").split(";")
            if len(parts) < 9:
                continue
            thread_id, stage_name = int(parts[0]), parts[1]
            if stage_name != stage:
                continue
            rows[thread_id] = {"count": int(parts[2]), "total_ms": float(parts[3])}
        parsed.append(rows)
    return max(parsed, key=len)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: sbatch 08_tbb_histogram.py /path/to/build/DP3")
    dp3_exe = sys.argv[1]
    env = common.sourced_env()

    with tempfile.TemporaryDirectory() as tmp:
        log = common.run(
            [
                dp3_exe, str(common.PSET),
                "numthreads=72", "msin.ntimes=30", "solve1.debuglevel=2",
                "solve1.usefastpredict=false", "solve1.useoriginalpredict=true", "msout=",
                *common.h5parm_args(Path(tmp)),
            ],
            env=env,
        )

    data = parse_per_thread(log)
    out_csv = common.DATA_DIR / "tbb_histogram.csv"
    with open(out_csv, "w") as f:
        f.write("thread_id,items,total_time_s\n")
        for t in sorted(data):
            f.write(f"{t},{data[t]['count']},{data[t]['total_ms']/1000.0:.4f}\n")
    print(f"wrote {out_csv} ({len(data)} threads)")


if __name__ == "__main__":
    main()
