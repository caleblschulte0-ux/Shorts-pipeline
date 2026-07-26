from __future__ import annotations

import unittest

from experiments.curiosity_nextgen.caption_readability import CaptionCue, CaptionDecision, analyze_caption_readability, evaluate_caption
from experiments.curiosity_nextgen.cognitive_load import InformationBeat, LoadDecision, analyze_cognitive_load, evaluate_information_beat
from experiments.curiosity_nextgen.continuity_editor import ContinuityDecision, ContinuityShot, analyze_continuity
from experiments.curiosity_nextgen.edit_blueprint import (
    EditArea,
    EditIssue,
    EditPass,
    StoryEditCandidate,
    build_batch_edit_program,
    build_edit_blueprint,
)
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
        text="The visible mechanism changes here.",
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
        location="lab",
        geography="neutral",
        era="modern",
        time_of_day="day",
        wardrobe="blue shirt",
        dominant_prop="model",
        screen_direction="left",
        lighting_family="soft daylight",
        factual_context="mechanism demonstration",
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
        repair="rebuild the opening from the detected defect contract",
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


def candidate(story_id: str, topic: str = "science", fmt: str = "mechanism", **overrides) -> StoryEditCandidate:
    values = dict(
        story_id=story_id,
        topic_family=topic,
        format_family=fmt,
        issues=(issue(f"{story_id}:hook"), issue(f"{story_id}:payoff", target_id="ending", repair="resolve the promised answer", is_hook=False, is_payoff=True)),
        readiness=8.0,
        novelty=8.0,
        strategic_value=7.0,
    )
    values.update(overrides)
    return StoryEditCandidate(**values)


class RetentionRiskTests(unittest.TestCase):
    def test_strong_moment_is_low_risk(self):
        self.assertEqual(evaluate_moment(retention()).level, RetentionRiskLevel.LOW)

    def test_weak_interest_is_detected(self):
        result = evaluate_moment(retention(novelty=2, curiosity=2, emotional_relevance=2))
        self.assertIn("weak_interest_signal", {item.code for item in result.defects})

    def test_early_risk_is_weighted_more_heavily(self):
        early = evaluate_moment(retention(start=0, novelty=3, curiosity=3, emotional_relevance=3))
        late = evaluate_moment(retention(start=40, novelty=3, curiosity=3, emotional_relevance=3))
        self.assertGreater(early.risk_score, late.risk_score)

    def test_duplicate_moment_id_raises(self):
        with self.assertRaises(ValueError):
            analyze_retention_risk((retention("x", 0), retention("x", 10)))


class CognitiveLoadTests(unittest.TestCase):
    def test_simple_beat_passes(self):
        self.assertEqual(analyze_cognitive_load((info(),)).decision, LoadDecision.PASS)

    def test_dense_speech_is_detected(self):
        result = evaluate_information_beat(info(spoken_words=40, duration_seconds=5))
        self.assertIn("speech_too_dense", {item.code for item in result.defects})

    def test_consecutive_overload_run_is_reported(self):
        report = analyze_cognitive_load((info("a", new_concepts=6), info("b", new_concepts=6)))
        self.assertTrue(report.consecutive_overload_runs)

    def test_duplicate_beat_id_raises(self):
        with self.assertRaises(ValueError):
            analyze_cognitive_load((info("x"), info("x")))


class CaptionReadabilityTests(unittest.TestCase):
    def test_readable_caption_passes(self):
        self.assertEqual(analyze_caption_readability((caption(),)).decision, CaptionDecision.PASS)

    def test_excess_reading_speed_is_detected(self):
        result = evaluate_caption(caption(end=0.5, text="This caption contains far too many words for half a second."))
        self.assertIn("reading_speed_excess", {item.code for item in result.defects})

    def test_low_contrast_is_detected(self):
        result = evaluate_caption(caption(contrast_ratio=2.0))
        self.assertIn("insufficient_contrast", {item.code for item in result.defects})

    def test_overlapping_cues_raise(self):
        with self.assertRaises(ValueError):
            analyze_caption_readability((caption("a", 0, 2), caption("b", 1, 3)))


class ContinuityEditorTests(unittest.TestCase):
    def test_consistent_shots_pass(self):
        self.assertEqual(analyze_continuity((shot("a", 0), shot("b", 1))).decision, ContinuityDecision.PASS)

    def test_geography_mismatch_blocks(self):
        report = analyze_continuity((shot("a", 0), shot("b", 1, geography="different_region")))
        self.assertEqual(report.decision, ContinuityDecision.BLOCK)

    def test_intentional_break_suppresses_transition_defects(self):
        report = analyze_continuity((shot("a", 0), shot("b", 1, geography="different_region", intentional_break=True, break_explanation="new example")))
        self.assertFalse(report.defects)

    def test_duplicate_shot_id_raises(self):
        with self.assertRaises(ValueError):
            analyze_continuity((shot("x", 0), shot("x", 1)))


class VisualReadabilityTests(unittest.TestCase):
    def test_clear_frame_passes(self):
        self.assertEqual(analyze_visual_readability((frame(),)).decision, ReadabilityDecision.PASS)

    def test_object_clutter_is_detected(self):
        result = evaluate_frame(frame(competing_object_count=9))
        self.assertIn("object_clutter", {item.code for item in result.defects})

    def test_illegible_evidence_can_block(self):
        report = analyze_visual_readability((frame(evidence_legible=False, focal_object_count=0, caption_zone_clear=False),))
        self.assertEqual(report.decision, ReadabilityDecision.BLOCK)


class HumorPersonalityTests(unittest.TestCase):
    def test_character_specific_joke_passes(self):
        self.assertEqual(evaluate_humor_beat(joke()).decision, HumorDecision.PASS)

    def test_irrelevant_joke_is_detected(self):
        result = evaluate_humor_beat(joke(relevance=2.0))
        self.assertIn("story_irrelevant_joke", {item.code for item in result.defects})

    def test_harmful_target_is_removed(self):
        self.assertEqual(evaluate_humor_beat(joke(targets_vulnerable_group=True)).decision, HumorDecision.REMOVE)


class EmotionalResonanceTests(unittest.TestCase):
    def test_varied_strong_emotion_passes(self):
        report = analyze_emotional_resonance((emotion("a", EmotionalFunction.STAKES), emotion("b", EmotionalFunction.RELIEF)))
        self.assertEqual(report.decision, ResonanceDecision.PASS)

    def test_abstract_stakes_are_detected(self):
        result = evaluate_emotional_beat(emotion(human_specificity=2.0))
        self.assertIn("abstract_human_stakes", {item.code for item in result.defects})

    def test_manipulative_language_blocks(self):
        report = analyze_emotional_resonance((emotion(manipulative_language=True),))
        self.assertEqual(report.decision, ResonanceDecision.BLOCK)


class EditBlueprintTests(unittest.TestCase):
    def test_dependencies_are_ordered(self):
        plan = build_edit_blueprint((issue("a"), issue("b", target_id="ending", repair="resolve ending", depends_on=("a",), is_hook=False, is_payoff=True)), 10)
        self.assertEqual([item.issue_id for item in plan.selected_edits], ["a", "b"])

    def test_budget_defers_lower_priority_work(self):
        plan = build_edit_blueprint((issue("a", effort=2), issue("b", target_id="middle", repair="fix middle", effort=3, is_hook=False)), 2.5)
        self.assertEqual(len(plan.selected_edits), 1)

    def test_hard_blocker_can_exceed_story_budget(self):
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

    def test_plan_warns_when_payoff_is_missing(self):
        plan = build_edit_blueprint((issue(),), 5)
        self.assertIn("the selected plan contains no payoff-focused edit", plan.warnings)

    def test_batch_program_handles_multiple_stories(self):
        program = build_batch_edit_program((candidate("story-a"), candidate("story-b", topic="history")), total_effort_budget=20, per_story_effort_cap=10)
        self.assertEqual(len(program.selected_plans), 2)

    def test_batch_program_supports_fifty_story_capacity(self):
        stories = tuple(candidate(f"story-{index}", topic=f"topic-{index}") for index in range(50))
        program = build_batch_edit_program(stories, total_effort_budget=500, per_story_effort_cap=10, max_stories=50, max_per_topic_family=1)
        self.assertEqual(len(program.selected_plans), 50)

    def test_more_than_fifty_story_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            build_batch_edit_program((candidate("a"),), total_effort_budget=10, per_story_effort_cap=5, max_stories=51)

    def test_duplicate_story_id_raises(self):
        with self.assertRaises(ValueError):
            build_batch_edit_program((candidate("same"), candidate("same", topic="history")), total_effort_budget=20, per_story_effort_cap=10)

    def test_topic_family_cap_defers_excess(self):
        program = build_batch_edit_program((candidate("a"), candidate("b"), candidate("c")), total_effort_budget=30, per_story_effort_cap=10, max_per_topic_family=2)
        self.assertEqual(len(program.selected_plans), 2)
        self.assertEqual(len(program.deferred_story_ids), 1)

    def test_total_budget_defers_excess_stories(self):
        program = build_batch_edit_program((candidate("a"), candidate("b")), total_effort_budget=4, per_story_effort_cap=10)
        self.assertEqual(len(program.selected_plans), 1)


if __name__ == "__main__":
    unittest.main()
