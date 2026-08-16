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

    def test_the_motion_does_not_read_as_shake(self):
        """The 2026-08-16 operator note, verbatim: "this weird fucking
        shaking motion". The gate needs pixels per frame (amp*w/fps); the
        eye objects to acceleration (amp*w^2). The first tuning satisfied
        the gate at 423 px/s^2 and the mascot idle stacked ~1080 on top —
        visible jiggle. Both axes now stay under 200 px/s^2, and this bound
        is why "raise the amplitude, never the frequency" is a rule and not
        advice."""
        self.assertLessEqual(cf.FLOAT_A * cf.FLOAT_WX ** 2, 200)
        self.assertLessEqual(cf.FLOAT_A * cf.FLOAT_WY ** 2, 200)

    def test_the_crop_cost_stays_invisible(self):
        """The whole-frame breath crops FLOAT_A px per side from an
        oversized frame — that must stay a few percent of frame width, or
        the 'camera' starts eating composition."""
        self.assertLessEqual(cf.FLOAT_A / 1080, 0.05)

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
        """Via crop_vf on the WHOLE finished frame — the per-layer
        overlay_xy float is deliberately gone (it was half of the shake:
        card and mascot oscillating at different frequencies)."""
        self.assertIn("camera_float", STUDIO)
        self.assertIn("_cf.crop_vf(", STUDIO)
        self.assertNotIn("_cf.overlay_xy(", STUDIO)

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

    def test_the_breath_wraps_the_whole_composite(self):
        """The CAMERA BREATH is applied to the finished frame — downstream
        of every tpad hold, chart overlay and mascot — so a beat whose
        content goes completely still STILL moves at the detector. Putting
        it any earlier recreates one of two former bugs: inside a layer it
        freezes with that layer's hold; on one layer only, layers drift
        relative to each other, which is the shake."""
        # anchor on the MASTER's call, not the half-scale proxy's
        i_breath = STUDIO.index("_cf.crop_vf(W, H)")
        self.assertLess(STUDIO.index("tpad=stop_mode=clone"), i_breath)
        seg = STUDIO.split("CAMERA BREATH", 1)[1]
        self.assertIn("_cf.crop_vf(W, H)", seg)

    def test_captions_burn_in_after_the_breath(self):
        """Subtitles ride on top of the drifting frame, pinned and crisp —
        floating captions read as broken, and re-rasterising them through
        the crop would soften them every frame."""
        i_breath = STUDIO.index("_cf.crop_vf(W, H)")
        i_ass = STUDIO.index("ass='{ass_esc}'")
        self.assertLess(i_breath, i_ass)


class TestTheSceneProxyMeasuresWhatShips(unittest.TestCase):
    """`_scene_metrics` used to overlay the build at a fixed 0:0, so it
    reported the RAW BUILD's cadence — a number the shipped video never has.
    The repair loop then chased it."""

    def test_the_proxy_includes_the_breath(self):
        """The layer sits at rest and the whole-frame breath goes over the
        top — the same order as the shipped master. (`overlay=0:0` is now
        CORRECT here: the motion comes after it, from crop_vf.)"""
        seg = STUDIO.split("def _scene_metrics", 1)[1].split(
            "\ndef ", 1)[0]
        self.assertIn("_cf.crop_vf(540, 960, amp=_A)", seg)
        self.assertNotIn("overlay_xy", seg)

    def test_the_metrics_sidecar_publishes_the_gate_and_the_fps(self):
        """scene_repair reads these two keys off disk; if they stop being
        written the repair silently falls back to guessing again."""
        seg = STUDIO.split("def _scene_metrics", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"gate": gate or "pass"', seg)
        self.assertIn('"effective_fps": ev.get("effective_fps")', seg)

    def test_candidate_scoring_also_includes_the_breath(self):
        """Candidates render at ~60 frames and ship at up to 1200. Scoring
        the raw build gave every candidate fps_score 1.0 while the shipped
        scene measured 1.0 effective fps. The proxy composites like the
        master: layer at rest, breath over the finished frame."""
        seg = REPAIR.split("def score_candidate", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("camera_float", seg)
        self.assertIn("crop_vf(540, 960, amp=_A)", seg)


if __name__ == "__main__":
    unittest.main()
