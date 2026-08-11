"""The camera float, and the rule it exists to enforce: EVERY visual layer
must be able to answer "how many pixels per frame?".

2026-08-11. Explainer had posted nothing for twelve days and trending was
down to 1-2 videos a day. Both were the same defect, and it is not a taste
question — it is arithmetic. The temporal grade measures the change between
CONSECUTIVE frames, so a movement stretched over more frames measures WORSE,
and a build stretched to fill its beat measures nothing at all:

    explainer chart build, reviewer's own detector, measured:
        60 frames  (2s)  ->  3.1 effective fps
        240 frames (8s)  ->  0.0 effective fps, duplicate_ratio 1.00
        600 frames (20s) ->  0.0 effective fps, duplicate_ratio 1.00

Only CYCLIC motion holds its per-frame rate at any duration. These tests
pin that the shipped constants clear the floor, that both publishing
channels use the ONE definition, and that nobody re-introduces a slow-and-
pretty drift that the gate cannot see.

    python -m unittest tests.test_camera_float -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import camera_float as cf  # noqa: E402

STUDIO = (ROOT / "data_learning" / "studio_render.py").read_text()
RACE = (ROOT / "engines" / "chart_race.py").read_text()
REPAIR = (ROOT / "scripts" / "scene_repair.py").read_text()


class TestTheConstantsClearTheFloor(unittest.TestCase):
    """These numbers are a MEASUREMENT. Changing them means re-measuring
    against `showrunner_review._temporal_evidence`, not guessing."""

    def test_x_axis_moves_enough_per_frame(self):
        self.assertGreaterEqual(
            cf.px_per_frame(cf.FLOAT_A, cf.FLOAT_WX, 30.0),
            cf.MIN_PX_PER_FRAME,
            "the x drift is sub-threshold at 30fps — the gate cannot see it")

    def test_y_axis_moves_enough_per_frame(self):
        # y is the slower axis; it may sit a little under the x margin but
        # must still be well clear of the 2.3 px/frame that measured 8.9 fps.
        self.assertGreaterEqual(
            cf.px_per_frame(cf.FLOAT_A, cf.FLOAT_WY, 30.0), 2.4)

    def test_it_also_clears_at_24fps(self):
        """graph_race renders at 24fps — fewer samples per second, so MORE
        pixels per frame. The floor must hold at both rates."""
        self.assertGreaterEqual(
            cf.px_per_frame(cf.FLOAT_A, cf.FLOAT_WX, 24.0),
            cf.MIN_PX_PER_FRAME)

    def test_the_dead_idle_would_fail_this_test(self):
        """`6*sin(1.3*t)` is the exact expression that shipped zero videos
        for eleven days: 0.26 px/frame. The test has to catch it."""
        self.assertLess(cf.px_per_frame(6, 1.3, 30.0), cf.MIN_PX_PER_FRAME)

    def test_amplitude_stays_inside_the_charts_own_margin(self):
        """The explainer chart card has ~31px of transparent margin once
        composited. Floating further than that clips real content — and the
        showrunner already blocks videos for 'headline clipped off the right
        edge'. If a future change wants a bigger float it must oversize the
        layer first, as the full-frame branch does."""
        self.assertLessEqual(cf.FLOAT_A, 26)

    def test_the_two_axes_use_different_frequencies(self):
        """Same frequency on both axes is a diagonal slide, which reads as
        drift; different frequencies trace a Lissajous, which reads as a
        floating camera."""
        self.assertNotEqual(cf.FLOAT_WX, cf.FLOAT_WY)


class TestTheExpressionsAreWellFormed(unittest.TestCase):
    def test_overlay_xy_carries_the_time_variable(self):
        x, y = cf.overlay_xy(12, 26)
        for e in (x, y):
            self.assertIn("*t)", e, f"{e!r} does not vary with time")
        self.assertTrue(x.startswith("12+"))
        self.assertTrue(y.startswith("26+"))

    def test_crop_vf_oversizes_before_cropping(self):
        """A full-frame layer has no margin, so the float must come out of an
        oversized render — otherwise it exposes the background at the edge."""
        vf = cf.crop_vf(1080, 1920)
        self.assertIn(f"scale={1080 + 2 * cf.FLOAT_A}:{1920 + 2 * cf.FLOAT_A}",
                      vf)
        self.assertIn("crop=1080:1920", vf)
        self.assertIn("*t)", vf)

    def test_amp_override_scales_the_whole_expression(self):
        x, _ = cf.overlay_xy(0, 0, amp=10)
        self.assertIn("10*sin", x)


class TestBothChannelsUseTheOneDefinition(unittest.TestCase):
    """CLAUDE.md: never copy shared logic into a channel. This is the exact
    failure shape that let trending ship six months of unwatched video while
    explainer was gated — one policy, two implementations."""

    def test_the_explainer_composites_through_it(self):
        self.assertIn("camera_float", STUDIO)
        self.assertIn("_cf.overlay_xy(", STUDIO)

    def test_graph_race_composites_through_it(self):
        self.assertIn("camera_float.crop_vf(", RACE)

    def test_neither_channel_hardcodes_its_own_amplitude(self):
        """A literal `sin(` in a chart overlay expression means somebody
        re-derived the constants locally."""
        for name, src in (("studio_render", STUDIO), ("chart_race", RACE)):
            body = "\n".join(l for l in src.splitlines()
                             if not l.lstrip().startswith("#"))
            for m in re.finditer(r"overlay=x='([^']*)'", body):
                self.assertNotIn("sin(", m.group(1).replace("{_fx}", ""),
                                 f"{name}: overlay x hardcodes a drift "
                                 f"instead of using camera_float")


class TestTheStaticChartCaseIsCovered(unittest.TestCase):
    """The float has to carry a scene whose build contributes NOTHING —
    that is the actual production case (600-frame builds measure 0.0)."""

    def test_the_explainer_floats_the_chart_even_while_it_holds(self):
        """The chart layer is tpad-held for the rest of the beat. The float
        is applied at OVERLAY time, which is outside the hold, so the held
        frames still move. If the float ever moves inside the tpad chain it
        would freeze with the build."""
        seg = STUDIO.split("Charts DRAW ON", 1)[1].split("Mascots", 1)[0]
        self.assertIn("tpad=stop_mode=clone", seg)
        i_tpad = seg.index("tpad=stop_mode=clone")
        i_float = seg.index("_cf.overlay_xy(")
        self.assertLess(i_float, i_tpad,
                        "the float must be computed for the overlay, not "
                        "baked into the padded source")
        self.assertIn("overlay=x='{_fx}':y='{_fy}'", seg)

    def test_a_full_frame_layer_is_oversized_so_nothing_shows_through(self):
        seg = STUDIO.split("Charts DRAW ON", 1)[1].split("Mascots", 1)[0]
        self.assertIn("vw + 2 * _A", seg)
        self.assertIn("vh + 2 * _A", seg)


class TestTheSceneProxyMeasuresWhatShips(unittest.TestCase):
    """`_scene_metrics` used to overlay the build at a fixed 0:0, so it
    reported the RAW BUILD's cadence — a number the shipped video never has.
    The repair loop then chased it."""

    def test_the_proxy_includes_the_float(self):
        seg = STUDIO.split("def _scene_metrics", 1)[1].split(
            "\ndef ", 1)[0]
        self.assertIn("_cf.overlay_xy(", seg)
        self.assertNotIn('"[0:v][c]overlay=0:0:shortest=1', seg)

    def test_the_metrics_sidecar_publishes_the_gate_and_the_fps(self):
        """scene_repair reads these two keys off disk; if they stop being
        written the repair silently falls back to guessing again."""
        seg = STUDIO.split("def _scene_metrics", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"gate": gate or "pass"', seg)
        self.assertIn('"effective_fps": ev.get("effective_fps")', seg)

    def test_candidate_scoring_also_includes_the_float(self):
        """Candidates render at ~60 frames and ship at up to 1200. Scoring
        the raw build gave every candidate fps_score 1.0 while the shipped
        scene measured 1.0 effective fps."""
        seg = REPAIR.split("def score_candidate", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("camera_float", seg)
        self.assertNotIn('"[0:v][c]overlay=0:0:shortest=1', seg)


if __name__ == "__main__":
    unittest.main()
