#!/usr/bin/env python3
"""Renders the talk as a single self-contained HTML file - all figures,
CSS and JS inlined (via quarto's embed-resources), so the result can be
opened directly in a browser or emailed around with no other files, no
quarto install, and no data/ directory needed alongside it.

This is deliberately separate from `quarto render slides.qmd`: day-to-day
rendering keeps figures as loose files in slides_files/ (faster
incremental re-renders while iterating), and this script is only for
producing something to hand out.

Usage: ./scripts/pack_standalone.py [output.html]
    defaults to dist/dp3-predict-talk.html
"""
import subprocess
import sys
from pathlib import Path

TALK_DIR = Path(__file__).resolve().parent.parent


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else TALK_DIR / "dist" / "dp3-predict-talk.html"
    out = out if out.is_absolute() else TALK_DIR / out
    out.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["quarto", "render", "slides.qmd", "-M", "embed-resources:true", "-o", out.name],
        cwd=TALK_DIR, check=True,
    )
    rendered = TALK_DIR / out.name
    if rendered != out:
        rendered.rename(out)

    print(f"wrote {out} ({out.stat().st_size // 1024 // 1024} MB)")


if __name__ == "__main__":
    main()
