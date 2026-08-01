from __future__ import annotations

from dataclasses import replace
import unittest

from experiments.curiosity_nextgen.autonomy_completeness import (
    DomainEvidence,
    assess_autonomy_completeness,
    complete_autonomy_reference_evidence,
)
from experiments.curiosity_nextgen.controlled_learning_loop import (
    LearningPolicy,
    PerformanceObservation,
    approve_learning_canary,
    propose_policy_update,
)
from experiments.curiosity_nextgen.launch_readiness import (
    LaunchEvidence,
    assess_launch_readiness,
    dormant_reference_assessment,
)


def observation(story_id: str, variant: str, *, experiment_id: str = "exp", policy_version: str = "v1", impressions: int = 1000, watch: float | None = None, completion: float | None = None, negative: float | None = None, hard_blocker: bool = False) -> PerformanceObservation:
    is_control = variant == "control"
    return PerformanceObservation(
        story_id=story_id,
        experiment_id=experiment_id,
        variant=variant,
        policy_version=policy_version,
        impressions=impressions,
        average_watch_ratio=watch if watch is not None else (0.50 if is_control else 0.53),
        completion_rate=completion if completion is not None else (0.40 if is_control else 0.42),
        negative_feedback_rate=negative if negative is not None else (0.010 if is_control else 0.012),
        hard_blocker=hard_blocker,
    )


def valid_observations() -> list[PerformanceObservation]:
    return [observation(f"c{i}", "control") for i in range(5)] + [observation(f"t{i}", "treatment") for i in range(5)]


def ready_evidence() -> LaunchEvidence:
    return LaunchEvidence(
        reference_coverage_percent=100,
        verified_test_percent=100,
        integrated_adapter_percent=100,
        fifty_story_simulation_passed=True,
        heterogeneous_shadow_batches_passed=3,
        autonomous_canary_videos_passed=3,
        artifact_hash_binding_active=True,
        factual_evidence_active=True,
        independent_judges_active=True,
        durable_execution_state_active=True,
        provider_fallbacks_active=True,
        bounded_recovery_active=True,
        budget_controls_active=True,
        monitoring_active=True,
        rollback_tested=True,
        kill_switch_tested=True,
        expected_channel_guard_active=True,
        publishing_disabled_by_default=True,
    )


class ControlledLearningTests(unittest.TestCase):
    def test_no_observations_hold(self) -> None:
        proposal = propose_policy_update([], control_variant="control", candidate_parameters={}, policy=LearningPolicy())
        self.assertEqual(proposal.status, "hold")
        self.assertIn("no_observations", proposal.blockers)

    def test_mixed_experiments_block(self) -> None:
        items = valid_observations()
        items[-1] = replace(items[-1], experiment_id="other")
        proposal = propose_policy_update(items, control_variant="control", candidate_parameters={}, policy=LearningPolicy())
        self.assertIn("mixed_experiments", proposal.blockers)

    def test_mixed_policy_versions_block(self) -> None:
        items = valid_observations()
        items[-1] = replace(items[-1], policy_version="v2")
        proposal = propose_policy_update(items, control_variant="control", candidate_parameters={}, policy=LearningPolicy())
        self.assertIn("mixed_policy_versions", proposal.blockers)

    def test_insufficient_impressions_block(self) -> None:
        items = [replace(item, impressions=100) for item in valid_observations()]
        proposal = propose_policy_update(items, control_variant="control", candidate_parameters={}, policy=LearningPolicy())
        self.assertIn("insufficient_total_impressions", proposal.blockers)

    def test_insufficient_story_count_blocks_each_variant(self) -> None:
        items = [observation("c1", "control", impressions=2500), observation("c2", "control", impressions=2500), observation("t1", "treatment", impressions=2500), observation("t2", "treatment", impressions=2500)]
        proposal = propose_policy_update(items, control_variant="control", candidate_parameters={}, policy=LearningPolicy())
        self.assertTrue(any(value.startswith("insufficient_story_count") for value in proposal.blockers))

    def test_hard_blocker_prevents_learning(self) -> None:
        items = valid_observations()
        items[-1] = replace(items[-1], hard_blocker=True)
        proposal = propose_policy_update(items, control_variant="control", candidate_parameters={}, policy=LearningPolicy())
        self.assertIn("hard_blocker:treatment", proposal.blockers)

    def test_valid_winner_requires_canary(self) -> None:
        proposal = propose_policy_update(valid_observations(), control_variant="control", candidate_parameters={"hook_weight": 0.05}, policy=LearningPolicy())
        self.assertEqual(proposal.status, "canary_required")
        self.assertEqual(proposal.winning_variant, "treatment")
        self.assertEqual(len(proposal.evidence_digest or ""), 64)

    def test_weak_treatment_does_not_win(self) -> None:
        items = [observation(f"c{i}", "control") for i in range(5)] + [observation(f"t{i}", "treatment", watch=0.505, completion=0.405) for i in range(5)]
        proposal = propose_policy_update(items, control_variant="control", candidate_parameters={}, policy=LearningPolicy())
        self.assertIn("no_variant_clears_guardrails", proposal.blockers)

    def test_excessive_parameter_delta_blocks(self) -> None:
        proposal = propose_policy_update(valid_observations(), control_variant="control", candidate_parameters={"hook_weight": 0.2}, policy=LearningPolicy())
        self.assertIn("parameter_delta_exceeds_limit:hook_weight", proposal.blockers)

    def test_canary_approval_requires_evidence_batches_and_rollback(self) -> None:
        proposal = propose_policy_update(valid_observations(), control_variant="control", candidate_parameters={"hook_weight": 0.05}, policy=LearningPolicy(required_canary_batches=2))
        approved, blockers = approve_learning_canary(proposal, passed_batches=2, rollback_ready=True)
        self.assertTrue(approved)
        self.assertEqual(blockers, ())


class LaunchReadinessTests(unittest.TestCase):
    def test_dormant_reference_assessment_accepts_exact_hundred(self) -> None:
        result = dormant_reference_assessment(100.0)
        self.assertTrue(result.ready)
        self.assertEqual(result.phase, "dormant_reference_complete")

    def test_dormant_reference_assessment_rejects_partial(self) -> None:
        result = dormant_reference_assessment(99.0)
        self.assertFalse(result.ready)

    def test_reference_incomplete_phase(self) -> None:
        result = assess_launch_readiness(replace(ready_evidence(), reference_coverage_percent=99))
        self.assertEqual(result.phase, "reference_incomplete")

    def test_execution_unverified_phase(self) -> None:
        result = assess_launch_readiness(replace(ready_evidence(), verified_test_percent=0))
        self.assertEqual(result.phase, "reference_complete_execution_unverified")

    def test_integration_incomplete_phase(self) -> None:
        result = assess_launch_readiness(replace(ready_evidence(), integrated_adapter_percent=0))
        self.assertEqual(result.phase, "execution_verified_integration_incomplete")

    def test_simulation_incomplete_phase(self) -> None:
        result = assess_launch_readiness(replace(ready_evidence(), fifty_story_simulation_passed=False))
        self.assertEqual(result.phase, "integration_complete_simulation_incomplete")

    def test_shadow_incomplete_phase(self) -> None:
        result = assess_launch_readiness(replace(ready_evidence(), heterogeneous_shadow_batches_passed=2))
        self.assertEqual(result.phase, "simulation_complete_shadow_incomplete")

    def test_canary_incomplete_phase(self) -> None:
        result = assess_launch_readiness(replace(ready_evidence(), autonomous_canary_videos_passed=2))
        self.assertEqual(result.phase, "shadow_complete_canary_incomplete")

    def test_hard_blocker_prevents_launch(self) -> None:
        result = assess_launch_readiness(replace(ready_evidence(), hard_blockers=("manual_block",)))
        self.assertEqual(result.phase, "canary_complete_launch_blocked")
        self.assertFalse(result.ready)

    def test_complete_evidence_is_launch_ready(self) -> None:
        result = assess_launch_readiness(ready_evidence())
        self.assertTrue(result.ready)
        self.assertEqual(result.phase, "launch_ready")


class AutonomyCompletenessTests(unittest.TestCase):
    def test_complete_reference_surface_is_hundred_percent(self) -> None:
        report = assess_autonomy_completeness(complete_autonomy_reference_evidence())
        self.assertEqual(report.reference_coverage_percent, 100.0)
        self.assertTrue(report.complete_reference_surface)

    def test_complete_reference_contains_twenty_four_domains(self) -> None:
        self.assertEqual(len(complete_autonomy_reference_evidence()), 24)

    def test_authored_reference_does_not_claim_execution(self) -> None:
        report = assess_autonomy_completeness(complete_autonomy_reference_evidence())
        self.assertEqual(report.verified_execution_percent, 0.0)

    def test_missing_domain_lowers_coverage(self) -> None:
        evidence = complete_autonomy_reference_evidence()[:-1]
        report = assess_autonomy_completeness(evidence)
        self.assertLess(report.reference_coverage_percent, 100.0)
        self.assertIn("claude_execution_handoff", report.missing_domains)

    def test_missing_implementation_path_invalidates_domain(self) -> None:
        evidence = list(complete_autonomy_reference_evidence())
        evidence[0] = replace(evidence[0], implementation_paths=())
        report = assess_autonomy_completeness(evidence)
        self.assertIn(evidence[0].domain, report.invalid_domains)

    def test_missing_positive_test_invalidates_domain(self) -> None:
        evidence = list(complete_autonomy_reference_evidence())
        evidence[0] = replace(evidence[0], positive_test_references=())
        report = assess_autonomy_completeness(evidence)
        self.assertIn(evidence[0].domain, report.invalid_domains)

    def test_missing_negative_test_invalidates_domain(self) -> None:
        evidence = list(complete_autonomy_reference_evidence())
        evidence[0] = replace(evidence[0], negative_test_references=())
        report = assess_autonomy_completeness(evidence)
        self.assertIn(evidence[0].domain, report.invalid_domains)

    def test_explicit_non_isolation_invalidates_domain(self) -> None:
        evidence = list(complete_autonomy_reference_evidence())
        evidence[0] = replace(evidence[0], isolated=False)
        report = assess_autonomy_completeness(evidence)
        self.assertIn(evidence[0].domain, report.non_isolated_domains)

    def test_production_path_invalidates_isolation(self) -> None:
        evidence = list(complete_autonomy_reference_evidence())
        evidence[0] = replace(evidence[0], implementation_paths=("scripts/live.py",))
        report = assess_autonomy_completeness(evidence)
        self.assertIn(evidence[0].domain, report.non_isolated_domains)

    def test_duplicate_domain_invalidates_report(self) -> None:
        evidence = complete_autonomy_reference_evidence()
        report = assess_autonomy_completeness(evidence + (evidence[0],))
        self.assertIn(evidence[0].domain, report.invalid_domains)
        self.assertFalse(report.complete_reference_surface)

    def test_verified_integrated_and_live_scores_are_separate(self) -> None:
        evidence = tuple(replace(item, verified_executed=True, integrated=True, live_evidence=True) for item in complete_autonomy_reference_evidence())
        report = assess_autonomy_completeness(evidence)
        self.assertEqual(report.verified_execution_percent, 100.0)
        self.assertEqual(report.integration_percent, 100.0)
        self.assertEqual(report.live_evidence_percent, 100.0)

    def test_unknown_domain_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            DomainEvidence("unknown", ("experiments/x.py",), ("positive",), ("negative",), True)


if __name__ == "__main__":
    unittest.main()
