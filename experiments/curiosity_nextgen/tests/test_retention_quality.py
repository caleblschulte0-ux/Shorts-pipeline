from __future__ import annotations

import unittest

from experiments.curiosity_nextgen.caption_readability import CaptionCue, CaptionDecision, analyze_caption_readability, evaluate_caption
from experiments.curiosity_nextgen.cognitive_load import InformationBeat, LoadDecision, analyze_cognitive_load, evaluate_information_beat
from experiments.curiosity_nextgen.continuity_editor import ContinuityDecision, ContinuityShot, analyze_continuity
from experiments.curiosity_nextgen.edit_blueprint import EditArea, EditIssue, EditPass, build_edit_blueprint, money_goes_retention_blueprint
from experiments.curiosity_nextgen.emotional_resonance import EmotionalBeat, EmotionalFunction, ResonanceDecision, analyze_emotional_resonance, evaluate_emotional_beat
from experiments.curiosity_nextgen.humor_personality import HumorBeat, HumorDecision, HumorDevice, analyze_humor_personality, evaluate_humor_beat
from experiments.curiosity_nextgen.retention_risk import RetentionMoment, RetentionRiskLevel, analyze_retention_risk, evaluate_moment
from experiments.curiosity_nextgen.visual_readability import FrameReadability, ReadabilityDecision, analyze_visual_readability, evaluate_frame


def retention(moment_id: str = "m1", start: float = 0.0, **overrides) -> RetentionMoment:
    values = dict(
        moment_id=moment_id,
        start_seconds=start,
        duration_seconds=6.0,
        novelty=8.0,
        curiosity=8.0,
        clarity=8.0,
        emotional_relevance=8.0,
        visual_change=8.0,
        audio_change=8.0,
        proof_strength=8.0,
        cognitive_load=4.0,
    )
    values.update(overrides)
    return RetentionMoment(**values)


def info(beat_id: str = "b1", **overrides) -> InformationBeat:
    values = dict(
        beat_id=beat_id,
        duration_seconds=8.0,
        spoken_words=20,
        visible_words=4,
        new_concepts=1,
        numeric_values=0,
        named_entities=0,
        simultaneous_visual_elements=3,
        includes_example=True,
        includes_visual_mapping=True,
        pause_after_seconds=1.0,
    )
    values.update(overrides)
    return InformationBeat(**values)


def caption(cue_id: str = "c1", start: float = 0.0, end: float = 2.5, **overrides) -> CaptionCue:
    values = dict(
        cue_id=cue_id,
        start_seconds=start,
        end_seconds=end,
        text="Your paycheck splits here.",
        line_count=1,
        max_line_characters=28,
        contrast_ratio=7.0,
        font_height_percent=5.0,
        bottom_safe_margin_percent=12.0,
        emphasized_word_count=1,
    )
    values.update(overrides)
    return CaptionCue(**values)


def shot(shot_id: str, order: int, **overrides) -> ContinuityShot:
    values = dict(
        shot_id=shot_id,
        order=order,
        subject_id="hero",
        location="office",
        geography="United States",
        era="modern",
        time_of_day="day",
        wardrobe="blue shirt",
        dominant_prop="paycheck",
        screen_direction="left",
        lighting_family="soft daylight",
        factual_context="paycheck deductions",
    )
    values.update(overrides)
    return ContinuityShot(**values)


def frame(frame_id: str = "f1", **overrides) -> FrameReadability:
    values = dict(
        frame_id=frame_id,
        focal_object_count=1,
        competing_object_count=2,
        text_element_count=1,
        smallest_important_detail_percent=5.0,
        subject_background_contrast=7.0,
        focal_separation=8.0,
        motion_competition=3.0,
        caption_zone_clear=True,
        evidence_legible=True,
        hierarchy_explicit=True,
        decorative_element_count=2,
    )
    values.update(overrides)
    return FrameReadability(**values)


def joke(beat_id: str = "j1", **overrides) -> HumorBeat:
    values = dict(
        beat_id=beat_id,
        device=HumorDevice.CHARACTER_REACTION,
        setup_clarity=8.0,
        surprise=8.0,
        relevance=8.0,
        tone_fit=8.0,
        character_specificity=8.0,
        punchline_speed_seconds=2.0,
    )
    values.update(overrides)
    return HumorBeat(**values)


def emotion(beat_id: str = "e1", function: EmotionalFunction = EmotionalFunction.STAKES, **overrides) -> EmotionalBeat:
    values = dict(
        beat_id=beat_id,
        function=function,
        human_specificity=8.0,
        visible_consequence=8.0,
        emotional_change=8.0,
        story_relevance=8.0,
        authenticity=8.0,
        setup_strength=6.0,
        payoff_strength=7.0,
    )
    values.update(overrides)
    return EmotionalBeat(**values)


def issue(issue_id: str = "i1", **overrides) -> EditIssue:
    values = dict(
        issue_id=issue_id,
        area=EditArea.RETENTION,
        target_id="opening",
        description="opening risk",
        repair="rebuild opening",
        severity=8.0,
        confidence=8.0,
        expected_uplift=0.8,
        effort=2.0,
        edit_pass=EditPass.STORY,
        start_seconds=0.0,
        is_hook=True,
    )
    values.update(overrides)
    return EditIssue(**values)


class RetentionRiskTests(unittest.TestCase):
    def test_strong_moment_is_low_risk(self):
        self.assertEqual(evaluate_moment(retention()).level, RetentionRiskLevel.LOW)

    def test_weak_interest_is_detected(self):
        report = evaluate_moment(retention(novelty=2, curiosity=2, emotional_relevance=2))
        self.assertIn("weak_interest_signal", {item.code for item in report.defects})

    def test_cognitive_overload_is_detected(self):
        report = evaluate_moment(retention(cognitive_load=10))
        self.assertIn("cognitive_overload", {item.code for item in report.defects})

    def test_static_hold_is_detected(self):
        report = evaluate_moment(retention(static_seconds=5.0))
        self.assertIn("long_static_hold", {item.code for item in report.defects})

    def test_early_risk_is_weighted_more_heavily(self):
        early = evaluate_moment(retention(start=0, novelty=3, curiosity=3, emotional_relevance=3))
        late = evaluate_moment(retention(start=40, novelty=3, curiosity=3, emotional_relevance=3))
        self.assertGreater(early.risk_score, late.risk_score)

    def test_payoff_without_proof_is_penalized(self):
        report = evaluate_moment(retention(payoff_moment=True, proof_strength=1))
        self.assertIn("weak_visible_proof", {item.code for item in report.defects})

    def test_duplicate_moment_id_raises(self):
        with self.assertRaises(ValueError):
            analyze_retention_risk((retention("x", 0), retention("x", 10)))

    def test_overlapping_moments_raise(self):
        with self.assertRaises(ValueError):
            analyze_retention_risk((retention("a", 0), retention("b", 3)))


class CognitiveLoadTests(unittest.TestCase):
    def test_simple_beat_passes(self):
        self.assertEqual(analyze_cognitive_load((info(),)).decision, LoadDecision.PASS)

    def test_dense_speech_is_detected(self):
        result = evaluate_information_beat(info(spoken_words=40, duration_seconds=5))
        self.assertIn("speech_too_dense", {item.code for item in result.defects})

    def test_reading_conflict_is_detected(self):
        result = evaluate_information_beat(info(visible_words=30, duration_seconds=5))
        self.assertIn("text_reading_conflict", {item.code for item in result.defects})

    def test_concept_stack_is_detected(self):
        result = evaluate_information_beat(info(new_concepts=4))
        self.assertIn("concept_stack", {item.code for item in result.defects})

    def test_number_stack_is_detected(self):
        result = evaluate_information_beat(info(numeric_values=5))
        self.assertIn("number_stack", {item.code for item in result.defects})

    def test_consecutive_overload_run_is_reported(self):
        report = analyze_cognitive_load((info("a", new_concepts=6), info("b", new_concepts=6)))
        self.assertTrue(report.consecutive_overload_runs)

    def test_duplicate_beat_id_raises(self):
        with self.assertRaises(ValueError):
            analyze_cognitive_load((info("x"), info("x")))

    def test_empty_load_input_raises(self):
        with self.assertRaises(ValueError):
            analyze_cognitive_load(())


class CaptionReadabilityTests(unittest.TestCase):
    def test_readable_caption_passes(self):
        self.assertEqual(analyze_caption_readability((caption(),)).decision, CaptionDecision.PASS)

    def test_excess_reading_speed_is_detected(self):
        result = evaluate_caption(caption(end=0.5, text="This caption contains far too many words for half a second."))
        self.assertIn("reading_speed_excess", {item.code for item in result.defects})

    def test_too_many_lines_are_detected(self):
        result = evaluate_caption(caption(line_count=4))
        self.assertIn("too_many_lines", {item.code for item in result.defects})

    def test_low_contrast_is_detected(self):
        result = evaluate_caption(caption(contrast_ratio=2.0))
        self.assertIn("insufficient_contrast", {item.code for item in result.defects})

    def test_unsafe_margin_is_detected(self):
        result = evaluate_caption(caption(bottom_safe_margin_percent=2.0))
        self.assertIn("unsafe_bottom_margin", {item.code for item in result.defects})

    def test_focal_overlap_is_detected(self):
        result = evaluate_caption(caption(important_visual_overlap=True))
        self.assertIn("focal_visual_overlap", {item.code for item in result.defects})

    def test_semantic_break_is_detected(self):
        result = evaluate_caption(caption(hard_line_break_mid_phrase=True))
        self.assertIn("semantic_line_break", {item.code for item in result.defects})

    def test_overlapping_cues_raise(self):
        with self.assertRaises(ValueError):
            analyze_caption_readability((caption("a", 0, 2), caption("b", 1, 3)))


class ContinuityEditorTests(unittest.TestCase):
    def test_consistent_shots_pass(self):
        self.assertEqual(analyze_continuity((shot("a", 0), shot("b", 1))).decision, ContinuityDecision.PASS)

    def test_geography_mismatch_blocks(self):
        report = analyze_continuity((shot("a", 0), shot("b", 1, geography="Japan")))
        self.assertIn("geography_mismatch", {item.code for item in report.defects})
        self.assertEqual(report.decision, ContinuityDecision.BLOCK)

    def test_era_mismatch_blocks(self):
        report = analyze_continuity((shot("a", 0), shot("b", 1, era="Victorian")))
        self.assertIn("era_mismatch", {item.code for item in report.defects})

    def test_wardrobe_jump_is_detected(self):
        report = analyze_continuity((shot("a", 0), shot("b", 1, wardrobe="red coat")))
        self.assertIn("wardrobe_jump", {item.code for item in report.defects})

    def test_direction_flip_is_detected(self):
        report = analyze_continuity((shot("a", 0), shot("b", 1, screen_direction="right")))
        self.assertIn("screen_direction_flip", {item.code for item in report.defects})

    def test_intentional_break_suppresses_transition_defects(self):
        report = analyze_continuity((shot("a", 0), shot("b", 1, geography="Japan", intentional_break=True, break_explanation="new example")))
        self.assertFalse(report.defects)

    def test_duplicate_shot_id_raises(self):
        with self.assertRaises(ValueError):
            analyze_continuity((shot("x", 0), shot("x", 1)))

    def test_duplicate_order_raises(self):
        with self.assertRaises(ValueError):
            analyze_continuity((shot("a", 0), shot("b", 0)))


class VisualReadabilityTests(unittest.TestCase):
    def test_clear_frame_passes(self):
        self.assertEqual(analyze_visual_readability((frame(),)).decision, ReadabilityDecision.PASS)

    def test_missing_focal_object_is_detected(self):
        result = evaluate_frame(frame(focal_object_count=0))
        self.assertIn("missing_focal_object", {item.code for item in result.defects})

    def test_object_clutter_is_detected(self):
        result = evaluate_frame(frame(competing_object_count=9))
        self.assertIn("object_clutter", {item.code for item in result.defects})

    def test_tiny_evidence_is_detected(self):
        result = evaluate_frame(frame(smallest_important_detail_percent=1.0))
        self.assertIn("important_detail_too_small", {item.code for item in result.defects})

    def test_weak_contrast_is_detected(self):
        result = evaluate_frame(frame(subject_background_contrast=2.0))
        self.assertIn("weak_subject_contrast", {item.code for item in result.defects})

    def test_blocked_caption_zone_is_detected(self):
        result = evaluate_frame(frame(caption_zone_clear=False))
        self.assertIn("caption_zone_blocked", {item.code for item in result.defects})

    def test_illegible_evidence_can_block(self):
        report = analyze_visual_readability((frame(evidence_legible=False, focal_object_count=0, caption_zone_clear=False),))
        self.assertEqual(report.decision, ReadabilityDecision.BLOCK)

    def test_duplicate_frame_id_raises(self):
        with self.assertRaises(ValueError):
            analyze_visual_readability((frame("x"), frame("x")))


class HumorPersonalityTests(unittest.TestCase):
    def test_character_specific_joke_passes(self):
        self.assertEqual(evaluate_humor_beat(joke()).decision, HumorDecision.PASS)

    def test_irrelevant_joke_is_detected(self):
        result = evaluate_humor_beat(joke(relevance=2.0))
        self.assertIn("story_irrelevant_joke", {item.code for item in result.defects})

    def test_tone_break_is_detected(self):
        result = evaluate_humor_beat(joke(tone_fit=2.0))
        self.assertIn("tone_break", {item.code for item in result.defects})

    def test_generic_voice_is_detected(self):
        result = evaluate_humor_beat(joke(character_specificity=2.0))
        self.assertIn("generic_voice", {item.code for item in result.defects})

    def test_slow_punchline_is_detected(self):
        result = evaluate_humor_beat(joke(punchline_speed_seconds=9.0))
        self.assertIn("slow_punchline", {item.code for item in result.defects})

    def test_harmful_target_is_removed(self):
        self.assertEqual(evaluate_humor_beat(joke(targets_vulnerable_group=True)).decision, HumorDecision.REMOVE)

    def test_unresolved_callback_is_detected(self):
        result = evaluate_humor_beat(joke(callback_key="paycheck"))
        self.assertIn("unresolved_humor_callback", {item.code for item in result.defects})

    def test_duplicate_humor_beat_raises(self):
        with self.assertRaises(ValueError):
            analyze_humor_personality((joke("x"), joke("x")))


class EmotionalResonanceTests(unittest.TestCase):
    def test_varied_strong_emotion_passes(self):
        report = analyze_emotional_resonance((emotion("a", EmotionalFunction.STAKES), emotion("b", EmotionalFunction.RELIEF)))
        self.assertEqual(report.decision, ResonanceDecision.PASS)

    def test_abstract_stakes_are_detected(self):
        result = evaluate_emotional_beat(emotion(human_specificity=2.0))
        self.assertIn("abstract_human_stakes", {item.code for item in result.defects})

    def test_invisible_consequence_is_detected(self):
        result = evaluate_emotional_beat(emotion(visible_consequence=2.0))
        self.assertIn("consequence_not_visible", {item.code for item in result.defects})

    def test_static_emotion_is_detected(self):
        result = evaluate_emotional_beat(emotion(emotional_change=1.0))
        self.assertIn("emotionally_static", {item.code for item in result.defects})

    def test_manipulative_language_blocks(self):
        report = analyze_emotional_resonance((emotion(manipulative_language=True),))
        self.assertEqual(report.decision, ResonanceDecision.BLOCK)

    def test_unsupported_stakes_block(self):
        report = analyze_emotional_resonance((emotion(unsupported_stakes=True),))
        self.assertEqual(report.decision, ResonanceDecision.BLOCK)

    def test_setup_without_payoff_is_detected(self):
        result = evaluate_emotional_beat(emotion(setup_strength=9.0, payoff_strength=1.0))
        self.assertIn("emotional_setup_without_payoff", {item.code for item in result.defects})

    def test_duplicate_emotional_beat_raises(self):
        with self.assertRaises(ValueError):
            analyze_emotional_resonance((emotion("x"), emotion("x")))


class EditBlueprintTests(unittest.TestCase):
    def test_dependencies_are_ordered(self):
        plan = build_edit_blueprint((issue("a"), issue("b", target_id="ending", repair="resolve ending", depends_on=("a",), is_hook=False, is_payoff=True)), 10)
        self.assertEqual([item.issue_id for item in plan.selected_edits], ["a", "b"])

    def test_budget_defers_lower_priority_work(self):
        plan = build_edit_blueprint((issue("a", effort=2), issue("b", target_id="middle", repair="fix middle", effort=3, is_hook=False)), 2.5)
        self.assertEqual(len(plan.selected_edits), 1)
        self.assertTrue(plan.deferred_issue_ids)

    def test_hard_blocker_can_exceed_budget(self):
        plan = build_edit_blueprint((issue("a", effort=5, hard_blocker=True),), 1)
        self.assertEqual(plan.selected_edits[0].issue_id, "a")

    def test_unknown_dependency_raises(self):
        with self.assertRaises(ValueError):
            build_edit_blueprint((issue("a", depends_on=("missing",)),), 5)

    def test_dependency_cycle_raises(self):
        with self.assertRaises(ValueError):
            build_edit_blueprint((issue("a", depends_on=("b",)), issue("b", target_id="x", repair="other", depends_on=("a",), is_hook=False)), 10)

    def test_duplicate_issue_id_raises(self):
        with self.assertRaises(ValueError):
            build_edit_blueprint((issue("x"), issue("x", target_id="y", repair="other")), 10)

    def test_money_goes_blueprint_contains_hook_and_payoff(self):
        items = money_goes_retention_blueprint()
        self.assertTrue(any(item.is_hook for item in items))
        self.assertTrue(any(item.is_payoff for item in items))

    def test_plan_warns_when_payoff_is_missing(self):
        plan = build_edit_blueprint((issue(),), 5)
        self.assertIn("the selected plan contains no payoff-focused edit", plan.warnings)


if __name__ == "__main__":
    unittest.main()
