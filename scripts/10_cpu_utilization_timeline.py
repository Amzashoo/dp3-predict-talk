#!/usr/bin/env python3
"""Slide 10 (CPU usage over time): per-6s-bin CPU utilization, baseline vs
TBB, merged into one CSV.

Unlike the other scripts this one submits nothing - it re-reports two
VTune results that already exist, so it runs on the login node in seconds.
The collection itself was done by
../../DP3/presentation_data/cpu_utilization_timeline/collect_timeline_generic.sh
(a `threading` collect bounded by -duration=180, which is what fixes both
runs to the same 30 x 6s bins and makes them comparable).

On the units, which are easy to get wrong: `-report timeline
-group-by=core` reports "CPU Time:Self" as percent-of-bin per core, summed
over cores - so it maxes out at 100 * ncores (7200 here), not at
bin_width * ncores. Utilization% is therefore the raw value / ncores, and
the peak of 7097 lands at 98.6%. Dividing by (bin_width * ncores) instead
looks plausible and yields >1000%.

Usage: ./scripts/10_cpu_utilization_timeline.py [baseline_result tbb_result]
"""
import csv
import subprocess
import sys
from pathlib import Path

import os
sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common

DEFAULTS = ("r_timeline_baseline_20260826_162415", "r_timeline_tbb_20260826_162424")


def timeline(result_dir: Path, env: dict) -> list[tuple[float, float, float]]:
    """(bin_start, bin_end, utilization_pct) per bin for one result."""
    out = subprocess.run(
        ["vtune", "-quiet", "-report", "timeline", "-r", str(result_dir),
         "-group-by=core", "-report-knob", "column-by=RefTime",
         "-format=csv", "-csv-delimiter=comma"],
        env=env, capture_output=True, text=True, check=True,
    ).stdout
    rows = []
    for r in csv.DictReader(out.splitlines()):
        rows.append((
            float(r["Bin Start Time"]),
            float(r["Bin End Time"]),
            float(r["CPU Time:Self"]) / common.NCORES,
        ))
    if not rows:
        raise RuntimeError(f"no timeline bins in {result_dir}")
    return rows


def main():
    args = sys.argv[1:] or list(DEFAULTS)
    if len(args) != 2:
        sys.exit("usage: 10_cpu_utilization_timeline.py [baseline_result tbb_result]")
    paths = [Path(a) if Path(a).is_absolute() else common.DP3_REPO / a for a in args]
    for p in paths:
        if not p.is_dir():
            sys.exit(f"missing VTune result: {p}")

    env = common.sourced_env(vtune=True)
    base, tbb = (timeline(p, env) for p in paths)
    if len(base) != len(tbb):
        sys.exit(f"bin count differs ({len(base)} vs {len(tbb)}) - the two "
                 "collections weren't bounded by the same -duration")

    out_csv = common.DATA_DIR / "cpu_utilization_timeline.csv"
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["bin_start_s", "bin_end_s",
                    "baseline_utilization_pct", "tbb_utilization_pct"])
        for (s, e, b), (_, _, t) in zip(base, tbb):
            w.writerow([s, e, round(b, 2), round(t, 2)])
    print(f"wrote {out_csv} ({len(base)} bins)")
    print(f"  baseline peak {max(b for _, _, b in base):.1f}%  "
          f"tbb peak {max(t for _, _, t in tbb):.1f}%")


if __name__ == "__main__":
    main()
