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


# NEUTRAL BY DEFAULT. This said `unit="years"` while the unit meant nothing to
# the router; since batch 6 a pair measured in years IS a duration, so a
# filler unit was quietly asserting one. Tests that want a time unit now say
# so, and the ones that want "two named things" get a unit that claims
# nothing.
def _things(pairs, unit="count", topic="cost", main="A tops"):
    return _Ins([_Pt(n, v) for n, v in pairs], unit, topic, main)


_BOX = (vs.RX0, vs.RTOP, vs.RX1, vs.RBOT)


class _pil:
    """A throwaway canvas + draw handle, for asserting on what a machine
    REFUSES. Some refusals are only reachable by calling the draw function —
    the builder cannot know that a pair grew instead of shrank."""

    def __enter__(self):
        from PIL import Image, ImageDraw
        self.canvas = Image.new("RGBA", (1080, 1280), (18, 20, 28, 255))
        return ImageDraw.Draw(self.canvas), self.canvas

    def __exit__(self, *a):
        return False


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

    def test_the_hurdle_says_whether_it_cleared_AND_BY_HOW_MUCH(self):
        """It used to say only "clears it" / "does not clear it". The margin
        is the interesting half — 11.3 against an average of 5.9 is not the
        same story as 6.0 against 5.9, and the picture cannot show that
        difference at a glance when the bar is nearly the same height."""
        import inspect
        src = inspect.getsource(vs.draw_hurdle)
        self.assertIn("clears it by", src)
        self.assertIn("short of it", src)
        self.assertIn("abs(abs(v) - abs(bv))", src)

    def test_the_hurdle_stands_on_a_GROUND(self):
        """Drawn full-width with legs to the floor it was a staple across the
        whole frame, and his value a line floating above it: two unrelated
        horizontals rather than a thing and the bar it cleared."""
        import inspect
        src = inspect.getsource(vs.draw_hurdle)
        self.assertIn("THE GROUND", src)

    def test_no_machine_label_is_hung_off_a_moving_edge(self):
        """Both of the hurdle's labels ran off the frame when they were
        anchored to the bar, whose x moves with the box. Pinned to bx0/bx1
        they cannot clip."""
        import inspect
        src = inspect.getsource(vs.draw_hurdle)
        self.assertIn("bx1 - 24", src)
        self.assertIn("bx0 + 24", src)

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

        def _pct(pairs):
            i = _ins(pairs)
            i.unit = "percent"
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
        # EVERY machine, not a sample of them. The case list below started as
        # four and grew batch by batch, which meant a machine was only ever
        # measured if somebody remembered to add it — and on 2026-09-07 a
        # sweep of all forty-two found four that had never been measured and
        # were failing: darts (47), funnel (50), pipes (54) and road (47), all
        # at production frame size. Three were staged reveals that finished
        # and held; road scrolled its dashes on `settle`, so they slowed to a
        # crawl exactly when the eye had nothing else to watch.
        #
        # `MACHINES_MEASURED_ELSEWHERE` is empty on purpose. If a machine
        # cannot be given a sample here it does not get measured, and a
        # machine nobody measures is one that ships frozen.
        stages = [("Applied", 12000), ("Screened", 9800),
                  ("Interviewed", 2100), ("Offered", 1700), ("Hired", 1500)]
        zig = [(str(2016 + k), v) for k, v in
               enumerate([99, 101, 97, 100, 98, 101, 97, 99])]
        cases = (("tower", vs.tower_scene, _ins(years), None),
                 ("staircase", vs.staircase_scene, _ins(years), None),
                 ("race", vs.race_scene, _ins(cities), None),
                 ("hurdle", vs.hurdle_scene, _ins([("San Jose", 11.3)]),
                  ("US average", 5.9)),
                 # The flow family. Every one of these was a staged reveal and
                 # nothing else when first written: the bottleneck measured a
                 # 0.908 duplicate ratio and a 51-frame frozen run, the chain
                 # 49. Geometry that is correct and completely still is a
                 # still image with a caption, and the gate is right to hold
                 # it. Each now carries the flow it is describing.
                 ("bottleneck", vs.bottleneck_scene, _ins(stages), None),
                 ("leaky", vs.leaky_scene,
                  _ins([("Enrolled", 4800), ("Finished", 860)]), None),
                 ("inout", vs.inout_scene,
                  _ins([("Inflow", 1840), ("Outflow", 1310)]), None),
                 ("sorter", vs.sorter_scene,
                  _ins([("Housing", 4200), ("Transit", 2600),
                        ("Parks", 1400), ("Admin", 900)]), None),
                 ("chain", vs.chain_scene,
                  _ins([("Wafer", 940), ("Assembly", 720), ("Test", 210),
                        ("Ship", 880)]), None),
                 # The uncertainty family. The fan is the one to watch: it is
                 # a staged line reveal and would hold perfectly still the
                 # moment the cone finished drawing.
                 ("spinner", vs.spinner_scene, _pct([("Rain", 23.0)]), None),
                 ("doors", vs.doors_scene, _pct([("Match", 4.0)]), None),
                 ("fan", vs.fan_scene,
                  _ins([(str(2016 + k), 62 + k * 3.1) for k in range(8)]
                       + [("2040", 108.0)]), None),
                 ("gears", vs.gears_scene,
                  _ins([("Median rent", 2400), ("Median wage", 3100)]), None),
                 ("slider", vs.slider_scene,
                  _ins([("Top speed", 82), ("Range", 148)]), None),
                 # The physical comparisons. The chairs are the one to watch:
                 # a 5px crowd shuffle spread over 120 frames is a quarter of
                 # a pixel a frame and measured as a 54-frame freeze.
                 ("density", vs.density_scene,
                  _ins([("Manila", 46000), ("Houston", 1400)]), None),
                 ("nest", vs.nest_scene,
                  _ins([("Alaska", 1723000), ("New Jersey", 22600)]), None),
                 ("chairs", vs.chairs_scene,
                  _ins([("Applicants", 41000), ("Homes", 1200)]), None),
                 ("hourglass", vs.hourglass_scene,
                  _ins([("San Jose", 11.3), ("Detroit", 2.4)]), None),
                 ("trophies", vs.trophies_scene,
                  _ins([("Djokovic", 24), ("Nadal", 22),
                        ("Federer", 20)]), None),
                 ("basket", vs.basket_scene,
                  _ins([("1999", 34), ("2026", 19)]), None),
                 # The seventeen that had no sample until 2026-09-07. Four of
                 # them were failing the moment they were measured.
                 ("bridge", vs.bridge_scene, _ins([("Now", 76)]),
                  ("Target", 100)),
                 ("burden", vs.burden_scene,
                  _ins([(str(2016 + k), 22.0 + k * 1.6) for k in range(8)]),
                  None),
                 ("centre", vs.centre_scene, _ins(cities), None),
                 ("coaster", vs.coaster_scene, _ins(zig), None),
                 ("conveyor", vs.conveyor_scene, _ins([("Parcels", 1400)]),
                  None),
                 ("darts", vs.darts_scene,
                  _ins([("A", 100), ("B", 102), ("C", 101), ("D", 99),
                        ("E", 100), ("F", 101)]), None),
                 ("elevator", vs.elevator_scene,
                  _ins([(str(2016 + k), 96.0 - k * 7) for k in range(8)]),
                  None),
                 ("funnel", vs.funnel_scene, _ins(stages), None),
                 ("gauge", vs.gauge_scene, _ins([("Rate", 22.9)]), None),
                 ("pipes", vs.pipes_scene,
                  _ins([("Rent", 34), ("Food", 22), ("Transit", 18),
                        ("Other", 26)]), None),
                 ("queue", vs.queue_scene,
                  _ins([(str(2016 + k), 200.0 + k * 180) for k in range(8)]),
                  None),
                 ("road", vs.road_scene,
                  _ins([(str(2016 + k), 50.0 + (k % 2) * 0.2)
                        for k in range(8)]), None),
                 ("skyline", vs.skyline_scene,
                  _ins([("Tokyo", 37.4), ("Delhi", 9.2), ("Cairo", 7.8),
                        ("Lima", 4.1)]), None),
                 ("spotlight", vs.spotlight_scene, _ins(zig), None),
                 ("tape", vs.tape_scene, _ins([("2016", 42), ("2026", 97)]),
                  None),
                 ("thermometer", vs.thermometer_scene, _ins([("Now", 88)]),
                  ("Limit", 100)),
                 ("wheel", vs.wheel_scene,
                  _ins([(str(2016 + k), v) for k, v in
                        enumerate([10, 60, 12, 58, 11, 62, 13, 59])]), None))
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


class BatchThreeIsTheFlowFamily(unittest.TestCase):
    """Five machines that all draw the SAME numbers and make five different
    claims — which is exactly why the router must read the words.

    Stages that shrink are a funnel, a ranking, a bottleneck, a supply chain
    and a set of sorting bins all at once by SHAPE. Only the claim separates
    them, so every one of these classifiers requires the language and falls
    back to a plain ranking when it is absent. Getting that wrong does not
    produce an ugly picture; it produces a confident wrong sentence at 42pt.
    """

    def test_the_claim_decides_and_not_the_shape(self):
        pairs = [("A", 1000), ("B", 700), ("C", 200), ("D", 120)]
        self.assertEqual(rel.classify(_things(pairs, main="A tops the list")),
                         rel.RANK)
        for claim, want in (
                ("the bottleneck is stage C", rel.BOTTLENECK),
                ("only some are retained to the end", rel.RETENTION),
                ("where the money was routed", rel.ROUTING),
                ("each step of the supply chain", rel.CHAIN)):
            self.assertEqual(rel.classify(_things(pairs, main=claim)), want,
                             claim)

    def test_an_inflow_and_an_outflow_are_not_a_duel(self):
        self.assertEqual(
            rel.classify(_things([("Inflow", 1840), ("Outflow", 1310)],
                                 main="inflow against outflow")),
            rel.INFLOW_OUTFLOW)

    def test_each_batch_three_relationship_has_a_machine(self):
        for name in (rel.BOTTLENECK, rel.RETENTION, rel.INFLOW_OUTFLOW,
                     rel.ROUTING, rel.CHAIN):
            self.assertTrue(sr._MACHINES.get(name), name)

    def test_the_bottleneck_leads_with_the_bottleneck_not_the_funnel(self):
        """A funnel is a legitimate runner-up and a wrong lead: it says they
        leak away all the way down, which is a description. The pinch names a
        culprit, which is the whole reason the relationship exists."""
        self.assertEqual(sr._MACHINES[rel.BOTTLENECK][0], "bottleneck_scene")

    def test_the_bucket_drains_rather_than_fills(self):
        """Filling up to the retained share animates the wrong event. Nobody
        joined — they left — so the bucket starts whole."""
        import inspect
        src = inspect.getsource(vs.draw_leaky)
        self.assertIn("1.0 - (1.0 - frac) * e", src)

    def test_the_inout_water_is_the_SURPLUS_and_says_which_way(self):
        import inspect
        src = inspect.getsource(vs.draw_inout)
        self.assertIn("surplus = inflow - outflow", src)
        self.assertIn("left over", src)
        self.assertIn("short", src)

    def test_the_inout_keeps_the_authored_order_as_the_direction(self):
        """Taking max() as the inflow makes the machine incapable of drawing a
        shortfall, which is the case worth drawing."""
        import inspect
        self.assertNotIn("max(a_v, b_v)", inspect.getsource(vs.draw_inout))

    def test_the_sorter_bins_add_up_to_one_whole(self):
        """Filling each bin against the LARGEST would overstate every share."""
        import inspect
        src = inspect.getsource(vs.draw_sorter)
        self.assertIn("share = v / tot", src)

    def test_the_chain_runs_at_its_WORST_link_not_its_average(self):
        import inspect
        src = inspect.getsource(vs.draw_chain)
        self.assertIn("weak = vals.index(min(vals))", src)
        self.assertIn("the whole line runs at", src)

    def test_the_flow_machines_refuse_data_they_cannot_serve(self):
        one = _Ins([_Pt("A", 5)], "count", "t", "m")
        for build in (vs.bottleneck_scene, vs.leaky_scene, vs.inout_scene,
                      vs.sorter_scene, vs.chain_scene):
            self.assertFalse(build(one), build)

    def test_the_bucket_refuses_to_keep_more_than_it_started_with(self):
        """A retention picture drawn from a GROWING pair would overflow, and
        would be claiming a loss that did not happen."""
        grew = _Ins([_Pt("Enrolled", 800), _Pt("Finished", 4800)],
                    "count", "t", "m")
        with _pil() as (d, canvas):
            self.assertIsNone(vs.draw_leaky(d, canvas, _BOX, grew,
                                            vs.HIGHLIGHT, 1.0, "count"))


class BatchFourIsTheUncertaintyFamily(unittest.TestCase):
    """Four relationships that are indistinguishable from their neighbours by
    the numbers alone, and only separable by the claim.

    A probability and a share are both "23%". A projection and a measurement
    are both a point on a series. Drawing one as the other is not an ugly
    picture, it is a lie about what the number IS — so every classifier here
    requires the language and the shape never decides on its own.
    """

    def test_a_chance_is_not_a_share(self):
        """The dot field lights 23 figures in 100 and asserts a population you
        could count out. "A 23% chance" is one trial. Same number, different
        claim, and the words are the only thing that separates them."""
        self.assertEqual(
            rel.classify(_things([("Rain", 23.0), ("Dry", 77.0)],
                                 "percent", "weather",
                                 "the chance of rain tomorrow")),
            rel.PROBABILITY)
        self.assertNotEqual(
            rel.classify(_things([("Own one", 23.0), ("Do not", 77.0)],
                                 "percent", "ownership",
                                 "23% of households own one")),
            rel.PROBABILITY)

    def test_a_projection_needs_BOTH_the_word_and_a_dated_tail(self):
        """Forecast language over a run of measurements is just a writer being
        loose. The tail has to actually be dated past the data."""
        measured = [(str(2016 + i), 62 + i * 3.0) for i in range(8)]
        self.assertEqual(
            rel.classify(_Ins([_Pt(a, b) for a, b in
                               measured + [("2040", 108.0)]],
                              "millions", "population",
                              "projected to reach", kind="trend")),
            rel.FORECAST)
        self.assertNotEqual(
            rel.classify(_Ins([_Pt(a, b) for a, b in measured],
                              "millions", "population",
                              "projected to reach", kind="trend")),
            rel.FORECAST)

    def test_a_forecast_is_not_claimed_without_the_word(self):
        pairs = [(str(2016 + i), 62 + i * 3.0) for i in range(8)] + \
                [("2040", 108.0)]
        self.assertNotEqual(
            rel.classify(_Ins([_Pt(a, b) for a, b in pairs], "millions",
                              "population", "it went up", kind="trend")),
            rel.FORECAST)

    def test_moving_together_and_trading_off_both_need_saying(self):
        pair = [("Median rent", 2400), ("Median wage", 3100)]
        self.assertEqual(
            rel.classify(_things(pair, "usd", "cost",
                                 "rents move with wages")), rel.CORRELATION)
        self.assertEqual(
            rel.classify(_things(pair, "usd", "cost",
                                 "more of one at the cost of the other")),
            rel.TRADEOFF)
        self.assertEqual(
            rel.classify(_things(pair, "usd", "cost", "rent beats wages")),
            rel.DUEL)

    def test_each_batch_four_relationship_has_a_machine(self):
        for name in (rel.PROBABILITY, rel.FORECAST, rel.CORRELATION,
                     rel.TRADEOFF):
            self.assertTrue(sr._MACHINES.get(name), name)

    def test_the_spinner_never_lands(self):
        """Landing it shows an OUTCOME — a win or a loss nobody measured. The
        honest statement is the size of the slice."""
        import inspect
        src = inspect.getsource(vs.draw_spinner)
        self.assertIn("never stops", src)
        self.assertIn("360.0 * p", src, "the slice is not the probability")

    def test_the_doors_are_only_for_a_real_one_in_n(self):
        import inspect
        self.assertIn("k != 1", inspect.getsource(vs.draw_doors))

    def test_the_chance_reader_refuses_what_it_cannot_read(self):
        self.assertIsNone(vs._chance_of(_Ins([_Pt("A", 4200)], "usd", "t",
                                             "m")))
        self.assertIsNone(vs._chance_of(_Ins([], "percent", "t", "m")))
        self.assertAlmostEqual(
            vs._chance_of(_Ins([_Pt("Rain", 23.0)], "percent", "t", "m")),
            0.23, places=6)

    def test_the_fan_says_where_the_data_stops(self):
        import inspect
        src = inspect.getsource(vs.draw_fan)
        self.assertIn("the data stops here", src)
        self.assertIn("measured to", src)
        self.assertIn("projected", src)

    def test_the_fan_spaces_its_x_axis_by_YEAR(self):
        """Evenly spaced, a projection seventeen years out sits one step past
        a run of annual figures and looks like next year — the cone would be
        claiming near-term precision it does not have."""
        import inspect
        self.assertIn("X BY YEAR", inspect.getsource(vs.draw_fan))

    def test_the_gears_never_claim_causation(self):
        """A gear train looks like causation if you let it. The data is a
        correlation, so the words on screen have to stay a correlation."""
        import inspect
        src = inspect.getsource(vs.draw_gears)
        self.assertIn("they move together", src)
        # Only what is DRAWN. The docstring is allowed to say the word in
        # order to forbid it.
        drawn = [ln for ln in src.splitlines() if "d.text(" in ln
                 or ('"' in ln and "fill=" not in ln and "font=" in ln)]
        body = src.split('"""', 2)[-1]
        for word in ("drives", "causes", "caused by", "because of"):
            self.assertNotIn(f'"{word}', body, drawn)

    def test_the_uncertainty_machines_refuse_data_they_cannot_serve(self):
        """The BUILDER only counts items, so the refusals that matter here are
        in the draw functions: a lone dollar figure is not a chance, and two
        points are not a forecast. Each has to hand back None so the depiction
        falls through to something true rather than drawing a wheel whose
        slice means nothing."""
        money = _Ins([_Pt("Rent", 4200)], "usd", "t", "m")
        shortsr = _Ins([_Pt("2016", 4), _Pt("2017", 6)], "count", "t", "m")
        cases = ((vs.draw_spinner, money), (vs.draw_doors, money),
                 (vs.draw_fan, shortsr),
                 (vs.draw_gears, _Ins([_Pt("A", 0)], "usd", "t", "m")),
                 (vs.draw_slider, _Ins([_Pt("A", 0)], "usd", "t", "m")))
        for fn, ins in cases:
            with _pil() as (d, canvas):
                self.assertIsNone(
                    fn(d, canvas, _BOX, ins, vs.HIGHLIGHT, 1.0, "usd"),
                    fn.__name__)

    def test_the_doors_refuse_odds_too_long_to_draw(self):
        """"1 in 4,000" as four thousand doors is a grey rectangle. It falls
        through to the spinner, which can state any chance."""
        with _pil() as (d, canvas):
            rare = _Ins([_Pt("Hit", 0.02)], "percent", "t", "m")
            self.assertIsNone(vs.draw_doors(d, canvas, _BOX, rare,
                                            vs.HIGHLIGHT, 1.0, "percent"))


class BatchFiveIsThePhysicalComparisons(unittest.TestCase):
    """The last six: density, scale, scarcity, duration, records, buying power.

    Same discipline as the rest — the claim decides — and one extra rule that
    only shows up here: several of these encode a value as AREA or as a COUNT
    OF OBJECTS, and both are easy to overstate by accident. A density panel
    that scales the box as well as the packing double-counts the difference; a
    scale grid that fills its square exactly draws 81 tiles for "76 times
    over". Those are wrong numbers on screen, not rough pictures.
    """

    def test_the_claim_decides_here_too(self):
        pairs = [("A", 1000), ("B", 420)]
        for claim, want in (("people per square km", rel.DENSITY),
                            ("Tokyo is 12 times bigger", rel.SCALE),
                            ("40 applicants per opening", rel.SCARCITY),
                            ("what $100 buys", rel.BUYING_POWER),
                            ("most grand slam titles", rel.RECORD),
                            ("how long it takes to save for a home",
                             rel.DURATION)):
            self.assertEqual(rel.classify(_things(pairs, main=claim)), want,
                             claim)
        self.assertEqual(rel.classify(_things(pairs, main="A tops the list")),
                         rel.DUEL)

    def test_every_relationship_now_has_a_machine(self):
        """OTHER is the only one allowed to have none — it means draw a chart,
        and saying so is the honest answer."""
        names = {v for k, v in vars(rel).items()
                 if k.isupper() and isinstance(v, str) and not k.startswith("_")}
        missing = sorted(n for n in names - {rel.OTHER}
                         if not sr._MACHINES.get(n))
        self.assertEqual(missing, [], f"relationships with no picture: {missing}")

    def test_the_density_box_never_scales(self):
        """Scaling the panel as well as the packing would encode the same
        difference twice and overstate it."""
        import inspect
        src = inspect.getsource(vs.draw_density)
        self.assertIn("A FIXED grid", src)
        self.assertIn("cells = 14", src)

    def test_the_scale_grid_draws_the_RATIO_and_not_a_full_square(self):
        import inspect
        src = inspect.getsource(vs.draw_nest)
        self.assertIn("total = max(1, int(round(ratio)))", src)
        self.assertNotIn("total = across * across", src)

    def test_the_scale_grid_refuses_ratios_it_cannot_draw(self):
        with _pil() as (d, canvas):
            near = _Ins([_Pt("A", 1000), _Pt("B", 990)], "count", "t", "m")
            huge = _Ins([_Pt("A", 1000000), _Pt("B", 1)], "count", "t", "m")
            self.assertIsNone(vs.draw_nest(d, canvas, _BOX, near,
                                           vs.HIGHLIGHT, 1.0, "count"))
            self.assertIsNone(vs.draw_nest(d, canvas, _BOX, huge,
                                           vs.HIGHLIGHT, 1.0, "count"))

    def test_the_hourglass_leaves_the_duration_ON_SCREEN_at_the_end(self):
        """Draining the short wait faster is true of a real hourglass and
        useless here: both end empty, so the final frame — the one people look
        at — shows no difference at all. The pile left in the bottom is the
        number."""
        import inspect
        src = inspect.getsource(vs.draw_hourglass)
        self.assertIn("share = v / vmax", src)
        self.assertIn("lh = half * share * e", src)

    def test_the_shelf_refuses_a_tally_too_long_to_count(self):
        many = _Ins([_Pt("A", 210), _Pt("B", 140)], "count", "t", "m")
        with _pil() as (d, canvas):
            self.assertIsNone(vs.draw_trophies(d, canvas, _BOX, many,
                                               vs.HIGHLIGHT, 1.0, "count"))

    def test_the_chairs_need_a_real_shortage(self):
        """Equal numbers are not a shortage, and drawing one would invent the
        finding."""
        even = _Ins([_Pt("People", 500), _Pt("Seats", 500)], "count", "t", "m")
        with _pil() as (d, canvas):
            self.assertIsNone(vs.draw_chairs(d, canvas, _BOX, even,
                                             vs.HIGHLIGHT, 1.0, "count"))

    def test_the_basket_states_what_was_LOST(self):
        import inspect
        self.assertIn("less in the basket", inspect.getsource(vs.draw_basket))


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


class APictureMayNotClaimAWholeThatIsNotThere(unittest.TestCase):
    """The oldest bug in this channel, caught twice and fixed once.

    First form: "2019 IS 9% OF THE WHOLE" over a run of mortgage rates. Years
    do not sum. That was guarded — by a TIME-SERIES test, which is only half
    the rule.

    Second form, found in a live render on 2026-09-07: "EGGS IS 37% OF THE
    WHOLE" over eggs +37%, coffee +21%, beef +18%, bread +14%, milk +11% —
    six independent price increases. Not a time series, so the guard let it
    through; the director's `is_share` test was "the unit is a percent and
    there are at least three of them", the chart auto-routed to a stacked
    column, and the claim printed at 40pt. Eggs are 37% of nothing. They are a
    37% price increase.

    Percentages that do not sum are RATES, and rates never compose. The test
    lives in ONE place so the code that CHOOSES the chart and the code that
    writes the claim on it cannot disagree.

    Not a one-off: of the 133 percent-unit datasets with three or more items
    in `data_learning/data/`, 110 were eligible for that routing and do not
    compose. The 23 that do all sum to a hundred.
    """

    JUMPS = [("Eggs", 37), ("Coffee", 21), ("Beef", 18), ("Bread", 14),
             ("Milk", 11), ("All groceries", 10)]

    def _pct(self, pairs, topic):
        return _Ins([_Pt(a, b) for a, b in pairs], "percent", topic, topic)

    def test_price_increases_do_not_compose(self):
        self.assertFalse(rel.composes(
            self._pct(self.JUMPS, "price jump since 2020")))

    def test_parts_that_add_to_a_hundred_DO_compose(self):
        self.assertTrue(rel.composes(
            self._pct([("Rent", 34), ("Food", 22), ("Transport", 18),
                       ("Other", 26)], "household budget")))

    def test_a_claim_that_says_composition_composes(self):
        self.assertTrue(rel.composes(
            self._pct([("Owners", 62), ("Renters", 38)],
                      "share of all households")))

    def test_percentages_that_overshoot_a_hundred_do_not_compose(self):
        """"Infant care as share of income" sums to 118 across states: each
        item is a share of its OWN state's income, not of one pie. It says
        "share of" and does not compose, which is why the arithmetic decides
        and not the wording."""
        self.assertFalse(rel.composes(
            self._pct([("MA", 41), ("CA", 33), ("NY", 26), ("TX", 18)],
                      "infant care as a share of income")))

    def test_a_named_SUBSET_is_not_the_whole_either(self):
        """Three types totalling 8% of men are not a pie. Claiming "N% of the
        whole" would measure against a whole the picture never shows."""
        self.assertFalse(rel.composes(
            self._pct([("Deutan", 5), ("Protan", 2), ("Tritan", 1)],
                      "red-green colour blindness by type")))

    def test_years_still_do_not_compose(self):
        self.assertFalse(rel.composes(
            self._pct([("2019", 9), ("2020", 12), ("2021", 15)],
                      "the mortgage rate")))

    def test_a_dominant_slice_of_a_REAL_whole_still_composes(self):
        """`composes` is not `classify() == SHARE`. A composition where one
        slice dwarfs the rest comes back DOMINANCE and still adds to one."""
        ins = self._pct([("Housing", 71), ("Food", 12), ("Transport", 9),
                         ("Other", 8)], "a breakdown of the budget")
        self.assertEqual(rel.classify(ins), rel.DOMINANCE)
        self.assertTrue(rel.composes(ins))

    def test_the_subtitle_refuses_the_claim(self):
        from data_learning import charts
        jumps = self._pct(self.JUMPS, "price jump since 2020")
        sub = charts._whole_subtitle(jumps, jumps.items[0])
        self.assertNotIn("of the whole", sub.lower())
        self.assertIn("Eggs", sub)

    def test_the_segment_labels_refuse_it_too(self):
        """The same false claim in a smaller font is the same false claim.

        Coffee is a 21% price increase and 19% of the stacked column. The
        segment must read 21 — its own value — and never 19, which is a
        number nobody measured.
        """
        from data_learning import charts
        jumps = self._pct(self.JUMPS, "price jump since 2020")
        coffee = jumps.items[1]
        share = abs(coffee.value) / sum(abs(p.value) for p in jumps.items) * 100
        self.assertAlmostEqual(share, 19.0, delta=1.0)
        lab = charts._seg_label(jumps, coffee, share)
        self.assertIn("21", lab)
        self.assertNotIn("19", lab)

    def test_the_director_does_not_CHOOSE_a_composition_for_them(self):
        """Refusing to print the claim is not enough — a stacked column is a
        composition claim in geometry before it is one in words."""
        from data_learning import viz_director
        jumps = self._pct(self.JUMPS, "price jump since 2020")
        self.assertFalse(viz_director._features(jumps)["is_share"])
        real = self._pct([("Rent", 34), ("Food", 22), ("Transport", 18),
                          ("Other", 26)], "household budget")
        self.assertTrue(viz_director._features(real)["is_share"])


class OneMascotPerFrame(unittest.TestCase):
    """Every machine draws the host itself, so the travelling overlay has to
    be suppressed on any beat one of them owns — otherwise there are two
    mascots on screen.

    `render_scene` used to name `timeline_axis` alone, which was true when the
    scene kit was mostly still pictures. The moment a machine became a beat's
    PRIMARY depiction that list was wrong for forty of them.

    Held against the SOURCE in both directions, because a declared list is
    exactly the kind of thing that goes stale the next time a machine lands:
    one that bakes him and is missing from the set renders two mascots, and
    one listed that does not bake him renders none.
    """

    def _bakes(self, fn):
        import inspect
        return "scene_host(" in inspect.getsource(fn)

    def _real(self):
        extra = {"balance": vs.draw_balance, "race_track": vs.draw_race,
                 "unit_figures": vs.draw_unit_figures,
                 "dot_field": vs.draw_dot_field}
        real = {t for t, fn in vs._MACHINE_DRAW.items() if self._bakes(fn)}
        real |= {t for t, fn in extra.items() if self._bakes(fn)}
        return real | {"timeline_axis"}

    def test_nothing_declared_that_does_not_bake_him(self):
        ghosts = sorted(vs._SELF_HOSTING - self._real())
        self.assertEqual(ghosts, [],
                         f"declared self-hosting but draws no host: {ghosts}")

    def test_nothing_bakes_him_that_is_not_declared(self):
        missing = sorted(self._real() - vs._SELF_HOSTING)
        self.assertEqual(missing, [],
                         f"bakes the host but would get a second one: {missing}")

    def test_the_suppression_reads_the_set_and_not_one_name(self):
        import inspect
        src = inspect.getsource(vs.render_scene)
        self.assertIn("_SELF_HOSTING", src)


class TheMachinesActuallyREACHTheScreen(unittest.TestCase):
    """A library nothing reaches for is not a library.

    Measured on 2026-09-07, after all 42 machines were built, wired and
    documented: of the 933 configured explainer beats, 550 carried an authored
    scene that VALIDATED at assign time, was honoured, and then bailed at draw
    time to a fallback chart, because it was image-only and the channel runs
    with images off. Another 122 were authored as a lone `timeline_axis`,
    which does render — three of them in one video is three line charts, and
    the showrunner had already said so ("three near-identical chart layouts
    stretched over 96 seconds", scores 26-52).

    So the machines were reachable only through the "one line chart per video"
    post-pass — a tie-breaker on a repeat. This class holds the three rules
    that changed that, because each of them is easy to undo by accident.
    """

    def test_an_authored_scene_must_actually_RENDER_to_be_honoured(self):
        """`validate` asks whether a scene is well formed. That is not the
        same question as whether it can be drawn."""
        from data_learning import viz_director as vd
        ins = _things([("A", 5), ("B", 3)])
        image_only = {"title": True,
                      "elements": [{"type": "object", "region": "full",
                                    "subject": "house",
                                    "data": {"value_from": "star"}}]}
        drawable = {"title": True,
                    "elements": [{"type": "timeline_axis", "region": "full"}]}
        self.assertFalse(vd._renders_here(image_only, ins))
        self.assertTrue(vd._renders_here(drawable, ins))

    def test_a_generic_authored_scene_may_not_repeat(self):
        """A bespoke scene is distinct by construction. A lone `timeline_axis`
        is the same line with different numbers, and three in one video is
        three line charts."""
        from data_learning import viz_director as vd
        generic = {"elements": [{"type": "timeline_axis"}]}
        bespoke = {"elements": [{"type": "object", "subject": "house"},
                                {"type": "caption", "text": "x"}]}
        self.assertIsNotNone(vd._scene_signature(generic))
        self.assertIsNone(vd._scene_signature(bespoke))

    def test_the_machine_LEADS_and_the_chart_follows(self):
        """The ruling is that a chart is the fallback. Appending the machines
        after the beat's own chart made them a tie-breaker instead."""
        from data_learning import viz_director as vd
        ins = _things([("San Jose", 11.3), ("LA", 9.7), ("Miami", 8.2),
                       ("Seattle", 6.8)])
        cands = vd._candidates(ins, vd._features(ins))
        self.assertTrue(cands, "no depiction offered at all")
        self.assertIn(cands[0], vd._SCENE_BUILDERS,
                      f"a chart still leads: {cands[:4]}")

    def test_the_pool_rotates_so_one_machine_cannot_take_everything(self):
        """Reading `_MACHINES` directly instead of `_machines_for` skips the
        anti-template rotation, and handed all 429 of the catalogue's duels
        the same set of scales."""
        import inspect
        src = inspect.getsource(vd_src := __import__(
            "data_learning.viz_director", fromlist=["x"])._machine_candidates)
        self.assertIn("_machines_for", src)
        self.assertNotIn("_MACHINES.get", src)


class TheRegistryDocTellsTheTruth(unittest.TestCase):
    """`docs/DATA_MACHINES.md` is the map a future session reads before it
    touches any of this. A doc that lists a machine the code does not have —
    or omits one it does — is the failure CLAUDE.md calls rule zero: it reads
    as progress and inherits as a lie.
    """

    @property
    def doc(self):
        return (Path(__file__).resolve().parents[1]
                / "docs" / "DATA_MACHINES.md").read_text(encoding="utf-8")

    def test_the_doc_exists_and_names_the_three_files(self):
        for f in ("relationships.py", "studio_render.py", "viz_scene.py"):
            self.assertIn(f, self.doc)

    def test_every_relationship_with_a_machine_is_in_the_doc(self):
        doc = self.doc
        missing = sorted(k for k in sr._MACHINES
                         if k != rel.OTHER and f"`{k}`" not in doc)
        self.assertEqual(missing, [], f"undocumented relationships: {missing}")

    def test_every_machine_the_doc_names_actually_exists(self):
        """Only the REGISTRY TABLES are scanned — the rows beginning with a
        pipe. The prose names functions too (`render_scene`), and a first cut
        of this test flagged that as a missing machine, which is the test
        being wrong rather than the doc."""
        import re as _re
        rows = [ln for ln in self.doc.splitlines() if ln.lstrip().startswith("|")]
        named = set(_re.findall(r"`([a-z_]+_scene)`", "\n".join(rows)))
        ghosts = sorted(t for t in named if t not in sr._SCENE_TOKENS
                        and t not in sr._SELF_HOSTED)
        self.assertEqual(ghosts, [], f"documented but unbuilt: {ghosts}")

    def test_every_machine_in_the_router_is_in_the_doc(self):
        doc = self.doc
        used = {m for t in sr._MACHINES.values() for m in t}
        missing = sorted(m for m in used if f"`{m}`" not in doc)
        self.assertEqual(missing, [], f"undocumented machines: {missing}")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class NoPictureInventsANumber(unittest.TestCase):
    """Found by watching a finished video, not by a test — which is why this
    class exists now.

    The spotlight's marker wanders inside the range, because the finding is
    that the number never settled. It also PRINTED where it happened to be,
    at 52pt, in the same type as a fact. Three seconds of one beat read
    "$1,164.9B", "$1,154.2B", "$1,282.5B" — positions in a wobble, not
    measurements. The two ends of the lane are real and stay labelled.

    And `_superlative`: the subtitle used `items[0]`, which is the strongest
    item on a ranking and the EARLIEST on a trend. A rising series rendered as
    bars therefore announced "2019 TOPS THE LIST" over a chart whose tallest
    bar was 2026 and whose highlight was on 2026 — caption and picture
    contradicting each other, in the caption's favour.
    """

    def test_the_spotlight_marker_prints_no_value(self):
        import inspect
        src = inspect.getsource(vs.draw_spotlight)
        self.assertIn("THE MARKER CARRIES NO NUMBER", src)
        self.assertNotIn("cur = lo + (hi - lo) * wob", src)

    def test_the_spotlight_still_labels_the_REAL_ends(self):
        import inspect
        src = inspect.getsource(vs.draw_spotlight)
        self.assertIn("charts._ulabel(lo, unit)", src)
        self.assertIn("charts._ulabel(hi, unit)", src)

    def test_a_superlative_names_the_item_that_actually_leads(self):
        from data_learning import charts as ch
        rising = _Ins([_Pt(str(2019 + k), v) for k, v in
                       enumerate([930, 1000, 860, 990, 1130, 1210, 1290,
                                  1370])],
                      "usd", "credit card debt", "it climbed")
        sub = ch._superlative(rising, False)
        self.assertIn("2026", sub)
        self.assertNotIn("2019", sub)

    def test_years_are_not_called_competitors(self):
        """"2026 tops the list" is true and still the wrong sentence: years do
        not compete with each other."""
        from data_learning import charts as ch
        rising = _Ins([_Pt(str(2019 + k), 900 + k * 60) for k in range(8)],
                      "usd", "credit card debt", "it climbed")
        self.assertNotIn("tops the list", ch._superlative(rising, False))
        self.assertIn("highest in", ch._superlative(rising, False))

    def test_a_real_ranking_still_gets_ranking_language(self):
        from data_learning import charts as ch
        cities = _Ins([_Pt("San Jose", 11.3), _Pt("LA", 9.7),
                       _Pt("Miami", 8.2)], "years", "cost", "San Jose leads")
        self.assertEqual(ch._superlative(cities, False),
                         "San Jose tops the list")
        self.assertEqual(ch._superlative(cities, True), "Miami sits lowest")

    def test_it_never_raises_on_empty_or_broken_items(self):
        from data_learning import charts as ch
        self.assertEqual(ch._superlative(_Ins([], "", "t", "m"), False), "")


class TheUnitSaysWhatKindOfQuantityThisIs(unittest.TestCase):
    """Batch 6, and the measurement that forced it.

    Over the 1,104 live datasets on 2026-09-08 `duration` classified exactly
    ONE, while 106 are published in years/hours/days, 60 in miles or feet and
    30 in mph. The hourglass was built, wired, documented and tested, and it
    led about one beat in a thousand — because every specialised relationship
    was detected from the CLAIM, and a dataset title says "Maximum recorded
    lifespan by animal (years)", not "how long".

    A unit is not an inference the way a claim is. It is a declared property
    of the measurement, published by the source.
    """

    def _ins(self, pairs, unit, topic="t"):
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-08")
        return Insight(kind="rank", topic=topic, main_insight="",
                       items=[DataPoint(label=str(a), value=float(b))
                              for a, b in pairs],
                       source=src, unit=unit,
                       highlight_label=str(pairs[0][0]))

    def test_a_pair_measured_in_time_is_a_DURATION(self):
        self.assertEqual(
            rel.classify(self._ins([("Apex predator", 20.0),
                                    ("Prey animal", 1.9)], "hours")),
            rel.DURATION)

    def test_a_speed_is_a_SPEED_and_a_distance_is_a_DISTANCE(self):
        self.assertEqual(
            rel.classify(self._ins([("Peregrine", 240), ("Swift", 105),
                                    ("Frigatebird", 100)], "mph")),
            rel.SPEED)
        self.assertEqual(
            rel.classify(self._ins([("Arctic tern", 44000),
                                    ("Sooty shearwater", 22000),
                                    ("Humpback", 18000)], "miles")),
            rel.DISTANCE)

    def test_a_DATE_is_not_a_duration(self):
        """"Deadliest pandemics" is published in years and its values are 1350
        and 1918. Sand running for 1,918 years is a picture of nothing."""
        self.assertNotEqual(
            rel.classify(self._ins([("Black Death", 1350),
                                    ("Spanish flu", 1918)], "years")),
            rel.DURATION)
        # ... and a real span that happens to look like one is refused in the
        # SAFE direction — it falls through to a ranking, which is honest.
        self.assertEqual(
            rel.classify(self._ins([("Bristlecone", 4900),
                                    ("Oak", 400)], "years")),
            rel.DURATION)

    def test_a_HEIGHT_is_not_a_journey(self):
        """Tallest and deepest are measured in feet too, and a measuring tape
        laid out flat is the wrong picture for both. They belong to the
        skyline, which dominance and rank already reach."""
        for topic in ("Tallest buildings in the world",
                      "Deepest point in each ocean",
                      "Highest altitude reached"):
            self.assertNotEqual(
                rel.classify(self._ins([("A", 2722), ("B", 1500),
                                        ("C", 1100)], "feet", topic)),
                rel.DISTANCE, topic)

    def test_a_RUNAWAY_LEADER_keeps_the_skyline(self):
        """Lightning at 270,000mph against a peregrine at 240 is exactly the
        broken chart `race_scene` warns about in its own docstring."""
        self.assertEqual(
            rel.classify(self._ins([("Lightning", 270000), ("Peregrine", 240),
                                    ("Cheetah", 70)], "mph")),
            rel.DOMINANCE)

    def test_the_dominance_test_is_defined_ONCE(self):
        """It is used by the tail of `_classify` as the DOMINANCE rule and by
        the unit rules as the thing they stand down for. Two copies drift."""
        import inspect
        src = inspect.getsource(rel._classify)
        self.assertEqual(src.count("_dominant("), 2)
        self.assertNotIn("3.0 * (sum(rest)", src)

    def test_a_THEN_AND_NOW_is_not_two_waits(self):
        """Caught by the existing before/after test the moment the unit rules
        landed: "commute in 2019 vs 2026, in hours" is ONE subject at two
        dates, and two hourglasses side by side says it is two different
        waits. The date test is defined once and both rules use it."""
        self.assertEqual(
            rel.classify(self._ins([("2019", 27.0), ("2026", 44.0)], "hours")),
            rel.BEFORE_AFTER)
        import inspect
        self.assertEqual(
            inspect.getsource(rel._classify).count("_dated_pair("), 2)

    def test_durations_route_in_PAIRS_only(self):
        """The hourglass draws two glasses and the tape has two ends. A
        six-item duration ranking sent there drops four rows silently."""
        six = [(str(k), 10.0 + k) for k in range(6)]
        self.assertNotEqual(rel.classify(self._ins(six, "hours")),
                            rel.DURATION)

    def test_an_explicit_CLAIM_still_beats_the_unit(self):
        """The unit rules run last among the specialised checks on purpose."""
        self.assertEqual(
            rel.classify(self._ins([("Applicants", 41000), ("Homes", 1200)],
                                   "years",
                                   "applicants per opening in the shortage")),
            rel.SCARCITY)

    def test_both_new_relationships_have_machines_that_exist(self):
        for name in (rel.SPEED, rel.DISTANCE):
            machines = sr._MACHINES.get(name)
            self.assertTrue(machines, f"{name} classifies but draws nothing")
            for m in machines:
                self.assertTrue(callable(getattr(vs, m, None)), f"{name}->{m}")


class AMachineRefusesWhatItCannotDraw(unittest.TestCase):
    """Two silent failures, both of which put a false frame on screen.

    Every draw function slices its items, and the builders accepted any
    number — so the extras went to a slice that dropped them. Two of six waits
    drawn as "the comparison" is a DIFFERENT comparison, and nothing
    downstream could see it happen.
    """

    def _ins(self, vals, unit="hours"):
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-08")
        return Insight(kind="rank", topic="t", main_insight="",
                       items=[DataPoint(label=str(i), value=float(v))
                              for i, v in enumerate(vals)],
                       source=src, unit=unit, highlight_label="0")

    def test_no_builder_accepts_more_rows_than_its_machine_draws(self):
        """MEASURED against the draw functions themselves, so a new machine
        with a `[:n]` slice and no cap is caught the day it lands."""
        import inspect
        import re as _re
        # The rankings, where showing the top n of many IS the picture and
        # reads as one. Everything else claims to show the whole set.
        RANKINGS = {"skyline", "trophies"}
        bad = {}
        for kind, fn in sorted(vs._MACHINE_DRAW.items()):
            if kind in RANKINGS:
                continue
            m = _re.search(r"_ordered_items\(insight\)\[:(\d+)\]",
                           inspect.getsource(fn))
            if not m:
                continue
            cap = int(m.group(1))
            build = getattr(vs, f"{kind}_scene", None)
            if build is None:
                continue
            if build(self._ins([10.0 + k for k in range(cap + 2)])):
                bad[kind] = cap
        self.assertEqual(bad, {},
                         f"builders that accept rows they will drop: {bad}")

    def test_a_ratio_no_picture_can_show_is_refused(self):
        """2.94e16 miles against 250 draws the second at zero pixels, and the
        frame then says the ISS is nowhere."""
        self.assertFalse(vs.race_scene(self._ins([2.94e16, 250], "miles")))
        self.assertTrue(vs.race_scene(self._ins([44000, 22000], "miles")))

    def test_a_zero_runs_but_does_not_pour(self):
        """A runner on the start line is readable and is what the number
        says. An empty hourglass is indistinguishable from a finished one."""
        self.assertTrue(vs.race_scene(self._ins([70, 0], "mph")))
        self.assertFalse(vs.hourglass_scene(self._ins([70, 0])))

    def test_the_hourglass_refuses_a_wait_it_cannot_show(self):
        self.assertTrue(vs.hourglass_scene(self._ins([20, 2])))
        self.assertFalse(vs.hourglass_scene(self._ins([3000, 15])))


class NoMachineEatsTheCatalogue(unittest.TestCase):
    """Operator, 2026-09-08: *"we are going to use some graphs and non graphs
    too much and some not at all."*

    They were right, and it was measurable. Over the 944 real beats in
    `niche.config.json`, three machines took HALF of them — `units_scene`
    20%, `race_scene` 16.6%, `balance_scene` 13.9% — while ten machines led
    nothing at all.

    The cause was not the rotation, which works and is keyed on the story so
    a re-render is stable. It was the candidate LISTS: `units_scene` was
    named by ten of forty-one relationships, `balance_scene` by eight,
    `race_scene` by six. Rotation shares a relationship's beats evenly among
    its candidates, so a machine listed everywhere wins everywhere.

    The fix was to widen the three crowded relationships with machines that
    are honest for them and REFUSE what they cannot say — the tape needs two
    magnitudes it can lay end to end, the nest only draws a ratio between
    1.5x and 150x, the shelf refuses above thirty trophies. Nothing was
    forced: a machine that does not fit falls through exactly as before.
    """

    def _beats(self):
        import json
        from data_learning import beat_claims as bc
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        root = Path(__file__).resolve().parent.parent
        cfg = json.loads((root / "data_learning" / "niche.config.json").read_text())
        data = root / "data_learning" / "data"
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-08")
        out = []
        for s in cfg["stories"]:
            beats = []
            for seg in (s.get("segments") or []):
                f = (seg.get("params") or {}).get("file")
                p = data / f if f else None
                if not p or not p.exists():
                    continue
                d = json.loads(p.read_text())
                pts = [DataPoint(label=str(x["label"]), value=float(x["value"]))
                       for x in d.get("points", []) if x.get("value") is not None]
                if len(pts) < 2:
                    continue
                beats.append(Insight(
                    kind=seg.get("insight_type", "rank"),
                    topic=seg.get("topic", ""), main_insight=seg.get("say", ""),
                    items=pts, source=src, unit=d.get("unit", ""),
                    highlight_label=str(pts[0].label)))
            if len(beats) > 1:
                beats = bc.prune_restatements(beats, floor=2)[0]
            out.extend(beats)
        return out

    def test_no_three_machines_take_half_the_channel(self):
        """MEASURED over the real catalogue, because the failure this catches
        is invisible in any single video: every beat is individually well
        chosen and the channel still looks like it owns four pictures."""
        import collections
        beats = self._beats()
        self.assertGreater(len(beats), 800, "the catalogue did not load")
        lead = collections.Counter()
        for ins in beats:
            ms = sr._machines_for(ins)
            lead[ms[0] if ms else "(chart)"] += 1
        top3 = sum(v for _, v in lead.most_common(3)) / len(beats)
        # 0.505 before this landed, 0.367 after. 0.45 leaves room for the
        # catalogue to drift without letting it slide back to half.
        self.assertLess(top3, 0.45,
                        f"three machines carry {top3:.1%}: {lead.most_common(4)}")

    def test_no_single_machine_is_named_by_a_quarter_of_the_router(self):
        """`units_scene` was in ten of forty-one lists. A machine listed
        everywhere wins everywhere, whatever the rotation does."""
        import collections
        cnt = collections.Counter()
        for ms in sr._MACHINES.values():
            for m in ms:
                cnt[m] += 1
        worst, n = cnt.most_common(1)[0]
        self.assertLessEqual(n / len(sr._MACHINES), 0.25,
                             f"{worst} is named by {n} of {len(sr._MACHINES)}")

    def test_the_widened_lists_still_refuse_what_they_cannot_draw(self):
        """The whole reason widening is safe. If any of the three additions
        ever stops refusing, a duel of 1 against 2,000,000 gets a measuring
        tape with one end off the frame."""
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-08")

        def _i(pairs):
            return Insight(kind="comparison", topic="t", main_insight="",
                           items=[DataPoint(label=a, value=float(b))
                                  for a, b in pairs],
                           source=src, unit="count", highlight_label=pairs[0][0])
        # the nest refuses a ratio it cannot tile
        self.assertFalse(vs.nest_scene(_i([("A", 1.0), ("B", 1.2)])))
        # the shelf refuses a tally too long to count
        self.assertFalse(vs.trophies_scene(_i([("A", 400), ("B", 380)])))

    def test_every_widened_candidate_is_a_machine_that_exists(self):
        for name in ("duel", "rank", "dominance"):
            for m in sr._MACHINES[name]:
                self.assertTrue(
                    m in sr._SCENE_TOKENS or hasattr(vs, m) or m in ("orbit",),
                    f"{name} -> {m} names nothing")


class ABuilderNeverAcceptsWhatItsDrawingRefuses(unittest.TestCase):
    """The hole that widening the router opened, and the reason it is worth a
    sweep rather than three patches.

    `nest_scene` and `trophies_scene` were built by the generic factory,
    which only ever counted items — while `draw_nest` refuses a ratio outside
    1.5x..150x and `draw_trophies` refuses a tally over thirty. So the
    builder said yes, the director spent the beat on that machine, the draw
    returned None, and the render degraded to a chart: a slot spent, no
    variety, and nothing anywhere saying why. Invisible in every log.

    It only started to matter when those two were added to `duel`, `rank` and
    `dominance` — 53% of the catalogue — which is exactly when a latent bug
    becomes a daily one.
    """

    def _cases(self):
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-08")

        def mk(pairs, unit="count", topic="t"):
            return Insight(kind="comparison", topic=topic, main_insight="",
                           items=[DataPoint(label=a, value=float(b))
                                  for a, b in pairs],
                           source=src, unit=unit,
                           highlight_label=pairs[0][0])
        return [
            ("a pair that barely differs", mk([("A", 100), ("B", 98)])),
            ("a pair that differs enormously", mk([("A", 1e6), ("B", 1)])),
            ("a tally too long for a shelf", mk([("A", 400), ("B", 380)])),
            ("a zero", mk([("A", 50), ("B", 0)])),
            ("three of a kind", mk([("A", 9), ("B", 6), ("C", 3)])),
        ]

    def test_every_builder_the_hot_lists_use_agrees_with_its_drawing(self):
        """The three biggest relationships are 53% of the catalogue. A
        builder/draw disagreement anywhere in their candidate lists is a
        chart shipped in place of a machine, every day, silently."""
        from PIL import Image, ImageDraw
        from data_learning import charts
        hot = {m for name in ("duel", "rank", "dominance")
               for m in sr._MACHINES[name]}
        bad = []
        for label, ins in self._cases():
            for m in sorted(hot):
                build = getattr(vs, m, None)
                if not callable(build):
                    continue          # `orbit` and friends are not scenes
                spec = build(ins)
                if not spec:
                    continue          # refused honestly, nothing to check
                kind = (spec.get("elements") or [{}])[0].get("type")
                draw = vs._MACHINE_DRAW.get(kind)
                if draw is None:
                    continue
                img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
                got = vs._guarded(kind, draw, ImageDraw.Draw(img), img, _BOX,
                                  vs.drawable_insight(ins) or ins,
                                  charts.HIGHLIGHT, 0.95, ins.unit)
                if got is None:
                    bad.append(f"{m} accepted {label} and drew nothing")
        self.assertEqual(bad, [], "; ".join(bad))

    def test_the_nest_band_has_one_definition(self):
        import inspect
        self.assertIn("NEST_MIN", inspect.getsource(vs.draw_nest))
        self.assertIn("NEST_MIN", inspect.getsource(vs.nest_scene))
        # The BAND is what must not be re-written as a literal — not the
        # digits. A first version banned the bare string "150" and then
        # failed on `by0 + 150`, an unrelated y-offset in a comment about a
        # different bug entirely: a proximity check wearing the clothes of a
        # semantic one, which is the same mistake the restatement detector
        # made with its 600-character window.
        src = inspect.getsource(vs.draw_nest)
        self.assertNotIn("ratio > 150", src)
        self.assertNotIn("ratio < 1.5", src)

    def test_the_shelf_limit_has_one_definition(self):
        import inspect
        self.assertIn("TROPHY_MAX", inspect.getsource(vs.draw_trophies))
        self.assertIn("TROPHY_MAX", inspect.getsource(vs.trophies_scene))


class TheTapeDEPICTSItsNumbers(unittest.TestCase):
    """A regression found by auditing a change from the same day it landed.

    `tape_scene` was added to `duel` — 30% of the catalogue — to spread the
    load off three overused machines. Then the tape was measured: it ran from
    one edge of the frame to the other whatever the numbers were, and printed
    them as text at each end. A 30/70 pair and a 49/51 pair came out **99.5%
    identical, pixel for pixel** — same tape, same posts, same ground, only
    the digits different.

    That is the showrunner's `bare_number_card` verbatim: the number is
    stated, not demonstrated. It was survivable while the tape only drew
    `delta`, where the gap IS the whole claim; picking it for a duel because
    it improved a distribution statistic was choosing a picture for the wrong
    reason entirely.

    Now the ruler runs 0..max, each post stands at its own value, and the
    tape spans between them.
    """

    def _tape(self, pairs, reveal=1.0):
        from PIL import Image, ImageDraw
        from data_learning import charts
        from data_learning.insights import Insight
        from data_learning.sources.base import DataPoint, Source
        src = Source(name="X", publisher="Y", url="https://x",
                     access_date="2026-09-08")
        ins = Insight(kind="comparison", topic="t", main_insight="",
                      items=[DataPoint(label=a, value=float(b))
                             for a, b in pairs],
                      source=src, unit="percent",
                      highlight_label=pairs[0][0])
        img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        vs._guarded("tape", vs._MACHINE_DRAW["tape"], ImageDraw.Draw(img),
                    img, _BOX, vs.drawable_insight(ins), charts.HIGHLIGHT,
                    reveal, "percent")
        return img

    def test_two_different_duels_do_not_draw_the_same_picture(self):
        try:
            import numpy as np
        except ImportError:  # noqa: BLE001
            self.skipTest("numpy not installed")
        a = np.asarray(self._tape([("Left", 30), ("Right", 70)]).split()[-1],
                       dtype=np.float32)
        b = np.asarray(self._tape([("Left", 49), ("Right", 51)]).split()[-1],
                       dtype=np.float32)
        differ = (np.abs(a - b) > 8).mean()
        # 0.005 before the fix (the digits alone), 0.025 after. The bar is
        # deliberately just above the text-only floor: what it forbids is a
        # picture whose GEOMETRY ignores its data.
        self.assertGreater(differ, 0.012,
                           f"a 30/70 and a 49/51 draw the same tape ({differ:.3f})")

    def test_the_posts_stand_at_the_VALUES(self):
        import inspect
        src = inspect.getsource(vs.draw_tape)
        self.assertIn("def _pos(", src)
        self.assertIn("abs(v) / vmax", src)
        # the old fixed-width span is gone
        self.assertNotIn("(bx1 - 90 - x0) * e", src)

    def test_the_tape_is_YANKED_open_not_slid(self):
        """CI measured a 44-frame frozen run the first time the tape spanned
        only the gap rather than the whole frame — the end advanced 3.6px a
        frame at 1080 wide, which is 0.6px once the detector downsamples, on
        a band 8px tall. Locally the same machine measured 15, so the source
        is the only place this is pinned; the rendered check lives in
        `MotionMustBeVISIBLE`, which is what caught it."""
        import inspect
        src = inspect.getsource(vs.draw_tape)
        self.assertIn("TAPE_PULLS", src)
        self.assertIn("_math.floor", src)
        self.assertGreaterEqual(vs.TAPE_PULLS, 8,
                                "too few pulls and the tape jumps in halves")

    def test_it_still_says_how_far_APART(self):
        """The gap is still the headline — the fix changed how the picture is
        drawn, not what it claims."""
        import inspect
        self.assertIn("apart", inspect.getsource(vs.draw_tape))
