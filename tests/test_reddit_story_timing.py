"""Reddit story illustrated-panel timing.

Doctor finding a544d37c275e (2026-08-11, confirmed 2026-08-17): the old
`_visual_track` dropped any shot whose image failed to resolve, then handed
the SURVIVING panels an equal share of the ENTIRE remaining duration. One
surviving panel could therefore be stretched across the whole story while
the narration moved through several unrelated beats — the showrunner
blocked two reddit stories on exactly that ("the last ~11s freezes on one
repeated clock still").

Every reddit_story shot already carries a `phrase` that
`shared/package_schema.py` verifies is a real substring of the script, so
the fix reuses `make_explainer_stacked.find_phrase_start` (the resolver the
explainer renderer has used for years) to give each shot its OWN
phrase-aligned window, and a shot with no resolved image simply gets no
clip instead of donating its window to a neighbor.

    python -m unittest tests.test_reddit_story_timing -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

import make_reddit_story as mrs                        # noqa: E402
from make_explainer_stacked import Word                 # noqa: E402


def _words(*tokens_and_starts: tuple[str, float], dur: float = 0.4) -> list[Word]:
    return [Word(start, start + dur, text) for text, start in tokens_and_starts]


class TestShotWindows(unittest.TestCase):
    def test_windows_track_each_shots_own_phrase(self):
        # "one two three four five six seven eight", one word per second.
        words = _words(*[(w, i * 1.0) for i, w in enumerate(
            ["one", "two", "three", "four", "five", "six", "seven", "eight"])])
        shots = [{"phrase": "two three"}, {"phrase": "five six"}]
        windows = mrs._shot_windows(shots, words, title_end=0.0, total=8.4)

        self.assertEqual(len(windows), 2)
        # Each window starts where ITS OWN phrase is actually spoken, not at
        # an arbitrary equal-division boundary.
        self.assertAlmostEqual(windows[0]["start"], 1.0, places=2)
        self.assertAlmostEqual(windows[1]["start"], 4.0, places=2)
        # Windows chain: shot 0 ends where shot 1 begins, and the last shot
        # runs to the end of the story — no gap, no overlap.
        self.assertAlmostEqual(windows[0]["end"], windows[1]["start"], places=2)
        self.assertAlmostEqual(windows[1]["end"], 8.4, places=2)
        # Strictly ordered: no window starts before the previous one.
        for a, b in zip(windows, windows[1:]):
            self.assertLessEqual(a["start"], b["start"])

    def test_unmatched_phrase_gets_a_floor_not_a_collapse(self):
        words = _words(("hello", 0.0), ("world", 1.0))
        shots = [{"phrase": "hello"}, {"phrase": "this phrase never appears"}]
        windows = mrs._shot_windows(shots, words, title_end=0.0, total=10.0)

        self.assertAlmostEqual(windows[0]["start"], 0.0, places=2)
        # Missing phrase -> a 2.5s floor after the previous shot's cursor,
        # not 0 and not a KeyError/None leaking through.
        self.assertAlmostEqual(windows[1]["start"], 2.6, places=2)
        self.assertGreater(windows[1]["end"], windows[1]["start"])

    def test_single_shot_window_spans_whole_story(self):
        words = _words(("only", 0.5))
        windows = mrs._shot_windows([{"phrase": "only"}], words,
                                    title_end=0.0, total=12.0)
        self.assertEqual(len(windows), 1)
        self.assertAlmostEqual(windows[0]["end"], 12.0, places=2)


class TestVisualTrackGaps(unittest.TestCase):
    """A shot whose image never resolved must not hand its screen time to a
    neighboring panel — that IS the bug the showrunner blocked on."""

    def setUp(self):
        self._orig_panels = mrs._shot_panels
        self._orig_run = mrs._run
        mrs._run = lambda cmd: None   # never shell out to real ffmpeg

    def tearDown(self):
        mrs._shot_panels = self._orig_panels
        mrs._run = self._orig_run

    def test_unresolved_panels_are_skipped_not_stretched(self):
        # 4 narrated beats, one word each, one second apart.
        words = _words(*[(w, i * 1.0) for i, w in enumerate(
            ["alpha", "bravo", "charlie", "delta"])])
        pkg = {"shots": [{"phrase": "alpha"}, {"phrase": "bravo"},
                         {"phrase": "charlie"}, {"phrase": "delta"}]}
        # Only shot 0's image ever resolved — 3 of 4 panels failed, exactly
        # the "image generation mostly failed" shape from production.
        mrs._shot_panels = lambda pkg, workdir: {0: Path("panel0.jpg")}

        visual = mrs._visual_track(pkg, words, title_end=0.0, total=4.4,
                                   workdir=Path("/tmp"))

        self.assertIsNotNone(visual)
        # A single surviving panel must cover only ITS OWN window, never the
        # full remaining story — that is what "cannot pass as fully
        # illustrated" means structurally.
        self.assertEqual(len(visual), 1)
        self.assertAlmostEqual(visual[0]["start"], 0.0, places=2)
        self.assertLess(visual[0]["end"], 4.4)

    def test_no_resolved_panels_falls_back_to_no_illustration(self):
        words = _words(("alpha", 0.0))
        pkg = {"shots": [{"phrase": "alpha"}]}
        mrs._shot_panels = lambda pkg, workdir: {}

        visual = mrs._visual_track(pkg, words, title_end=0.0, total=5.0,
                                   workdir=Path("/tmp"))
        self.assertIsNone(visual)


if __name__ == "__main__":
    unittest.main()
