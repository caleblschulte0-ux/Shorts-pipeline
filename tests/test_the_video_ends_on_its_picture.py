"""The last frame of a video is its finished picture, never an empty card.

Operator, 2026-10-28: "What's with the werid last frame of all our videos".
Every explainer posted that week ended on the bare navy ground with Data
holding a blank price tag; the showrunner had named it on 10-17, 10-18,
10-21, 10-22, 10-24, 10-25 and on all five 10-28 verdicts ("the video ends
on an empty dark void with a blank price tag", payoff@-0.4).

The cause: the closing span ends at the closing line's window
(`windows[-1][1]`), the master is cut at the narration's length + 0.3s, and
a real voice's file runs past its last word. Nothing was enabled in that
gap, so the ground and the gap-fill host showed through.
"""
import ast
import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import studio_render as R  # noqa: E402


def _seg(*spans):
    return SimpleNamespace(spans=[dict(s) for s in spans])


def _covered(segments, total, step=1 / 30):
    spans = [x for s in segments for x in s.spans]
    t, gaps = 0.0, []
    while t < total - 1e-9:
        if not any(x["t0"] <= t <= x["t1"] for x in spans):
            gaps.append(round(t, 3))
        t += step
    return gaps


class TheLastPictureRunsToTheCut(unittest.TestCase):
    # the 10-28 fishing-gear shape: closing window ends 0.6s before the cut
    TOTAL = 36.1

    def story(self):
        return [
            _seg({"kind": "subject_scene", "t0": 0.0, "t1": 14.5,
                  "host_baked": True}),
            _seg({"kind": "subject_scene", "t0": 14.5, "t1": 22.1,
                  "host_baked": True}),
            _seg({"kind": "subject_scene", "t0": 22.1, "t1": 28.6,
                  "host_baked": True},
                 {"kind": "subject_scene", "t0": 28.6, "t1": 35.5,
                  "host_baked": True, "closing": True}),
        ]

    def test_the_old_timeline_had_a_hole_at_the_end(self):
        segs = self.story()
        gaps = _covered(segs, self.TOTAL)
        self.assertTrue(gaps and min(gaps) > 35.4,
                        "the fixture must reproduce the end gap")

    def test_every_frame_up_to_the_cut_shows_a_picture(self):
        segs = self.story()
        gain = R.run_to_the_cut(segs, self.TOTAL)
        self.assertAlmostEqual(gain, 0.6, places=6)
        self.assertEqual(_covered(segs, self.TOTAL), [])
        self.assertEqual(segs[-1].spans[-1]["t1"], self.TOTAL)

    def test_the_host_is_not_gap_filled_over_the_end(self):
        segs = self.story()
        R.run_to_the_cut(segs, self.TOTAL)
        baked = R.baked_spans_of(segs, {}, {})
        self.assertTrue(any(a <= self.TOTAL - 0.05 and b >= self.TOTAL
                            for a, b in baked),
                        "the end must be a baked range, so no gap-fill "
                        "Data with a blank tag is laid there")

    def test_only_the_last_picture_moves_and_never_shrinks(self):
        segs = self.story()
        before = [[x["t1"] for x in s.spans] for s in segs]
        R.run_to_the_cut(segs, self.TOTAL)
        after = [[x["t1"] for x in s.spans] for s in segs]
        self.assertEqual(before[:2], after[:2])
        self.assertEqual(before[2][0], after[2][0])
        # a timeline already past the cut is left alone
        segs = self.story()
        segs[-1].spans[-1]["t1"] = 40.0
        self.assertEqual(R.run_to_the_cut(segs, self.TOTAL), 0.0)
        self.assertEqual(segs[-1].spans[-1]["t1"], 40.0)

    def test_no_spans_is_harmless(self):
        self.assertEqual(R.run_to_the_cut([_seg()], 10.0), 0.0)


class TheRenderCallsIt(unittest.TestCase):
    def test_render_extends_the_last_span_before_the_host_is_staged(self):
        src = inspect.getsource(R)
        tree = ast.parse(src)
        calls = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.setdefault(node.func.id, []).append(node.lineno)
        self.assertIn("run_to_the_cut", calls,
                      "the render never carries its last picture to the cut")
        self.assertLess(min(calls["run_to_the_cut"]),
                        min(calls["baked_spans_of"]),
                        "it has to run before the host's gap fill is planned")


if __name__ == "__main__":
    unittest.main()
