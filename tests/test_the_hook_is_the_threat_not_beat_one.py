"""The hook is the threat, never beat one said twice.

Operator, 2026-10-15, of the Panama Canal video, which opened on "The
Panama Canal is down to 24 ships a day, and a drought did it" and then said
24 and the drought again in beat one: "we say that twice ... nobody knows
what that means ... maybe 24 is high, maybe it's low ... If I was writing
that, I would have said, the Panama Canal is drying up, and it might
already be too late."
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from shared import hook_doctrine as H  # noqa: E402
from shared import narration as N  # noqa: E402

THEIRS = "The Panama Canal is drying up, and it might already be too late."
PANAMA = {
    "slug": "panama", "title": "Panama Canal Transits Just Dropped From 36 To 24",
    "hook": "The Panama Canal is down to 24 ships a day, and a drought did it.",
    "segments": [{"say": "A historic drought forced the Panama Canal to cut "
                         "its normal daily ship crossings down to just 24."},
                 {"say": "The lake that feeds the locks dropped to 80.3 feet."}]}


class TheOperatorsHookClearsTheFloor(unittest.TestCase):
    def test_a_threat_is_not_a_hedge(self):
        self.assertEqual(H.floor(THEIRS), [])
        self.assertEqual(H.floor("Your savings may never come back."), [])

    def test_a_hedge_on_the_fact_still_fails(self):
        self.assertIn("hedge", H.floor("Your coffee might get gutted."))
        self.assertIn("hedge", H.floor("Prices may have doubled."))

    def test_it_is_the_bar_the_brain_is_shown(self):
        self.assertIn(THEIRS, H.DOCTRINE)
        self.assertIn("drying up", H._LISTEN)


class TheHookIsNotBeatOneSaidTwice(unittest.TestCase):
    def test_the_posted_hook_repeats_beat_one(self):
        self.assertTrue(H.repeats_beat_one(PANAMA["hook"], PANAMA))
        self.assertEqual(H.repeats_beat_one(THEIRS, PANAMA), [])

    def test_a_repeating_hook_is_rewritten_not_kept(self):
        def brain(prompt):
            if "ranking" in prompt:
                return '{"ranking": [1]}'
            return '{"hooks": ["%s"]}' % THEIRS
        got = H.sharpen(dict(PANAMA), brain=brain, log=lambda m: None)
        self.assertEqual(got, THEIRS)

    def test_a_rewrite_that_repeats_is_refused(self):
        said = []

        def brain(prompt):
            if "ranking" in prompt:
                return '{"ranking": [1]}'
            return '{"hooks": ["Only 24 ships a day now."]}'
        self.assertIsNone(H.sharpen(dict(PANAMA), brain=brain, log=said.append))
        self.assertTrue(any("beat one says" in m for m in said), said)


class ANumberComesWithItsYardstick(unittest.TestCase):
    def test_the_narration_is_told_and_heard_for_it(self):
        self.assertIn("YARDSTICK", N.DOCTRINE)
        self.assertIn("a lot or a", N._LISTEN)
        self.assertIn("repeats the", N._LISTEN)


if __name__ == "__main__":
    unittest.main()
