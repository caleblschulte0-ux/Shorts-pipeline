from __future__ import annotations

from dataclasses import replace
import unittest

from experiments.curiosity_nextgen.adapter_contracts import (
    AdapterDescriptor,
    AdapterRequirement,
    Capability,
    negotiate_adapter,
    validate_separation_of_duties,
)
from experiments.curiosity_nextgen.audit_chain import append_record, locate_first_break, verify_chain
from experiments.curiosity_nextgen.drift_monitor import (
    DriftSeverity,
    MetricObservation,
    build_baseline,
    evaluate_drift,
    evaluate_metric,
)
from experiments.curiosity_nextgen.environment_lock import (
    DependencyPin,
    EnvironmentManifest,
    compare_environments,
    validate_manifest,
)
from experiments.curiosity_nextgen.generalization_suite import (
    GeneralizationPolicy,
    StoryArchetype,
    StoryFixture,
    assess_generalization,
    fixture_matrix,
)
from experiments.curiosity_nextgen.lifecycle_controls import (
    BackupSnapshot,
    ChangeStep,
    RecoveryObjective,
    RetentionClass,
    RolloutSignals,
    RolloutStage,
    StoredArtifact,
    assess_recovery,
    build_rollback_plan,
    evaluate_rollout,
    plan_purge,
)
from experiments.curiosity_nextgen.policy_snapshot import (
    PolicyError,
    PolicyRule,
    PolicySnapshot,
    derive_snapshot,
    evaluate_policy,
    validate_snapshot,
)
from experiments.curiosity_nextgen.portfolio_optimizer import (
    PortfolioPolicy,
    StoryCandidate,
    build_portfolio,
)
from experiments.curiosity_nextgen.review_queue import (
    ReviewRequest,
    ReviewRole,
    ReviewState,
    artifact_is_fully_approved,
    claim,
    decide,
    enqueue,
    escalate_overdue,
)
from experiments.curiosity_nextgen.structural_completeness import (
    DomainEvidence,
    StructuralDomain,
    assess_structural_completeness,
    complete_reference_evidence,
)


HASH = "a" * 64


class PolicySnapshotTests(unittest.TestCase):
    def snapshot(self) -> PolicySnapshot:
        return PolicySnapshot(
            "release-policy",
            1,
            (
                PolicyRule("publish_enabled", False, False),
                PolicyRule("maximum_jobs", 2, True),
            ),
        )

    def test_snapshot_hash_is_deterministic(self) -> None:
        first = self.snapshot()
        second = PolicySnapshot("release-policy", 1, tuple(reversed(first.rules)))
        self.assertEqual(first.sha256, second.sha256)

    def test_immutable_override_is_rejected(self) -> None:
        result = evaluate_policy(self.snapshot(), runtime_overrides={"publish_enabled": True})
        self.assertFalse(result.valid)
        self.assertIn("immutable_override:publish_enabled", result.blockers)

    def test_mutable_override_is_allowed(self) -> None:
        result = evaluate_policy(self.snapshot(), runtime_overrides={"maximum_jobs": 4})
        self.assertTrue(result.valid)
        self.assertEqual(result.effective_values["maximum_jobs"], 4)

    def test_unknown_override_is_rejected(self) -> None:
        result = evaluate_policy(self.snapshot(), runtime_overrides={"mystery": True})
        self.assertIn("unknown_override:mystery", result.blockers)

    def test_derived_snapshot_links_parent(self) -> None:
        parent = self.snapshot()
        child = derive_snapshot(parent, version=2, replacements={"maximum_jobs": 3})
        self.assertEqual(child.parent_sha256, parent.sha256)
        self.assertEqual(child.as_mapping()["maximum_jobs"], 3)

    def test_derived_version_must_increase(self) -> None:
        with self.assertRaises(PolicyError):
            derive_snapshot(self.snapshot(), version=1, replacements={})


class AdapterContractTests(unittest.TestCase):
    def adapter(self, adapter_id: str = "renderer", **overrides: object) -> AdapterDescriptor:
        values: dict[str, object] = {
            "adapter_id": adapter_id,
            "version": "1.0",
            "capabilities": frozenset({Capability.RENDER_VIDEO}),
            "input_schema_versions": (1, 2),
            "output_schema_versions": (1, 2),
            "deterministic": True,
            "supports_idempotency": True,
            "provider_family": "local",
        }
        values.update(overrides)
        return AdapterDescriptor(**values)

    def test_eligible_adapter_is_selected(self) -> None:
        result = negotiate_adapter(
            (self.adapter(),),
            AdapterRequirement(Capability.RENDER_VIDEO, 2, 2, deterministic_required=True),
        )
        self.assertTrue(result.accepted)
        self.assertEqual(result.selected_adapter_id, "renderer")

    def test_missing_capability_rejects_adapter(self) -> None:
        result = negotiate_adapter((self.adapter(),), AdapterRequirement(Capability.PUBLISH_CANARY, 1, 1))
        self.assertFalse(result.accepted)
        self.assertIn("missing_capability", result.blockers)

    def test_preferred_adapter_wins(self) -> None:
        result = negotiate_adapter(
            (self.adapter("a"), self.adapter("b")),
            AdapterRequirement(Capability.RENDER_VIDEO, 1, 1),
            preferred_adapter_ids=("b",),
        )
        self.assertEqual(result.selected_adapter_id, "b")

    def test_same_provider_judges_violate_separation(self) -> None:
        technical = self.adapter(
            "tech",
            capabilities=frozenset({Capability.JUDGE_TECHNICAL}),
            provider_family="same",
        )
        editorial = self.adapter(
            "editor",
            capabilities=frozenset({Capability.JUDGE_EDITORIAL}),
            provider_family="same",
        )
        self.assertIn("same_provider_family", validate_separation_of_duties(technical, editorial))

    def test_nondeterministic_adapter_can_be_blocked(self) -> None:
        result = negotiate_adapter(
            (self.adapter(deterministic=False),),
            AdapterRequirement(Capability.RENDER_VIDEO, 1, 1, deterministic_required=True),
        )
        self.assertIn("nondeterministic_adapter", result.blockers)


class AuditChainTests(unittest.TestCase):
    def chain(self):
        records = append_record((), timestamp=1, actor="worker", action="render", subject="story", details={"x": 1})
        return append_record(records, timestamp=2, actor="judge", action="review", subject="story", details={"pass": True})

    def test_valid_chain_verifies(self) -> None:
        self.assertTrue(verify_chain(self.chain()).valid)

    def test_detail_tampering_breaks_hash(self) -> None:
        records = self.chain()
        altered = records[:1] + (replace(records[1], details={"pass": False}),)
        self.assertFalse(verify_chain(altered).valid)

    def test_previous_hash_tampering_is_detected(self) -> None:
        records = self.chain()
        altered = records[:1] + (replace(records[1], previous_hash="b" * 64),)
        self.assertIn("previous_hash_mismatch:2", verify_chain(altered).blockers)

    def test_timestamp_regression_is_detected(self) -> None:
        records = self.chain()
        altered = records[:1] + (replace(records[1], timestamp=0),)
        self.assertIn("timestamp_regression:2", verify_chain(altered).blockers)

    def test_first_break_is_reported(self) -> None:
        records = self.chain()
        altered = (replace(records[0], record_hash="c" * 64),) + records[1:]
        self.assertEqual(locate_first_break(altered), 1)


class ReviewQueueTests(unittest.TestCase):
    def request(self, role: ReviewRole = ReviewRole.FACTS, request_id: str = "r1") -> ReviewRequest:
        return ReviewRequest(request_id, HASH, role, 10, 20, "author")

    def test_request_can_be_enqueued(self) -> None:
        result = enqueue((), self.request())
        self.assertFalse(result.blockers)
        self.assertEqual(len(result.requests), 1)

    def test_duplicate_open_review_is_rejected(self) -> None:
        first = self.request()
        result = enqueue((first,), self.request(request_id="r2"))
        self.assertIn("duplicate_open_review", result.blockers)

    def test_self_review_is_forbidden(self) -> None:
        with self.assertRaises(ValueError):
            claim(self.request(), reviewer_id="author", now=12)

    def test_assigned_reviewer_can_approve(self) -> None:
        claimed = claim(self.request(), reviewer_id="reviewer", now=12)
        approved = decide(claimed, reviewer_id="reviewer", approved=True, reason="verified", now=13)
        self.assertEqual(approved.state, ReviewState.APPROVED)

    def test_overdue_review_escalates(self) -> None:
        escalated = escalate_overdue((self.request(),), now=21)[0]
        self.assertEqual(escalated.state, ReviewState.ESCALATED)
        self.assertEqual(escalated.escalation_level, 1)

    def test_all_four_roles_are_required(self) -> None:
        approvals = tuple(
            replace(
                self.request(role, f"r-{role.value}"),
                state=ReviewState.APPROVED,
                reviewer_id=f"reviewer-{role.value}",
                decision_reason="pass",
            )
            for role in ReviewRole
        )
        self.assertTrue(artifact_is_fully_approved(approvals, HASH))
        self.assertFalse(artifact_is_fully_approved(approvals[:-1], HASH))


class LifecycleControlTests(unittest.TestCase):
    def test_expired_transient_artifact_is_purged(self) -> None:
        artifact = StoredArtifact("tmp", HASH, 0, RetentionClass.TRANSIENT)
        self.assertEqual(plan_purge((artifact,), now=100_000).purge_ids, ("tmp",))

    def test_legal_hold_prevents_purge(self) -> None:
        artifact = StoredArtifact("held", HASH, 0, RetentionClass.TRANSIENT, legal_hold=True)
        self.assertEqual(plan_purge((artifact,), now=100_000).retained_ids, ("held",))

    def test_open_run_reference_prevents_purge(self) -> None:
        artifact = StoredArtifact("open", HASH, 0, RetentionClass.TRANSIENT, referenced_by_open_run=True)
        self.assertEqual(plan_purge((artifact,), now=100_000).retained_ids, ("open",))

    def test_recovery_accepts_recent_tested_replica(self) -> None:
        snapshot = BackupSnapshot("s1", 90, HASH, 10, ("east", "west"), 95, 5)
        result = assess_recovery((snapshot,), incident_at=100, objective=RecoveryObjective(20, 10))
        self.assertTrue(result.recoverable)

    def test_recovery_rejects_untested_snapshot(self) -> None:
        snapshot = BackupSnapshot("s1", 90, HASH, 10, ("east", "west"))
        result = assess_recovery((snapshot,), incident_at=100, objective=RecoveryObjective(20, 10))
        self.assertFalse(result.recoverable)
        self.assertTrue(any("restore_not_tested" in blocker for blocker in result.blockers))

    def test_recovery_rejects_single_region(self) -> None:
        snapshot = BackupSnapshot("s1", 90, HASH, 10, ("east",), 95, 5)
        result = assess_recovery((snapshot,), incident_at=100, objective=RecoveryObjective(20, 10))
        self.assertTrue(any("insufficient_region_replicas" in blocker for blocker in result.blockers))

    def test_rollback_reverses_dependency_order(self) -> None:
        steps = (
            ChangeStep("schema", (), True, "restore schema"),
            ChangeStep("adapter", ("schema",), True, "restore adapter"),
        )
        result = build_rollback_plan(steps, backup_available=True)
        self.assertTrue(result.safe)
        self.assertEqual(result.ordered_step_ids, ("adapter", "schema"))

    def test_irreversible_step_blocks_rollout(self) -> None:
        result = build_rollback_plan((ChangeStep("x", (), False, None),), backup_available=True)
        self.assertFalse(result.safe)
        self.assertIn("irreversible_step:x", result.blockers)

    def test_state_migration_requires_backup(self) -> None:
        step = ChangeStep("data", (), True, "restore", state_migration=True)
        self.assertIn("backup_required:data", build_rollback_plan((step,), backup_available=False).blockers)

    def test_healthy_rollout_promotes_one_stage(self) -> None:
        signals = RolloutSignals(0.0, 0.0, 8.5, 20, True, True)
        decision = evaluate_rollout(RolloutStage.SHADOW, signals)
        self.assertTrue(decision.promote)
        self.assertEqual(decision.next_stage, RolloutStage.INTERNAL)

    def test_bad_error_rate_freezes(self) -> None:
        signals = RolloutSignals(0.2, 0.0, 8.5, 20, True, True)
        decision = evaluate_rollout(RolloutStage.CANARY, signals)
        self.assertEqual(decision.next_stage, RolloutStage.FROZEN)

    def test_frozen_stage_requires_manual_unfreeze(self) -> None:
        signals = RolloutSignals(0.0, 0.0, 8.5, 20, True, True)
        decision = evaluate_rollout(RolloutStage.FROZEN, signals)
        self.assertIn("manual_unfreeze_required", decision.blockers)


class EnvironmentLockTests(unittest.TestCase):
    def manifest(self) -> EnvironmentManifest:
        return EnvironmentManifest(
            "3.12.1",
            "linux",
            "x86_64",
            (DependencyPin("ffmpeg", "7", "b" * 64, "binary"),),
            {"renderer": "1"},
            ("CURIOSITY_MODE",),
        )

    def test_identical_environments_match(self) -> None:
        result = compare_environments(self.manifest(), self.manifest())
        self.assertTrue(result.compatible)

    def test_dependency_version_drift_is_blocked(self) -> None:
        observed = replace(self.manifest(), dependencies=(DependencyPin("ffmpeg", "8", "b" * 64, "binary"),))
        self.assertIn("dependency_mismatch:ffmpeg", compare_environments(self.manifest(), observed).blockers)

    def test_allowed_tool_drift_becomes_warning(self) -> None:
        observed = replace(self.manifest(), tool_versions={"renderer": "2"})
        result = compare_environments(self.manifest(), observed, allowed_tool_drift=("renderer",))
        self.assertTrue(result.compatible)
        self.assertIn("allowed_tool_drift:renderer", result.warnings)

    def test_bad_dependency_hash_is_invalid(self) -> None:
        manifest = replace(self.manifest(), dependencies=(DependencyPin("ffmpeg", "7", "bad"),))
        self.assertIn("invalid_dependency_hash:ffmpeg", validate_manifest(manifest))


class DriftMonitorTests(unittest.TestCase):
    def test_baseline_requires_three_values(self) -> None:
        with self.assertRaises(ValueError):
            build_baseline("quality", (8.0, 8.1))

    def test_stable_metric_has_no_drift(self) -> None:
        baseline = build_baseline("quality", (7.8, 8.0, 8.2))
        finding = evaluate_metric(baseline, (MetricObservation("quality", 8.0, 1),))
        self.assertEqual(finding.severity, DriftSeverity.NONE)

    def test_large_harmful_drift_freezes(self) -> None:
        baseline = build_baseline("quality", (7.9, 8.0, 8.1))
        finding = evaluate_metric(baseline, (MetricObservation("quality", 5.0, 1),))
        self.assertEqual(finding.severity, DriftSeverity.FREEZE)

    def test_missing_metric_holds(self) -> None:
        baseline = build_baseline("quality", (7.9, 8.0, 8.1))
        report = evaluate_drift((baseline,), ())
        self.assertEqual(report.severity, DriftSeverity.HOLD)


class PortfolioOptimizerTests(unittest.TestCase):
    def candidate(self, slug: str, topic: str, visual: str, **overrides: object) -> StoryCandidate:
        values: dict[str, object] = {
            "slug": slug,
            "topic_family": topic,
            "emotional_tone": "wonder",
            "visual_family": visual,
            "factual_complexity": 2,
            "estimated_cost": 1.0,
            "readiness_score": 85.0,
            "novelty_score": 0.8,
            "audience_value": 0.8,
        }
        values.update(overrides)
        return StoryCandidate(**values)

    def test_diverse_portfolio_is_selected(self) -> None:
        candidates = (self.candidate("a", "space", "diagram"), self.candidate("b", "history", "archive"))
        result = build_portfolio(candidates, PortfolioPolicy(2, 3.0))
        self.assertTrue(result.valid)
        self.assertEqual(len(result.selected), 2)

    def test_topic_family_limit_defers_duplicate(self) -> None:
        candidates = (self.candidate("a", "space", "diagram"), self.candidate("b", "space", "archive"))
        result = build_portfolio(candidates, PortfolioPolicy(2, 3.0))
        self.assertTrue(any(reason == "topic_family_limit" for _, reason in result.deferred))

    def test_exploration_quota_is_enforced(self) -> None:
        result = build_portfolio((self.candidate("a", "space", "diagram"),), PortfolioPolicy(1, 2.0, minimum_exploration_slots=1))
        self.assertIn("exploration_quota_unmet", result.blockers)

    def test_blocked_story_is_never_selected(self) -> None:
        result = build_portfolio((self.candidate("a", "space", "diagram", blocked=True),), PortfolioPolicy(1, 2.0, minimum_exploration_slots=0))
        self.assertFalse(result.selected)


class GeneralizationSuiteTests(unittest.TestCase):
    def fixtures(self) -> tuple[StoryFixture, ...]:
        return (
            StoryFixture("mechanism", StoryArchetype.MECHANISM, "science", "required", 5, 60, True, True, 4, True),
            StoryFixture("history", StoryArchetype.HISTORICAL, "history", "required", 5, 70, True, False, 3, True),
            StoryFixture("scale", StoryArchetype.SCALE_COMPARISON, "space", "required", 4, 55, False, True, 2, True),
            StoryFixture("process", StoryArchetype.PROCESS, "industry", "required", 6, 75, True, False, 4, True),
            StoryFixture("negative", StoryArchetype.COUNTERINTUITIVE, "biology", "required", 3, 50, False, True, 2, False, "missing_evidence"),
        )

    def test_diverse_fixture_suite_passes(self) -> None:
        self.assertTrue(assess_generalization(self.fixtures()).valid)

    def test_missing_negative_control_fails(self) -> None:
        result = assess_generalization(self.fixtures()[:-1], GeneralizationPolicy(minimum_fixtures=4))
        self.assertIn("missing_negative_control", result.blockers)

    def test_required_mode_needs_claims(self) -> None:
        fixture = StoryFixture("bad", StoryArchetype.MECHANISM, "science", "required", 4, 50, True, True, 0, True)
        result = assess_generalization((fixture,), GeneralizationPolicy(1, 1, 1, False, False))
        self.assertTrue(any("required_mode_without_claims" in item for item in result.blockers))

    def test_fixture_matrix_reports_media_modes(self) -> None:
        matrix = fixture_matrix(self.fixtures())
        self.assertIn("mixed", matrix["media_modes"])
        self.assertIn("real", matrix["media_modes"])


class StructuralCompletenessTests(unittest.TestCase):
    def test_complete_reference_surface_scores_100(self) -> None:
        report = assess_structural_completeness(complete_reference_evidence())
        self.assertTrue(report.reference_complete)
        self.assertEqual(report.reference_coverage_percent, 100.0)
        self.assertEqual(report.verified_execution_percent, 0.0)

    def test_verified_surface_scores_100_for_execution(self) -> None:
        report = assess_structural_completeness(complete_reference_evidence(execution_verified=True))
        self.assertTrue(report.execution_complete)
        self.assertEqual(report.verified_execution_percent, 100.0)

    def test_missing_one_domain_prevents_100(self) -> None:
        evidence = complete_reference_evidence()[:-1]
        report = assess_structural_completeness(evidence)
        self.assertFalse(report.reference_complete)
        self.assertLess(report.reference_coverage_percent, 100.0)
        self.assertTrue(report.missing_domains)

    def test_nonisolated_domain_prevents_100(self) -> None:
        evidence = list(complete_reference_evidence())
        evidence[0] = replace(evidence[0], isolated=False)
        report = assess_structural_completeness(evidence)
        self.assertFalse(report.reference_complete)
        self.assertIn(evidence[0].domain, report.invalid_domains)

    def test_outside_module_path_prevents_100(self) -> None:
        evidence = list(complete_reference_evidence())
        evidence[0] = DomainEvidence(
            StructuralDomain.ARTIFACT_IDENTITY,
            ("scripts/live.py",),
            ("positive", "negative"),
            True,
        )
        report = assess_structural_completeness(evidence)
        self.assertIn("artifact_identity:module_outside_isolation_boundary", report.blockers)


if __name__ == "__main__":
    unittest.main()
