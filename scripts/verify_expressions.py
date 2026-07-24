#!/usr/bin/env python3
"""Verify that expressions produce visible changes in rendered frames.

Extracts and compares frames from baseline vs expression clips to demonstrate
that pose changes are actually happening.
"""

import subprocess
import sys
from pathlib import Path
from PIL import Image
import numpy as np

TESTS_DIR = Path(__file__).resolve().parent.parent / "tests" / "expression_tests"


def extract_frame(video_path: Path, time: float) -> Image.Image | None:
    """Extract a frame from video using ffmpeg."""
    temp_png = Path("/tmp/frame.png")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(video_path),
                "-ss", f"{time:.2f}",
                "-vframes", "1",
                str(temp_png),
            ],
            check=True,
            timeout=10,
        )
        return Image.open(temp_png)
    except Exception as e:
        print(f"[ERROR] Failed to extract frame from {video_path}: {e}")
        return None


def compute_difference(img1: Image.Image, img2: Image.Image) -> float:
    """Compute mean squared difference between two images (0-1 scale)."""
    arr1 = np.array(img1).astype(float)
    arr2 = np.array(img2).astype(float)

    if arr1.shape != arr2.shape:
        arr2 = np.array(img2.resize(img1.size)).astype(float)

    mse = np.mean((arr1 - arr2) ** 2)
    return mse / (255 ** 2)  # Normalize to 0-1


def main():
    """Verify expression changes in all test cases."""
    print("[verify_expressions] Comparing baseline vs expression frames...\n")

    test_cases = [
        "paycheck", "taxes", "housing", "transportation", "treadmill", "money_drain"
    ]

    all_passed = True

    for case in test_cases:
        baseline_mp4 = TESTS_DIR / f"{case}_baseline.mp4"
        expr_mp4 = TESTS_DIR / f"{case}_expr.mp4"

        if not baseline_mp4.exists() or not expr_mp4.exists():
            print(f"  ⊘ {case}: test files not found")
            continue

        # Extract frames at different times to show progression
        differences = []

        for time, label in [(0.5, "mid"), (1.25, "mid-late"), (2.0, "late")]:
            baseline_frame = extract_frame(baseline_mp4, time)
            expr_frame = extract_frame(expr_mp4, time)

            if baseline_frame and expr_frame:
                diff = compute_difference(baseline_frame, expr_frame)
                differences.append(diff)
                status = "✓" if diff > 0.02 else "⊘"
                print(f"  {status} {case:15} @ {time:3.1f}s: {diff:.4f} change")
            else:
                print(f"  ✗ {case:15} @ {time:3.1f}s: frame extraction failed")
                all_passed = False

        # Summary: mean difference should be >0.02 (2% change visible)
        if differences:
            mean_diff = np.mean(differences)
            if mean_diff > 0.02:
                print(f"  ✓ {case:15} average change: {mean_diff:.4f}\n")
            else:
                print(f"  ✗ {case:15} average change: {mean_diff:.4f} (too small)\n")
                all_passed = False
        else:
            all_passed = False

    print("[verify_expressions]", "All checks passed!" if all_passed else "Some checks failed")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
