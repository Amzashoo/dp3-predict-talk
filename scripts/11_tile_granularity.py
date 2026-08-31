#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 1:00:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-11-tile-granularity
#SBATCH --output=talk-11-tile-granularity-%j.out
"""Does the tiled build's residual load imbalance come from work-unit
granularity? Sweeps DP3_PREDICT_SOURCE_BLOCKS and measures balance.

The tiled build sizes its work units as `target_units = 16 * n_threads`
(OnePredictNew.cc), i.e. 1152 units = 16 per thread at 72 threads. Measured
balance: 38 ms idle per timestep against a mean unit of 42.6 ms - the idle
is ~0.9 of one unit, the classic last-unit tail. TBB's source dispatch gets
~136 units per thread and idles 0.4%.

Prediction, if that reading is right: doubling the unit count should
roughly halve the idle, and keep halving until some other cost takes over
(each extra source block needs its own accumulator, and the
predict.sum_source_blocks reduction at the end grows with the block count).
If idle instead stays flat, the tail is not granularity and the
explanation is wrong.

Writes data/tile_granularity.csv. Does NOT touch load_balance.csv - this is
an experiment, not one of the deck's measured rows.

Usage: sbatch 11_tile_granularity.py /path/to/build/DP3 [blocks ...]
"""
import csv
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common

DEFAULT_SWEEP = [128, 256, 512, 1024]  # 128 is the built-in default here
NTIMES = 12


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: sbatch 11_tile_granularity.py /path/to/build/DP3 [blocks ...]")
    dp3_exe = sys.argv[1]
    sweep = [int(a) for a in sys.argv[2:]] or DEFAULT_SWEEP

    rows = []
    for blocks in sweep:
        env = common.sourced_env()
        env["DP3_PREDICT_SOURCE_BLOCKS"] = str(blocks)
        with tempfile.TemporaryDirectory() as tmp:
            log = common.run(
                [
                    dp3_exe, str(common.PSET),
                    "numthreads=72", f"msin.ntimes={NTIMES}",
                    "solve1.debuglevel=2", "solve1.usefastpredict=false",
                    "solve1.useoriginalpredict=false", "msout=",
                    *common.h5parm_args(Path(tmp)),
                ],
                env=env,
            )
        stats, blk, idx = common.balance_from_log(log)
        units = sum(c for c, _ in blk[0].values())
        predict = common.predict_timestep_times(log)
        normal = sorted(predict)[:-2] or predict
        row = {
            "source_blocks": blocks,
            "units_per_timestep": units,
            "units_per_thread": f"{units / 72:.1f}",
            "utilization_pct": stats["utilization_pct"],
            "spread_pct": stats["spread_pct"],
            "idle_ms": f"{float(stats['idle_s']) * 1000:.1f}",
            "makespan_s": stats["makespan_s"],
            "normal_predict_s": f"{sum(normal) / len(normal):.3f}",
        }
        rows.append(row)
        print(f"blocks={blocks:>5} units={units:>6} ({units/72:>5.1f}/thread) "
              f"util={row['utilization_pct']}% spread={row['spread_pct']}% "
              f"idle={row['idle_ms']}ms predict={row['normal_predict_s']}s")

    out = common.DATA_DIR / "tile_granularity.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
