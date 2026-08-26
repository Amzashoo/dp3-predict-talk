"""Shared setup for every script in this directory. Import, don't run.

This repo (dp3-predict-talk) is independent of the DP3 checkout, but every
script here still needs one - to build the branches/commits named in its
own header comment (see ../REPRODUCTION.md), and to reuse DP3's
setup_env.sh / measures-data fix. Point DP3_REPO at it; defaults to a
sibling checkout next to this repo (../DP3), which is where it happened to
live when this repo was split out.

Every script here assumes:
  - it runs from a git worktree checked out at the commit/branch named in
    its own header comment
  - it runs on a SCITAS-style SLURM cluster node with --exclusive, one job
    per node, 72 cores (2x Intel Xeon Platinum 8360Y, Ice Lake-SP)
  - intel-oneapi-vtune is available via `module load` where a script needs
    it (see sourced_env(vtune=True))

None of these scripts are wired into slides.qmd automatically - they
regenerate the CSVs under ../data/, which the qmd reads.
"""
from __future__ import annotations

import csv
import os
import re
import subprocess
import sys
from pathlib import Path

TALK_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = TALK_DIR / "data"

_dp3_repo_env = os.environ.get("DP3_REPO")
DP3_REPO = Path(_dp3_repo_env) if _dp3_repo_env else (TALK_DIR.parent / "DP3")
if not DP3_REPO.is_dir():
    sys.exit(
        f"DP3_REPO not found at {DP3_REPO}. Set DP3_REPO=/path/to/DP3 "
        "or check out DP3 as a sibling of this repo."
    )
PSET = DP3_REPO / "params_compare.pset"

NCORES = 72


def sourced_env(vtune: bool = False) -> dict:
    """The environment after sourcing DP3's setup_env.sh (and, if vtune,
    `module load intel-oneapi-vtune`) - so subprocess calls see the same
    spack/module environment the original bash scripts did. Shells out
    once and diffs os.environ, since Python can't source a bash script
    in-process."""
    shell_cmd = f"source {DP3_REPO}/setup_env.sh"
    if vtune:
        shell_cmd += " && module load intel-oneapi-vtune"
    shell_cmd += " && env -0"

    result = subprocess.run(
        ["bash", "-c", shell_cmd], capture_output=True, check=True
    )
    env = dict(os.environ)
    for entry in result.stdout.split(b"\0"):
        if b"=" in entry:
            key, _, value = entry.decode().partition("=")
            env[key] = value
    env["CASARCFILES"] = str(DP3_REPO / "presentation_data" / "measures.casarc")
    return env


def run(cmd: list[str], env: dict, log_path: Path | None = None) -> str:
    """Runs `cmd`, returns combined stdout+stderr as text. Raises on a
    nonzero exit UNLESS check=False is what you want - callers that expect
    a nonzero exit (e.g. vtune -duration killing the target on purpose)
    should call subprocess.run directly instead."""
    result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)
    text = result.stdout + result.stderr
    if log_path:
        log_path.write_text(text)
    return text


def parse_predict_times(text: str) -> tuple[list[float], list[float]]:
    """Returns (normal_times, beam_times). The 2 largest 'Predict time:'
    values in a debuglevel>=1 log are the beam-recompute timesteps, same
    convention used throughout this project's data."""
    times = [float(x) for x in re.findall(r"Predict time:\s*([\d.]+)", text)]
    srt = sorted(times)
    return srt[:-2], srt[-2:]


def write_scaling_row(csv_path: Path, threads: int, normal: list[float], beam: list[float]):
    """Appends one row to a scaling-table CSV, creating it with a header
    if it doesn't exist yet."""
    is_new = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["threads", "n_normal", "normal_mean_s", "n_beam", "beam_mean_s", "predict_agg_s"])
        w.writerow([
            threads, len(normal), f"{sum(normal)/len(normal):.4f}",
            len(beam), f"{sum(beam)/len(beam):.4f}", f"{sum(normal)+sum(beam):.4f}",
        ])


def h5parm_args(h5dir: Path) -> list[str]:
    """DP3 needs distinct h5parm output paths per run, or concurrent jobs
    silently collide on a shared default path and stall (found the hard
    way - see git history of scripts/collect_cpuutil_generic.sh in the
    main DP3 repo's presentation_data/ for the postmortem)."""
    h5dir.mkdir(parents=True, exist_ok=True)
    return [f"solve{i}.h5parm={h5dir / f'solve{i}.h5parm'}" for i in (1, 2, 3, 4)]
