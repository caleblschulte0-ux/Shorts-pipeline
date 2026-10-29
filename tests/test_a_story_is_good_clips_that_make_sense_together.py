"""A story is interesting clips that make sense in the order they are in.

2026-10-28, the operator, after every structured story arm failed: "we
ain't Dan Harmon we don't need a perfectly structured story it's just
need to be interesting clips that make sense to put in the order we put
them in and make a larger product then just one clip"; then "they need to
make sense not just random clips". The loose slot drops the plot (so/but
chain, single payoff) and keeps every check that a stranger can follow
it."""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO))

from third_capture import story_director as sd  # noqa: E402


class _Loose:
    def __enter__(self):
        sd.loose(True)

    def __exit__(self, *a):
        sd.loose(False)


def _critic(problems, payoff_at=30.0):
    return {"publish": True, "story_score": 84,
            "stranger_summary": "Kai gets three terrible Uber drivers",
            "payoff_at": payoff_at, "entertaining_at": 12.0,
            "entertaining_why": "the driver starts singing",
            "problems": problems}


class TheBarIsLooserOnlyWhereItAskedForAPlot(unittest.TestCase):
    def _review(self, out):
        with mock.patch.object(sd, "_brain", return_value=out):
            return sd.review_rough_cut({"beats": []}, "", None, 40.0)

    def test_and_is_a_link_only_in_the_loose_slot(self):
        self.assertNotIn("and", sd.LINKS)
        self.assertIn("and", sd.LOOSE_LINKS)

    def test_no_single_payoff_is_not_a_block_in_the_loose_slot(self):
        weak = [{"type": "weak_payoff", "at": 38, "fix": "no answer"}]
        self.assertFalse(self._review(_critic(weak))["publish"])
        with _Loose():
            got = self._review(_critic(weak))
        self.assertTrue(got["publish"])
        self.assertEqual(got["story_score"], 84)

    def test_it_still_has_to_make_sense(self):
        for t in ("confusing", "missing_context", "misleading"):
            with _Loose():
                got = self._review(_critic(
                    [{"type": t, "at": 5, "fix": "who is this?"}]))
            self.assertFalse(got["publish"], t)
            self.assertLessEqual(got["story_score"], sd.UNFINISHED_MAX)

    def test_it_still_has_to_be_interesting(self):
        out = dict(_critic([]), entertaining_at=None)
        with _Loose():
            got = self._review(out)
        self.assertFalse(got["publish"])

    def test_every_brain_is_told_the_bar(self):
        seen = []
        with _Loose(), mock.patch.object(
                sd, "_brain",
                side_effect=lambda u, s, **k: seen.append(s) or None):
            sd.scout_stories(["C1 | a", "C2 | b"], {"C1", "C2"})
            sd.review_rough_cut({"beats": []}, "", None, 40.0)
        self.assertTrue(seen)
        self.assertTrue(all("Dan" not in s and "OVERRIDES" in s
                            for s in seen))
        seen.clear()
        with mock.patch.object(
                sd, "_brain",
                side_effect=lambda u, s, **k: seen.append(s) or None):
            sd.scout_stories(["C1 | a", "C2 | b"], {"C1", "C2"})
        self.assertNotIn("OVERRIDES", seen[0])


class AFullStoryStillComesFirst(unittest.TestCase):
    def test_the_run_of_clips_is_the_floor_not_the_goal(self):
        # operator, 2026-10-29: "this is the min bar like if we can throw a
        # story together that does fit a good beginning middle and end
        # payoff then obviously we should do that"
        self.assertIn("THE FLOOR, NOT THE GOAL", sd._LOOSE_RULE)
        self.assertLess(sd._LOOSE_RULE.index("THE FLOOR, NOT THE GOAL"),
                        sd._LOOSE_RULE.index("2-5 clips"))


class TheSlotIsWired(unittest.TestCase):
    def test_compilation_turns_it_on(self):
        src = (REPO / "scripts" / "run_third.py").read_text()
        self.assertIn('story_director.loose(spec.get("story_pick") == '
                      '"compilation")', src)
        bt = (REPO / "scripts" / "story_backtest.py").read_text()
        self.assertIn('"compilation"', bt)


if __name__ == "__main__":
    unittest.main()
