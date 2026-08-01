#!/usr/bin/env python3
"""Tests for the lookmatch engine: in-band assets pass through UNTOUCHED,
out-of-band assets move TOWARD the measured house target with clamped
corrections (never a creative regrade), and every failure path returns
None per the engines contract."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from engines import lookmatch as lm  # noqa: E402


def _frame(color: str, dest: Path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"color=c={color}:s=320x180:d=1",
                    "-frames:v", "1", str(dest)], check=True)


def main():
    assert lm.available(), "ffmpeg/ffprobe missing — engine cannot self-test"

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        dark, bright, mid = root / "dark.jpg", root / "bright.jpg", \
            root / "mid.jpg"
        _frame("0x151515", dark)          # far below the house band
        _frame("0xdddddd", bright)        # far above it
        _frame("0x404040", mid)           # inside the band (target ~66)

        # 1. plan() reads honest stats and flags band membership
        pd, pb, pm = lm.plan(dark), lm.plan(bright), lm.plan(mid)
        assert pd and not pd["in_band"] and pd["gamma"] > 1.0
        assert pb and not pb["in_band"] and pb["gamma"] < 1.0
        assert pm and pm["in_band"] and pm["gamma"] == 1.0
        print("ok  1. plan: dark lifts, bright drops, in-band untouched")

        # 2. corrections are CLAMPED — never past the configured ceiling
        assert 1.0 < pd["gamma"] <= 1.0 + lm.MAX_GAIN
        assert 1.0 - lm.MAX_GAIN <= pb["gamma"] < 1.0
        print("ok  2. gamma clamped: a nudge toward the band, not a regrade")

        # 3. in-band harmonize returns the INPUT path (no re-encode)
        out = lm.maybe_harmonize(mid, root / "mid_out.jpg")
        assert out == mid and not (root / "mid_out.jpg").exists()
        print("ok  3. in-band asset passes through untouched")

        # 4. out-of-band harmonize writes a file measurably closer to target
        fixed = lm.maybe_harmonize(dark, root / "dark_fixed.jpg")
        assert fixed and fixed != dark and Path(fixed).exists()
        before = lm._stats(dark)[0]
        after = lm._stats(Path(fixed))[0]
        assert abs(after - lm.TARGET_LUMA) < abs(before - lm.TARGET_LUMA), \
            (before, after)
        print(f"ok  4. dark asset moved toward target "
              f"({before:.0f} -> {after:.0f}, target {lm.TARGET_LUMA:.0f})")

        # 5. failure paths return None, never raise
        assert lm.maybe_harmonize(root / "missing.jpg",
                                  root / "x.jpg") is None
        junk = root / "junk.jpg"
        junk.write_bytes(b"not an image at all" * 40)
        assert lm.maybe_harmonize(junk, root / "y.jpg") is None
        print("ok  5. missing/corrupt input -> None (engines contract)")

        # 6. GATED means gated: no production renderer imports it yet
        for mod in ("data_learning/pro_render.py",
                    "data_learning/footage_hybrid.py",
                    "data_learning/media.py"):
            assert "lookmatch" not in (REPO / mod).read_text(), \
                f"{mod} adopted lookmatch without the required preview render"
        print("ok  6. no renderer calls it — adoption still requires a preview")

    print("lookmatch: 6/6 tests pass")


if __name__ == "__main__":
    main()
