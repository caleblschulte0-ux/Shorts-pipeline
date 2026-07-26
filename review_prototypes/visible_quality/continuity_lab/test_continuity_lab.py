from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from .audio_alignment import audio_sync_score, compile_audio
from .compiler import compile_bundle
from .fixtures import FIXTURES
from .models import Box, StoryScene
from .motion_flow import motion_flow_score
from .occupancy import BOTTOM_UI, RIGHT_RAIL, occupancy_score, solve_layout
from .rhythm import story_rhythm_score
from .scorecard import sprint8_scorecard
from .transition_graph import transition_score


class GeometryTests(unittest.TestCase):
    def test_box_bounds(self):
        Box(0, 0, 100, 100).validate()
        with self.assertRaises(ValueError):
            Box(1000, 0, 100, 100).validate()

    def test_overlap(self):
        self.assertTrue(Box(0, 0, 100, 100).overlaps(Box(50, 50, 100, 100)))
        self.assertFalse(Box(0, 0, 100, 100).overlaps(Box(200, 200, 50, 50)))


class OccupancyTests(unittest.TestCase):
    def test_all_archetypes_clear_platform_ui(self):
        for name in FIXTURES:
            layout = solve_layout(name, "hook", "collision")
            self.assertFalse(layout.caption.overlaps(RIGHT_RAIL))
            self.assertFalse(layout.caption.overlaps(BOTTOM_UI))
            if layout.secondary:
                self.assertFalse(layout.secondary.overlaps(RIGHT_RAIL))
                self.assertFalse(layout.secondary.overlaps(BOTTOM_UI))

    def test_all_archetypes_score_above_90(self):
        for name in FIXTURES:
            self.assertGreaterEqual(occupancy_score(solve_layout(name, "hook", "collision")), 90)

    def test_hero_never_collides_with_caption(self):
        for name in FIXTURES:
            for role in ("hook", "setup", "explanation", "consequence", "payoff"):
                layout = solve_layout(name, role, "physical_event")
                self.assertFalse(layout.hero.overlaps(layout.caption, padding=18))


class AudioTests(unittest.TestCase):
    def _scene(self, role="hook", narration="2019 was $680 and 2026 is $1,030."):
        return StoryScene("s", role, narration, "value_collision_slam", "2026", 3.2, "token" if role in {"hook", "payoff"} else "")

    def test_hook_primary_hits_by_point_one(self):
        self.assertLessEqual(compile_audio(self._scene()).cues[0].at, .10)

    def test_number_ticks_align_to_emphasis(self):
        plan = compile_audio(self._scene())
        for target in plan.emphasis_times:
            self.assertTrue(any(c.kind == "number_tick" and abs(c.at-target) <= .04 for c in plan.cues))

    def test_ducking_exists(self):
        self.assertTrue(any(point.voice_gain_db <= -3 for point in compile_audio(self._scene()).ducking))

    def test_payoff_has_silence(self):
        plan = compile_audio(self._scene("payoff", "The original $680 and $1,030 return."))
        self.assertIsNotNone(plan.payoff_silence)
        self.assertGreaterEqual(plan.payoff_silence[1] - plan.payoff_silence[0], .20)

    def test_audio_score_is_high(self):
        for fixture in FIXTURES.values():
            for index, raw in enumerate(fixture["scenes"]):
                scene = StoryScene.from_mapping(raw, index)
                self.assertGreaterEqual(audio_sync_score(compile_audio(scene), scene), 95)


class MotionTransitionTests(unittest.TestCase):
    def test_motion_chain_is_continuous(self):
        for fixture in FIXTURES.values():
            bundle = compile_bundle(fixture)
            plans = tuple(scene.motion for scene in bundle.scenes)
            self.assertTrue(all(a.exit_edge == b.entry_edge for a, b in zip(plans, plans[1:])))
            self.assertGreaterEqual(motion_flow_score(plans), 90)

    def test_global_transitions_have_callback(self):
        for fixture in FIXTURES.values():
            self.assertEqual(compile_bundle(fixture).transitions[-1].kind, "callback_return")

    def test_transition_score_is_high(self):
        for fixture in FIXTURES.values():
            self.assertGreaterEqual(transition_score(compile_bundle(fixture).transitions), 90)

    def test_transition_sequence_is_not_one_repeated_template(self):
        for fixture in FIXTURES.values():
            self.assertGreaterEqual(len(set(t.kind for t in compile_bundle(fixture).transitions)), 3)


class RhythmTests(unittest.TestCase):
    def test_hook_starts_immediately(self):
        self.assertEqual(compile_bundle(FIXTURES["money"]).scenes[0].rhythm[0].at, 0.0)

    def test_consequence_is_global_peak(self):
        bundle = compile_bundle(FIXTURES["money"])
        peaks = [max(beat.intensity for beat in scene.rhythm) for scene in bundle.scenes]
        self.assertEqual(peaks[-2], max(peaks))

    def test_payoff_contains_release(self):
        bundle = compile_bundle(FIXTURES["money"])
        self.assertLessEqual(min(beat.intensity for beat in bundle.scenes[-1].rhythm), .40)

    def test_story_rhythm_score_is_high(self):
        for fixture in FIXTURES.values():
            bundle = compile_bundle(fixture)
            self.assertGreaterEqual(story_rhythm_score(tuple(scene.rhythm for scene in bundle.scenes)), 90)


class BundleTests(unittest.TestCase):
    def test_all_archetypes_compile_without_failures(self):
        for name, fixture in FIXTURES.items():
            bundle = compile_bundle(fixture)
            self.assertFalse(bundle.failures, name)
            self.assertGreaterEqual(bundle.quality_score, 94, name)

    def test_all_dimensions_clear_thresholds(self):
        for fixture in FIXTURES.values():
            dims = compile_bundle(fixture).dimensions
            self.assertGreaterEqual(dims["audio_synchronization"], 95)
            self.assertGreaterEqual(dims["transition_continuity"], 90)
            self.assertGreaterEqual(dims["useful_occupancy"], 90)
            self.assertGreaterEqual(dims["motion_flow"], 90)
            self.assertGreaterEqual(dims["story_rhythm"], 90)

    def test_svg_is_deterministic(self):
        a = compile_bundle(FIXTURES["money"])
        b = compile_bundle(FIXTURES["money"])
        self.assertEqual([s.svg for s in a.scenes], [s.svg for s in b.scenes])

    def test_svg_contains_audio_and_motion_evidence(self):
        svg = compile_bundle(FIXTURES["money"]).scenes[0].svg
        self.assertIn("ENTRY", svg)
        self.assertIn("<polyline", svg)
        self.assertIn("stroke=\"#F2C14E\"", svg)

    def test_callback_token_matches_ends(self):
        for fixture in FIXTURES.values():
            bundle = compile_bundle(fixture)
            self.assertEqual(bundle.scenes[0].scene.callback_token, bundle.callback_token)
            self.assertEqual(bundle.scenes[-1].scene.callback_token, bundle.callback_token)

    def test_invalid_story_fails_closed(self):
        broken = dict(FIXTURES["money"])
        broken["scenes"] = list(broken["scenes"])[1:]
        with self.assertRaises(ValueError):
            compile_bundle(broken)

    def test_manifest_round_trip(self):
        text = json.dumps(compile_bundle(FIXTURES["money"]).to_dict(), sort_keys=True)
        self.assertIn("quality_score", text)
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), hashlib.sha256(text.encode()).hexdigest())

    def test_preview_files_can_be_written(self):
        bundle = compile_bundle(FIXTURES["money"])
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for index, scene in enumerate(bundle.scenes):
                (root / f"scene_{index:02d}.svg").write_text(scene.svg)
            self.assertEqual(len(list(root.glob("*.svg"))), 5)


class ScorecardTests(unittest.TestCase):
    def test_review_scope_is_above_97(self):
        self.assertGreaterEqual(sprint8_scorecard()["review_scope_percent"], 97)

    def test_production_claims_remain_zero(self):
        dims = sprint8_scorecard()["dimensions"]
        self.assertEqual(dims["production_wiring"], 0)
        self.assertEqual(dims["finished_mp4_proof"], 0)
        self.assertEqual(dims["real_channel_performance_proof"], 0)

    def test_pipeline_modified_is_false(self):
        self.assertFalse(sprint8_scorecard()["production_pipeline_modified"])


if __name__ == "__main__":
    unittest.main()
