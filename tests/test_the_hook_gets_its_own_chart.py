"""The hook is written about segment 0, so segment 0 must not move.

2026-08-11. The showrunner blocked the macao story with:

    "Three unrelated datasets stapled together - the hook promises Macao's
     density but the first 14 seconds are a cropland bar race, and the
     closing line about 'the most crowded place' lands over a fertilizer
     line chart."

It was describing a real desync, not a bad script. `story_forge` authors
title / hook / says[i] / closing against `dss` IN SEQUENCE, and
`studio_render` makes segment 0's chart span the hook window (`lead_hook`).
`story.build` then sorted EVERY segment to push `trend` (line) charts to the
end — so any story whose opening dataset is a time series had its hook
narrated over somebody else's chart.

That is most of them. Of the six most recently authored stories, four open
on a trend and every one of those hooks names the opening dataset:

    solo-living-overtakes-family   "1 in 3 homes now has just one person."
                                   seg0 = US one-person households (trend)
    sand-mining-crisis             "We're mining sand faster than nature
                                    makes it."  seg0 = sand extraction
    boomerang-generation           "Living with your parents at 27?"
                                   seg0 = living with parents over time
    chatgpt-fastest-adoption-ever  "This app broke every growth record."
                                   seg0 = ChatGPT users over time

The "never open on a line chart" rule is real and stays — it is now applied
to the DEPICTION rather than the ORDER, which is what the code already did
for the all-trend case.

    python -m unittest tests.test_the_hook_gets_its_own_chart -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

SRC = (ROOT / "data_learning" / "story.py").read_text()
BUILD = SRC.split("def build(", 1)[1].split("\n    for i, (seg_cfg", 1)[0]


class Ins:
    """Just enough of an Insight for the ordering logic."""

    def __init__(self, kind, tag):
        self.kind = kind
        self.tag = tag

    def __repr__(self):
        return f"<{self.tag}:{self.kind}>"


def reorder(kinds, keep_order=False):
    """Run the ordering exactly as `story.build` does, on stand-ins."""
    inss = [Ins(k, i) for i, k in enumerate(kinds)]
    seg_cfgs = [{"n": i} for i in range(len(kinds))]
    if not keep_order and inss:
        tail = sorted(range(1, len(inss)),
                      key=lambda i: (inss[i].kind == "trend", i))
        order = [0] + tail
        seg_cfgs = [seg_cfgs[i] for i in order]
        inss = [inss[i] for i in order]
        if inss[0].kind == "trend":
            inss[0].kind = "timeline"
    return [s["n"] for s in seg_cfgs], [i.kind for i in inss]


class TestSegmentZeroNeverMoves(unittest.TestCase):

    def test_a_leading_trend_stays_at_the_front(self):
        """The exact shape of four of the six most recent stories."""
        order, kinds = reorder(["trend", "rank", "rank"])
        self.assertEqual(order[0], 0,
                         "the hook's own dataset was moved off the open")
        self.assertNotEqual(kinds[0], "trend",
                            "and it must not still be a line chart")

    def test_it_is_re_depicted_rather_than_relocated(self):
        _order, kinds = reorder(["trend", "rank", "rank"])
        self.assertEqual(kinds[0], "timeline")

    def test_a_non_trend_opener_is_left_completely_alone(self):
        order, kinds = reorder(["share", "rank", "rank"])
        self.assertEqual(order, [0, 1, 2])
        self.assertEqual(kinds[0], "share")

    def test_segment_zero_holds_for_every_opening_kind(self):
        for k in ("trend", "rank", "share", "comparison", "bubbles",
                  "timeline"):
            order, _kinds = reorder([k, "rank", "trend"])
            self.assertEqual(order[0], 0, f"opening {k} was moved")


class TestTheLineChartRuleStillHolds(unittest.TestCase):
    """Removing the desync must not resurrect "opens on a line chart"."""

    def test_the_video_never_opens_on_a_trend(self):
        for kinds in (["trend", "rank", "rank"], ["trend", "trend", "trend"],
                      ["trend"], ["trend", "share"]):
            _order, out = reorder(kinds)
            self.assertNotEqual(out[0], "trend", f"{kinds} opens on a line")

    def test_later_trends_still_sink_to_the_end(self):
        """The rule's other half — a line chart mid-video moves back."""
        order, _k = reorder(["share", "trend", "rank"])
        self.assertEqual(order, [0, 2, 1])

    def test_several_later_trends_keep_their_relative_order(self):
        order, _k = reorder(["share", "trend", "rank", "trend"])
        self.assertEqual(order, [0, 2, 1, 3])

    def test_keep_order_still_opts_out_entirely(self):
        order, kinds = reorder(["trend", "rank"], keep_order=True)
        self.assertEqual(order, [0, 1])
        self.assertEqual(kinds[0], "trend")


class TestEdges(unittest.TestCase):
    def test_a_single_segment_story(self):
        order, kinds = reorder(["trend"])
        self.assertEqual(order, [0])
        self.assertEqual(kinds[0], "timeline")

    def test_no_segments_at_all(self):
        self.assertEqual(reorder([]), ([], []))


class TestTheCodeSaysWhy(unittest.TestCase):
    """The next person to "simplify" this back into one sort has to meet the
    argument, so the reason lives next to the code."""

    def test_the_pin_is_explained(self):
        self.assertIn("SEGMENT 0 IS PINNED", BUILD)
        self.assertIn("lead_hook", BUILD)

    def test_it_no_longer_sorts_from_zero(self):
        self.assertIn("range(1, len(inss))", BUILD)
        self.assertNotIn("sorted(range(len(inss))", BUILD)

    def test_studio_render_really_does_span_the_hook_with_segment_zero(self):
        """The whole argument rests on this — pin it against the renderer so
        the two cannot drift apart silently."""
        studio = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("windows[0][0] if (i == 0 and lead_hook)", studio)


if __name__ == "__main__":
    unittest.main()
