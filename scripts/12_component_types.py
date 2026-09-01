#!/usr/bin/env python3
"""Counts POINT vs GAUSSIAN components in the sourcedb -> data/component_types.csv.

Not a measurement: it reads the static sky model the talk is benchmarked
against. Here rather than typed into a CSV so the number tracks the input
file if it is ever swapped.

Usage: ./scripts/12_component_types.py [skymodel.txt]
"""
import csv
import sys
from collections import Counter
from pathlib import Path

DEFAULT = Path("/work/ska/hchouh/inputs/calibration_skymodel.txt")
OUT = Path(__file__).resolve().parent.parent / "data" / "component_types.csv"


def main():
    sky = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    counts = Counter()
    for line in sky.read_text().splitlines():
        if not line.strip() or line.startswith(("#", "FORMAT")):
            continue
        fields = [f.strip() for f in line.split(",")]
        # A patch-definition line carries the patch centre and an empty Type.
        if len(fields) > 1 and fields[1]:
            counts[fields[1].upper()] += 1

    OUT.parent.mkdir(exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "count"])
        for kind in sorted(counts):
            w.writerow([kind.lower(), counts[kind]])
    print(f"wrote {OUT}: {dict(counts)} (total {sum(counts.values())})")


if __name__ == "__main__":
    main()
