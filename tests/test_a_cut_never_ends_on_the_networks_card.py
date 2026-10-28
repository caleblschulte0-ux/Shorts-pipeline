"""A sports cut never ends on the broadcast's own logo or bumper (operator,
2026-10-28: "we won't play clips that don't make sense"; a sample of
Barkley and Shaq ran four seconds into ESPN's "Tip-Off" bumper)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import sports_samples as ss  # noqa: E402
from shared import shot_relevance  # noqa: E402


class TheCutStopsBeforeTheCard(unittest.TestCase):
    def _run(self, cuts, verdict, cut=(0.0, 32.0)):
        edit = {"cut": {"start": cut[0], "end": cut[1]}}
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(ss, "_cuts_in", return_value=cuts), \
                mock.patch("funnel.find_footage._frame",
                           side_effect=lambda v, a, o: o), \
                mock.patch.object(shot_relevance, "judge_panels",
                                  return_value=verdict):
            return ss.end_card(Path("x.mp4"), edit, Path(td))["cut"]

    def test_it_ends_where_the_card_begins(self):
        got = self._run([25.0, 28.0], {0: {"depicts": True},
                                       1: {"depicts": False, "why": "logo"}})
        self.assertEqual(got["end"], 27.95)

    def test_real_shots_keep_the_ending(self):
        got = self._run([25.0, 28.0], {0: {"depicts": True},
                                       1: {"depicts": True}})
        self.assertEqual(got["end"], 32.0)

    def test_no_brain_keeps_it(self):
        self.assertEqual(self._run([28.0], None)["end"], 32.0)

    def test_never_shorter_than_ten_seconds(self):
        got = self._run([5.0], {0: {"depicts": False}}, cut=(0.0, 12.0))
        self.assertEqual(got["end"], 12.0)

    def test_make_runs_it(self):
        src = (REPO / "scripts" / "sports_samples.py").read_text()
        body = src[src.index("def make("):]
        self.assertLess(body.index("end_card(raw"),
                        body.index("clip_edit.edit("))


if __name__ == "__main__":
    unittest.main()
