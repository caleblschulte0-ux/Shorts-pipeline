#!/usr/bin/env python3
"""Verify that expressions produce visible changes in rendered frames.

Extracts frames from baseline vs expression clips at several beat times and
measures the pixel difference, so "the expression works" is a measured fact
rather than a claim. A per-frame mean-absolute-difference above THRESHOLD
counts as a visible change.
"""

import subprocess
import sys
from pathlib import Path
from PIL import Image
import numpy as np

TESTS_DIR = Path(__file__).resolve().parent.parent / "tests" / "expression_tests"

# A pose change is LOCALIZED (the figure is ~1-3% of a 1080p frame), so
# full-frame mean-difference dilutes it into noise. The right measurement is
# the count of strongly-changed pixels: |diff| > PIXEL_DELTA on any channel.
# Scene renders are deterministic, so identical output measures exactly 0;
# a real pose change sweeps 1,000-6,000 px (measured 2026-07-24 across all
# six scenes: 1404-5560). The bar sits well under that with margin over zero.
PIXEL_DELTA = 25
CHANGED_PX_THRESHOLD = 600


def extract_frame(video_path: Path, time: float, tag: str) -> Image.Image | None:
    """Extract one frame to its own temp file and load it EAGERLY.

    A shared temp path with PIL's lazy loading corrupts the first image when
    the second frame overwrites the file — each extraction gets its own path
    and the pixels are forced into memory before returning.
    """
    temp_png = TESTS_DIR / f"_vf_{tag}_{time:.2f}.png"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-ss", f"{time:.2f}", "-i", str(video_path),
             "-vframes", "1", str(temp_png)],
            check=True, timeout=20,
        )
        img = Image.open(temp_png)
        img.load()                      # force decode before the file changes
        return img
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] frame @{time:.2f}s from {video_path.name}: {e}")
        return None
    finally:
        temp_png.unlink(missing_ok=True)


def changed_pixels(img1: Image.Image, img2: Image.Image) -> tuple[int, tuple | None]:
    """Count strongly-changed pixels and return their bounding box."""
    a = np.asarray(img1.convert("RGB"), dtype=float)
    b = np.asarray(img2.convert("RGB"), dtype=float)
    if a.shape != b.shape:
        b = np.asarray(img2.convert("RGB").resize(img1.size), dtype=float)
    d = np.abs(a - b).max(axis=2)
    mask = d > PIXEL_DELTA
    n = int(mask.sum())
    if n == 0:
        return 0, None
    ys, xs = np.nonzero(mask)
    return n, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def main():
    print("[verify_expressions] baseline vs expression frame comparison\n")

    cases = ["paycheck", "taxes", "housing", "transportation", "treadmill",
             "money_drain"]
    all_passed = True
    results = []

    for case in cases:
        baseline = TESTS_DIR / f"{case}_baseline.mp4"
        expr = TESTS_DIR / f"{case}_expr.mp4"
        if not baseline.exists() or not expr.exists():
            print(f"  ⊘ {case}: clips missing (run test_expressions.py first)")
            all_passed = False
            continue

        counts = []
        for time in (0.5, 1.25, 2.0):
            f1 = extract_frame(baseline, time, f"{case}_b")
            f2 = extract_frame(expr, time, f"{case}_e")
            if f1 is None or f2 is None:
                all_passed = False
                continue
            n, bbox = changed_pixels(f1, f2)
            counts.append(n)
            mark = "✓" if n >= CHANGED_PX_THRESHOLD else "·"
            print(f"  {mark} {case:15} @ {time:4.2f}s  {n:6d} px changed"
                  f"  {bbox or ''}")

        # Expressions RAMP UP through the beat — the peak is the proof.
        peak = max(counts) if counts else 0
        ok = peak >= CHANGED_PX_THRESHOLD
        results.append((case, peak, ok))
        print(f"  {'✓' if ok else '✗'} {case:15} peak {peak} px "
              f"(threshold {CHANGED_PX_THRESHOLD})\n")
        if not ok:
            all_passed = False

    print("[verify_expressions]",
          "ALL VISIBLY DIFFERENT" if all_passed else "SOME CASES FAILED")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
