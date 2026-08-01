from __future__ import annotations

import unittest

from experiments.curiosity_nextgen.audio_dynamics import AudioBeat, AudioBeatKind, analyze_audio_dynamics
from experiments.curiosity_nextgen.curiosity_curve import CuriosityBeat, QuestionLoop, analyze_curiosity_curve
from experiments.curiosity_nextgen.narration_rhythm import NarrationSegment, analyze_narration
from experiments.curiosity_nextgen.promise_packaging import ThumbnailConcept, TitleCandidate, evaluate_packaging, rank_packaging
from experiments.curiosity_nextgen.scene_choreography import CameraMove, ChoreographyBeat, ScreenDirection, analyze_choreography
from experiments.curiosity_nextgen.viewer_experience import ExperienceArea, ExperienceObservation, evaluate_viewer_experience
from experiments.curiosity_nextgen.visual_grammar import BeatVisualNeed, SceneIntent, VisualFamily, VisualFamilySpec, plan_visual_grammar


class CuriosityCurveTests(unittest.TestCase):
    def beat(self, beat_id: str, start: float, novelty: float = 7, stakes: float = 7, revelation: float = 7):
        return CuriosityBeat(beat_id, start, novelty, stakes, revelation)

    def test_unresolved_major_loop_blocks_score(self):
        report = analyze_curiosity_curve((QuestionLoop("q1", 0, 9, 60),), (self.beat("b1", 0),))
        self.assertIn("unresolved_loop", {item.code for item in report.defects})
        self.assertLess(report.score, 9)

    def test_late_resolution_detected(self):
        loop = QuestionLoop("q1", 0, 7, 30, resolved_at=50, answer_specificity=8, visual_proof=True)
        self.assertIn("late_resolution", {item.code for item in analyze_curiosity_curve((loop,), (self.beat("b1", 0),)).defects})

    def test_vague_resolution_detected(self):
        loop = QuestionLoop("q1", 0, 7, 30, resolved_at=20, answer_specificity=3, visual_proof=True)
        self.assertIn("vague_resolution", {item.code for item in analyze_curiosity_curve((loop,), (self.beat("b1", 0),)).defects})

    def test_major_loop_requires_visual_proof(self):
        loop = QuestionLoop("q1", 0, 9, 30, resolved_at=20, answer_specificity=9)
        self.assertIn("major_loop_without_visual_proof", {item.code for item in analyze_curiosity_curve((loop,), (self.beat("b1", 0),)).defects})

    def test_open_loop_overload_detected(self):
        loops = tuple(QuestionLoop(f"q{i}", i, 6, 80, resolved_at=70, answer_specificity=8, visual_proof=True) for i in range(6))
        self.assertIn("open_loop_overload", {item.code for item in analyze_curiosity_curve(loops, (self.beat("b1", 0),)).defects})

    def test_revelation_drought_detected(self):
        beats = tuple(self.beat(f"b{i}", i * 5, novelty=3, revelation=2) for i in range(4))
        codes = {item.code for item in analyze_curiosity_curve((), beats).defects}
        self.assertIn("revelation_drought", codes)
        self.assertIn("low_novelty_run", codes)

    def test_strong_curve_scores_well(self):
        loops = (QuestionLoop("q1", 0, 9, 60, resolved_at=45, answer_specificity=9, visual_proof=True),)
        beats = (self.beat("b1", 0, stakes=4), self.beat("b2", 12, revelation=8), self.beat("b3", 25, stakes=7), self.beat("b4", 45, revelation=9, stakes=9))
        self.assertGreaterEqual(analyze_curiosity_curve(loops, beats).score, 8.5)

    def test_duplicate_loop_id_raises(self):
        loop = QuestionLoop("q", 0, 5, 20)
        with self.assertRaises(ValueError):
            analyze_curiosity_curve((loop, loop), ())


class NarrationRhythmTests(unittest.TestCase):
    def segment(self, segment_id: str, start: float, text: str = "Where did the money go? We follow every dollar.", duration: float = 5, pause: float = 0.4, emphasis: int = 1):
        return NarrationSegment(segment_id, start, duration, text, pause, emphasis)

    def test_missing_narration_is_failure(self):
        self.assertEqual(analyze_narration(()).score, 0)

    def test_fast_segment_detected(self):
        text = " ".join(["money"] * 50)
        self.assertIn("segment_too_fast", {item.code for item in analyze_narration((self.segment("s1", 0, text, 5),)).defects})

    def test_slow_segment_detected(self):
        self.assertIn("segment_too_slow", {item.code for item in analyze_narration((self.segment("s1", 0, "One idea.", 10),)).defects})

    def test_overlong_sentence_detected(self):
        text = " ".join(["word"] * 30) + "."
        self.assertIn("overlong_sentence", {item.code for item in analyze_narration((self.segment("s1", 20, text, 12),)).defects})

    def test_dense_opening_detected(self):
        text = " ".join(["word"] * 46) + "."
        self.assertIn("dense_opening", {item.code for item in analyze_narration((self.segment("s1", 0, text, 18),)).defects})

    def test_breathless_run_detected(self):
        text = " ".join(["word"] * 20) + "."
        segments = tuple(self.segment(f"s{i}", i * 6, text, 6, pause=0.0) for i in range(3))
        self.assertIn("breathless_run", {item.code for item in analyze_narration(segments).defects})

    def test_monotone_sentence_cadence_detected(self):
        text = "One two three four. Five six seven eight. Nine ten eleven twelve. Thirteen fourteen fifteen sixteen. Seventeen eighteen nineteen twenty."
        self.assertIn("monotone_sentence_cadence", {item.code for item in analyze_narration((self.segment("s1", 35, text, 12),)).defects})

    def test_strong_narration_scores_above_weak(self):
        strong = (
            self.segment("s1", 0, "Where did your paycheck go?", 2.5, 0.5, 1),
            self.segment("s2", 3, "First, the obvious slice: taxes.", 3.5, 0.4, 1),
            self.segment("s3", 7, "But the strange part is what happens after that.", 4.2, 0.6, 2),
        )
        weak_text = " ".join(["money"] * 50)
        weak = tuple(self.segment(f"w{i}", i * 5, weak_text, 5, 0.0, 0) for i in range(3))
        self.assertGreater(analyze_narration(strong).score, analyze_narration(weak).score)

    def test_duplicate_segment_id_raises(self):
        segment = self.segment("s1", 0)
        with self.assertRaises(ValueError):
            analyze_narration((segment, segment))


class VisualGrammarTests(unittest.TestCase):
    def specs(self):
        return (
            VisualFamilySpec(VisualFamily.CHARACTER, frozenset({SceneIntent.CHARACTER, SceneIntent.CONSEQUENCE, SceneIntent.PAYOFF}), supports_character=True),
            VisualFamilySpec(VisualFamily.REAL_MEDIA, frozenset({SceneIntent.EVIDENCE, SceneIntent.SCALE}), supports_real_evidence=True),
            VisualFamilySpec(VisualFamily.MECHANISM, frozenset({SceneIntent.MECHANISM, SceneIntent.COMPARISON, SceneIntent.PAYOFF})),
            VisualFamilySpec(VisualFamily.DIAGRAM, frozenset({SceneIntent.QUESTION, SceneIntent.MECHANISM, SceneIntent.COMPARISON})),
            VisualFamilySpec(VisualFamily.TEXT_CARD, frozenset(set(SceneIntent)), text_heavy=True),
        )

    def test_plan_uses_multiple_families(self):
        needs = (
            BeatVisualNeed("b1", SceneIntent.QUESTION, "money", "curious"),
            BeatVisualNeed("b2", SceneIntent.EVIDENCE, "money", "serious", requires_real_evidence=True),
            BeatVisualNeed("b3", SceneIntent.CHARACTER, "money", "worried", requires_character=True),
            BeatVisualNeed("b4", SceneIntent.MECHANISM, "money", "clear"),
        )
        self.assertGreaterEqual(len(plan_visual_grammar(needs, self.specs()).family_counts), 3)

    def test_character_requirement_is_enforced(self):
        plan = plan_visual_grammar((BeatVisualNeed("b1", SceneIntent.CHARACTER, "money", "curious", requires_character=True),), self.specs())
        self.assertEqual(plan.assignments[0].family, VisualFamily.CHARACTER)

    def test_evidence_requirement_is_enforced(self):
        plan = plan_visual_grammar((BeatVisualNeed("b1", SceneIntent.EVIDENCE, "money", "serious", requires_real_evidence=True),), self.specs())
        self.assertEqual(plan.assignments[0].family, VisualFamily.REAL_MEDIA)

    def test_no_eligible_family_raises(self):
        with self.assertRaises(ValueError):
            plan_visual_grammar((BeatVisualNeed("b1", SceneIntent.EVIDENCE, "money", "serious", requires_real_evidence=True),), (VisualFamilySpec(VisualFamily.TEXT_CARD, frozenset({SceneIntent.EVIDENCE})),))

    def test_text_card_overuse_detected(self):
        needs = tuple(BeatVisualNeed(f"b{i}", SceneIntent.QUESTION, "x", "x") for i in range(5))
        specs = (VisualFamilySpec(VisualFamily.TEXT_CARD, frozenset({SceneIntent.QUESTION}), text_heavy=True, max_consecutive=10),)
        self.assertIn("text_card_overuse", plan_visual_grammar(needs, specs).defects)

    def test_duplicate_beat_id_raises(self):
        need = BeatVisualNeed("b1", SceneIntent.QUESTION, "x", "x")
        with self.assertRaises(ValueError):
            plan_visual_grammar((need, need), self.specs())


class ChoreographyTests(unittest.TestCase):
    def beat(self, beat_id: str, action: str = "sorts bills", move: CameraMove = CameraMove.PUSH, **overrides):
        values = dict(beat_id=beat_id, subject_action=action, camera_move=move, duration_seconds=4, focal_change=True)
        values.update(overrides)
        return ChoreographyBeat(**values)

    def test_missing_choreography_is_failure(self):
        self.assertEqual(analyze_choreography(()).score, 0)

    def test_repeated_action_detected(self):
        beats = tuple(self.beat(f"b{i}", action="points") for i in range(3))
        self.assertIn("repeated_subject_action", {item.code for item in analyze_choreography(beats).defects})

    def test_static_camera_run_detected(self):
        beats = tuple(self.beat(f"b{i}", move=CameraMove.STATIC) for i in range(3))
        self.assertIn("static_camera_run", {item.code for item in analyze_choreography(beats).defects})

    def test_no_focal_progression_detected(self):
        beats = tuple(self.beat(f"b{i}", focal_change=False) for i in range(3))
        self.assertIn("no_focal_progression", {item.code for item in analyze_choreography(beats).defects})

    def test_direction_flip_detected(self):
        beats = (self.beat("b1", movement_direction=ScreenDirection.RIGHT), self.beat("b2", movement_direction=ScreenDirection.LEFT))
        self.assertIn("screen_direction_flip", {item.code for item in analyze_choreography(beats).defects})

    def test_cause_without_consequence_detected(self):
        self.assertIn("cause_without_consequence", {item.code for item in analyze_choreography((self.beat("b1", cause_key="missing_money"),)).defects})

    def test_effect_without_setup_detected(self):
        self.assertIn("effect_without_setup", {item.code for item in analyze_choreography((self.beat("b1", effect_key="answer"),)).defects})

    def test_strong_choreography_scores_above_weak(self):
        strong = (
            self.beat("s1", "opens paycheck", CameraMove.PUSH, cause_key="missing"),
            self.beat("s2", "follows deduction", CameraMove.TRACK, effect_key="missing", cause_key="split"),
            self.beat("s3", "rebuilds stack", CameraMove.ORBIT, effect_key="split"),
        )
        weak = tuple(self.beat(f"w{i}", "points", CameraMove.STATIC, focal_change=False) for i in range(3))
        self.assertGreater(analyze_choreography(strong).score, analyze_choreography(weak).score)


class AudioDynamicsTests(unittest.TestCase):
    def beat(self, beat_id: str, start: float, kind: AudioBeatKind = AudioBeatKind.EXPLANATION, **overrides):
        values = dict(beat_id=beat_id, start_seconds=start, duration_seconds=6, kind=kind, narration_energy=6, music_energy=4, sfx_count=1, silence_ms=300, ducking_db=-8, emphasis_hit=True)
        values.update(overrides)
        return AudioBeat(**values)

    def test_missing_audio_plan_is_failure(self):
        self.assertEqual(analyze_audio_dynamics(()).score, 0)

    def test_narration_masking_risk_detected(self):
        report = analyze_audio_dynamics((self.beat("b1", 0, narration_energy=5, music_energy=7, ducking_db=-2),))
        self.assertIn("narration_masking_risk", {item.code for item in report.defects})

    def test_overbusy_sound_design_detected(self):
        self.assertIn("overbusy_sound_design", {item.code for item in analyze_audio_dynamics((self.beat("b1", 0, sfx_count=5),)).defects})

    def test_hook_requires_audio_emphasis(self):
        self.assertIn("missing_audio_emphasis", {item.code for item in analyze_audio_dynamics((self.beat("b1", 0, AudioBeatKind.HOOK, emphasis_hit=False),)).defects})

    def test_flat_music_arc_detected(self):
        beats = tuple(self.beat(f"b{i}", i * 6, music_energy=4) for i in range(5))
        self.assertIn("flat_music_arc", {item.code for item in analyze_audio_dynamics(beats).defects})

    def test_no_breathing_room_detected(self):
        beats = tuple(self.beat(f"b{i}", i * 6, silence_ms=0, sfx_count=1) for i in range(3))
        self.assertIn("no_breathing_room", {item.code for item in analyze_audio_dynamics(beats).defects})

    def test_strong_audio_arc_scores_well(self):
        beats = (
            self.beat("b1", 0, AudioBeatKind.HOOK, music_energy=7),
            self.beat("b2", 6, music_energy=3),
            self.beat("b3", 12, AudioBeatKind.DISCOVERY, music_energy=6),
            self.beat("b4", 18, AudioBeatKind.PAYOFF, music_energy=8),
        )
        self.assertGreaterEqual(analyze_audio_dynamics(beats).score, 8.5)


class PackagingTests(unittest.TestCase):
    def title(self, **overrides):
        values = dict(title_id="t1", text="Where Your Paycheck Actually Goes Before You Spend It", specificity=8, curiosity=8, credibility=9, payoff_alignment=9)
        values.update(overrides)
        return TitleCandidate(**values)

    def thumbnail(self, **overrides):
        values = dict(concept_id="c1", subject_count=2, text="PAYCHECK SPLIT", focal_clarity=9, contrast=8, curiosity=8, payoff_alignment=9)
        values.update(overrides)
        return ThumbnailConcept(**values)

    def test_strong_package_scores_well(self):
        self.assertGreaterEqual(evaluate_packaging(self.title(), self.thumbnail()).score, 8)

    def test_long_title_penalized(self):
        result = evaluate_packaging(self.title(text="A" * 80), self.thumbnail())
        self.assertIn("title_too_long", result.defects)

    def test_hype_penalized(self):
        result = evaluate_packaging(self.title(text="You Won't Believe Where Your Paycheck Goes Every Month"), self.thumbnail())
        self.assertIn("unearned_hype", result.defects)

    def test_thumbnail_text_overload_detected(self):
        result = evaluate_packaging(self.title(), self.thumbnail(text="THIS IS WAY TOO MUCH THUMBNAIL TEXT"))
        self.assertIn("thumbnail_text_overload", result.defects)

    def test_too_many_subjects_detected(self):
        result = evaluate_packaging(self.title(), self.thumbnail(subject_count=5))
        self.assertIn("too_many_thumbnail_subjects", result.defects)

    def test_redundancy_detected(self):
        result = evaluate_packaging(self.title(), self.thumbnail(duplicates_title=True))
        self.assertIn("title_thumbnail_redundancy", result.defects)

    def test_promise_mismatch_detected(self):
        result = evaluate_packaging(self.title(payoff_alignment=4), self.thumbnail())
        self.assertIn("packaging_promise_mismatch", result.defects)

    def test_ranking_puts_strong_package_first(self):
        results = rank_packaging((self.title(), self.title(title_id="weak", credibility=3)), (self.thumbnail(),))
        self.assertEqual(results[0].title_id, "t1")


class ViewerExperienceTests(unittest.TestCase):
    def observations(self, score: float = 8.0):
        return tuple(ExperienceObservation(area, score) for area in ExperienceArea)

    def test_complete_strong_experience_passes(self):
        self.assertEqual(evaluate_viewer_experience(self.observations()).decision, "pass")

    def test_missing_mandatory_area_rejects(self):
        observations = tuple(item for item in self.observations() if item.area is not ExperienceArea.PAYOFF)
        result = evaluate_viewer_experience(observations)
        self.assertEqual(result.decision, "reject")
        self.assertTrue(any(item.startswith("missing_areas") for item in result.blockers))

    def test_hard_failure_rejects(self):
        items = list(self.observations())
        items[0] = ExperienceObservation(items[0].area, 8, hard_failure=True)
        self.assertEqual(evaluate_viewer_experience(items).decision, "reject")

    def test_below_floor_rejects(self):
        items = [ExperienceObservation(area, 4 if area is ExperienceArea.HOOK else 8) for area in ExperienceArea]
        self.assertIn("below_floor:hook", evaluate_viewer_experience(items).blockers)

    def test_largest_weighted_gap_is_prioritized(self):
        items = [ExperienceObservation(area, 5 if area is ExperienceArea.HOOK else 7) for area in ExperienceArea]
        self.assertEqual(evaluate_viewer_experience(items).prioritized_repairs[0].area, ExperienceArea.HOOK)

    def test_duplicate_area_raises(self):
        item = ExperienceObservation(ExperienceArea.HOOK, 8)
        with self.assertRaises(ValueError):
            evaluate_viewer_experience((item, item))


if __name__ == "__main__":
    unittest.main()
