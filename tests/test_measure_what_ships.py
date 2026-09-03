"""Measure the COMPOSITE, never a layer in isolation.

Every camera-shake bug this repo has had started as an honest measurement of
the wrong thing. The reddit panel is a still image, so someone measured the
panel clip on its own, watched it score 0.0 effective fps, and added a 22 px
orbital drift at ~0.95 Hz to make the number move. But that panel is never
shown on its own: it occupies the TOP HALF of the frame and live gameplay
plays underneath it, with word-by-word karaoke captions over the middle.

Measured with the reviewer's own detector (`showrunner_review._temporal_
evidence`), on 2026-09-03:

    static panel + gameplay underneath   ->  24.0 fps, dup 0.00, run 1   PASS
    the same panel measured ALONE        ->   0.0 fps, dup 1.00, run 192 FAIL

So the drift bought nothing the composite did not already have, and cost the
channel a handheld wobble on every video for a month. The rule this test
encodes: a layer's motion is only a problem if the SHIPPED FRAME is still.

Runs with pytest OR standalone:
    python3 tests/test_measure_what_ships.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _ffmpeg() -> str | None:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        # the detector shells out to bare `ffmpeg`
        os.environ["PATH"] = str(Path(exe).parent) + os.pathsep + os.environ["PATH"]
        link = Path(exe).parent / "ffmpeg"
        if not link.exists():
            try:
                os.symlink(exe, link)
            except OSError:
                pass
        return exe
    except Exception:  # noqa: BLE001
        return None


class MeasureWhatShips(unittest.TestCase):
    def _measure(self, filt: str, dur: int = 6) -> dict:
        ff = _ffmpeg()
        if not ff:
            self.skipTest("ffmpeg unavailable")
        import scripts.showrunner_review as sr
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            mp4 = td / "clip.mp4"
            subprocess.run(
                [ff, "-y", "-loglevel", "error",
                 "-f", "lavfi", "-i", "mandelbrot=size=540x480:rate=30",
                 "-f", "lavfi", "-i", f"color=c=0x1b2735:s=540x480:d={dur}:r=30",
                 "-filter_complex", filt, "-map", "[v]", "-t", str(dur),
                 "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)],
                check=True)
            return sr._temporal_evidence(mp4, td)

    def test_a_still_panel_over_gameplay_clears_the_floor(self):
        """The composite that actually ships. No camera motion anywhere in it:
        the top half is a frozen image and it still passes, because the bottom
        half is gameplay."""
        import scripts.showrunner_review as sr
        ev = self._measure("[0:v][1:v]vstack=inputs=2,format=yuv420p[v]")
        if ev.get("effective_fps") is None:
            self.skipTest(f"detector unavailable: {ev.get('error')}")
        self.assertIsNone(
            sr.temporal_hard_fail(ev),
            f"the shipped composite should pass with a locked camera: {ev}")
        self.assertGreaterEqual(ev["effective_fps"], 11.0, str(ev))

    def test_the_panel_alone_is_the_wrong_thing_to_measure(self):
        """The measurement that caused the bug. Kept as a live demonstration:
        this number is SUPPOSED to be bad, and it is not a reason to move the
        camera — it is a reason to measure the composite instead."""
        ev = self._measure("[1:v]scale=540:960,format=yuv420p[v]")
        if ev.get("effective_fps") is None:
            self.skipTest(f"detector unavailable: {ev.get('error')}")
        self.assertLess(
            ev["effective_fps"], 11.0,
            "a frozen layer measured alone should still score badly — if this "
            "starts passing, this test no longer demonstrates anything")


if __name__ == "__main__":
    unittest.main(verbosity=2)
