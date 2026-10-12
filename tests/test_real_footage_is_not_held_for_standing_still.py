"""A coach at a podium is a quiet shot, not a frozen one.

The 2026-10-12 Baller Bro run blocked a Kyle Shanahan press conference
(the sample the operator liked: "good beginning, middle, and payoff")
before the judge saw it: "too many held frames". Not one frame in it was
repeated. The cadence probe counts a pair of frames as held when no block
moves more than BLOCK_MOTION_THRESH, which is right for an animation and
wrong for a man standing still. On real footage the same floors are now
measured on frames that are really the same (FROZEN_THRESH), so a
low-fps source doubled into the master and a frozen stream still block.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import showrunner_review as sr


def _clip(d: Path, name: str, vf: str) -> Path:
    """A 6s 30fps clip of a slowly drifting test pattern, through `vf`."""
    p = d / f"{name}.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=s=540x960:r=30:d=6", "-vf", vf, "-c:v", "libx264",
         "-crf", "23", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         str(p)], check=True)
    return p


def _ev(path: Path) -> dict:
    with tempfile.TemporaryDirectory() as td:
        return sr._temporal_evidence(path, Path(td))


class RealFootageIsJudgedOnRepeatedFrames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        d = Path(cls.td.name)
        cls.smooth = _ev(_clip(d, "smooth", "null"))
        cls.low_fps = _ev(_clip(d, "low", "fps=8,fps=30"))
        # 1.5s of picture, then the last frame held for 4.5s
        cls.frozen = _ev(_clip(d, "frozen",
                               "trim=0:1.5,setpts=PTS-STARTPTS,"
                               "tpad=stop_mode=clone:stop_duration=4.5"))

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_it_measures_repeated_frames(self):
        for ev in (self.smooth, self.low_fps, self.frozen):
            self.assertIn("frozen_fps", ev)
            self.assertIn("max_frozen_run", ev)

    def test_a_low_fps_source_still_blocks_as_footage(self):
        self.assertIsNotNone(sr.temporal_hard_fail(self.low_fps,
                                                   footage=True))

    def test_a_frozen_stream_still_blocks_as_footage(self):
        self.assertIsNotNone(sr.temporal_hard_fail(self.frozen,
                                                   footage=True))

    def test_smooth_footage_passes(self):
        self.assertIsNone(sr.temporal_hard_fail(self.smooth, footage=True))


class AQuietShotIsNotAHeldOne(unittest.TestCase):
    # what the probe measured on the Shanahan press conference
    PODIUM = {"effective_fps": 11.3, "duplicate_ratio": 0.528,
              "max_dup_run": 50, "judder_fps": 23.9,
              "frozen_fps": 18.0, "frozen_ratio": 0.251,
              "max_frozen_run": 6}

    def test_the_podium_passes_as_footage(self):
        self.assertIsNone(sr.temporal_hard_fail(self.PODIUM, footage=True))

    def test_the_animation_floor_is_unchanged(self):
        self.assertIsNotNone(sr.temporal_hard_fail(self.PODIUM))

    def test_only_real_footage_formats_get_it(self):
        self.assertEqual(sr.REAL_FOOTAGE_FORMATS, {"sports_moment"})
        src = Path(sr.__file__).read_text()
        self.assertIn('in REAL_FOOTAGE_FORMATS)', src)


if __name__ == "__main__":
    unittest.main()
