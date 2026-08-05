"""The graph-race DATA DRAMA gate — the thing that decides whether a chart
is worth thirteen seconds of somebody's attention.

Written on 2026-08-05 after four of that day's charts were rendered and
measured against the showrunner's motion floor. Two facts came out of it and
both are encoded here:

1.  **Swing predicts watchability.** 171x -> 13.7 effective fps (pass);
    4.2x -> 13.1 fps at duplicate-ratio 0.453 against a 0.45 ceiling
    (marginal); 3.3x -> 6.6 fps (half the floor). No renderer work fixes a
    3.3x swing spread over seven points — the fault is in the data.

2.  **A flat reference line is not a competitor.** The cocoa spec paired a
    moving price against a constant "2018-2022 average". The price crossed
    that constant twice, `crossovers` read 2, the spec was handed the
    lenient CROSSOVER_SWING bar, and a chart that measured 6.6 fps sailed
    through a gate designed to catch exactly it.

The gate is only allowed to get stronger. These tests exist so a future
change that loosens it has to say so out loud.

    python -m unittest tests.test_chart_race -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engines import chart_race as cr                    # noqa: E402


def spec(series, years=None, **kw):
    years = years or list(range(2018, 2018 + len(series[0][1])))
    return dict({
        "title": "t", "y_label": kw.pop("y_label", "things"),
        "years": years,
        "series": [{"name": n, "color": "#fff", "values": v}
                   for n, v in series],
    }, **kw)


class TestTheSwingFloor(unittest.TestCase):
    def test_a_big_mover_passes(self):
        v = spec([("a", [100, 900, 4000, 17000]), ("b", [90, 200, 300, 500])])
        self.assertTrue(cr.assess(v)["ok"])

    def test_a_flat_pair_is_refused(self):
        v = spec([("a", [1000, 1100, 1200, 1300]),
                  ("b", [900, 950, 1000, 1050])])
        got = cr.assess(v)
        self.assertFalse(got["ok"])
        self.assertIn("barely move", got["reasons"][0])

    def test_the_floor_is_five_and_moving_it_down_is_a_deliberate_act(self):
        """Raised 3.0 -> 5.0 from measurement: a 4.2x swing rendered AT the
        showrunner's duplicate-ratio ceiling. Lowering it again is allowed —
        but it has to be a code change somebody signs, not a drift."""
        self.assertGreaterEqual(cr.MIN_SWING, 5.0)

    def test_the_measured_boundary_cases_land_where_measurement_said(self):
        # cocoa: 3.3x -> 6.6 effective fps. dow: 4.2x -> at the ceiling.
        for swing_x in (3.3, 4.2):
            v = spec([("a", [1000, 1000 * swing_x, 1000 * swing_x, 1000]),
                      ("b", [800, 820, 810, 830])])
            self.assertFalse(cr.assess(v)["ok"],
                             f"a {swing_x}x swing measured under the "
                             f"showrunner's motion floor — it must not pass")

    def test_a_collapse_is_as_dramatic_as_a_climb(self):
        v = spec([("a", [20000, 8000, 900, 100]), ("b", [500, 500, 480, 470])])
        self.assertTrue(cr.assess(v)["ok"])


class TestAFlatLineCannotRace(unittest.TestCase):
    """The loophole that let cocoa through, and the fix."""

    def test_crossing_a_constant_baseline_is_not_a_lead_change(self):
        v = spec([("cocoa price", [2000, 2600, 3200, 2100, 2500, 2900]),
                  ("2018-2022 average", [2423] * 6)])
        got = cr.assess(v)
        self.assertEqual(got["crossovers"], 0,
                         "a constant reference line cannot take the lead")
        self.assertFalse(got["ok"])
        self.assertIn("scenery", got["reasons"][0],
                      "the refusal must say WHY the crossings didn't count, "
                      "or the next author retries the same shape")

    def test_two_real_competitors_still_get_the_lenient_bar(self):
        """The lenient bar is not being removed — two things genuinely
        trading the lead IS dramatic even at a small swing."""
        v = spec([("a", [100, 300, 200, 400, 250]),
                  ("b", [200, 150, 350, 180, 380])])
        got = cr.assess(v)
        self.assertGreater(got["crossovers"], 0)
        self.assertLess(got["swing"], cr.MIN_SWING)
        self.assertTrue(got["ok"], "real lead changes still earn "
                                   "CROSSOVER_SWING")

    def test_a_nearly_flat_line_counts_as_flat(self):
        # 1% drift over the whole run is a reference line with rounding.
        self.assertTrue(cr.is_reference_line([1000, 1005, 1002, 1008]))
        self.assertFalse(cr.is_reference_line([1000, 1100, 1002, 1008]))

    def test_degenerate_series_are_reference_lines(self):
        for vals in ([], None, [0, 0, 0], [-5, -5]):
            self.assertTrue(cr.is_reference_line(vals), vals)


class TestUnitsAreNormalizedFirst(unittest.TestCase):
    """The magnitude floor judges what is ON SCREEN, so an author writing
    11.5 with y_label 'EVs sold (millions)' must not be punished."""

    def test_the_parenthetical_unit_is_applied_and_stripped(self):
        v = spec([("a", [1.0, 6.0, 40.0]), ("b", [0.9, 1.0, 1.2])],
                 y_label="EVs sold (millions)")
        got = cr.assess(v)
        self.assertTrue(got["ok"], got["reasons"])
        self.assertEqual(cr.normalize(v)["y_label"], "EVs sold")

    def test_normalize_is_idempotent(self):
        v = spec([("a", [1.0, 6.0, 40.0]), ("b", [0.9, 1.0, 1.2])],
                 y_label="EVs sold (millions)")
        once = cr.normalize(v)
        self.assertEqual(cr.normalize(once)["series"][0]["values"],
                         once["series"][0]["values"])

    def test_a_percentage_is_exempt_from_the_magnitude_floor(self):
        v = spec([("a", [2.0, 30.0, 71.0]), ("b", [1.0, 2.0, 3.0])],
                 y_label="share of households (%)")
        self.assertNotIn("too small",
                         " ".join(cr.assess(v)["reasons"]))


class TestTheShapeOfARace(unittest.TestCase):
    def test_one_line_is_not_a_race(self):
        v = spec([("a", [100, 5000, 90000])])
        got = cr.assess(v)
        self.assertFalse(got["ok"])
        self.assertIn("at least", " ".join(got["reasons"]))

    def test_an_empty_spec_is_refused_not_crashed(self):
        self.assertFalse(cr.assess({})["ok"])
        self.assertFalse(cr.assess({"years": [], "series": []})["ok"])

    def test_a_series_touching_zero_reports_the_cap_not_infinity(self):
        v = spec([("a", [0, 100, 5000]), ("b", [10, 20, 30])])
        got = cr.assess(v)
        self.assertLessEqual(got["swing"], cr.SWING_CAP)
        self.assertTrue(got["ok"])


class TestTheOnScreenCredit(unittest.TestCase):
    """Provenance is not being dropped — it moves to the description, where
    it is legible and copyable. On screen it must be ONE short line."""

    def test_a_long_provenance_blob_becomes_one_short_line(self):
        got = cr.credit_line(
            "Sources: NOAA National Centers for Environmental Information "
            "(NCEI), U.S. Billion-Dollar Weather and Climate Disasters, "
            "CPI-adjusted, accessed 2026-08-05")
        self.assertTrue(got.startswith("Source: NOAA"))
        self.assertLessEqual(len(got), len("Source: ") + cr.CREDIT_MAX_CHARS)
        self.assertNotIn("\n", got)

    def test_the_publisher_survives_the_squeeze(self):
        got = cr.credit_line("U.S. Fish & Wildlife Service bald eagle "
                             "population surveys; nesting-pair counts")
        self.assertIn("Fish & Wildlife", got)

    def test_a_short_source_is_left_alone(self):
        self.assertEqual(cr.credit_line("Sources: World Bank WDI"),
                         "Source: World Bank WDI")

    def test_no_source_draws_nothing(self):
        for empty in ("", None, "   ", "Sources:"):
            self.assertEqual(cr.credit_line(empty), "")

    def test_the_full_source_still_reaches_the_description(self):
        """The credit is a DISPLAY squeeze. If the description ever stopped
        carrying the full string this would be an attribution loss, so the
        two are asserted together."""
        sys.path.append(str(ROOT / "scripts"))
        import run_trending_daily as rtd
        full = ("Sources: NOAA NCEI, U.S. Billion-Dollar Weather and "
                "Climate Disasters, CPI-adjusted")
        desc = rtd._description({"title": "t", "format": "graph_race",
                                 "source": full, "series": [], "years": []})
        self.assertIn(full, desc)


class TestTheTimelineNeverFreezes(unittest.TestCase):
    """A chart that has not moved by second three has been scrolled past.
    The old smoothstep had slope zero at both ends and put three of four
    charts under the motion floor."""

    def test_the_opening_moves_immediately(self):
        # In the first 10% of the timeline the data must advance ~10%, not
        # the 2.8% a smoothstep gave.
        self.assertGreater(cr._race_ease(0.10), 0.08)

    def test_the_ease_is_monotonic_and_spans_the_full_range(self):
        pts = [cr._race_ease(i / 40) for i in range(41)]
        self.assertEqual(pts, sorted(pts))
        self.assertAlmostEqual(pts[0], 0.0)
        self.assertAlmostEqual(pts[-1], 1.0)

    def test_no_stretch_of_the_timeline_stalls(self):
        """Any 1/20th of the run must advance the data by at least half of
        an even share. This is the property the smoothstep violated."""
        step = 1 / 20
        for i in range(20):
            adv = cr._race_ease((i + 1) * step) - cr._race_ease(i * step)
            self.assertGreater(adv, step * 0.5,
                               f"the timeline stalls between "
                               f"{i * step:.2f} and {(i + 1) * step:.2f}")


class TestTodaysRealPackagesAreJudgedCorrectly(unittest.TestCase):
    """Regression against the actual specs that motivated the change. Skips
    cleanly once the day's packages age out of the repo."""

    DAY = ROOT / "state" / "trending_packages" / "20260805"

    def _load(self, name):
        import json
        p = self.DAY / name
        if not p.exists():
            self.skipTest(f"{name} no longer in the repo")
        return json.loads(p.read_text())

    def test_the_bald_eagle_chart_passes(self):
        got = cr.assess(self._load("02_graph-bald-eagle-comeback.json"))
        self.assertTrue(got["ok"], got["reasons"])

    def test_the_cocoa_chart_is_refused(self):
        got = cr.assess(self._load("03_graph-cocoa-price-spike.json"))
        self.assertFalse(got["ok"],
                         "cocoa measured 6.6 effective fps against a floor "
                         "of 11 — it must never render again")
        self.assertEqual(got["crossovers"], 0)

    def test_the_dow_chart_is_refused(self):
        got = cr.assess(self._load("04_graph-dow-record-climb.json"))
        self.assertFalse(got["ok"])


if __name__ == "__main__":
    unittest.main()
