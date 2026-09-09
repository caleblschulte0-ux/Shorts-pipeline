"""TWELVE MOON LANDINGS AT HALF A MOON LANDING EACH.

    "seg2:start uses red car pictograms for the count of crewed Moon
     landings, with 12 icons at 'each = 0.5' — mismatched imagery and an
     arithmetic legend"       fifty-years-since-moon-landing, 2026-09-09

`draw_unit_figures` says what it is for in its own first line: *"an ISOTYPE:
N copies of one thing, where COUNTING THEM IS THE NUMBER."* `unit_plan`
chooses how many copies and what each is worth, and it did not have that rule.

It scores candidate units by how close the resulting count lands to 18 — a
good heuristic, enough to read as "a lot" and few enough to actually count.
For 12 the scores tie exactly:

    each = 0.5  ->  24 icons   |24 - 18| = 6
    each = 1    ->  12 icons   |12 - 18| = 6

and `score < best[0]` keeps whichever was found FIRST, which is the smaller
step. So the channel shipped twelve moons at half a Moon landing each.

A unit below 1 on a countable quantity is not an isotype at all: it asks the
viewer to count half-things and then multiply. Two rules now: one icon is one
thing whenever the number allows it, and a whole quantity never takes a
fractional unit. A genuinely fractional one (2.4 tonnes, 0.8 hectares) still
may.

Runs standalone:  python3 tests/test_one_icon_one_thing.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning.viz_scene import unit_plan   # noqa: E402


class TheNamedCase(unittest.TestCase):
    def test_twelve_moon_landings_are_twelve_icons(self):
        self.assertEqual(unit_plan(12, 1.0), (12, 1.0))

    def test_the_legend_would_read_each_equals_one(self):
        _n, per = unit_plan(12, 1.0)
        self.assertEqual(per, 1.0)


class AWholeThingNeverTakesAFractionalUnit(unittest.TestCase):
    def test_no_integer_value_gets_a_unit_below_one(self):
        bad = {}
        for v in range(1, 400):
            n, per = unit_plan(v, 1.0)
            if per < 1.0:
                bad[v] = per
        self.assertEqual(bad, {}, f"fractional units on whole counts: {bad}")

    def test_a_genuinely_fractional_quantity_still_may(self):
        """2.4 tonnes is not a count, and forcing it to whole units would
        draw two icons for it."""
        _n, per = unit_plan(2.4, 1.0)
        self.assertLess(per, 1.0)

    def test_one_icon_one_thing_across_the_readable_band(self):
        for v in (6, 7, 9, 12, 24, 40, 60):
            n, per = unit_plan(v, 1.0)
            self.assertEqual((n, per), (v, 1.0), v)


class ItIsStillAREADABLEPicture(unittest.TestCase):
    """The count heuristic is why this function exists; the honesty rule must
    not turn a big number into wallpaper."""

    CAP = 60

    def test_no_value_ever_draws_more_than_the_cap(self):
        for v in (61, 100, 417, 1400, 71467, 3_000_000):
            n, _per = unit_plan(v, 1.0)
            self.assertLessEqual(n, self.CAP, v)

    def test_a_big_number_still_gets_a_round_unit(self):
        for v in (100, 417, 1400, 71467):
            _n, per = unit_plan(v, 1.0)
            mant = per
            while mant >= 10:
                mant /= 10.0
            while mant < 1:
                mant *= 10.0
            self.assertIn(round(mant, 6), (1.0, 2.0, 5.0), f"{v} -> {per}")

    def test_the_picture_still_says_the_number(self):
        """Rounding to the nearest unit is inherent to an isotype, and the
        legend states the unit — but it may never be off by more than half
        of one icon."""
        for v in (6, 12, 61, 100, 417, 1400, 71467, 2.4, 0.8):
            n, per = unit_plan(v, 1.0)
            self.assertLessEqual(abs(n * per - v), per * 0.5 + 1e-9, v)

    def test_a_tie_takes_the_BIGGER_unit(self):
        """Fewer icons, each worth something rounder — and it is the tie-break
        that was wrong in the first place."""
        n, per = unit_plan(12, 1.0)
        self.assertEqual(n, 12)
        self.assertEqual(per, 1.0)


class ItNeverReturnsNonsense(unittest.TestCase):
    def test_zero_and_negatives_do_not_explode(self):
        for v in (0, -12, -0.5):
            n, per = unit_plan(v, 1.0)
            self.assertGreaterEqual(n, 1)
            self.assertGreater(per, 0)

    def test_an_authored_per_value_of_zero_is_survivable(self):
        n, per = unit_plan(24, 0)
        self.assertGreaterEqual(n, 1)
        self.assertGreater(per, 0)


if __name__ == "__main__":
    unittest.main()
