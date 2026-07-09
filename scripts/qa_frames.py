#!/usr/bin/env python3
"""Frame QA — the screenshot-worthy-frame contact sheet (CURIOSITY_BRAIN
§7.5). Operator doctrine: EVERY MINUTE must contain one screenshot-worthy
frame. The test: "if this frame became the thumbnail, would someone
click?" If no, that minute gets redone.

Extracts one frame per minute (plus the final frame) and tiles them into
a single contact sheet for the eye-QA judgment — this tool renders the
evidence; a human (or the routine's eye pass) renders the verdict.

    python3 scripts/qa_frames.py output/curiosity_<slug>.mp4 \
        [--out sheet.png] [--per-minute 1]

Always exits 0 unless extraction itself fails — judging click-worthiness
is not automatable; the sheet exists to make skipping the judgment
impossible.
"""
from __future__ import annotations

import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path


def _dur(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--out", type=Path, default=None,
                    help="contact sheet path (default: <video>_frames.png)")
    ap.add_argument("--per-minute", type=int, default=1)
    args = ap.parse_args()

    out = args.out or args.video.with_name(args.video.stem + "_frames.png")
    total = _dur(args.video)
    step = 60.0 / max(1, args.per_minute)
    # Sample mid-window so the frame represents its minute, not its cut.
    times = [min(total - 0.2, t + step / 2)
             for t in [i * step for i in range(max(1, math.ceil(total / step)))]]
    times.append(max(0.0, total - 1.0))          # the closing frame counts

    with tempfile.TemporaryDirectory() as td:
        for i, t in enumerate(times):
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
                 "-i", str(args.video), "-frames:v", "1",
                 "-vf", "scale=640:-1", str(Path(td) / f"f{i:03d}.png")],
                check=True)
        cols = min(4, len(times))
        rows = math.ceil(len(times) / cols)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-pattern_type", "glob",
             "-i", str(Path(td) / "f*.png"),
             "-filter_complex",
             f"tile={cols}x{rows}:padding=4:color=0x101626",
             str(out)], check=True)

    mins = total / 60.0
    print(f"contact sheet: {out}")
    print(f"{len(times)} frames across {mins:.1f} min — judge each against "
          "the thumbnail-click test; any minute without a click-worthy "
          "frame gets redone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
