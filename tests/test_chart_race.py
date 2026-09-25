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


class TestAssessRefusesUnjudgeableData(unittest.TestCase):
    """Doctor d64b063a21bd: string values used to CRASH assess with a
    TypeError, and the structural gate's blanket except read every crash as
    'engine absent' and passed the package. assess now refuses garbage with
    named reasons — a refusal, never a raise."""

    def test_string_values_are_refused_not_crashed(self):
        v = spec([("a", ["1", "2", "3", "4"]), ("b", ["4", "3", "2", "1"])])
        got = cr.assess(v)
        self.assertFalse(got["ok"])
        self.assertTrue(any("finite" in r for r in got["reasons"]),
                        got["reasons"])

    def test_nan_and_inf_are_refused(self):
        for poison in (float("nan"), float("inf")):
            v = spec([("a", [100, poison, 4000, 17000]),
                      ("b", [90, 200, 300, 500])])
            got = cr.assess(v)
            self.assertFalse(got["ok"], poison)
            self.assertTrue(any("finite" in r for r in got["reasons"]))

    def test_string_years_are_refused(self):
        v = spec([("a", [100, 900, 4000, 17000]),
                  ("b", [90, 200, 300, 500])],
                 years=["2018", "2019", "2020", "2021"])
        self.assertFalse(cr.assess(v)["ok"])

    def test_unsorted_years_are_refused(self):
        v = spec([("a", [100, 900, 4000, 17000]),
                  ("b", [90, 200, 300, 500])],
                 years=[2018, 2020, 2019, 2021])
        got = cr.assess(v)
        self.assertFalse(got["ok"])
        self.assertTrue(any("increasing" in r for r in got["reasons"]))

    def test_length_mismatch_is_refused_not_crashed(self):
        v = spec([("a", [100, 900, 4000]),           # 3 values, 4 years
                  ("b", [90, 200, 300, 500])],
                 years=[2018, 2019, 2020, 2021])
        got = cr.assess(v)
        self.assertFalse(got["ok"])
        self.assertTrue(any("values for" in r for r in got["reasons"]))

    def test_bools_are_not_data(self):
        v = spec([("a", [True, True, False, True]),
                  ("b", [90, 200, 300, 500])])
        self.assertFalse(cr.assess(v)["ok"])

    def test_clean_numeric_data_is_untouched_by_the_new_checks(self):
        v = spec([("a", [100, 900, 4000, 17000]), ("b", [90, 200, 300, 500])])
        self.assertTrue(cr.assess(v)["ok"])


class TheTipLabelClearsTheMarker(unittest.TestCase):
    """Without a logo the tip still carries a 16pt marker dot, and the label
    used to start 8pt from its centre — so a label flipped to the LEFT of
    the tip put its last glyph under the dot ("1276.8B" with the B behind
    the leader's marker, clean-energy race, 2026-09-22)."""

    def test_the_no_icon_offset_clears_the_dots_radius_and_edge(self):
        src = (ROOT / "engines" / "chart_race.py").read_text()
        i = src.index("iw = 0.0 if art is None")
        blk = src[i:i + 900]
        self.assertNotIn("off = 8 if art is None", blk)
        self.assertIn("_dot_r = (16 if rank == 0 else 13) / 2.0 + 1.4", blk)
        self.assertIn("off = (_dot_r + 8) if art is None", blk)


class TheHookCardIsReadableAndOffTheAxis(unittest.TestCase):
    """"the hook card 'Tesla Out-Valued Toyota' sits on top of the y-axis
    tick labels and the plot gridlines, then fades through a dark brown
    that is unreadable on the black ground" — auto-fail `unreadable`,
    2026-09-22. Full ink until a short cut; fitted to and centred on the
    axes box so it cannot reach the tick labels."""

    def test_full_ink_then_a_short_cut_not_a_long_fade(self):
        src = (ROOT / "engines" / "chart_race.py").read_text()
        i = src.index("if hook and f < HOOK_S * fps:")
        blk = src[i:i + 4000]
        self.assertNotIn("alpha = max(0.0, 1.0 - f / (HOOK_S * fps))", blk)
        self.assertIn("alpha = 1.0\n", blk)
        self.assertNotIn("_left / 0.25", blk)

    def test_it_is_fitted_to_and_centred_on_the_axes(self):
        src = (ROOT / "engines" / "chart_race.py").read_text()
        i = src.index("if hook and f < HOOK_S * fps:")
        blk = src[i:i + 4000]
        self.assertIn("_text_px(fig, hook, _hsize) > _bb.width * 0.86", blk)
        self.assertIn("_hx = (_bb.x0 + _bb.x1) / 2.0 / W", blk)
        self.assertIn("fig.text(_hx, _hy, hook", blk)


if __name__ == "__main__":
    unittest.main()


class TestTheOpeningIsNotAnEmptyFrame(unittest.TestCase):
    """Doctor d17724dfb1c0: the drama numbers are timeline-wide but the
    renderer's axes are not — full year span from frame one, y-camera
    floored at 12% of the global max. Two races were blocked on 2026-08-09
    for mostly-empty openings AFTER passing preflight. assess() now derives
    the opening's painted area and the leader's screen travel from the same
    axis math the renderer uses, and refuses before a slot is spent."""

    def test_a_hockey_stick_parked_at_zero_is_refused(self):
        # ten flat near-zero years, then the spike: peak and swing look
        # great, the first fifth of the video is an empty black plot.
        vals = [1, 1, 1, 1, 1, 1, 1, 1, 2, 5, 4000, 17000]
        v = spec([("a", vals), ("b", [1] * 10 + [300, 900])],
                 years=list(range(2010, 2022)))
        got = cr.assess(v)
        self.assertFalse(got["ok"])
        self.assertTrue(any("opening paints" in r for r in got["reasons"]),
                        got["reasons"])
        self.assertLess(got["open_area"], cr.OPEN_AREA_MIN)

    def test_a_race_already_moving_at_the_open_passes(self):
        v = spec([("a", [1500, 2400, 5200, 9000, 17000]),
                  ("b", [1400, 1800, 2500, 3200, 4200])],
                 years=[2018, 2019, 2020, 2021, 2022])
        got = cr.assess(v)
        self.assertTrue(got["ok"], got["reasons"])
        self.assertGreaterEqual(got["open_area"], cr.OPEN_AREA_MIN)

    def test_a_line_that_never_climbs_the_frame_is_refused(self):
        # crossovers grant the lenient 1.6x swing bar, but 60->100 against
        # a 100 camera is ~40% travel shared across wiggles — build one
        # that stays under the travel floor while keeping its crossover.
        v = spec([("a", [80, 84, 88, 86, 90]),
                  ("b", [82, 80, 86, 89, 88])],
                 years=[2018, 2019, 2020, 2021, 2022])
        got = cr.assess(v)
        self.assertFalse(got["ok"])
        self.assertTrue(any("screen travel" in r for r in got["reasons"]),
                        got["reasons"])

    def test_the_verdict_reports_both_measurements(self):
        v = spec([("a", [1500, 2400, 5200, 9000, 17000]),
                  ("b", [1400, 1800, 2500, 3200, 4200])])
        got = cr.assess(v)
        self.assertIn("open_area", got)
        self.assertIn("travel", got)


class ACrossoverRaceRunsShort(unittest.TestCase):
    """All three graph_races of 2026-09-25 were crossovers ('X passed Y')
    that passed on the lenient swing and were blocked at 7.9-10.5 effective
    fps over 13 seconds. Measured on the same specs at 7s: 14-20 fps."""

    def _spec(self, a, b):
        return {"title": "t", "y_label": "lbs", "duration": 13,
                "years": [1970, 1980, 1990, 2000, 2010, 2020, 2023],
                "series": [{"name": "Beef", "values": a},
                           {"name": "Chicken", "values": b}]}

    def test_a_crossover_on_a_small_swing_is_capped(self):
        from engines import chart_race as C
        s = self._spec([84, 72, 64, 64, 57, 55, 58], [27, 32, 42, 54, 58, 65, 68])
        self.assertEqual(C.race_duration(C.normalize(s)), C.CROSSOVER_MAX_S)

    def test_a_big_mover_keeps_its_authored_length(self):
        from engines import chart_race as C
        s = self._spec([80, 70, 60, 50, 40, 30, 20],
                       [5, 20, 60, 150, 300, 600, 900])
        self.assertEqual(C.race_duration(C.normalize(s)), 13.0)


class TheCreditIsNeverCutMidThought(unittest.TestCase):
    """"The source line is cut off with '...' in every frame" — all three
    graph races of 2026-09-25. Held against every real spec on record."""

    def _all_sources(self):
        import glob
        import json
        seen = set()
        for f in glob.glob(str(ROOT / "state" / "trending_packages" / "**" /
                               "*.json"), recursive=True):
            try:
                p = json.loads(Path(f).read_text())
            except Exception:  # noqa: BLE001
                continue
            if isinstance(p, dict) and p.get("format") == "graph_race" \
                    and p.get("source") and p["source"] not in seen:
                seen.add(p["source"])
                yield p["source"]

    def test_no_real_credit_ends_in_an_ellipsis_or_an_open_bracket(self):
        import re
        n = 0
        for src in self._all_sources():
            got = cr.credit_line(src)
            n += 1
            self.assertNotIn("…", got, src)
            self.assertNotIn("...", got, src)
            self.assertTrue(cr._balanced(got), got)
            self.assertFalse(re.search(r"[+/&,]$|'s$", got), got)
            self.assertLessEqual(len(got), len("Source: ") + cr.CREDIT_MAX_CHARS)
        self.assertGreater(n, 20)

    def test_the_chicken_credit_names_its_publisher(self):
        got = cr.credit_line(
            "US per-capita meat availability (boneless/retail-weight basis), "
            "USDA Economic Research Service Charts of Note and Food "
            "Availability data series: chicken's per-capita availability "
            "first passed beef's in 2010")
        self.assertIn("USDA Economic Research Service", got)
        self.assertNotIn("(", got)


class TheYearAxisKeepsOneStep(unittest.TestCase):
    """"The x-axis ticks rescale unevenly (1976/1984/1992/2000 at mid2, then
    decades), which looks jumpy" — c-sections, 2026-09-25."""

    def test_one_step_inside_the_data(self):
        t = cr.year_ticks([1970, 1980, 1990, 2000, 2010, 2020, 2023])
        self.assertEqual(t, [1970, 1980, 1990, 2000, 2010, 2020])
        t = cr.year_ticks([1999, 2007, 2012, 2021, 2024])
        self.assertEqual(len({b - a for a, b in zip(t, t[1:])}), 1)
        self.assertLessEqual(t[-1], 2024)
        self.assertLessEqual(len(t), 6)

    def test_the_renderer_no_longer_rechooses_it_per_frame(self):
        src = (ROOT / "engines" / "chart_race.py").read_text()
        self.assertNotIn("MaxNLocator(", src)
        self.assertIn("FixedLocator(ticks)", src)


class ThePassIsMarked(unittest.TestCase):
    YEARS = [1970, 1980, 1990, 2000, 2010, 2020, 2023]

    def test_the_chicken_pass_is_found_between_its_samples(self):
        got = cr.lead_change(self.YEARS, [
            {"name": "Beef", "values": [84, 72, 64, 64, 57, 55, 58]},
            {"name": "Chicken", "values": [27, 32, 42, 54, 58, 65, 68]}])
        self.assertEqual((got["leader"], got["passed"]), ("Chicken", "Beef"))
        self.assertTrue(2000 < got["x"] < 2010)

    def test_a_leader_that_never_trailed_gets_no_invented_pass(self):
        self.assertIsNone(cr.lead_change(self.YEARS, [
            {"name": "A", "values": [90, 91, 92, 93, 94, 95, 96]},
            {"name": "B", "values": [10, 20, 30, 40, 50, 60, 70]}]))

    def test_the_last_pass_is_the_one_marked(self):
        got = cr.lead_change([1, 2, 3, 4, 5], [
            {"name": "A", "values": [1, 5, 1, 1, 9]},
            {"name": "B", "values": [3, 3, 3, 3, 3]}])
        self.assertTrue(4 < got["x"] < 5)

    def test_the_caption_agrees_with_its_subject(self):
        self.assertEqual(cr.pass_caption("Chicken", "Beef"),
                         "Chicken passes Beef")
        self.assertEqual(cr.pass_caption("C-Sections", "Vaginal Births"),
                         "C-Sections pass Vaginal Births")


class TheYearTravels(unittest.TestCase):
    """The x camera follows the pen, so the tip is still on screen; on a slow
    stretch the year's last digit was the only thing moving and the
    c-sections race measured 0.425 duplicate frames (ceiling 0.45). With the
    year riding a track: 0.14 on all three 2026-09-25 specs."""

    def test_the_counter_is_placed_by_progress(self):
        import ast
        src = (ROOT / "engines" / "chart_race.py").read_text()
        tree = ast.parse(src)
        self.assertLess(cr.YEAR_TRACK[0], cr.YEAR_TRACK[1])
        placed = [n for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "text"
                  and n.args and isinstance(n.args[0], ast.Name)
                  and n.args[0].id == "yx"]
        self.assertTrue(placed, "the year counter must be drawn at `yx`")
