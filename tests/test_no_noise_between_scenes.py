"""No noise on a scene change, and every scene starts with its own line.

Operator, 2026-10-17, of the household-size video: "The hell is that noise
between the scene changes?" The soundtrack played a burst of filtered brown
noise on every cut. It also landed on the wrong spot: each scene window is
its line plus a breath, but the lines were joined back to back with no
breath, so by the fourth line the cut and its noise sat half a second into
the next line's first word. The Google voice's lines are trimmed tight,
which is why it showed now.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_learning import studio_render as SR  # noqa: E402


def _tone(p: Path, secs: float) -> Path:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"sine=f=220:d={secs}:r=24000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(p)], check=True)
    return p


class NothingPlaysOnACut(unittest.TestCase):
    def test_the_only_sounds_are_the_numbers_and_the_closing(self):
        runs = []
        saved = SR._run, SR._build_music
        try:
            SR._run = lambda cmd, *a, **k: runs.append(cmd)
            SR._build_music = lambda *a, **k: None
            windows = [(0, 3), (3, 6), (6, 9), (9, 12), (12, 15)]
            events = [{"ps": 4.0, "punch": {"text": "29%", "color": ""}}]
            SR._build_soundtrack(Path("n.wav"), windows, events, 15.0, "calm",
                                 Path(tempfile.mkdtemp()), "slug")
        finally:
            SR._run, SR._build_music = saved
        mix = runs[-1]
        sfx_in = [mix[i + 1] for i, a in enumerate(mix)
                  if a == "-i" and "sfx_" in mix[i + 1]]
        self.assertEqual(len(sfx_in), len(events) + 1, sfx_in)
        self.assertFalse(any("noise" in " ".join(c) for c in runs))


class EverySceneStartsWithItsLine(unittest.TestCase):
    def test_the_audio_carries_the_gap_the_windows_count(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            lines = [_tone(d / f"s{i}.wav", s) for i, s in enumerate((1.3, 0.7, 2.1))]
            t, windows = 0.0, []
            for w in lines:
                dur = SR._dur(w) + SR.LINE_GAP
                windows.append((t, t + dur)); t += dur
            raw = SR._join_lines(lines, d)
            self.assertAlmostEqual(SR._dur(raw), windows[-1][1] + 0.18, delta=0.03)


class AnIllustratedStoryKeepsItsWrittenOrder(unittest.TestCase):
    """The same video ended on "131% of US homes hold one person": the build
    moved a trend beat to the end, and each saved scene, drawn for its own
    config beat, was laid over the shuffled beat's numbers."""

    def test_the_build_does_not_shuffle_an_illustrated_story(self):
        import os
        from data_learning import story as ST
        saved = os.environ.get("EXPLAINER_STYLE")
        try:
            os.environ["EXPLAINER_STYLE"] = "illustrated"
            self.assertTrue(ST._illustrated({"slug": "household-size-shrinking"}))
            os.environ["EXPLAINER_STYLE"] = "current"
            self.assertFalse(ST._illustrated({"slug": "household-size-shrinking"}))
        finally:
            if saved is None:
                os.environ.pop("EXPLAINER_STYLE", None)
            else:
                os.environ["EXPLAINER_STYLE"] = saved
        src = (REPO / "data_learning" / "story.py").read_text()
        self.assertIn('story_cfg.get("keep_order") or _illustrated(story_cfg)', src)


if __name__ == "__main__":
    unittest.main()
