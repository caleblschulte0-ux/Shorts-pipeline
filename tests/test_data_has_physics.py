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

    def test_a_flat_series_is_STABLE_which_is_a_finding(self):
        """This asserted OTHER — draw a chart — which was right while nothing
        could depict "it did not move". A road he is cruising says the number
        is live and going nowhere, which is the actual claim; a flat line makes
        it look like nothing happened rather than like nothing changed."""
        self.assertEqual(rel.classify(_series([50, 50.2, 50.1, 50.3, 50.2])),
                         rel.STABLE)

    def test_two_things_are_a_duel(self):
        self.assertEqual(rel.classify(_things([("Wind", 42), ("Solar", 28)])),
                         rel.DUEL)

    def test_two_YEARS_are_a_before_and_after_not_a_duel(self):
        """A then-and-now is a change in ONE subject, not two things weighed
        against each other, and it wants the subject itself growing. Measured
        on the live queue, treating them the same put 123 of 222 beats into
        `duel` and sent over half the catalogue to the same set of scales."""
        self.assertEqual(rel.classify(_things([("2019", 270), ("2026", 449)])),
                         rel.BEFORE_AFTER)

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

    def test_a_duel_reaches_for_a_duel_machine(self):
        """Named after the relationship, not one member of its list — `duel`
        is rotatable, so scales, two lanes and a count are all valid picks and
        pinning one of them makes the test a coin flip."""
        seq = sr._depiction_sequence(
            _things([("Wind", 42), ("Solar", 28)], "percent"), set(), 12.0)
        self.assertTrue(any(k in sr._MACHINES["duel"] for k in seq[1:]), seq)

    def test_a_before_and_after_reaches_for_the_subject_growing(self):
        seq = sr._depiction_sequence(
            _things([("2019", 270), ("2026", 449)], "thousand dollars"),
            set(), 12.0)
        self.assertTrue(any(k in sr._MACHINES["before_after"] for k in seq[1:]),
                        seq)

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
        # The coaster joined it later: it shows the shape of the ride without
        # claiming where the ride ended, which is the same honesty test.

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

    def test_one_runner_is_not_a_race(self):
        self.assertEqual(vs.race_scene(_Ins([_Pt("A", 1)])), {})

    def test_two_lanes_are_allowed(self):
        """This used to require three, on the reasoning that a pair belongs on
        the scales. True — and it left `duel` with exactly one picture while
        being 104 of the live queue's 222 beats, so half the catalogue was
        heading for the same seesaw. A drag race is a legitimate head-to-head
        and the operator's list names it."""
        self.assertTrue(vs.race_scene(_things([("A", 1), ("B", 2)])))

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
        direction and a zig-zag has none. A spotlight asserts only a range, and
        a coaster only a shape — neither says where it ended up. Pinned as a
        PROPERTY rather than an exact tuple, so adding another honest form does
        not break it."""
        forms = sr._MACHINES["volatile"]
        self.assertTrue(forms)
        self.assertTrue(set(forms) <= {"spotlight_scene", "coaster_scene"},
                        f"a directional form crept into volatile: {forms}")


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


class MotionMustBeVISIBLE(unittest.TestCase):
    """Real motion is not the same as motion the cadence gate can see.

    The hurdle slid the host up to his value across the whole visual. The move
    was genuine and it measured as a TWO-SECOND FROZEN STRETCH, because spread
    over 183 frames it is a sub-pixel change per frame in a small part of the
    screen — and the detector takes the max over 12x12 blocks of the MEAN
    change inside a block. Every machine that passes (staircase, race, tower)
    has DISCRETE arrivals: a step lands, a runner moves a visible distance, a
    block drops.

    So a machine whose only motion is one slow glide is not finished, however
    correct its geometry.
    """

    def test_the_hurdle_is_a_jump_not_a_glide(self):
        import inspect
        src = inspect.getsource(vs.draw_hurdle)
        self.assertIn("the run-up", src)
        self.assertIn("the jump", src)

    def test_the_jump_actually_leaves_the_ground(self):
        """A "jump" that interpolates linearly to the final height is the glide
        again with a new comment."""
        import inspect
        self.assertIn("_math.sin", inspect.getsource(vs.draw_hurdle))

    def test_no_machine_holds_still_long_enough_to_be_called_frozen(self):
        """MEASURED, with the gate's own detector, because the source cannot
        tell you this.

        A first version of this test pattern-matched for staged reveals and got
        it wrong in both directions: it cleared the TOWER, which was 107 of 119
        frames unchanged with a 53-frame still run, and it flagged the RACE,
        whose five sprites all travel at once and is fine. Only rendering the
        frames and diffing them answers the question.
        """
        try:
            import numpy as np
        except ImportError:  # noqa: BLE001
            self.skipTest("numpy not installed")
        import tempfile
        from PIL import Image
        from data_learning import charts
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source

        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-07")
        years = [(str(2015 + k), 100 + k * 22) for k in range(12)]
        cities = [("San Jose", 11.3), ("LA", 9.7), ("Miami", 8.2),
                  ("Seattle", 6.8), ("Denver", 5.4)]

        def _ins(pairs, base=None):
            i = Insight(kind="scene", topic="t", main_insight="m",
                        items=[DataPoint(label=str(a), value=float(b))
                               for a, b in pairs],
                        source=src, unit="count",
                        highlight_label=str(pairs[0][0]))
            if base:
                i.baseline = DataPoint(label=base[0], value=float(base[1]))
            return i

        def _block_max(a, b):
            return max(np.abs(a[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]
                              - b[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16]).mean()
                       for r in range(12) for c in range(12))

        # CALIBRATED, not guessed. The gate samples the finished video at
        # 24fps and allows a 45-frame run; a ~6s visual is ~144 sampled frames,
        # so its ceiling is about 31% of a visual. At 120 frames that is 37.
        # 35 leaves a little margin and still separates the cases cleanly: the
        # tower measured 53 before it was fixed and 27 after.
        #
        # A short sample was tried first (40 frames, ceiling 15) and the
        # quantisation made it unreliable — the same tower measured 23% at 120
        # frames and 40% at 40. Measuring the thing properly costs a minute.
        #
        # This is also deliberately LOOSER than a per-machine ideal, for the
        # reason `_scene_metrics` had to be rewritten today: a machine measured
        # in isolation is stricter than reality, because in the finished video
        # the host, the captions and the closing all contribute motion. This
        # catches a machine that is grossly still, not one that is marginal.
        FRAMES = 120
        CEILING = 35
        cases = (("tower", vs.tower_scene, _ins(years), None),
                 ("staircase", vs.staircase_scene, _ins(years), None),
                 ("race", vs.race_scene, _ins(cities), None),
                 ("hurdle", vs.hurdle_scene, _ins([("San Jose", 11.3)]),
                  ("US average", 5.9)))
        worst = {}
        for name, build, ins, base in cases:
            if base:
                ins.baseline = DataPoint(label=base[0], value=float(base[1]))
            ins.scene = build(ins)
            if not ins.scene:
                continue
            with tempfile.TemporaryDirectory() as td:
                charts.FULLFRAME_RENDERERS["scene"](
                    ins, Path(td), name, FRAMES)
                fs = sorted(Path(td).glob(name + "*.png"))
                if len(fs) < 5:
                    continue
                arr = [np.asarray(Image.open(f).convert("L").resize((192, 192)),
                                  dtype=np.float32) for f in fs]
                run = best = 0
                for k in range(len(arr) - 1):
                    if _block_max(arr[k], arr[k + 1]) < 6.0:
                        run += 1
                        best = max(best, run)
                    else:
                        run = 0
                if best > CEILING:
                    worst[name] = best
        self.assertEqual(worst, {}, f"machines that hold still: {worst}")


class BatchOneRelationships(unittest.TestCase):
    """Six more shapes the router reads off the data itself."""

    def _ser(self, vals):
        return _series(vals)

    def test_a_flat_series_is_a_FINDING_not_an_absence(self):
        """"This has not moved in twenty years" is a story. It used to fall
        through to OTHER and get a flat line — the one picture that makes it
        look like nothing HAPPENED rather than like nothing CHANGED."""
        self.assertEqual(rel.classify(self._ser([50, 50.2, 50.1, 50.3, 50.2,
                                                 50.1])), rel.STABLE)
        self.assertEqual(sr._MACHINES["stable"], ("road_scene",))

    def test_a_turn_is_not_a_zigzag(self):
        """One way, then the other, and it STUCK — there is a moment where it
        changed its mind, which a swinging series does not have."""
        self.assertEqual(rel.classify(self._ser([10, 30, 55, 80, 60, 35, 12,
                                                 8])), rel.REVERSAL)
        self.assertEqual(rel.classify(self._ser([10, 90, 20, 85, 15, 80])),
                         rel.VOLATILE)

    def test_compounding_is_not_merely_rising(self):
        """At a looser bar an ordinary rise — 10, 14, 19, 25, 33, 41 — came
        back ACCELERATION, because almost every growing series speeds up a
        little. The claim is that the rise is compounding."""
        self.assertEqual(rel.classify(self._ser([2, 5, 11, 22, 44, 88])),
                         rel.ACCELERATION)
        self.assertEqual(rel.classify(self._ser([10, 14, 19, 25, 33, 41])),
                         rel.GROWTH)

    def test_every_new_relationship_has_a_machine(self):
        for name in (rel.STABLE, rel.DELTA, rel.GAP, rel.CENTRE,
                     rel.ACCELERATION, rel.REVERSAL):
            self.assertTrue(sr._MACHINES.get(name),
                            f"{name} classifies but draws nothing")

    def test_the_reversal_and_volatile_pictures_claim_no_destination(self):
        """A turn and a zig-zag both end somewhere the data does not endorse
        as a trend, so neither may be drawn as a climb."""
        directional = {"staircase_scene", "burden_scene", "tower_scene",
                       "race_scene", "skyline_scene", "funnel_scene"}
        for name in ("reversal", "volatile"):
            for k in sr._MACHINES[name]:
                self.assertNotIn(k, directional, f"{name} -> {k}")


class BatchOneMachines(unittest.TestCase):
    def test_the_road_says_it_barely_moved(self):
        import inspect
        self.assertIn("barely moved", inspect.getsource(vs.draw_road))

    def test_the_tape_states_the_distance_not_the_ends(self):
        import inspect
        self.assertIn("apart", inspect.getsource(vs.draw_tape))

    def test_the_bridge_states_the_shortfall(self):
        import inspect
        self.assertIn("short", inspect.getsource(vs.draw_bridge))

    def test_the_bridge_measures_the_gap_against_the_far_bank(self):
        """Scaling the deck to the FRAME instead put the far bank inside the
        span the deck was measured against, and a 24% shortfall came out as a
        60px nick — too small to draw the measurement across, so the number
        never appeared at all."""
        import inspect
        self.assertIn("far_x - x0", inspect.getsource(vs.draw_bridge))

    def test_the_centre_walks_him_to_the_middle(self):
        import inspect
        src = inspect.getsource(vs.draw_centre)
        self.assertIn("sorted(", src)
        self.assertIn("mid_i", src)

    def test_the_machines_that_need_a_baseline_refuse_without_one(self):
        no_base = _Ins([_Pt("A", 1.0)], "count", "x", "y")
        for fn in (vs.draw_bridge,):
            import inspect
            self.assertIn("base is None", inspect.getsource(fn))
        self.assertIsNotNone(no_base)


class BatchTwoRelationships(unittest.TestCase):
    def test_a_repeat_is_a_cycle_and_a_crash_is_not(self):
        """A cycle is a stronger claim than volatility: it says the movement
        RECURS. A series that crashed once and recovered would otherwise be
        drawn as a season, which it is not."""
        self.assertEqual(
            rel.classify(_series([10, 60, 12, 58, 11, 62, 13, 59, 10, 61])),
            rel.CYCLE)
        self.assertNotEqual(
            rel.classify(_series([60, 58, 59, 10, 12, 55, 57, 58])), rel.CYCLE)

    def test_near_identical_values_are_a_SPREAD_not_a_ranking(self):
        """"These are all basically the same" is a finding, and a sorted bar
        chart is the one picture that hides it — five near-identical bars look
        like a ranking."""
        self.assertEqual(
            rel.classify(_things([("A", 100), ("B", 102), ("C", 101),
                                  ("D", 99), ("E", 100), ("F", 101)])),
            rel.SPREAD)

    def test_a_real_ranking_is_still_a_ranking(self):
        self.assertEqual(
            rel.classify(_things([("A", 11.3), ("B", 9.7), ("C", 8.2),
                                  ("D", 6.8)])), rel.RANK)

    def test_each_batch_two_relationship_has_a_machine(self):
        for name in (rel.CYCLE, rel.SPREAD, rel.QUEUE):
            self.assertTrue(sr._MACHINES.get(name), name)

    def test_the_cycle_machine_actually_turns(self):
        import inspect
        src = inspect.getsource(vs.draw_wheel)
        self.assertIn("2.0 * _math.pi", src, "the wheel does not revolve")

    def test_the_darts_board_is_the_RANGE_not_an_axis(self):
        """The picture is the CLUSTERING, so the board has to be scaled to the
        spread. Against an absolute axis six near-identical values land on one
        another and say nothing."""
        import inspect
        self.assertIn("abs(v - mean) / span",
                      inspect.getsource(vs.draw_darts))


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
