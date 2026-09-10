"""THE VOICE SAID A NUMBER THE PICTURE COULD NOT SHOW.

    "seg1 shows 2000-vs-2012 at 33% while the voice says 92% by 2023"
    "the scale's numbers never reach the narrated 3.5M / 3.0M"
                                self-checkout-cashier-jobs, 2026-09-09

`shared/beat_match` has answered "is this number derivable from this beat's
data" since 2026-09-07, generously — a difference, a percentage change, a
share of the total and a unit rescale all pass. It was wired into the story
forge's retry loop and NOWHERE ELSE. The forge is not the only author, it
gives up after three attempts and ships anyway, and 305 stories were written
before the check existed. Nothing downstream ever looked.

Measured over the 957 configured beats that speak a quantity, **131 fail**.

## Two tokeniser faults first, because they were blaming the wrong number

`check` refuses the LOUDEST quantity in a line, so a spurious one hijacks the
whole diagnosis.

**A digit welded to a word is part of the word.** `car-cost-explosion` seg2
reads *"1,920 dollars a month, what a 2-bedroom rented for"* over a chart of
1,080..1,920 — and the beat was failed for saying "2". Ordinals and ranges do
the same: "1st", "9-to-5", "3x". The magnitude suffixes are the exception and
now scale properly: 50K, 2.6B.

**A year is written without a separator.** That same beat's real headline,
1,920, was being discarded as a YEAR — which is what left it with nothing but
the 2. The only thing separating "1,920 dollars" from "since 2007" is the
comma.

Together those were 6 beats and 5 stories failed for nothing.

## Then the gate, set where it only catches the indefensible

Refusing all 131 would hold a third of the queue, and most are a writer's
aside ("on a 50 thousand dollar car") rather than a lie. But the tail is not
that: **33 beats are a thousand times or more away from everything on
screen** — "About 117 billion people have ever been born" over a chart whose
largest value is in the thousands. A viewer hearing that looks for it, finds
nothing remotely like it, and stops trusting the picture.

28 of 305 stories are held. The other 98 beats are REPORTED into `reasons`
where the run log and the repair loop can see them, and do not fail the story.

Runs standalone:  python3 tests/test_say_a_number_the_picture_shows.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from shared import beat_match as bm   # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "editorial_gate", _REPO / "scripts" / "editorial_gate.py")
eg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eg)

_TMP = Path(tempfile.mkdtemp())
eg.DATA_DIR = _TMP


def _sc(say, values, unit="count"):
    (_TMP / "t.json").write_text(json.dumps(
        {"key": "t", "unit": unit, "insight_type": "trend",
         "points": [{"label": str(i), "value": v}
                    for i, v in enumerate(values)],
         "source": {"publisher": "p", "officiality": "official",
                    "access_date": "2026-09-09"}}))
    return {"segments": [{"key": "t", "say": say}]}


class ADigitWeldedToAWordIsPartOfTheWord(unittest.TestCase):
    def test_the_named_case(self):
        """"what a 2-bedroom rented for" is not the beat saying two."""
        q = bm.spoken_quantities(
            "Owning a car now runs 1,920 dollars a month, what a 2-bedroom "
            "rented for not long ago.")
        self.assertEqual(q, [1920.0])

    def test_ordinals_and_ranges(self):
        self.assertEqual(bm.spoken_quantities("a 9-to-5 job and a 1st-round "
                                              "pick"), [])

    def test_magnitude_suffixes_are_the_exception(self):
        self.assertEqual(bm.spoken_quantities("raised 50K and 2.6B in total"),
                         [50_000.0, 2_600_000_000.0])

    def test_a_plain_word_after_a_number_is_still_a_quantity(self):
        self.assertEqual(bm.spoken_quantities("8.1 percent"), [8.1])
        self.assertEqual(bm.spoken_quantities("2.6 billion people"),
                         [2_600_000_000.0])


class AYearIsWrittenWithoutASeparator(unittest.TestCase):
    def test_a_grouped_number_in_the_year_range_is_money_not_a_date(self):
        self.assertEqual(bm.spoken_quantities("runs 1,920 dollars a month"),
                         [1920.0])

    def test_a_bare_year_is_still_skipped(self):
        self.assertEqual(bm.spoken_quantities("the highest since 2007"), [])

    def test_a_year_followed_by_a_comma_is_still_a_year(self):
        """"In 1990, 22 percent" — the comma is punctuation, not grouping."""
        self.assertEqual(bm.spoken_quantities(
            "In 1990, 22 percent of the world was nearsighted."), [22.0])

    def test_a_real_pair_reads_correctly(self):
        self.assertEqual(bm.spoken_quantities(
            "417 pairs in 1963, over 71,000 by 2020"), [417.0, 71000.0])


class TheGateHoldsOnlyTheIndEFENSIBLE(unittest.TestCase):
    def test_a_number_from_another_universe_is_refused(self):
        sc = _sc("About 117 billion people have ever been born.",
                 [1200.0, 1400.0])
        v = eg.beat_numbers_are_on_screen(sc)
        self.assertFalse(v["ok"])
        self.assertIn("away from anything", v["reasons"][0])

    def test_a_writers_aside_is_reported_but_not_refused(self):
        """"on a 50 thousand dollar car" over a chart of interest rates is
        loose, not a lie — it is 6,000x away, well under the line."""
        sc = _sc("Auto loan rates peaked at 8.1 percent. On a 50 thousand "
                 "dollar car that's about 10,700 in interest.",
                 [5.2, 8.1], unit="percent")
        v = eg.beat_numbers_are_on_screen(sc)
        self.assertTrue(v["ok"], v["reasons"])
        self.assertTrue(v["notes"], "the miss was not reported at all")

    def test_a_beat_that_says_its_own_number_passes_clean(self):
        sc = _sc("Adoption reached 92 percent by 2023.",
                 [6.0, 33.0, 92.0], unit="percent")
        v = eg.beat_numbers_are_on_screen(sc)
        self.assertTrue(v["ok"])
        self.assertEqual(v["notes"], [])

    def test_a_derived_number_still_passes(self):
        """A difference is derivable and the picture supports it."""
        sc = _sc("The gap is 86 points.", [6.0, 92.0], unit="percent")
        self.assertTrue(eg.beat_numbers_are_on_screen(sc)["ok"])

    def test_it_reaches_the_pre_render_verdict(self):
        sc = _sc("About 117 billion people have ever been born.",
                 [1200.0, 1400.0])
        sc.update(title="How Many People Have Ever Lived?",
                  hook="117 billion people have been born.")
        v = eg.pre_render_verdict(sc, use_llm=False)
        self.assertFalse(v["ok"])
        self.assertFalse(v["beats_ok"])


class ItNeverAccusesAStoryItCannotJudge(unittest.TestCase):
    def test_no_dataset_no_accusation(self):
        self.assertTrue(
            eg.beat_numbers_are_on_screen({"segments": [{"key": "nope"}]})["ok"])

    def test_no_say_line_no_accusation(self):
        sc = _sc("", [1.0, 2.0])
        self.assertTrue(eg.beat_numbers_are_on_screen(sc)["ok"])

    def test_a_say_with_no_numbers_at_all_passes(self):
        sc = _sc("This kept happening, year after year.", [1.0, 2.0])
        self.assertTrue(eg.beat_numbers_are_on_screen(sc)["ok"])


class TheThresholdIsNamedOnce(unittest.TestCase):
    def test_the_line_is_a_constant_not_a_literal(self):
        self.assertIsInstance(eg.WILD_NUMBER, float)
        self.assertGreaterEqual(eg.WILD_NUMBER, 100.0)


if __name__ == "__main__":
    unittest.main()
