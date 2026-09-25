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


class ThePictureOfTheThingOpensTheBeat(unittest.TestCase):
    """Coffee, 2026-09-25: "the middle falls back to bar and bubble charts
    with Data perched" — the copies scene was there, half a beat late."""

    def test_a_chart_beat_opens_on_the_claim_led_machine(self):
        ins = mk([("February 2024", 2.0), ("February 2025", 4.41)], "usd",
                 topic=DOUBLE)
        ins.kind = "bubbles"
        seq = sr._depiction_sequence(ins, set(), 13.0)
        self.assertEqual(seq[0], "copies_scene")

    def test_an_icon_grid_gives_way_and_is_not_kept(self):
        ins = mk([("September Estimate", 45.4), ("Revised Estimate", 34.4)],
                 "million", topic=CUT)
        ins.kind = "scene"
        ins.scene = {"title": True, "elements": [
            {"type": "unit_figures", "region": "full", "subject": CUT}]}
        seq = sr._depiction_sequence(ins, set(), 13.0)
        self.assertEqual(seq[0], "hole_scene")
        self.assertNotIn("scene", seq)

    def test_a_used_machine_does_not_lead_twice(self):
        ins = mk([("February 2024", 2.0), ("February 2025", 4.41)], "usd",
                 topic=DOUBLE)
        ins.kind = "bubbles"
        seq = sr._depiction_sequence(ins, {"copies_scene"}, 13.0)
        self.assertEqual(seq[0], "bubbles")


class TheSameWordsAtTwoDatesAreAThenAndNow(unittest.TestCase):
    """"February 2024" vs "February 2025" came back `duel` — two things on
    a set of scales — because the date test only knew a bare year."""

    def test_a_month_or_quarter_at_two_years_is_dated(self):
        from data_learning import relationships as rel
        self.assertTrue(rel._dated_pair(["February 2024", "February 2025"]))
        self.assertTrue(rel._dated_pair(["Q3 2023", "Q3 2024"]))
        self.assertTrue(rel._dated_pair(["2019", "2025"]))

    def test_two_places_in_one_year_are_not(self):
        from data_learning import relationships as rel
        self.assertFalse(rel._dated_pair(["Brazil 2025", "Vietnam 2025"]))
        self.assertFalse(rel._dated_pair(["September Estimate",
                                          "Revised Estimate"]))
        self.assertFalse(rel._dated_pair(["2013-2022 avg", "1983-1992 avg"]))


class AfterThePictureOfTheThingNoGenericRestatement(unittest.TestCase):
    def test_tiles_do_not_follow_the_copies(self):
        ins = mk([("February 2024", 2.0), ("February 2025", 4.41)], "usd",
                 topic=DOUBLE)
        ins.kind = "bubbles"
        seq = sr._depiction_sequence(ins, set(), 13.0)
        self.assertEqual(seq[0], "copies_scene")
        self.assertNotIn("nest_scene", seq)
        self.assertNotIn("units_scene", seq)


class TheIconMustDepictTheSubject(unittest.TestCase):
    """'California's kelp forests' maps to a land tree — the junk_imagery
    CLAUDE.md names. The machines that draw WITH the subject ask the brain
    first, once per subject."""

    def setUp(self):
        vs._ICON_OK.clear()

    def tearDown(self):
        vs._ICON_OK.clear()

    def test_a_wrong_icon_is_not_drawn(self):
        from unittest import mock
        from shared import shot_relevance as R
        ins = mk([("Pre-2014 canopy", 100), ("Canopy now", 4)], "percent",
                 topic="California's kelp forests disappear")
        with mock.patch.object(R, "enabled", lambda: True), \
                mock.patch.object(R, "judge_panels",
                                  lambda *a, **k: {0: {"depicts": False,
                                                       "why": "a land tree"}}):
            self.assertIsNone(vs._subject_glyph(ins))
            self.assertFalse(vs.hole_scene(ins))

    def test_no_brain_keeps_the_icon(self):
        from unittest import mock
        from shared import shot_relevance as R
        with mock.patch.object(R, "enabled", lambda: False):
            self.assertTrue(vs.icon_depicts("coffee"))


class ACollapseIsACut(unittest.TestCase):
    def test_ninety_nine_percent_gone_is_drawn(self):
        ins = mk([("Before 2013", 100.0), ("After the outbreak", 1.0)],
                 "percent", topic="sea stars wiped out by disease")
        self.assertAlmostEqual(vs.hole_fraction(ins), 0.99, 6)
        self.assertLessEqual(vs.HOLE_MIN, 0.99)
        self.assertLessEqual(0.99, vs.HOLE_MAX)

    def test_since_and_before_read_as_now_and_then(self):
        ins = mk([("Since 2014", 10100.0), ("Before 2014", 100.0)], "count")
        then, now = vs._then_now(ins)
        self.assertEqual((then.label, now.label), ("Before 2014", "Since 2014"))


class AMonthAndAYearIsAPointInTime(unittest.TestCase):
    """Waymo's weekly rides, 'Oct 2023 / Aug 2024 / Feb 2025', came back
    `dominance` and were drawn as a skyline (2026-09-25)."""

    def test_month_quarter_and_season_dates_are_a_series(self):
        from data_learning import relationships as rel
        for labels in (["Oct 2023", "Aug 2024", "Feb 2025"],
                       ["Q1 2020", "Q2 2020", "Q3 2020"],
                       ["Summer 2019", "Summer 2021", "Summer 2023"]):
            ins = mk([(l, float(k + 1) * 10) for k, l in enumerate(labels)])
            self.assertTrue(rel.is_time_series(ins), labels)

    def test_places_are_still_not(self):
        from data_learning import relationships as rel
        ins = mk([("Tokyo", 37.4), ("Delhi", 9.2), ("Cairo", 7.8)])
        self.assertFalse(rel.is_time_series(ins))


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
