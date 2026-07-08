#!/usr/bin/env python3
"""Motion QA — the 'never a static frame' gate (CURIOSITY_BRAIN.md §9).

Samples N points across a video, grabs consecutive-frame pairs at each,
and reports the mean absolute pixel difference. A locked frame reads
~0.0; the one-take world engine should never produce one.

    python3 scripts/qa_motion.py output/curiosity_<slug>.mp4 [--points 8]

Exits 1 if any sample point is (near-)static.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

STATIC_THRESHOLD = 0.05     # mean abs diff below this = a locked frame


def _dur(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--points", type=int, default=8)
    args = ap.parse_args()

    import numpy as np
    from PIL import Image

    total = _dur(args.video)
    bad = 0
    with tempfile.TemporaryDirectory() as td:
        for i in range(args.points):
            t = total * (i + 0.5) / args.points
            pair = []
            for j, dt in enumerate((0.0, 0.5)):
                f = Path(td) / f"p{i}_{j}.png"
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error",
                     "-ss", f"{t + dt:.3f}", "-i", str(args.video),
                     "-frames:v", "1", str(f)], check=True)
                pair.append(np.asarray(Image.open(f), dtype=float))
            diff = float(np.abs(pair[0] - pair[1]).mean())
            flag = "STATIC!" if diff < STATIC_THRESHOLD else "ok"
            if diff < STATIC_THRESHOLD:
                bad += 1
            print(f"t={t:7.1f}s  diff={diff:7.3f}  {flag}")
    if bad:
        print(f"\nFAIL: {bad}/{args.points} sample points are static — "
              "the camera locked somewhere.")
        return 1
    print(f"\nOK: real motion at all {args.points} sample points.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
