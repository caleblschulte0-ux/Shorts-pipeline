"""Data is on screen for the whole video, including the beats he is not
baked into.

Operator, 2026-09-11, looking at the re-rendered ozone hook: *"where's the
mascot?"* — and he was right, there wasn't one. Measured on the render, the
first eight seconds carried 37-64 stray antialiasing pixels of his teal
against 197-703 on the beats where he actually appears.

A segment renders a SEQUENCE of visuals — the
"[studio] seg2: mechanic(6.9s) -> bars(6.9s)" line — and only the CHARTS
draw him inside themselves. `_seg_is_baked` judged the whole segment from
its INSIGHT kind, which is the chart the segment would draw, not the visual
that actually rendered. So a `trend` segment showing a brain-authored
mechanic for its first half claimed "a chart draws Data here" for a stretch
where nothing did, the gap-filler skipped it, and he was absent.

On this story all three segments are trend / comparison / rank — every one
in `BAKED_CHART_KINDS` — and every one also carries a mechanic. So
`all(_seg_is_baked(...))` was True and the travelling overlay was switched
off for the ENTIRE video. He survived only where a chart happened to draw
him, and the hook had no mascot at all.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from data_learning import studio_render as SR                # noqa: E402


class _Seg:
    def __init__(self, kind, spans=None):
        self.kind = kind
        self.insight = None
        self.host_baked = False
        if spans is not None:
            self.spans = spans


def _span(kind, t0, t1):
    return {"kind": kind, "t0": t0, "t1": t1, "path": "x", "anchors": []}


class OnlyAChartBakesHim(unittest.TestCase):
    def test_the_charts_do(self):
        for k in ("bars", "trend", "rank", "comparison", "stack",
                  "pictograph", "geo_city", "fill_vessel", "timeline"):
            self.assertTrue(SR._kind_bakes(k), k)

    def test_the_generated_visuals_do_NOT(self):
        """`mechanic` is brain-authored code and draws exactly what it says;
        `scene` and `diorama` are what it falls back to."""
        for k in ("mechanic", "scene", "diorama", "race"):
            self.assertFalse(SR._kind_bakes(k), k)

    def test_nothing_is_baked(self):
        for k in (None, "", "not_a_kind"):
            self.assertFalse(SR._kind_bakes(k), repr(k))


class TheOverlayCoversWhatTheChartsDoNot(unittest.TestCase):
    """The two decisions the bug turned on, exercised directly."""

    # The renderer's OWN helpers — this test used to re-implement them, which
    # is how it stayed green while the real code parked a second Data.
    def _baked_spans(self, segs, disp_start, disp_end):
        return SR.baked_spans_of(segs, disp_start, disp_end)

    def _fully_baked(self, segs):
        return SR.fully_baked(segs)

    def test_the_ozone_shape_no_longer_hides_the_mascot(self):
        """Three baked-kind segments, each showing a mechanic first."""
        segs = [_Seg("trend", [_span("mechanic", 0.0, 8.0),
                               _span("comparison", 8.0, 14.8)]),
                _Seg("comparison", [_span("mechanic", 14.8, 19.0),
                                    _span("comparison", 19.0, 23.4)]),
                _Seg("rank", [_span("mechanic", 23.4, 30.0),
                              _span("bars", 30.0, 37.2)])]
        self.assertFalse(self._fully_baked(segs),
                         "the overlay would be switched off for the video")
        spans = self._baked_spans(segs, {}, {})
        self.assertEqual(spans, [(8.0, 14.8), (19.0, 23.4), (30.0, 37.2)])

    def test_the_hook_window_is_not_claimed_by_a_chart(self):
        segs = [_Seg("trend", [_span("mechanic", 0.0, 8.0),
                               _span("comparison", 8.0, 14.8)])]
        covered = self._baked_spans(segs, {}, {})
        self.assertFalse(any(a <= 1.0 <= b for a, b in covered),
                         "t=1.0s is still claimed as baked")

    def test_an_all_chart_story_still_suppresses_the_overlay(self):
        """The suppression exists for a reason — without it the home host
        parks at bottom-centre beside a chart that already draws him, which
        the gate reads as a second, decorative Data."""
        segs = [_Seg("bars", [_span("bars", 0.0, 10.0)]),
                _Seg("trend", [_span("trend", 10.0, 20.0)])]
        self.assertTrue(self._fully_baked(segs))

    def test_a_story_with_no_spans_falls_back_to_the_segment(self):
        """`spans` is set during render; anything reading a story before that
        must still get the old answer rather than an empty list."""
        segs = [_Seg("bars"), _Seg("trend")]
        self.assertTrue(self._fully_baked(segs))
        self.assertEqual(self._baked_spans(segs, {0: 0.0, 1: 5.0},
                                           {0: 5.0, 1: 9.0}),
                         [(0.0, 5.0), (5.0, 9.0)])

    def test_a_wholly_generated_story_gets_the_overlay_throughout(self):
        segs = [_Seg("trend", [_span("mechanic", 0.0, 12.0)])]
        self.assertFalse(self._fully_baked(segs))
        self.assertEqual(self._baked_spans(segs, {}, {}), [])


class AMachineThatDrawsHimIsBakedAndAMechanicAfterItIsNot(unittest.TestCase):
    """THE SECOND DATA WITH THE CLIPBOARD (`invasive-species-price-tag`,
    2026-09-21, held at 48 twice; `fusion-net-energy-gain` before it):
    a trajectory machine drew Data on its tip, the gap-filler trusted only
    chart KINDS, called the `scene` span unbaked, and parked the home host
    over the whole beat — "a SECOND copy of Data ... holding a clipboard in
    an identical arm-out pose in every frame from seg1:start through
    payoff". The renderer sets `insight.host_baked` while it draws him, and
    the span records that answer, per span."""

    def test_a_scene_that_recorded_host_baked_is_baked(self):
        self.assertTrue(SR._span_bakes(dict(_span("scene", 0, 5), host_baked=True)))

    def test_a_scene_that_did_not_is_not(self):
        self.assertFalse(SR._span_bakes(_span("scene", 0, 5)))
        self.assertFalse(SR._span_bakes(dict(_span("mechanic", 0, 5), host_baked=False)))

    def test_a_chart_kind_is_baked_without_the_flag(self):
        self.assertTrue(SR._span_bakes(_span("bars", 0, 5)))

    def test_the_invasive_species_shape(self):
        """seg1 = a trajectory machine (self-hosting scene) then a mechanic.
        The machine's range is baked; the mechanic's is not; and the flag
        left on the INSIGHT by the machine must not leak onto the mechanic."""
        seg = _Seg("trend", [dict(_span("scene", 4.3, 9.0), host_baked=True),
                             dict(_span("mechanic", 9.0, 14.0), host_baked=False)])
        seg.insight = type("I", (), {"host_baked": True})()   # leaked flag
        self.assertEqual(SR.baked_spans_of([seg], {}, {}), [(4.3, 9.0)])
        self.assertFalse(SR.fully_baked([seg]))

    def test_a_story_of_machines_only_suppresses_the_overlay(self):
        segs = [_Seg("trend", [dict(_span("scene", 0, 8), host_baked=True)]),
                _Seg("rank", [dict(_span("scene", 8, 16), host_baked=True)])]
        self.assertTrue(SR.fully_baked(segs))

    def test_an_empty_story_is_not_fully_baked(self):
        self.assertFalse(SR.fully_baked([]))


class TheRendererUsesIt(unittest.TestCase):
    def _code(self):
        import ast
        import inspect
        src = inspect.getsource(SR.render)
        tree = ast.parse(src.lstrip())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        return ast.unparse(tree)

    def test_it_reads_the_spans_not_the_segment_kind(self):
        code = self._code()
        self.assertIn("baked_spans_of(st.segments", code)
        self.assertIn("fully_baked(st.segments)", code)
        self.assertNotIn("all(_seg_is_baked(s) for s in st.segments)", code)

    def test_the_span_records_whether_it_drew_him(self):
        """Cleared before every span's render, recorded on the span after —
        otherwise the flag a machine left on the insight makes the mechanic
        after it read as baked, and Data is missing from the best beat."""
        code = self._code()
        self.assertIn("seg.insight.host_baked = False", code)
        # (string constants are blanked, so the key and the attribute name
        # inside getattr read as '' here — the SHAPE is what is asserted)
        self.assertIn("bool(getattr(seg.insight, '', False))", code)

    def test_the_overlay_is_decided_per_span(self):
        code = self._code()
        self.assertIn("_span_bakes(sp)", code)
        self.assertNotIn("if _seg_is_baked(st.segments[i]):\n                return {'hidden': True}",
                         code)


if __name__ == "__main__":
    unittest.main()
