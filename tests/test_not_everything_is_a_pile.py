"""Not everything is a pile.

Operator, 2026-10-11: *"we kind of overuse piles. Like, a pile of envelopes,
pile of baby diapers, a pile of stuff coming out of slot machines. The slot
machine one makes a lot more sense, obviously, but I think we need to relax
on the piles."*

The prompt used to answer every "make the change big" with "draw what piles
up", and THE PILE is one of the bars, so the brain drew heaps of tokens for
debts and births. Now the blind viewer says whether the change is a heap of
copies, the judge (given the narration) says whether that heap is a token
count or the story's own stuff really piling up, and a token count is
refused. Prompt rule 19 says so.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import scene_author as SA  # noqa: E402

PTS = [["2019", 10.0], ["2024", 30.0]]


class APileOfTokensIsRefused(unittest.TestCase):
    def _glance(self, heap, judge, say="Medical debt fell off 16 million credit reports."):
        seen = {"object": "a pile of envelopes", "object_from": "its own shape",
                "tells": "flaps", "substance": "envelopes",
                "change": "the pile of envelopes grows", "how_much": "dramatic",
                "shot": "a place", "heap": heap}
        answers = [seen, {"is_hero": True, "substance_fits": True,
                          "cause_makes_sense": True, "story_fit": True, **judge}]
        with mock.patch.object(SA, "glance_frames", return_value=[]), \
             mock.patch.object(SA, "declared", return_value={
                 "HERO": "a pile of bills", "SUBSTANCE": "envelopes",
                 "CAUSE": "Data shovels them"}), \
             mock.patch.object(SA, "ask_glance",
                               side_effect=lambda p, i: answers.pop(0)) as ask:
            out = SA.glance(lambda *a: None, PTS, log=lambda m: None, say=say)
        return out, ask

    def test_a_token_pile_is_refused(self):
        out, ask = self._glance("yes", {"heap_fits": False})
        self.assertTrue(any("pile of copies" in p for p in out), out)
        self.assertIn("a heap of copies of one object: yes",
                      ask.call_args_list[1].args[0])

    def test_a_pile_that_is_the_story_passes(self):
        out, _ = self._glance("yes", {"heap_fits": True},
                              say="Plastic waste will nearly triple by 2060.")
        self.assertEqual(out, [])

    def test_no_heap_is_never_refused_as_one(self):
        out, _ = self._glance("no", {"heap_fits": False})
        self.assertEqual(out, [])

    def test_without_narration_the_pile_is_not_judged(self):
        out, _ = self._glance("yes", {"heap_fits": False}, say="")
        self.assertEqual(out, [])


class TheBrainIsToldAndTheViewerIsAsked(unittest.TestCase):
    def test_the_viewer_reports_a_heap(self):
        self.assertIn('"heap"', SA._LOOK)
        self.assertIn('"heap_fits"', SA._JUDGE)

    def test_rule_19_is_in_the_prompt(self):
        p = SA.build_prompt("t", "x", "y", PTS, "")
        self.assertIn("19. NOT EVERYTHING IS A PILE", p)
        self.assertIn("relax on the piles", p)

    def test_big_change_no_longer_defaults_to_a_pile(self):
        p = SA.build_prompt("t", "x", "y", PTS, "")
        self.assertNotIn("draw what piles up", p)
        src = (ROOT / "data_learning" / "scene_author.py").read_text()
        self.assertNotIn("draw what piles up", src)

    def test_saved_scenes_are_rejudged_under_the_rule(self):
        self.assertGreaterEqual(SA.STANDARD, "2026-10-11")


if __name__ == "__main__":
    unittest.main()
