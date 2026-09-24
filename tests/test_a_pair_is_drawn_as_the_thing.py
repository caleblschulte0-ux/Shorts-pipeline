"""A cut and a multiple are drawn as the SUBJECT, not as two numbers.

The judge on coffee-price-record, 2026-09-24: "the 11M-bag drought hole, the
core shock of the story, is never shown; the seesaw barely tilts", and "show
'more than double' physically". `hole_scene` and `copies_scene` answer both —
and refuse everything they are not about, which is what these tests hold.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import studio_render as sr     # noqa: E402
from data_learning import viz_scene as vs         # noqa: E402
from tests._machine_samples import mk             # noqa: E402

CUT = "why coffee supply keeps shrinking"
DOUBLE = "how much coffee prices have doubled"


class TheCutIsAHole(unittest.TestCase):
    def test_the_coffee_cut_draws(self):
        ins = mk([("September Estimate", 45.4), ("Revised Estimate", 34.4)],
                 "million", topic=CUT)
        self.assertTrue(vs.hole_scene(ins))
        self.assertAlmostEqual(vs.hole_fraction(ins), 11.0 / 45.4, 6)

    def test_it_leads_the_pair_in_the_router(self):
        ins = mk([("September Estimate", 45.4), ("Revised Estimate", 34.4)],
                 "million", topic=CUT)
        self.assertEqual(sr._machines_for(ins)[0], "hole_scene")

    def test_two_categories_are_not_a_before_and_after(self):
        """Measured on the live catalogue: 'fossil vs clean power' matched
        the cut words and was handed a cup with a bite out of it."""
        ins = mk([("Fossil fuels", 59.1), ("Clean power", 40.9)],
                 "percent", topic="fossil power share is falling")
        self.assertFalse(vs.hole_scene(ins))
        self.assertNotIn("hole_scene", sr._machines_for(ins))

    def test_a_rise_is_not_a_cut(self):
        ins = mk([("2019", 10.0), ("2024", 14.0)], "million",
                 topic="coffee supply dropped")
        self.assertFalse(vs.hole_scene(ins))

    def test_the_words_have_to_say_cut(self):
        ins = mk([("2019", 45.0), ("2024", 34.0)], "million",
                 topic="coffee harvest by year")
        self.assertFalse(vs.hole_scene(ins))

    def test_a_projection_is_never_drawn_as_a_fact(self):
        ins = mk([("2024", 45.0), ("2040 (projected)", 30.0)], "million",
                 topic="coffee supply will shrink")
        self.assertFalse(vs.hole_scene(ins))
        future = mk([("2024", 45.0), ("2090", 30.0)], "million",
                    topic="coffee supply will shrink")
        self.assertFalse(vs.hole_scene(future))


class TheMultipleIsCopies(unittest.TestCase):
    def test_the_coffee_doubling_draws_whichever_order_the_source_gave(self):
        for pairs in ([("February 2024", 2.0), ("February 2025", 4.41)],
                      [("February 2025", 4.41), ("February 2024", 2.0)]):
            ins = mk(pairs, "usd", topic=DOUBLE)
            self.assertTrue(vs.copies_scene(ins), pairs)
            self.assertAlmostEqual(vs.copies_ratio(ins), 4.41 / 2.0, 6)

    def test_a_ratio_you_cannot_count_is_refused(self):
        big = mk([("2000", 1.0), ("2024", 40.0)], "usd",
                 topic="coffee prices are forty times higher")
        self.assertFalse(vs.copies_scene(big))
        small = mk([("2000", 1.0), ("2024", 1.2)], "usd",
                   topic="coffee prices doubled")
        self.assertFalse(vs.copies_scene(small))

    def test_a_fall_is_not_a_multiple(self):
        ins = mk([("2019", 4.0), ("2024", 2.0)], "usd",
                 topic="coffee prices halved, not doubled")
        self.assertFalse(vs.copies_scene(ins))


class NeitherIsAFieldOfIcons(unittest.TestCase):
    """Operator, 2026-09-22: a crowd of one thing is used very sparingly.
    The hole is ONE object; the copies are at most five."""

    def test_the_copies_are_capped(self):
        self.assertLessEqual(vs.COPIES_MAX, 5.0)

    def test_neither_counts_against_the_repeated_icon_budget(self):
        self.assertFalse(sr.is_repeated_icon("hole_scene"))
        self.assertFalse(sr.is_repeated_icon("copies_scene"))


if __name__ == "__main__":
    unittest.main()
