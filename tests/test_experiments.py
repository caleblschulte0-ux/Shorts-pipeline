"""Tests for shared/experiments.py sample scoping.

Doctor finding 66364106b455 (2026-08-17): Third's story-vs-clip arm records
`actual_structure` per video (clip / story / simple_fallback — a self-healed
fallback still gets a `story` slot assignment but ships as
`actual_structure="clip"` or `"simple_fallback"`). Before this fix,
`eligible_videos()` only scoped by `channel`/`format`, so a story experiment
scoped to `format="third"` would credit every clip and fallback in the
window as a "story" sample and could conclude on the wrong population.

    python -m unittest tests.test_experiments -v
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import experiments as ex                  # noqa: E402


def _video(**over):
    v = {"published_at": "2026-09-01T00:00:00Z", "_channel": "third",
         "format": "third", "actual_structure": "clip"}
    v.update(over)
    return v


class TestStructureScoping(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="exp-struct-"))
        self._saved = (ex.RETRO_STATE, ex.REGISTER)
        ex.RETRO_STATE = self.tmp
        ex.REGISTER = self.tmp / "experiments.json"

    def tearDown(self):
        ex.RETRO_STATE, ex.REGISTER = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _reg(self, **over):
        kw = dict(change="c", metric="views_per_hour", direction="up",
                  baseline=0.03, channel="third", format="third",
                  now="2026-08-01T00:00:00Z")
        kw.update(over)
        return ex.register("story arm test", **kw)

    def test_unscoped_experiment_counts_every_structure(self):
        """Before this fix this was the ONLY behaviour available — proves
        the new parameter is additive, not a breaking change."""
        e = self._reg()
        videos = [_video(actual_structure="clip"),
                  _video(actual_structure="story"),
                  _video(actual_structure="simple_fallback")]
        self.assertEqual(len(ex.eligible_videos(e, videos)), 3)

    def test_structure_scoped_experiment_excludes_other_structures(self):
        """The bug this closes: a story-arm experiment must not count a
        self-healed fallback clip as a story sample just because it shipped
        from the same daily slot."""
        e = self._reg(structure="story")
        videos = [_video(actual_structure="clip"),
                  _video(actual_structure="story"),
                  _video(actual_structure="simple_fallback"),
                  _video(actual_structure="story")]
        got = ex.eligible_videos(e, videos)
        self.assertEqual(len(got), 2)
        self.assertTrue(all(v["actual_structure"] == "story" for v in got))

    def test_structure_scoping_composes_with_channel_and_format(self):
        e = self._reg(structure="story")
        videos = [
            _video(actual_structure="story"),                    # counts
            _video(actual_structure="story", _channel="explainer"),  # wrong channel
            _video(actual_structure="story", format="graph_race"),   # wrong format
            _video(actual_structure="clip"),                     # wrong structure
        ]
        got = ex.eligible_videos(e, videos)
        self.assertEqual(len(got), 1)

    def test_advance_recount_respects_structure_scope(self):
        """advance() drives the daily sample count off eligible_videos() —
        prove the fix reaches the real entry point, not just the helper."""
        e = self._reg(structure="story")
        videos_by_channel = {"third": [
            _video(actual_structure="story"),
            _video(actual_structure="clip"),
            _video(actual_structure="simple_fallback"),
        ]}
        ex.advance(videos_by_channel)
        reloaded = ex.all_experiments()[0]
        self.assertEqual(reloaded["samples_seen"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
