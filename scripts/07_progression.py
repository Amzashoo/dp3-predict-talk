#!/usr/bin/env python3
#SBATCH --exclusive
#SBATCH --comment=scitas_hwperf
#SBATCH -t 3:00:00
#SBATCH --partition=standard,bigmem
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=72
#SBATCH --job-name=talk-07-progression
#SBATCH --output=talk-07-progression-%j.out
"""Slides 11-14 (progression table): predict time at four real,
already-existing commits on rebase-onto-upstream, each one stage of the
tiling rework. Unlike the other scripts here, this one builds FOUR
separate worktrees itself (one per commit) rather than taking a prebuilt
binary, since the whole point is comparing across commits.

Commits (see ../REPRODUCTION.md for how this ordering was verified
against git log):
    3e439717  tiled layout alone, before the accumulator work
    62c44168  + split real/imag float planes
    cd6f63fb  + slab width rounded to a whole vector width
    5c9ff19e  + xsimd::sincos / xsimd::exp (current HEAD is a superset of
              this - HEAD also has the numthreads/TBB-arena fix,
              d1005c27, which is a no-op at 72 threads so doesn't affect
              this number)

Usage: sbatch 07_progression.py
(no argument - it builds everything itself; budget ~3h for 4 clean builds)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import os
import sys
sys.path.insert(0, os.environ.get(
    "SLURM_SUBMIT_DIR", os.path.dirname(os.path.abspath(__file__))
))
import common

STAGES = [
    ("3e439717", "tiled_layout", "channel x source tiling alone"),
    ("62c44168", "split_planes", "split real/imag float accumulation"),
    ("cd6f63fb", "slab_rounding", "slab width rounded to vector width (53->48 channels)"),
    ("5c9ff19e", "simd_sincos", "xsimd::sincos + xsimd::exp explicit vectorisation"),
]


def build_worktree(commit: str, workdir: Path) -> Path:
    wt = workdir / commit
    subprocess.run(["git", "-C", str(common.DP3_REPO), "worktree", "add", str(wt), commit, "--detach"], check=True)
    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=wt, check=True)
    build = wt / "build"
    build.mkdir()
    subprocess.run(["cmake", "-DBUILD_TESTING=OFF", ".."], cwd=build, check=True)
    subprocess.run(["make", "DP3", "-j72"], cwd=build, check=True)
    return build / "DP3"


def main():
    env = common.sourced_env()
    out_csv = common.DATA_DIR / "progression.csv"

    with open(out_csv, "w") as f:
        f.write("stage,commit,predict_s,normal_timestep_s,note\n")
        f.write("upstream_original,upstream_master,1161,,"
                "StaticFor baseline (from build-fast/slurm-threeway-65941437.out, "
                "not reproduced by this script)\n")

        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            for commit, stage, note in STAGES:
                print(f"building {commit} ({stage})...")
                dp3_exe = build_worktree(commit, workdir)

                log = common.run(
                    [
                        str(dp3_exe), str(common.PSET),
                        "numthreads=72", "msin.ntimes=30", "solve1.debuglevel=1",
                        "solve1.usefastpredict=false", "solve1.useoriginalpredict=false", "msout=",
                    ],
                    env=env,
                )
                normal, beam = common.parse_predict_times(log)
                predict_total = sum(normal) + sum(beam)
                normal_mean = sum(normal) / len(normal)
                f.write(f"{stage},{commit},{predict_total:.1f},{normal_mean:.4f},{note}\n")
                print(f"  predict_agg={predict_total:.1f}s (30 timesteps) "
                      f"normal_mean={normal_mean:.4f}s")

                subprocess.run(
                    ["git", "-C", str(common.DP3_REPO), "worktree", "remove", str(workdir / commit), "--force"],
                    check=True,
                )

    print(f"wrote {out_csv}")


if __name__ == "__main__":
    main()
