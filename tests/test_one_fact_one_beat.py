"""ONE FACT IS ONE BEAT.

Operator, 2026-09-08, on a video that had just posted: *"we would say the same
thing in 3 different beats just show it a different way that's dumb af."*

`driving-side-of-the-road`, verbatim from the config:

    beat 1  30% of the world's PEOPLE drive on the left        30 / 70
    beat 2  76 COUNTRIES on the left, 163 on the right         32 / 68
    beat 3  25% of the world's ROAD MILES are left-hand        25 / 75

Three datasets, three machines, one fact — and beat three's narration says
"it's even more lopsided", which 75/25 is not.

Half of these tests exist for the DETECTOR'S OWN MISTAKES. Three false
positives were caught by hand before this shipped, and each one would have
deleted a real beat from a working video, which is a worse failure than the
bug being fixed. They are pinned here as cases that must always survive.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_learning import beat_claims as bc          # noqa: E402
from data_learning.insights import Insight           # noqa: E402
from data_learning.sources.base import DataPoint, Source  # noqa: E402

SRC = Source(name="X", publisher="Y", url="https://x", access_date="2026-09-08")


def ins(pairs, unit="percent", topic="t", kind="comparison"):
    return Insight(kind=kind, topic=topic, main_insight="",
                   items=[DataPoint(label=str(a), value=float(b))
                          for a, b in pairs],
                   source=SRC, unit=unit, highlight_label=str(pairs[0][0]))


class TheDrivingSideVideo(unittest.TestCase):
    """The case that prompted all of this, with its real numbers."""

    P = ins([("Left-hand traffic", 30), ("Right-hand traffic", 70)])
    C = ins([("Drive on the right", 163), ("Drive on the left", 76)],
            unit="count")
    R = ins([("Right-hand traffic roadways", 75),
             ("Left-hand traffic roadways", 25)])

    def test_countries_restate_population(self):
        self.assertTrue(bc.restates(self.P, self.C))

    def test_road_miles_restate_population(self):
        self.assertTrue(bc.restates(self.P, self.R))

    def test_the_units_do_not_save_it(self):
        """Percent, then a count, then percent again. Changing what you
        measure is not changing what you SAY."""
        self.assertNotEqual(self.P.unit, self.C.unit)
        self.assertTrue(bc.restates(self.P, self.C))


class TheMistakesTheDetectorMade(unittest.TestCase):
    """Every one of these was flagged by a version of this code, checked by
    hand, and found to be a real beat. They are the reason the rules are as
    narrow as they are."""

    def test_a_RANKING_is_not_a_restatement_of_a_ranking(self):
        """`two-americas-cost` — cost-of-living index, then household income,
        then rent, across the same six states. Three different facts, and the
        story's point is that they DIVERGE. They were flagged because any
        six-item ranking of a positive quantity normalises to the same gentle
        descending curve, and the shared state names made the subject check
        vote to convict."""
        cost = ins([("Hawaii", 184), ("California", 142), ("New York", 125),
                    ("Massachusetts", 123), ("Texas", 93), ("Mississippi", 85)],
                   unit="index")
        rent = ins([("California", 2150), ("Hawaii", 2100), ("New York", 1980),
                    ("Massachusetts", 1850), ("Texas", 1290),
                    ("Mississippi", 950)], unit="dollars")
        self.assertFalse(bc.restates(cost, rent))

    def test_a_LOPSIDED_split_is_not_a_slightly_less_lopsided_one(self):
        """`colorblind-by-the-numbers` — 8% of men vs 0.5% of women is 94/6;
        8% vs achromatopsia's 0.0033% is 99.96/0.04. A flat tolerance called
        those the same because they differ by 0.058 in absolute terms, while
        the minority share differs by a factor of 150. On screen one is a
        sliver and the other is invisible."""
        gap = ins([("Men", 8), ("Women", 0.5)])
        total = ins([("Any red-green deficiency (men)", 8),
                     ("Total colorblindness (achromatopsia)", 0.0033)])
        self.assertFalse(bc.restates(gap, total))

    def test_the_STORYS_OWN_TOPIC_is_not_evidence_of_anything(self):
        """`fruit-is-not-created-equal` — a banana tree's yield against an
        apple tree's, then watermelon's water content against a date's. The
        ratios are close and the labels share nothing; they matched only on
        the word "fruit", which every beat in that story carries by
        construction."""
        yield_ = ins([("Banana tree", 100), ("Apple tree", 20)],
                     unit="pounds", topic="Fruit Yield")
        water = ins([("Watermelon", 92), ("Date", 21)],
                    topic="Fruit Water Content")
        self.assertFalse(bc.restates(yield_, water))

    def test_two_things_that_both_rose_are_two_facts(self):
        """`housing-affordability-wall` — house prices climbing and mortgage
        rates climbing over the same eight years. Both are rising series of
        the same length; the story is that BOTH happened."""
        prices = ins([(str(2019 + k), v) for k, v in
                      enumerate([270, 300, 360, 410, 418, 428, 440, 449])],
                     unit="thousand dollars", kind="trend")
        rates = ins([(str(2019 + k), v) for k, v in
                     enumerate([3.9, 3.1, 2.96, 5.34, 6.81, 6.72, 6.55, 6.62])],
                    kind="trend")
        self.assertFalse(bc.restates(prices, rates))

    def test_matching_numbers_with_nothing_else_in_common_are_two_facts(self):
        a = ins([("Left-hand traffic", 30), ("Right-hand traffic", 70)])
        b = ins([("Households with a cat", 30), ("Households without", 70)])
        self.assertFalse(bc.restates(a, b))


class ItAlsoCatchesTheOnesNobodyReported(unittest.TestCase):
    def test_the_same_two_numbers_with_one_label_changed(self):
        """`thinnest-materials-ever-made`, beats one and two: 0.34 against
        1.1, then 0.34 against 1.1 again with "Few-layer graphene" renamed
        "Silicon"."""
        a = ins([("Single-layer graphene", 0.34), ("Few-layer graphene", 1.1)],
                unit="nanometers")
        b = ins([("Graphene", 0.34), ("Silicon", 1.1)], unit="nanometers")
        self.assertTrue(bc.restates(a, b))

    def test_the_same_ranking_measured_three_ways(self):
        """`the-deepest-ocean`: depth, then zone count, then pressure — the
        same three trenches in the same order with the same spacing every
        time. Every beat says "Mariana is biggest, Tonga next".

        The real topics matter here and are not decoration: "Deepest Oceans"
        trips the router's VERTICAL guard, so the depths classify as a
        ranking rather than a distance and both beats land on the same
        relationship. Rule 1 compares relationships, so a beat re-measured
        into a different unit FAMILY can still slip past — a known limit,
        recorded rather than papered over."""
        depth = ins([("Mariana Trench", 36000), ("Tonga Trench", 35000),
                     ("Kermadec Trench", 32000)], unit="feet", kind="rank",
                    topic="Deepest Oceans")
        zones = ins([("Mariana Trench", 5), ("Tonga Trench", 4),
                     ("Kermadec Trench", 3)], unit="count", kind="rank",
                    topic="Ocean Zones")
        self.assertTrue(bc.restates(depth, zones))


class PruningNeverEmptiesAStory(unittest.TestCase):
    """A one-beat video is not an improvement on a repetitive one, and an
    empty slot is worse than both. The renderer produces the least repetitive
    cut a story can make; refusing belongs at authoring time."""

    def _driving(self):
        return [TheDrivingSideVideo.P, TheDrivingSideVideo.C,
                TheDrivingSideVideo.R]

    def test_it_keeps_the_floor_and_picks_the_FURTHEST_survivor(self):
        kept, dropped = bc.prune_restatements(self._driving(), floor=2)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(dropped), 1)
        # 30/70 and 25/75 are further apart than 30/70 and 32/68, so the
        # country count is the one that goes.
        self.assertIs(kept[1], TheDrivingSideVideo.R)

    def test_the_storys_own_ORDER_survives_pruning(self):
        """The narration was written in that order — `says[i]` is authored
        against beat i, and a re-admitted beat that jumps the queue would be
        read out over the wrong picture."""
        kept, _ = bc.prune_restatements(self._driving(), floor=2)
        self.assertIs(kept[0], TheDrivingSideVideo.P)

    def test_without_a_floor_it_prunes_all_the_way_down(self):
        kept, _ = bc.prune_restatements(self._driving())
        self.assertEqual(len(kept), 1)

    def test_a_story_of_real_beats_is_untouched(self):
        beats = [ins([("A", 90), ("B", 10)], topic="one"),
                 ins([("C", 55), ("D", 45)], topic="two"),
                 ins([("E", 30), ("F", 70)], topic="three")]
        kept, dropped = bc.prune_restatements(beats, floor=2)
        self.assertEqual(dropped, [])
        self.assertEqual(len(kept), 3)


class ItDoesNotStrandASentence(unittest.TestCase):
    """The narration is authored per beat and travels with its segment, so a
    cut is usually invisible. It is not invisible when the NEXT beat opens by
    pointing backwards — `driving-side-of-the-road` beat three begins "It's
    even more lopsided in road miles", and cutting the beat in front of it
    leaves that sentence reaching for something nobody saw.

    One story in the twenty-one that prune hits this, which is exactly the
    frequency at which a bug ships unnoticed."""

    def test_a_backward_leaning_opener_is_recognised(self):
        self.assertTrue(bc.leans_backward(
            "It's even more lopsided in road miles: right-hand traffic..."))
        self.assertTrue(bc.leans_backward("That's nearly double."))
        self.assertFalse(bc.leans_backward(
            "About 163 countries and territories drive on the right."))

    def test_a_restatement_its_neighbour_leans_on_is_kept(self):
        beats = [TheDrivingSideVideo.P, TheDrivingSideVideo.C,
                 TheDrivingSideVideo.R]
        says = ["Only about 30 percent of the world's population...",
                "It's not 50/50 either. About 163 countries...",
                "It's even more lopsided in road miles..."]
        kept, dropped = bc.prune_restatements(beats, floor=2, says=says)
        self.assertEqual(len(kept), 3, "the leaned-on beat was cut anyway")
        self.assertEqual(dropped, [])

    def test_without_the_lean_it_still_prunes(self):
        beats = [TheDrivingSideVideo.P, TheDrivingSideVideo.C,
                 TheDrivingSideVideo.R]
        says = ["Only about 30 percent...", "About 163 countries...",
                "Road miles are lopsided too..."]
        kept, dropped = bc.prune_restatements(beats, floor=2, says=says)
        self.assertEqual(len(kept), 2)

    def test_the_render_path_passes_the_narration_in(self):
        """A guard the caller never feeds is a guard that does nothing."""
        import inspect
        from data_learning import story
        self.assertIn("says=", inspect.getsource(story.build))


class TheRenderPathActuallyRunsIt(unittest.TestCase):
    """Rule zero: a capability nothing calls is not a capability. This was
    the state five modules were in at the 2026-08-01 audit."""

    def test_story_build_prunes_restated_beats(self):
        import inspect
        from data_learning import story
        src = inspect.getsource(story.build)
        self.assertIn("prune_restatements", src)
        self.assertIn("floor=2", src)

    def test_it_says_out_loud_which_beats_it_dropped(self):
        """A silent cut is how a bug hides for weeks."""
        import inspect
        from data_learning import story
        self.assertIn("restated beat", inspect.getsource(story.build))


class RefusingHappensWhereThereIsAnotherStoryToRender(unittest.TestCase):
    """Pruning is salvage; it cannot invent a second fact. Refusing is the
    right answer only where the queue has another story — which is true in
    the pre-render gate and false in the renderer.

    `one_fact_stretched` shipped in #338 with NO CALLER, which is the exact
    thing rule zero forbids: a capability nothing calls is not a capability,
    and the module docstring claiming stories were "refused" was a lie the
    next session would have inherited."""

    def test_the_pre_render_gate_calls_it(self):
        import inspect
        from scripts import editorial_gate as eg
        self.assertIn("one_fact_stretched",
                      inspect.getsource(eg.beats_are_distinct))
        self.assertIn("beats_are_distinct",
                      inspect.getsource(eg.pre_render_verdict))

    def test_the_driving_story_is_refused_before_it_renders(self):
        import json
        from scripts import editorial_gate as eg
        cfg = json.loads((Path(__file__).resolve().parent.parent
                          / "data_learning" / "niche.config.json").read_text())
        sc = next(s for s in cfg["stories"]
                  if s["slug"] == "driving-side-of-the-road")
        v = eg.beats_are_distinct(sc)
        self.assertFalse(v["ok"])
        self.assertIn("one fact stretched", v["reasons"][0])

    def test_a_real_story_is_not_accused(self):
        import json
        from scripts import editorial_gate as eg
        cfg = json.loads((Path(__file__).resolve().parent.parent
                          / "data_learning" / "niche.config.json").read_text())
        for slug in ("two-americas-cost", "housing-affordability-wall",
                     "colorblind-by-the-numbers"):
            sc = next(s for s in cfg["stories"] if s["slug"] == slug)
            self.assertTrue(eg.beats_are_distinct(sc)["ok"], slug)

    def test_it_judges_nothing_it_cannot_load(self):
        """A story whose datasets are unresolvable here is reported by
        `data_provenance`, not accused of being repetitive."""
        from scripts import editorial_gate as eg
        self.assertTrue(eg.beats_are_distinct({"segments": []})["ok"])
        self.assertTrue(eg.beats_are_distinct(
            {"segments": [{"key": "nope", "params": {"file": "nope.json"}}]}
        )["ok"])

    def test_only_TWO_stories_in_the_catalogue_are_refused(self):
        """A gate that starts refusing broadly empties the channel."""
        import json
        from scripts import editorial_gate as eg
        cfg = json.loads((Path(__file__).resolve().parent.parent
                          / "data_learning" / "niche.config.json").read_text())
        held = [s["slug"] for s in cfg["stories"]
                if not eg.beats_are_distinct(s)["ok"]]
        self.assertLess(len(held), 10, f"refusing too much: {held}")
        self.assertIn("driving-side-of-the-road", held)


class TheCatalogueIsMeasured(unittest.TestCase):
    """The numbers in the module docstring have to stay true, and a change
    that starts eating real beats has to show up as a number moving."""

    def test_restatements_are_a_minority_of_the_catalogue(self):
        import json
        from data_learning.sources.base import DataPoint as DP
        cfg = json.loads(
            (Path(__file__).resolve().parent.parent
             / "data_learning" / "niche.config.json").read_text())
        data = Path(__file__).resolve().parent.parent / "data_learning" / "data"
        hit = tot = 0
        for s in cfg["stories"]:
            beats = []
            for seg in (s.get("segments") or []):
                f = (seg.get("params") or {}).get("file")
                p = data / f if f else None
                if not p or not p.exists():
                    continue
                d = json.loads(p.read_text())
                pts = [DP(label=str(x["label"]), value=float(x["value"]))
                       for x in d.get("points", [])
                       if x.get("value") is not None]
                if len(pts) < 2:
                    continue
                beats.append(Insight(
                    kind=seg.get("insight_type", "rank"),
                    topic=seg.get("topic", ""), main_insight="", items=pts,
                    source=SRC, unit=d.get("unit", ""),
                    highlight_label=str(pts[0].label)))
            if len(beats) < 2:
                continue
            tot += 1
            if bc.prune_restatements(beats)[1]:
                hit += 1
        self.assertGreater(tot, 250, "the catalogue did not load")
        # Measured at 21/302 = 7.0% on 2026-09-08. A big jump means the
        # detector started eating real beats; a drop to zero means it stopped
        # detecting. Either is worth a look.
        self.assertGreater(hit, 5, f"detector stopped finding anything: {hit}")
        self.assertLess(hit / tot, 0.15,
                        f"{hit}/{tot} stories flagged — too many to be real")


if __name__ == "__main__":
    unittest.main()
