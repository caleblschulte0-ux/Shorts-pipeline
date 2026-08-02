from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from .choreography import action_repetition, compile_camera, compile_captions, compile_sounds, varied_moves
from .effects import render_event
from .models import Box
from .preview_compiler import compile_preview, storyboard_html, write_preview_bundle
from .quality_linter import lint_bundle

STORY = {
    "slug": "grocery_bill_jump",
    "topic": "Grocery prices",
    "claim": "The same grocery basket got dramatically more expensive.",
    "unit": "$",
    "data": [
        {"label": "2019", "value": 680, "period": 2019},
        {"label": "2022", "value": 860, "period": 2022},
        {"label": "2026", "value": 1030, "period": 2026},
    ],
    "beats": [
        {"role": "hook", "narration": "This grocery bill changed fast.", "duration": 3.2},
        {"role": "setup", "narration": "In 2019 the basket cost about six hundred eighty dollars.", "duration": 4.3},
        {"role": "explanation", "narration": "By 2022 the same basket had climbed to eight hundred sixty dollars.", "duration": 4.8},
        {"role": "consequence", "narration": "That means the household has to find hundreds more every year.", "duration": 4.4},
        {"role": "payoff", "narration": "The path between 2019 and 2026 is the story.", "duration": 3.8},
    ],
}
UPGRADE = {
    "slug": "grocery_bill_jump",
    "scenes": [
        {"scene_id": "seg00", "role": "hook", "visual_event": "split_screen_values_slam_then_gap_opens", "camera_move": "snap_push_in", "mascot_effort": "drag_line", "callback_token": "2019_vs_2026", "caption_chunks": ["2019: $680. 2026: $1,030."]},
        {"scene_id": "seg01", "role": "setup", "visual_event": "line_enters_flat_then_yanks_mascot_upward", "camera_move": "counter_pan", "mascot_effort": "pull_down_win", "callback_token": ""},
        {"scene_id": "seg02", "role": "explanation", "visual_event": "line_draws_under_tension_and_labels_land_on_impacts", "camera_move": "follow_tip", "mascot_effort": "ride", "callback_token": ""},
        {"scene_id": "seg03", "role": "consequence", "visual_event": "the_total_increase_builds_into_a_physical_stack_the_mascot_must_hold", "camera_move": "pressure_pull_back", "mascot_effort": "hoist_stack", "callback_token": ""},
        {"scene_id": "seg04", "role": "payoff", "visual_event": "opening_split_screen_returns_then_the_full_trend_draws_between_both_sides", "camera_move": "callback_pull_back", "mascot_effort": "drag_line", "callback_token": "2019_vs_2026"},
    ],
}


class CaptionTests(unittest.TestCase):
    def test_hook_caption_is_short_and_hits_early(self):
        cues = compile_captions("2019 was $680. Now it is $1,030.", 3.2, "hook")
        self.assertLessEqual(max(len(c.text.split()) for c in cues), 7)
        self.assertEqual(cues[0].enter, "slam")
        self.assertLess(cues[0].start, .2)

    def test_numeric_caption_gets_emphasis_and_impact(self):
        cues = compile_captions("The bill jumped by $350.", 3.0, "consequence")
        cue = next(c for c in cues if "$350" in c.text)
        self.assertIn("$350", cue.emphasis)
        self.assertIsNotNone(cue.impact_at)

    def test_no_orphan_word_tail(self):
        cues = compile_captions("This is a phrase with a weak orphan ending", 4.0, "explanation")
        self.assertGreater(len(cues[-1].text.split()), 1)


class MotionTests(unittest.TestCase):
    def test_camera_recipe_stays_tasteful(self):
        frames = compile_camera("snap_push_in", 3.2)
        self.assertTrue(all(.82 <= f.scale <= 1.30 for f in frames))
        self.assertEqual(frames[0].at, 0.0)

    def test_three_repeated_moves_are_rejected(self):
        self.assertFalse(varied_moves(["slow_push", "slow_push", "slow_push"]))
        self.assertTrue(varied_moves(["slow_push", "follow_tip", "slow_push"]))

    def test_action_repetition_is_measured(self):
        self.assertEqual(action_repetition(["ride", "ride", "push", "drag_line"]), .5)

    def test_sound_cues_are_bounded(self):
        captions = compile_captions("2019 was $680. 2026 is $1,030.", 3.2, "hook")
        cues = compile_sounds("split_screen_values_slam_then_gap_opens", captions, 3.2)
        self.assertLessEqual(len(cues), 5)
        self.assertTrue(all(0 <= c.at <= 3.2 for c in cues))


class EffectTests(unittest.TestCase):
    def test_every_supported_effect_returns_svg(self):
        data = tuple(STORY["data"])
        for event in (
            "split_screen_values_slam_then_gap_opens",
            "line_enters_flat_then_yanks_mascot_upward",
            "the_total_increase_builds_into_a_physical_stack_the_mascot_must_hold",
            "opening_split_screen_returns_then_the_full_trend_draws_between_both_sides",
        ):
            svg = render_event(event, .55, data, "Test scene")
            self.assertIn("<svg", svg)
            self.assertIn("1080", svg)
            self.assertIn("1920", svg)

    def test_money_values_are_visible_in_hook(self):
        svg = render_event("split_screen_values_slam_then_gap_opens", 1.0, tuple(STORY["data"]), "Grocery bill")
        self.assertIn("$680", svg)
        self.assertIn("$1,030", svg)

    def test_callback_reuses_opening_values(self):
        svg = render_event("opening_split_screen_returns_then_the_full_trend_draws_between_both_sides", 1.0, tuple(STORY["data"]), "The gap is the story")
        self.assertIn("2019", svg)
        self.assertIn("2026", svg)
        self.assertIn("THE GAP IS THE STORY", svg)
        self.assertIn("callback bridge", svg)
        self.assertIn("NOW THE OPENING MAKES SENSE", svg)


class PreviewTests(unittest.TestCase):
    def test_bundle_compiles_and_validates(self):
        bundle = compile_preview(STORY, UPGRADE)
        bundle.validate()
        self.assertEqual(len(bundle.scenes), 5)
        self.assertEqual(bundle.opening_callback, bundle.ending_callback)
        self.assertGreaterEqual(bundle.quality_score, 90)

    def test_visible_action_starts_by_point_four(self):
        bundle = compile_preview(STORY, UPGRADE)
        self.assertTrue(all(scene.keyframes[0].at <= .4 for scene in bundle.scenes))

    def test_preview_has_varied_camera_and_actions(self):
        bundle = compile_preview(STORY, UPGRADE)
        self.assertGreaterEqual(len(set(s.camera_move for s in bundle.scenes)), 4)
        self.assertGreaterEqual(len(set(s.mascot_action for s in bundle.scenes)), 4)

    def test_storyboard_contains_real_svg_frames(self):
        bundle = compile_preview(STORY, UPGRADE)
        html = storyboard_html(bundle)
        self.assertIn("iframe", html)
        self.assertIn("&lt;svg", html)
        self.assertIn("SFX", html)

    def test_write_bundle_creates_manifest_html_and_frames(self):
        bundle = compile_preview(STORY, UPGRADE)
        with tempfile.TemporaryDirectory() as td:
            written = write_preview_bundle(bundle, Path(td))
            self.assertTrue(Path(written["manifest"]).exists())
            self.assertTrue(Path(written["storyboard"]).exists())
            self.assertTrue(any(key.endswith(":final") for key in written))

    def test_quality_report_has_no_hard_failures(self):
        bundle = compile_preview(STORY, UPGRADE)
        report = lint_bundle(bundle)
        self.assertFalse(report.failures)
        self.assertGreaterEqual(report.dimensions["ending_callback"], 100)
        self.assertGreaterEqual(report.dimensions["useful_occupancy"], 70)

    def test_missing_callback_fails_closed(self):
        broken = dict(UPGRADE)
        broken["scenes"] = [dict(s) for s in UPGRADE["scenes"]]
        broken["scenes"][-1]["callback_token"] = "different"
        with self.assertRaises(ValueError):
            compile_preview(STORY, broken)

    def test_box_overlap_contract(self):
        self.assertTrue(Box(0, 0, 100, 100).overlaps(Box(50, 50, 100, 100)))
        self.assertFalse(Box(0, 0, 100, 100).overlaps(Box(200, 200, 100, 100)))


if __name__ == "__main__":
    unittest.main()
