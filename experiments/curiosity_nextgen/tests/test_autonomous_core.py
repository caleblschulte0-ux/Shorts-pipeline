from __future__ import annotations

import unittest

from experiments.curiosity_nextgen.autonomous_decision_engine import (
    DecisionPolicy,
    NextAction,
    StageOutcome,
    StageVerdict,
    StoryDecisionState,
    decide_next_action,
)
from experiments.curiosity_nextgen.production_stage_graph import ProductionGraph, StageName, StageSpec, build_default_graph
from experiments.curiosity_nextgen.story_intake_contract import (
    AudienceLevel,
    FactualRisk,
    IntakePolicy,
    MediaMode,
    StoryBrief,
    validate_story_batch,
)


def brief(story_id: str = "story-001", **overrides) -> StoryBrief:
    values = dict(
        story_id=story_id,
        topic_family="science",
        format_family="explainer",
        core_question="Why does this system behave strangely?",
        target_seconds=120,
        audience=AudienceLevel.GENERAL,
        factual_risk=FactualRisk.LOW,
        media_mode=MediaMode.MIXED,
        priority=50,
    )
    values.update(overrides)
    return StoryBrief(**values)


def outcome(**overrides) -> StageOutcome:
    values = dict(
        story_id="story-001",
        stage=StageName.SCRIPT,
        verdict=StageVerdict.FAIL,
        severity=6.0,
        confidence=8.0,
    )
    values.update(overrides)
    return StageOutcome(**values)


class StoryIntakeTests(unittest.TestCase):
    def test_valid_batch_is_accepted_and_priority_sorted(self):
        report = validate_story_batch((brief("low", priority=20), brief("high", priority=90)))
        self.assertEqual([item.story_id for item in report.accepted], ["high", "low"])
        self.assertTrue(report.valid)

    def test_duplicate_story_ids_raise(self):
        with self.assertRaises(ValueError):
            validate_story_batch((brief("same"), brief("same")))

    def test_batch_above_fifty_raises(self):
        with self.assertRaises(ValueError):
            validate_story_batch(tuple(brief(f"story-{index:03d}") for index in range(51)))

    def test_high_risk_story_requires_claim_contract(self):
        report = validate_story_batch((brief(factual_risk=FactualRisk.HIGH),))
        self.assertIn("high_risk_without_claim_contract", report.rejected[0].reasons)

    def test_unsupported_format_is_rejected(self):
        policy = IntakePolicy(supported_formats=frozenset({"documentary"}))
        report = validate_story_batch((brief(format_family="explainer"),), policy)
        self.assertIn("unsupported_format", report.rejected[0].reasons)

    def test_duration_outside_policy_is_rejected(self):
        report = validate_story_batch((brief(target_seconds=10),))
        self.assertIn("duration_out_of_policy", report.rejected[0].reasons)

    def test_vague_core_question_is_rejected(self):
        report = validate_story_batch((brief(core_question="Why now?"),))
        self.assertIn("core_question_too_vague", report.rejected[0].reasons)

    def test_high_risk_share_can_make_batch_invalid(self):
        items = (
            brief("a", factual_risk=FactualRisk.HIGH, required_claim_types=("scientific",)),
            brief("b", factual_risk=FactualRisk.LOW),
        )
        report = validate_story_batch(items, IntakePolicy(maximum_high_risk_share=0.25))
        self.assertFalse(report.valid)
        self.assertIn("high_risk_share_exceeds_policy", report.warnings)

    def test_low_diversity_batch_warns(self):
        report = validate_story_batch(tuple(brief(f"s{index}") for index in range(4)))
        self.assertIn("topic_diversity_low", report.warnings)
        self.assertIn("format_diversity_low", report.warnings)

    def test_policy_cannot_exceed_fifty_story_contract(self):
        with self.assertRaises(ValueError):
            IntakePolicy(maximum_stories=51)


class ProductionGraphTests(unittest.TestCase):
    def test_default_graph_contains_fact_review(self):
        graph = build_default_graph()
        self.assertIn(StageName.FACT_REVIEW, {stage.name for stage in graph.stages})

    def test_fact_review_can_be_disabled_generically(self):
        graph = build_default_graph(require_fact_review=False)
        self.assertNotIn(StageName.FACT_REVIEW, {stage.name for stage in graph.stages})

    def test_topological_order_starts_with_intake(self):
        self.assertEqual(build_default_graph().topological_order()[0], StageName.INTAKE)

    def test_publish_is_after_approval(self):
        order = build_default_graph().topological_order()
        self.assertLess(order.index(StageName.APPROVAL), order.index(StageName.PUBLISH))

    def test_only_intake_is_ready_initially(self):
        self.assertEqual(build_default_graph().ready_stages(()), (StageName.INTAKE,))

    def test_research_is_ready_after_intake(self):
        self.assertEqual(build_default_graph().ready_stages((StageName.INTAKE,)), (StageName.RESEARCH,))

    def test_reviews_are_parallel_after_draft(self):
        completed = {
            StageName.INTAKE,
            StageName.RESEARCH,
            StageName.CLAIMS,
            StageName.SCRIPT,
            StageName.STORYBOARD,
            StageName.MEDIA,
            StageName.DRAFT_RENDER,
        }
        ready = set(build_default_graph().ready_stages(completed))
        self.assertEqual(ready, {StageName.TECHNICAL_REVIEW, StageName.EDITORIAL_REVIEW, StageName.FACT_REVIEW})

    def test_graph_digest_is_stable(self):
        self.assertEqual(build_default_graph().digest, build_default_graph().digest)

    def test_graph_digest_changes_when_fact_review_changes(self):
        self.assertNotEqual(build_default_graph().digest, build_default_graph(require_fact_review=False).digest)

    def test_duplicate_stage_definition_raises(self):
        with self.assertRaises(ValueError):
            ProductionGraph((StageSpec(StageName.INTAKE), StageSpec(StageName.INTAKE)))

    def test_unknown_dependency_raises(self):
        stages = (
            StageSpec(StageName.INTAKE),
            StageSpec(StageName.PUBLISH, (StageName.APPROVAL,)),
        )
        with self.assertRaises(ValueError):
            ProductionGraph(stages)

    def test_descendants_include_terminal_publish(self):
        self.assertIn(StageName.PUBLISH, build_default_graph().descendants(StageName.RESEARCH))


class AutonomousDecisionTests(unittest.TestCase):
    def test_confident_pass_advances(self):
        decision = decide_next_action(outcome(verdict=StageVerdict.PASS), StoryDecisionState())
        self.assertEqual(decision.action, NextAction.ADVANCE)

    def test_low_confidence_pass_holds(self):
        decision = decide_next_action(outcome(verdict=StageVerdict.PASS, confidence=4.0), StoryDecisionState())
        self.assertEqual(decision.action, NextAction.WAIT_FOR_EVIDENCE)

    def test_incomplete_evidence_holds(self):
        decision = decide_next_action(outcome(evidence_complete=False), StoryDecisionState())
        self.assertEqual(decision.reason, "evidence_incomplete")

    def test_unbound_render_artifact_holds(self):
        decision = decide_next_action(
            outcome(stage=StageName.FINAL_RENDER, verdict=StageVerdict.PASS, artifact_hash_bound=False),
            StoryDecisionState(),
        )
        self.assertEqual(decision.reason, "artifact_not_hash_bound")

    def test_factual_gap_rewinds_to_research(self):
        decision = decide_next_action(outcome(factual_gap=True), StoryDecisionState())
        self.assertEqual(decision.action, NextAction.RESEARCH_MORE)
        self.assertEqual(decision.rewind_to, StageName.RESEARCH)

    def test_retryable_error_retries_within_limit(self):
        decision = decide_next_action(
            outcome(verdict=StageVerdict.ERROR, retryable=True),
            StoryDecisionState(stage_attempts=0),
        )
        self.assertEqual(decision.action, NextAction.RETRY_STAGE)

    def test_retry_exhaustion_quarantines(self):
        policy = DecisionPolicy(maximum_retries_per_stage=1)
        decision = decide_next_action(
            outcome(stage=StageName.TECHNICAL_REVIEW, verdict=StageVerdict.ERROR, retryable=True),
            StoryDecisionState(stage_attempts=1),
            policy,
        )
        self.assertEqual(decision.action, NextAction.QUARANTINE)

    def test_repairable_failure_schedules_repair(self):
        decision = decide_next_action(outcome(stage=StageName.EDITORIAL_REVIEW, repairable=True), StoryDecisionState())
        self.assertEqual(decision.action, NextAction.REPAIR)

    def test_repair_limit_exhaustion_quarantines(self):
        policy = DecisionPolicy(maximum_repairs_per_story=1)
        decision = decide_next_action(
            outcome(stage=StageName.EDITORIAL_REVIEW, repairable=True),
            StoryDecisionState(repair_count=1),
            policy,
        )
        self.assertEqual(decision.action, NextAction.QUARANTINE)

    def test_authoring_failure_can_reauthor(self):
        decision = decide_next_action(outcome(stage=StageName.STORYBOARD), StoryDecisionState())
        self.assertEqual(decision.action, NextAction.REAUTHOR)

    def test_reauthor_limit_exhaustion_quarantines(self):
        policy = DecisionPolicy(maximum_reauthors_per_story=1)
        decision = decide_next_action(outcome(stage=StageName.SCRIPT), StoryDecisionState(reauthor_count=1), policy)
        self.assertEqual(decision.action, NextAction.QUARANTINE)

    def test_policy_violation_quarantines_immediately(self):
        decision = decide_next_action(outcome(policy_violation=True, repairable=True), StoryDecisionState())
        self.assertEqual(decision.reason, "policy_violation")

    def test_high_severity_unrepairable_failure_quarantines(self):
        decision = decide_next_action(outcome(severity=9.5, repairable=False), StoryDecisionState())
        self.assertEqual(decision.action, NextAction.QUARANTINE)

    def test_hold_verdict_waits(self):
        decision = decide_next_action(outcome(verdict=StageVerdict.HOLD), StoryDecisionState())
        self.assertEqual(decision.action, NextAction.WAIT_FOR_EVIDENCE)

    def test_story_identifier_does_not_change_decision(self):
        left = decide_next_action(outcome(story_id="opaque-a", repairable=True), StoryDecisionState())
        right = decide_next_action(outcome(story_id="opaque-b", repairable=True), StoryDecisionState())
        self.assertEqual((left.action, left.reason), (right.action, right.reason))

    def test_invalid_outcome_score_raises(self):
        with self.assertRaises(ValueError):
            outcome(severity=11.0)


if __name__ == "__main__":
    unittest.main()
