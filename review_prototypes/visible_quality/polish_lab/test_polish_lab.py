from __future__ import annotations

import json
from pathlib import Path
import unittest

from .archetypes import ARCHETYPES, detect_archetype, select_mechanics
from .audio import audio_sync_score, compile_audio
from .caption_layout import font_size_for, layout_caption, platform_safe
from .caption_text import chunk_text, contrast_ratio, numeric_emphasis
from .critic import score_bundle
from .models import Box
from .render import render_polished_frame
from .suite import build_sprint_scorecard, compile_story_polish, render_story_frames
from .tension import compile_tension, tension_score
from .transitions import choose_transition, compile_transitions, transition_variety_score


def stories() -> dict[str, dict]:
    common = [
        {"role": "hook", "narration": "This changed faster than most people realize.", "duration": 3.2},
        {"role": "setup", "narration": "Start with the baseline so the scale is clear.", "duration": 4.0},
        {"role": "explanation", "narration": "Now watch the middle value move the story forward.", "duration": 4.2},
        {"role": "consequence", "narration": "That difference creates a real consequence for people.", "duration": 4.0},
        {"role": "payoff", "narration": "Return to the opening and make the gap finally click.", "duration": 3.6},
    ]
    return {
        "money": {"slug": "grocery", "unit": "$", "data": [{"label": "2019", "value": 680, "period": 2019}, {"label": "2022", "value": 860, "period": 2022}, {"label": "2026", "value": 1030, "period": 2026}], "beats": common},
        "share": {"slug": "energy_share", "unit": "%", "data": [{"label": "clean", "value": 42}, {"label": "fossil", "value": 58}], "beats": common},
        "ranking": {"slug": "population_rank", "unit": "", "data": [{"label": "A", "value": 1400}, {"label": "B", "value": 1420}, {"label": "C", "value": 340}, {"label": "D", "value": 280}], "beats": common},
        "comparison": {"slug": "rent_compare", "unit": "%", "data": [{"label": "City A", "value": 42}, {"label": "City B", "value": 68}], "beats": common},
        "single": {"slug": "single_stat", "unit": "%", "data": [{"label": "adults", "value": 73}], "beats": common},
    }


class TypographyTests(unittest.TestCase):
    def test_contrast_passes_white_on_dark(self):
        self.assertGreater(contrast_ratio("#F8FAFC", "#07101E"), 10)

    def test_invalid_hex_rejected(self):
        with self.assertRaises(ValueError):
            contrast_ratio("#FFF", "#000000")

    def test_numeric_emphasis(self):
        self.assertEqual(numeric_emphasis("2019 was $680 and now $1,030."), ("2019", "$680", "$1,030"))

    def test_caption_chunks_have_no_orphan(self):
        chunks = chunk_text("This is a sentence with one awkward final word")
        self.assertGreater(len(chunks[-1].split()), 1)

    def test_font_size_shrinks_for_longer_copy(self):
        self.assertGreater(font_size_for("BIG GAP", "hook", 820), font_size_for("This is a substantially longer hook phrase", "hook", 820))

    def test_layout_avoids_hero_and_platform_ui(self):
        hero = Box(100, 510, 760, 610)
        caption = layout_caption("2019 was $680. Now it is $1,030.", "hook", 3.2, hero)
        self.assertFalse(caption.box.overlaps(hero))
        self.assertTrue(platform_safe(caption.box))

    def test_no_space_raises(self):
        hero = Box(0, 180, 900, 1450)
        with self.assertRaises(ValueError):
            layout_caption("No space remains for this caption.", "hook", 3.0, hero)


class AudioTests(unittest.TestCase):
    def test_hook_audio_starts_early(self):
        caption = layout_caption("2019 was $680.", "hook", 3.0, Box(100, 510, 760, 610))
        plan = compile_audio("before_after_collision", caption, 3.0, "hook")
        self.assertLessEqual(plan.cues[0].at, .1)

    def test_numeric_emphasis_gets_ticks(self):
        caption = layout_caption("2019 was $680.", "hook", 3.0, Box(100, 510, 760, 610))
        plan = compile_audio("before_after_collision", caption, 3.0, "hook")
        self.assertTrue(any(cue.role == "caption" for cue in plan.cues))

    def test_payoff_has_silence_window(self):
        caption = layout_caption("The gap is the story.", "payoff", 3.4, Box(100, 510, 760, 610))
        plan = compile_audio("callback_bridge", caption, 3.4, "payoff")
        self.assertIsNotNone(plan.payoff_silence)

    def test_loudness_targets_are_bounded(self):
        caption = layout_caption("The bill jumped by $350.", "consequence", 3.0, Box(100, 510, 760, 610))
        plan = compile_audio("burden_stack", caption, 3.0, "consequence")
        self.assertEqual(plan.integrated_lufs_target, -14.0)
        self.assertLessEqual(plan.true_peak_dbtp, -1.0)

    def test_audio_sync_score_is_high(self):
        caption = layout_caption("2019 was $680.", "hook", 3.0, Box(100, 510, 760, 610))
        plan = compile_audio("before_after_collision", caption, 3.0, "hook")
        self.assertGreaterEqual(audio_sync_score(plan, caption), 80)


class TransitionTests(unittest.TestCase):
    def test_matching_focus_uses_object_match(self):
        trans = choose_transition({"role":"setup", "focal_label":"2026"}, {"role":"explanation", "focal_label":"2026"})
        self.assertEqual(trans.kind, "object_match")

    def test_line_to_stack_uses_morph(self):
        trans = choose_transition({"role":"explanation", "visual_event":"trend_line", "focal_label":"A"}, {"role":"consequence", "visual_event":"burden_stack", "focal_label":"B"})
        self.assertEqual(trans.kind, "data_morph")

    def test_callback_transition(self):
        trans = choose_transition({"role":"consequence", "callback_token":"x"}, {"role":"payoff", "callback_token":"x"})
        self.assertEqual(trans.kind, "callback_return")

    def test_repetition_falls_back(self):
        trans = choose_transition({"role":"setup", "focal_label":"x"}, {"role":"explanation", "focal_label":"x"}, ("object_match", "object_match"))
        self.assertEqual(trans.kind, "impact_cut")

    def test_transition_duration_is_short(self):
        trans = choose_transition({"role":"hook"}, {"role":"setup"})
        self.assertLessEqual(trans.duration, .45)

    def test_transition_sequence_varies(self):
        scenes = (
            {"role":"hook", "focal_label":"A"},
            {"role":"setup", "focal_label":"A"},
            {"role":"explanation", "visual_event":"trend_line", "focal_label":"B"},
            {"role":"consequence", "visual_event":"burden_stack", "focal_label":"C", "callback_token":"cb"},
            {"role":"payoff", "focal_label":"D", "callback_token":"cb"},
        )
        transitions = compile_transitions(scenes)
        self.assertEqual(len(transitions), 4)
        self.assertGreaterEqual(transition_variety_score(transitions), 75)


class TensionTests(unittest.TestCase):
    def test_consequence_is_peak_and_payoff_releases(self):
        scenes = tuple({"scene_id":f"s{i}", "role":role, "visual_event":event} for i,(role,event) in enumerate([
            ("hook","collision"),("setup","trend"),("explanation","trend"),("consequence","burden_stack"),("payoff","callback")]))
        plan = compile_tension(scenes)
        self.assertEqual(plan.peak_scene, "s3")
        self.assertGreaterEqual(plan.payoff_drop, 10)
        self.assertGreaterEqual(tension_score(plan), 85)


class ArchetypeTests(unittest.TestCase):
    def test_all_five_archetypes_detect(self):
        detected = {detect_archetype(story).name for story in stories().values()}
        self.assertEqual(detected, set(ARCHETYPES))

    def test_recent_mechanic_is_penalized(self):
        arch = ARCHETYPES["money_over_time"]
        first = select_mechanics(arch)[0]
        second = select_mechanics(arch, (first, first))[0]
        self.assertNotEqual(first, second)


class IntegrationTests(unittest.TestCase):
    def test_all_archetypes_compile_and_validate(self):
        for story in stories().values():
            bundle = compile_story_polish(story)
            bundle.validate()
            self.assertGreaterEqual(bundle.score, 85)

    def test_all_archetypes_render_svg(self):
        for story in stories().values():
            bundle = compile_story_polish(story)
            frames = render_story_frames(story, bundle)
            self.assertEqual(len(frames), len(story["beats"]))
            self.assertTrue(all("<svg" in svg and "1080" in svg and "1920" in svg for svg in frames.values()))

    def test_score_bundle_has_seven_dimensions(self):
        bundle = compile_story_polish(stories()["money"])
        score, dims, failures = score_bundle(bundle)
        self.assertEqual(len(dims), 7)
        self.assertFalse(failures)
        self.assertGreaterEqual(score, 85)

    def test_callback_transition_exists(self):
        bundle = compile_story_polish(stories()["money"])
        self.assertEqual(bundle.transitions[-1].kind, "callback_return")

    def test_caption_boxes_are_platform_safe(self):
        bundle = compile_story_polish(stories()["ranking"])
        self.assertTrue(all(scene.platform_safe for scene in bundle.scenes))

    def test_scorecard_is_honest_about_live_gaps(self):
        card = build_sprint_scorecard(30, 5)
        self.assertEqual(card.dimensions["production_wiring"], 0)
        self.assertEqual(card.dimensions["finished_mp4_proof"], 0)
        self.assertEqual(card.dimensions["real_channel_performance_proof"], 0)
        self.assertGreater(card.evidence["review_scope_percent"], 90)
        self.assertLess(card.overall_percent, 70)

    def test_scorecard_tracks_eleven_dimensions(self):
        card = build_sprint_scorecard(30, 5)
        self.assertEqual(len(card.dimensions), 11)

    def test_render_polished_frame_covers_each_archetype(self):
        for name, archetype in ARCHETYPES.items():
            story = next(story for story in stories().values() if detect_archetype(story).name == name)
            bundle = compile_story_polish(story)
            scene = bundle.scenes[0]
            svg = render_polished_frame(archetype, scene.visual_event, scene.caption, scene.hero_box)
            self.assertIn(archetype.name, svg)


class FixtureTests(unittest.TestCase):
    def test_fixture_summary_matches_current_outputs(self):
        fixture_path = Path(__file__).parent / "fixtures" / "sprint7_summary.json"
        summary = json.loads(fixture_path.read_text())
        bundles = [compile_story_polish(story) for story in stories().values()]
        self.assertEqual(summary["archetypes_proven"], len(bundles))
        self.assertEqual(summary["tests_passed"], 30)
        self.assertFalse(summary["production_pipeline_modified"])
        self.assertAlmostEqual(summary["average_polish_score"], round(sum(b.score for b in bundles)/len(bundles), 1))


if __name__ == "__main__":
    unittest.main()
