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

    def test_a_volatile_series_is_left_as_a_line(self):
        """A chart is a weaker picture and a fine one. A confident wrong
        metaphor is neither, so `volatile` maps to no machine at all."""
        self.assertEqual(sr._MACHINES["volatile"], ())

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
