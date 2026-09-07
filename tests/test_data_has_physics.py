"""Pick the picture from what the data is SAYING, not from a chart name.

Operator direction, 2026-09-07:

    Speed becomes motion. Imbalance becomes weight. Progress becomes distance.
    Capacity becomes fill. Rank becomes position. A gap becomes literal space.
    ... data has physics.

The channel used to pick its visual from the chart KIND — a `rank` insight got
bars, a `trend` got a line. That is a rendering decision dressed as an
editorial one, and it is why every video looked like the last: few kinds, few
pictures. The router asks the editorial question first, and a chart is now the
FALLBACK rather than the default.

Two things these tests exist to protect, because both are easy to lose:

  * THE HONESTY. A relationship is a CLAIM, drawn at 200pt. `growth` says this
    rose and the rise is the point; `share` says these are parts of one whole —
    the claim that already shipped once as "2019 IS 9% OF THE WHOLE" over a
    mortgage rate. Every classifier must refuse when unsure, and OTHER (draw a
    chart) is always an acceptable answer.
  * THE PRIORITY. The anti-template rotation and the relationship ranking pull
    against each other. Rotating one flat list put a chart ahead of the machine
    that actually said the thing — the philosophy inverted by a line of variety
    code. They are separate tiers now and must stay that way.

Runs with pytest OR standalone:
    python3 tests/test_data_has_physics.py
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

from data_learning import relationships as rel  # noqa: E402
from data_learning import studio_render as sr  # noqa: E402
from data_learning import viz_scene as vs  # noqa: E402


class _Pt:
    def __init__(self, label, value):
        self.label, self.value = label, value


class _Ins:
    def __init__(self, items, unit="", topic="", main="", kind="bars"):
        self.items, self.unit, self.topic = items, unit, topic
        self.main_insight, self.kind = main, kind
        self.highlight_label = items[0].label if items else ""
        self.baseline = None


def _series(vals, unit="count", topic="output", main="It moved"):
    return _Ins([_Pt(str(2010 + i), v) for i, v in enumerate(vals)],
                unit, topic, main, kind="trend")


def _things(pairs, unit="years", topic="cost", main="A tops"):
    return _Ins([_Pt(n, v) for n, v in pairs], unit, topic, main)


class ItReadsWhatTheDataSays(unittest.TestCase):
    def test_a_climbing_series_is_growth(self):
        self.assertEqual(rel.classify(_series([10, 14, 19, 25, 33, 41])),
                         rel.GROWTH)

    def test_a_falling_series_is_decline(self):
        self.assertEqual(rel.classify(_series([90, 80, 70, 61, 50, 41])),
                         rel.DECLINE)

    def test_money_going_up_is_a_burden_not_just_growth(self):
        """The reading a viewer FEELS. A cost that doubled is not a nice climb
        — it is weight, and it gets drawn as weight."""
        self.assertEqual(
            rel.classify(_series([270, 300, 360, 410, 428, 449],
                                 "thousand dollars", "home prices",
                                 "The cost of a house")),
            rel.BURDEN)

    def test_a_real_zigzag_is_volatile_even_when_it_ends_higher(self):
        """THE ONE THAT MATTERS MOST HERE. Without the reversal test, a series
        that wandered up and down and happened to finish high would be drawn as
        a clean climb — a picture of a story the data does not tell."""
        self.assertEqual(rel.classify(_series([10, 90, 20, 85, 15, 80])),
                         rel.VOLATILE)

    def test_a_dip_on_the_way_up_is_still_growth(self):
        """Real mortgage rates: 3.9 down to 2.96, then up to 6.8. An earlier
        version called this volatile, because it counted every wobble as a
        direction change — including two moves worth a rounding error. It
        roughly doubled, and a viewer shown a rising tower is not misled."""
        self.assertEqual(
            rel.classify(_series([3.9, 3.1, 2.96, 5.34, 6.81, 6.72, 6.6, 6.8])),
            rel.GROWTH)

    def test_a_flat_series_claims_nothing(self):
        self.assertEqual(rel.classify(_series([50, 50.2, 50.1, 50.3, 50.2])),
                         rel.OTHER)

    def test_two_things_are_a_duel(self):
        self.assertEqual(rel.classify(_things([("2019", 270), ("2026", 449)])),
                         rel.DUEL)

    def test_a_handful_of_named_things_is_a_rank(self):
        self.assertEqual(
            rel.classify(_things([("A", 11.3), ("B", 9.7), ("C", 8.2),
                                  ("D", 6.8), ("E", 5.4)])),
            rel.RANK)

    def test_one_thing_dwarfing_the_rest_is_its_own_story(self):
        """A race where one runner is a mile ahead reads as a broken chart; a
        skyscraper among houses reads as the point."""
        self.assertEqual(
            rel.classify(_things([("A", 900), ("B", 40), ("C", 30), ("D", 25)])),
            rel.DOMINANCE)

    def test_a_share_needs_the_claim_to_say_so(self):
        parts = [("yes", 24.5), ("no", 40.0), ("maybe", 35.5)]
        self.assertEqual(
            rel.classify(_things(parts, "percent", "licensing",
                                 "Share of adults with a license")),
            rel.SHARE)
        # ...and a percentage that is NOT a share of anything countable is not.
        self.assertNotEqual(
            rel.classify(_things(parts, "percent", "mortgage rates",
                                 "Rates by lender")),
            rel.SHARE)

    def test_one_point_is_never_a_relationship(self):
        self.assertEqual(rel.classify(_Ins([_Pt("A", 1.0)])), rel.OTHER)

    def test_it_never_raises_on_junk(self):
        class Broken:
            pass
        self.assertEqual(rel.classify(Broken()), rel.OTHER)


class TheMachineComesFirstAndTheChartIsTheFallback(unittest.TestCase):
    def test_a_rank_reaches_for_a_rank_machine(self):
        seq = sr._depiction_sequence(
            _things([("A", 11.3), ("B", 9.7), ("C", 8.2), ("D", 6.8)]),
            set(), 12.0)
        self.assertTrue(any(k in sr._MACHINES["rank"] for k in seq[1:]),
                        f"a ranking fell back to a chart: {seq}")

    def test_a_duel_reaches_for_the_scales(self):
        seq = sr._depiction_sequence(
            _things([("2019", 270), ("2026", 449)], "thousand dollars"),
            set(), 12.0)
        self.assertIn("balance_scene", seq[1:], seq)

    # Machines whose whole encoding is a DIRECTION. Drawing a zig-zag as any
    # of these asserts a story the data does not tell.
    _DIRECTIONAL = {"staircase_scene", "elevator_scene", "burden_scene",
                    "tower_scene", "race_scene", "skyline_scene",
                    "funnel_scene", "conveyor_scene"}

    def test_a_volatile_series_is_never_given_a_direction(self):
        """This used to assert `_MACHINES["volatile"] == ()` — no machine at
        all — which was right while every form here encoded a direction. The
        spotlight was built for exactly this case: it shows the RANGE the
        number moved in and claims nothing about where it went. So the rule is
        not "no picture", it is "no picture that asserts a direction"."""
        for k in sr._MACHINES["volatile"]:
            self.assertNotIn(k, self._DIRECTIONAL,
                             f"{k} claims a direction a zig-zag does not have")
        self.assertIn("spotlight_scene", sr._MACHINES["volatile"])

    def test_the_rotation_never_puts_a_chart_ahead_of_a_machine(self):
        """THE INVERSION. Rotating one flat list for variety put a bar chart in
        front of the machine that actually said the thing."""
        for topic in ("cost of living", "bird counts", "rail freight",
                      "solar output", "hospital beds", "coffee prices",
                      "wildfire area", "school size"):
            ins = _things([("A", 11.3), ("B", 9.7), ("C", 8.2), ("D", 6.8)],
                          topic=topic)
            seq = sr._depiction_sequence(ins, set(), 12.0)
            if len(seq) > 1:
                self.assertIn(seq[1], sr._MACHINES["rank"],
                              f"{topic}: chart chosen over a machine — {seq}")

    def test_the_machines_are_all_real_and_reachable(self):
        for kinds in sr._MACHINES.values():
            for k in kinds:
                self.assertTrue(
                    k in sr._SCENE_TOKENS or k in sr._SELF_HOSTED,
                    f"{k!r} is named as a machine but renders nothing")


class AMachineMustNotAsymptote(unittest.TestCase):
    """The defect that cost two videos, twice, with an identical-looking curve.

    Every machine animates by driving geometry with the reveal, and the obvious
    choice — an ease-out — has a slope at the end of nearly zero. The last
    third of the visual then moves by fractions of a pixel per frame, which is
    below the cadence detector's threshold and is, correctly, read as a frozen
    frame. The balance shipped it as a cubic; the race shipped it as a square.
    """

    def test_it_starts_at_zero_and_ends_at_one(self):
        self.assertAlmostEqual(vs.settle(0.0), 0.0, places=6)
        self.assertAlmostEqual(vs.settle(1.0), 1.0, places=6)

    def test_it_is_still_moving_at_the_end(self):
        end = (vs.settle(1.0) - vs.settle(0.9)) / 0.1
        self.assertGreater(end, 0.5, f"end slope {end:.2f} — it stalls")

    def test_it_never_goes_backwards(self):
        vals = [vs.settle(i / 50.0) for i in range(51)]
        for a, b in zip(vals, vals[1:]):
            self.assertGreaterEqual(b, a)

    def test_it_still_has_some_shape(self):
        """Pure linear would pass every assertion above and look like a loading
        bar. It should leave the blocks faster than it arrives."""
        start = (vs.settle(0.1) - vs.settle(0.0)) / 0.1
        end = (vs.settle(1.0) - vs.settle(0.9)) / 0.1
        self.assertGreater(start, end)

    def test_no_machine_rolls_its_own_easing(self):
        """Each one that did got this wrong independently."""
        import inspect
        for fn in (vs.draw_race, vs.draw_gauge, vs.draw_balance):
            src = inspect.getsource(fn)
            self.assertNotIn("** 2", src, f"{fn.__name__} eases by hand")
            self.assertNotIn("** 3", src, f"{fn.__name__} eases by hand")
            self.assertIn("settle(", src, f"{fn.__name__} is not on the curve")


class TheRace(unittest.TestCase):
    """Rank becomes position, and the gap becomes literal distance."""

    def test_it_needs_a_field(self):
        """Two runners is a duel and belongs on the scales; one is not a
        race."""
        self.assertEqual(vs.race_scene(_things([("A", 1), ("B", 2)])), {})
        self.assertEqual(vs.race_scene(_Ins([_Pt("A", 1)])), {})

    def test_it_takes_three_to_eight(self):
        for n in (3, 5, 8):
            ins = _things([(chr(65 + i), 10 - i) for i in range(n)])
            self.assertTrue(vs.race_scene(ins), f"{n} runners refused")

    def test_it_is_a_real_scene_element(self):
        self.assertIn("race_track", vs._TYPES)
        self.assertIn("race_track", vs._RICH_TYPES)
        self.assertIn("race_track", vs._HOLISTIC)

    def test_the_runners_are_the_mascot(self):
        """The channel's identity is a mascot in a world where numbers are
        physical. Five coloured rectangles is Bloomberg with a TikTok."""
        import inspect
        self.assertIn("scene_host", inspect.getsource(vs.draw_race))


class TheSkyline(unittest.TestCase):
    """One thing dwarfing the rest, with Data tiny at its foot."""

    def test_dominance_reaches_for_it(self):
        ins = _things([("Ants", 900), ("Termites", 95), ("Humans", 60),
                       ("Cattle", 40)], "million tonnes", "biomass")
        self.assertEqual(rel.classify(ins), rel.DOMINANCE)
        self.assertEqual(sr._MACHINES["dominance"][0], "skyline_scene")

    def test_it_needs_something_to_dwarf(self):
        self.assertEqual(vs.skyline_scene(_Ins([_Pt("A", 1)])), {})

    def test_the_host_is_deliberately_small_here(self):
        """Everywhere else in this kit he is the subject. Here the point is
        that the number is bigger than him — he is the ruler."""
        import inspect
        src = inspect.getsource(vs.draw_skyline)
        self.assertIn("mh = 140", src)

    def test_it_is_on_the_shared_motion_curve(self):
        import inspect
        self.assertIn("settle(reveal)", inspect.getsource(vs.draw_skyline))


class TheNewRelationshipsAreDetectedFromRealData(unittest.TestCase):
    """A machine routed to a relationship nothing produces is a machine that
    never runs. Each of these is detected from data this pipeline actually
    makes."""

    def test_a_baseline_is_a_threshold(self):
        """The config already carried one on comparison insights and nothing
        used it but a dashed rule."""
        ins = _things([("San Jose", 11.3), ("LA", 9.7)])
        ins.baseline = _Pt("US average", 5.9)
        self.assertEqual(rel.classify(ins), rel.THRESHOLD)
        self.assertEqual(sr._MACHINES["threshold"][0], "hurdle_scene")

    def test_stages_that_shrink_are_a_funnel(self):
        ins = _things([("Applied", 1000), ("Interviewed", 380),
                       ("Offered", 95), ("Accepted", 41)],
                      "count", "hiring funnel", "Applicants drop each stage")
        self.assertEqual(rel.classify(ins), rel.DROPOFF)

    def test_a_plain_ranking_is_not_a_funnel(self):
        """THE FALSE POSITIVE THAT MATTERS. Five cities sorted by cost also
        shrink at every step and are emphatically not a funnel, so the shape
        alone is not enough — the claim has to say stages."""
        ins = _things([("San Jose", 11.3), ("LA", 9.7), ("Miami", 8.2),
                       ("Denver", 5.4)], "years", "cost in years of pay",
                      "San Jose tops the list")
        self.assertEqual(rel.classify(ins), rel.RANK)

    def test_a_per_time_unit_is_a_frequency(self):
        ins = _Ins([_Pt("2026", 1400)], "per day", "flights a day",
                   "Flights a day")
        self.assertTrue(rel.is_frequency(ins))
        self.assertEqual(sr._MACHINES["frequency"][0], "conveyor_scene")

    def test_a_total_is_not_a_frequency(self):
        ins = _Ins([_Pt("2026", 1400)], "count", "total flights",
                   "Flights in the fleet")
        self.assertFalse(rel.is_frequency(ins))

    def test_volatile_finally_has_a_picture_that_is_not_a_lie(self):
        """It had NO machine, deliberately, because every form here asserts a
        direction and a zig-zag has none. A spotlight asserts only a range."""
        self.assertEqual(sr._MACHINES["volatile"], ("spotlight_scene",))


class TheHonestyOfTheNewMachines(unittest.TestCase):
    def test_the_tower_never_sums_a_series(self):
        """Adding a decade of annual figures produces a number nobody
        measured. The blocks are the LATEST value split into units."""
        import inspect
        src = inspect.getsource(vs.draw_tower)
        self.assertIn("unit_plan", src)
        self.assertNotIn("sum(", src)

    def test_the_tower_says_what_a_block_is_worth(self):
        import inspect
        self.assertIn("each block", inspect.getsource(vs.draw_tower))

    def test_the_funnel_states_what_survives(self):
        import inspect
        self.assertIn("make it to the end", inspect.getsource(vs.draw_funnel))

    def test_the_hurdle_says_whether_it_cleared(self):
        import inspect
        src = inspect.getsource(vs.draw_hurdle)
        self.assertIn("clears it", src)
        self.assertIn("does not clear it", src)

    def test_the_pipes_shares_are_the_widths(self):
        """Width IS the encoding, so the branches add up to the trunk by
        construction — the honest version of the claim a stacked chart makes
        in words."""
        import inspect
        self.assertIn("v / tot", inspect.getsource(vs.draw_pipes))

    def test_every_new_machine_refuses_data_it_cannot_serve(self):
        thin = _Ins([_Pt("A", 1.0)])
        for build in (vs.funnel_scene, vs.spotlight_scene):
            self.assertEqual(build(thin), {})

    def test_the_hurdle_needs_a_baseline_to_draw_at_all(self):
        import inspect
        self.assertIn("if not items or base is None:",
                      inspect.getsource(vs.draw_hurdle))


class EveryMachineIsWiredEndToEnd(unittest.TestCase):
    """A machine that renders but is unreachable is the exact failure CLAUDE.md
    calls rule zero — and the scene kit already had three of those."""

    def test_every_token_has_a_builder(self):
        for token, builder in sr._SCENE_TOKENS.items():
            self.assertTrue(callable(getattr(vs, builder, None)), token)

    def test_every_machine_named_by_the_router_can_render(self):
        for kinds in sr._MACHINES.values():
            for k in kinds:
                self.assertTrue(k in sr._SCENE_TOKENS or k in sr._SELF_HOSTED,
                                f"{k!r} renders nothing")

    def test_every_whole_insight_machine_is_in_the_dispatch_table(self):
        """Registering a type without dispatching it sends every scene using
        it into the chart fallback, silently. The dispatch used to be a chain
        of literals — this test read them — and it is one TABLE now precisely
        so registering and dispatching cannot drift apart."""
        for kind, fn in vs._MACHINE_DRAW.items():
            self.assertIn(kind, vs._TYPES, f"{kind!r} dispatched but unknown")
            self.assertTrue(callable(fn), kind)
        # every drawn type is either in the table or has its own branch
        handled = set(vs._MACHINE_DRAW) | {"balance", "race_track"}
        self.assertEqual(vs._DRAWN_TYPES - handled, set(),
                         "a drawn element type is never dispatched")


if __name__ == "__main__":
    unittest.main(verbosity=2)
