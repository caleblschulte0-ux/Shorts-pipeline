"""The number the VOICE says must be one the PICTURE can show.

The operator, 2026-09-07: *"we need to be matching the beats a lot better."*

Measured over the 858 configured explainer beats that speak a quantity, 84.5%
have their headline number on screen and 15.5% do not — and the misses are
one class, every time. The writer converts the measured figure into a second,
louder one the dataset does not contain:

    "By 2020 that hit 34 percent — 2.6 billion people."   chart: 22% / 34%
    "Auto loan rates peaked at 8.1 percent. On a 50
     thousand dollar car..."                              chart: 5.2% / 8.1%
    "We've named about 240 thousand ocean species and
     think there are 2 million."                          chart: 240K

A rate becomes a headcount, a rate becomes a dollar amount, and the viewer
hears a number they cannot find anywhere on the frame.

This is an AUTHORING fault, not a rendering one, and it already breaks the
standing rule that the brain writes only the words while every number comes
from the source. `shared/beat_match.py` is the check and the story forge feeds
a failure back to the brain inside the retry loop it already has — the story
is fine, the SENTENCE is fixable.

Deliberately generous about what counts as derivable: a difference, a
percentage change, a share of the total and a unit rescale are all things the
beat can honestly say and the chart can honestly be showing. Only the HEADLINE
number is checked — a supporting figure mentioned in passing is fine; the one
the beat is ABOUT is not allowed to be missing.

Runs standalone:  python3 tests/test_beats_match_the_words.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from shared import beat_match as bm  # noqa: E402


class TheHeadlineNumberMustBeOnScreen(unittest.TestCase):
    def test_a_headcount_invented_from_a_rate_is_refused(self):
        got = bm.check("By 2020 that hit 34 percent — 2.6 billion people.",
                       [22, 26, 30, 34], "percent")
        self.assertFalse(got["ok"])
        self.assertAlmostEqual(got["headline"], 2.6e9)

    def test_a_price_invented_from_a_rate_is_refused(self):
        got = bm.check("Rates peaked at 8.1 percent. On a 50 thousand dollar "
                       "car that is real money.", [4.5, 5.2, 8.1], "percent")
        self.assertFalse(got["ok"])

    def test_the_measured_number_itself_passes(self):
        self.assertTrue(bm.check("Eggs are up 86 percent since 2020.",
                                 [10, 21, 86], "percent")["ok"])

    def test_a_ROUNDED_restatement_passes(self):
        """"nearly 1.4 trillion" for 1,370 billion is the same fact said
        aloud, and the writer should be free to say it that way."""
        self.assertTrue(bm.check(
            "Card debt just passed 1,370 billion dollars, nearly 1.4 "
            "trillion on plastic.", [860, 930, 1370], "billion dollars")["ok"])

    def test_a_DIFFERENCE_between_two_values_passes(self):
        self.assertTrue(bm.check(
            "The bill hit 1,030 dollars, about 310 more than 2019.",
            [720, 880, 1030], "dollars")["ok"])

    def test_a_PERCENTAGE_CHANGE_passes(self):
        self.assertTrue(bm.check(
            "Your employer paid 8,120 per worker, up 35 percent from 6,015.",
            [6015, 7358, 8120], "dollars")["ok"])

    def test_a_UNIT_RESCALE_passes(self):
        """The screen writes "$50.4K" for a value of 50.4 in thousands. The
        voice saying "50,400 dollars" is the same number, not a mismatch —
        an earlier attempt at this check got that wrong and reported a
        disagreement that did not exist."""
        self.assertTrue(bm.check(
            "The average new car hit 50,400 dollars in 2026.",
            [38.0, 44.0, 50.4], "thousand dollars")["ok"])


class ItRefusesToBeTrivial(unittest.TestCase):
    def test_a_YEAR_is_not_a_quantity(self):
        """Counting "since 2007" as a spoken number would make every beat
        match something and the check would mean nothing."""
        self.assertEqual(bm.spoken_quantities("It rose from 2007 to 2019."),
                         [])

    def test_a_line_with_no_quantity_is_not_a_failure(self):
        self.assertTrue(bm.check("It barely moved at all.", [5, 9], "%")["ok"])

    def test_a_beat_with_no_data_is_not_a_failure(self):
        self.assertTrue(bm.check("Ten million people.", [], "")["ok"])

    def test_magnitude_words_scale_the_spoken_number(self):
        self.assertEqual(bm.spoken_quantities("about 2.6 billion people"),
                         [2.6e9])
        self.assertEqual(bm.spoken_quantities("240 thousand species"),
                         [240000.0])


class TheForgeFeedsItBackToTheBrain(unittest.TestCase):
    def test_the_word_loop_checks_every_say_line(self):
        src = (_REPO / "scripts" / "story_forge.py").read_text(encoding="utf-8")
        self.assertIn("from shared import beat_match as bm", src)
        self.assertIn("BEAT MATCHING", src)
        self.assertIn('w.get("says")', src)

    def test_a_failure_is_a_REWRITE_not_a_refusal(self):
        """The story and its data are fine — only the sentence is wrong, and
        the retry loop already exists to fix sentences."""
        src = (_REPO / "scripts" / "story_forge.py").read_text(encoding="utf-8")
        block = src[src.index("BEAT MATCHING"):]
        self.assertIn("reasons.append", block[:2000])


if __name__ == "__main__":
    unittest.main(verbosity=2)
