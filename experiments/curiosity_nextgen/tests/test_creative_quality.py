from __future__ import annotations

import unittest

from experiments.curiosity_nextgen.beat_dynamics import BeatRole, BeatSignal, analyze_dynamics
from experiments.curiosity_nextgen.chapter_style_planner import ChapterNeed, TransitionFamily, plan_chapter_styles
from experiments.curiosity_nextgen.creative_uplift import CreativeArea, CreativeTask, money_goes_reference_tasks, plan_uplift
from experiments.curiosity_nextgen.hook_lab import HookCandidate, HookDecision, evaluate_hook, rank_hooks
from experiments.curiosity_nextgen.payoff_contract import StoryAnswer, StoryQuestion, evaluate_payoffs
from experiments.curiosity_nextgen.personality_arc import CharacterBeat, EmotionalState, analyze_personality_arc


def hook(**overrides):
    values = dict(
        hook_id="h1",
        text="Your paycheck disappears before you spend it — here is where it actually goes.",
        duration_seconds=7.0,
        first_visual_seconds=0.4,
        clarity=8.5,
        curiosity_gap=8.5,
        stakes=8.0,
        specificity=8.0,
        surprise=7.5,
        visualizability=8.5,
        payoff_promise=8.0,
    )
    values.update(overrides)
    return HookCandidate(**values)


def beat(beat_id: str, start: float, family: str = "mechanism", **overrides):
    values = dict(
        beat_id=beat_id,
        start_seconds=start,
        duration_seconds=5.0,
        role=BeatRole.MECHANISM,
        visual_family=family,
        energy=7.0,
        novelty=7.0,
        information_density=5.0,
        emotional_intensity=6.0,
        motion_score=7.0,
        has_character_action=True,
        has_new_question=False,
        resolves_question=False,
    )
    values.update(overrides)
    return BeatSignal(**values)


class HookLabTests(unittest.TestCase):
    def test_strong_hook_passes(self):
        self.assertEqual(evaluate_hook(hook()).decision, HookDecision.STRONG)

    def test_long_hook_is_penalized(self):
        result = evaluate_hook(hook(duration_seconds=18.0))
        self.assertIn("hook_too_long", result.defects)
        self.assertLess(result.score, evaluate_hook(hook()).score)

    def test_late_visual_is_penalized(self):
        result = evaluate_hook(hook(first_visual_seconds=5.0))
        self.assertIn("visual_arrives_late", result.defects)

    def test_generic_language_is_penalized(self):
        result = evaluate_hook(hook(generic_phrase_count=4))
        self.assertIn("generic_language", result.defects)

    def test_explanation_open_is_penalized(self):
        result = evaluate_hook(hook(opens_with_explanation=True))
        self.assertIn("opens_with_explanation", result.defects)

    def test_weak_first_image_blocks_strong_decision(self):
        result = evaluate_hook(hook(visualizability=4.0))
        self.assertNotEqual(result.decision, HookDecision.STRONG)

    def test_unclear_payoff_blocks_strong_decision(self):
        result = evaluate_hook(hook(payoff_promise=4.0))
        self.assertNotEqual(result.decision, HookDecision.STRONG)

    def test_rank_hooks_puts_strong_first(self):
        results = rank_hooks((hook(hook_id="weak", clarity=3.0), hook(hook_id="strong")))
        self.assertEqual(results[0].hook_id, "strong")

    def test_invalid_hook_score_raises(self):
        with self.assertRaises(ValueError):
            hook(clarity=11.0)


class BeatDynamicsTests(unittest.TestCase):
    def test_repeated_family_run_detected(self):
        report = analyze_dynamics((beat("b1", 0, "stock"), beat("b2", 5, "stock"), beat("b3", 10, "stock")))
        self.assertIn("visual_family_run", {item.code for item in report.defects})

    def test_flat_energy_run_detected(self):
        report = analyze_dynamics(tuple(beat(f"b{i}", i * 5, energy=2.0) for i in range(4)))
        self.assertIn("flat_energy_run", {item.code for item in report.defects})

    def test_dense_explanation_run_detected(self):
        report = analyze_dynamics(tuple(beat(f"b{i}", i * 5, information_density=9.0) for i in range(4)))
        self.assertIn("dense_explanation_run", {item.code for item in report.defects})

    def test_character_absence_run_detected(self):
        report = analyze_dynamics(tuple(beat(f"b{i}", i * 5, has_character_action=False) for i in range(6)))
        self.assertIn("character_absence_run", {item.code for item in report.defects})

    def test_curiosity_gap_detected(self):
        report = analyze_dynamics((beat("b1", 0, has_new_question=True), beat("b2", 45), beat("b3", 90)))
        self.assertIn("curiosity_gap_dormant", {item.code for item in report.defects})

    def test_strong_turn_is_reported(self):
        report = analyze_dynamics((beat("b1", 0, energy=2, emotional_intensity=2), beat("b2", 5, energy=9, emotional_intensity=9)))
        self.assertIn("b2", report.strongest_turns)

    def test_duplicate_beat_id_raises(self):
        with self.assertRaises(ValueError):
            analyze_dynamics((beat("b1", 0), beat("b1", 5)))


class ChapterPlannerTests(unittest.TestCase):
    def setUp(self):
        self.chapters = tuple(ChapterNeed(f"c{i}", "money", "curious") for i in range(6))
        self.families = (
            TransitionFamily("mechanism", frozenset({"money"}), frozenset({"curious"})),
            TransitionFamily("character", frozenset({"money"}), frozenset({"curious"}), supports_character=True),
            TransitionFamily("media", frozenset({"money"}), frozenset({"curious"}), supports_real_media=True),
        )

    def test_planner_uses_multiple_families(self):
        plan = plan_chapter_styles(self.chapters, self.families)
        self.assertGreaterEqual(len(plan.family_counts), 2)

    def test_no_family_dominates_default_plan(self):
        plan = plan_chapter_styles(self.chapters, self.families)
        self.assertLessEqual(plan.dominant_share, 0.5)

    def test_missing_required_character_support_raises(self):
        chapters = (ChapterNeed("c1", "money", "curious", requires_character=True),)
        with self.assertRaises(ValueError):
            plan_chapter_styles(chapters, (TransitionFamily("text"),))

    def test_duplicate_chapter_id_raises(self):
        with self.assertRaises(ValueError):
            plan_chapter_styles((self.chapters[0], self.chapters[0]), self.families)


class PersonalityArcTests(unittest.TestCase):
    def test_missing_arc_is_defect(self):
        report = analyze_personality_arc(())
        self.assertEqual(report.defects[0].code, "missing_character_arc")

    def test_flat_emotions_detected(self):
        beats = tuple(CharacterBeat(f"b{i}", "hero", EmotionalState.CURIOUS, f"action{i}", "learn", obstacle="wall", consequence="change") for i in range(3))
        report = analyze_personality_arc(beats)
        self.assertIn("emotionally_flat", {item.code for item in report.defects})

    def test_repeated_actions_detected(self):
        states = (EmotionalState.CURIOUS, EmotionalState.WORRIED, EmotionalState.RELIEVED)
        beats = tuple(CharacterBeat(f"b{i}", "hero", state, "points", "learn", obstacle="wall", consequence="change") for i, state in enumerate(states))
        report = analyze_personality_arc(beats)
        self.assertIn("overused_character_action", {item.code for item in report.defects})

    def test_missing_obstacle_detected(self):
        beats = (
            CharacterBeat("b1", "hero", EmotionalState.CURIOUS, "opens envelope", "understand"),
            CharacterBeat("b2", "hero", EmotionalState.SURPRISED, "sorts bills", "understand", consequence="discovers split"),
            CharacterBeat("b3", "hero", EmotionalState.RELIEVED, "rebuilds stack", "understand", consequence="sees answer"),
        )
        self.assertIn("no_obstacle", {item.code for item in analyze_personality_arc(beats).defects})

    def test_unresolved_callback_detected(self):
        beats = (
            CharacterBeat("b1", "hero", EmotionalState.CURIOUS, "opens envelope", "understand", obstacle="missing money", callback_key="envelope"),
            CharacterBeat("b2", "hero", EmotionalState.WORRIED, "checks account", "understand", obstacle="fees", consequence="finds deduction"),
            CharacterBeat("b3", "hero", EmotionalState.DETERMINED, "maps flow", "understand", obstacle="complexity", consequence="finds path"),
        )
        self.assertIn("unresolved_character_callback", {item.code for item in analyze_personality_arc(beats).defects})

    def test_resolved_arc_scores_higher(self):
        weak = (CharacterBeat("w1", "hero", EmotionalState.CURIOUS, "points", "learn"),)
        strong = (
            CharacterBeat("s1", "hero", EmotionalState.CONFIDENT, "opens paycheck", "find money", obstacle="money missing", callback_key="paycheck"),
            CharacterBeat("s2", "hero", EmotionalState.CONFUSED, "sorts deductions", "find money", obstacle="too many paths", consequence="isolates taxes"),
            CharacterBeat("s3", "hero", EmotionalState.DETERMINED, "builds flow map", "find money", obstacle="hidden fees", consequence="traces flow"),
            CharacterBeat("s4", "hero", EmotionalState.RELIEVED, "reassembles paycheck", "find money", consequence="paycheck explained", callback_key="paycheck"),
        )
        self.assertGreater(analyze_personality_arc(strong).score, analyze_personality_arc(weak).score)


class PayoffContractTests(unittest.TestCase):
    def question(self):
        return StoryQuestion("q1", "Where does the paycheck go?", 0.0, 9.0, "paycheck", "money split")

    def test_unanswered_question_detected(self):
        report = evaluate_payoffs((self.question(),), ())
        self.assertIn("unanswered_question", {item.code for item in report.defects})

    def test_unknown_answer_raises(self):
        with self.assertRaises(ValueError):
            evaluate_payoffs((self.question(),), (StoryAnswer("q2", 10, "answer"),))

    def test_major_payoff_requires_visual_proof(self):
        answer = StoryAnswer("q1", 120, "It splits among taxes, benefits, and spending.", consequence_shown="money split", callback_shown=True, specificity=9)
        report = evaluate_payoffs((self.question(),), (answer,))
        self.assertIn("major_payoff_without_visual_proof", {item.code for item in report.defects})

    def test_major_payoff_requires_consequence(self):
        answer = StoryAnswer("q1", 120, "It splits among taxes, benefits, and spending.", visual_evidence="paycheck flow", callback_shown=True, specificity=9)
        report = evaluate_payoffs((self.question(),), (answer,))
        self.assertIn("major_payoff_without_consequence", {item.code for item in report.defects})

    def test_major_payoff_requires_callback(self):
        answer = StoryAnswer("q1", 120, "It splits among taxes, benefits, and spending.", visual_evidence="paycheck flow", consequence_shown="money split", specificity=9)
        report = evaluate_payoffs((self.question(),), (answer,))
        self.assertIn("missing_setup_callback", {item.code for item in report.defects})

    def test_complete_payoff_scores_well(self):
        answer = StoryAnswer("q1", 120, "It splits among taxes, benefits, and spending.", visual_evidence="paycheck flow", consequence_shown="money split", callback_shown=True, specificity=9)
        report = evaluate_payoffs((self.question(),), (answer,))
        self.assertGreaterEqual(report.score, 7.5)


class CreativeUpliftTests(unittest.TestCase):
    def test_money_goes_plan_covers_direct_quality_areas(self):
        areas = {task.area for task in money_goes_reference_tasks()}
        self.assertTrue({CreativeArea.HOOK, CreativeArea.MEDIA, CreativeArea.VISUAL_VARIETY, CreativeArea.PERSONALITY, CreativeArea.PAYOFF}.issubset(areas))

    def test_dependencies_are_ordered(self):
        plan = plan_uplift(money_goes_reference_tasks(), current_score=6.0, effort_budget=20.0)
        ids = [task.task_id for task in plan.ordered_tasks]
        self.assertLess(ids.index("restore_hook_composition"), ids.index("strengthen_final_callback"))

    def test_budget_limits_selected_work(self):
        full = plan_uplift(money_goes_reference_tasks(), current_score=6.0, effort_budget=20.0)
        small = plan_uplift(money_goes_reference_tasks(), current_score=6.0, effort_budget=2.0)
        self.assertLess(len(small.ordered_tasks), len(full.ordered_tasks))

    def test_unknown_dependency_raises(self):
        task = CreativeTask("x", CreativeArea.HOOK, "test", 1.0, 0.8, 1.0, depends_on=("missing",))
        with self.assertRaises(ValueError):
            plan_uplift((task,), current_score=6.0, effort_budget=2.0)

    def test_duplicate_task_raises(self):
        task = CreativeTask("x", CreativeArea.HOOK, "test", 1.0, 0.8, 1.0)
        with self.assertRaises(ValueError):
            plan_uplift((task, task), current_score=6.0, effort_budget=2.0)

    def test_projected_score_does_not_exceed_ten(self):
        plan = plan_uplift(money_goes_reference_tasks(), current_score=9.8, effort_budget=20.0)
        self.assertLessEqual(plan.projected_overall_score, 10.0)


if __name__ == "__main__":
    unittest.main()
