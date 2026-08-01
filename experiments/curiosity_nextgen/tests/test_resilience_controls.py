from __future__ import annotations

from dataclasses import replace
import unittest

from experiments.curiosity_nextgen.checkpoint_store import (
    Checkpoint,
    CheckpointLedger,
    ResumeDecision,
    StageState,
)
from experiments.curiosity_nextgen.circuit_breaker import (
    BreakerPolicy,
    BreakerState,
    CircuitBreaker,
)
from experiments.curiosity_nextgen.fault_injection import (
    ExpectedDecision,
    FaultKind,
    FaultObservation,
    FaultScenario,
    default_fault_campaign,
    evaluate_observation,
    validate_campaign,
)
from experiments.curiosity_nextgen.lineage_graph import LineageGraph, LineageNode
from experiments.curiosity_nextgen.migration_planner import (
    MigrationCatalog,
    MigrationDecision,
    MigrationStep,
    plan_migration,
)
from experiments.curiosity_nextgen.replay_engine import (
    RunEnvelope,
    RunRecord,
    StageRecord,
    build_run_record,
    canonical_digest,
    compare_replay,
)
from experiments.curiosity_nextgen.resilience_lab import (
    ResilienceDecision,
    ResilienceInput,
    simulate_resilience_preflight,
)
from experiments.curiosity_nextgen.resource_governor import (
    ResourceDecision,
    ResourcePolicy,
    ResourceRequest,
    govern_resources,
)
from experiments.curiosity_nextgen.schema_registry import (
    CompatibilityMode,
    SchemaDefinition,
    SchemaField,
    SchemaRegistry,
    compare_schemas,
    validate_payload,
)
from experiments.curiosity_nextgen.security_scanner import (
    FindingKind,
    redact_payload,
    scan_payload,
)


MANIFEST = "a" * 64
OTHER_MANIFEST = "b" * 64
INPUT = "c" * 64
OUTPUT = "d" * 64
POLICY = "e" * 64


def schema_v1(*, allow_unknown: bool = False) -> SchemaDefinition:
    return SchemaDefinition(
        "story-package",
        1,
        (
            SchemaField("story_slug", "str"),
            SchemaField("manifest_sha256", "sha256"),
            SchemaField("metadata", "dict", required=False, default_present=True),
        ),
        allow_unknown_fields=allow_unknown,
    )


def valid_payload() -> dict[str, object]:
    return {"story_slug": "demo", "manifest_sha256": MANIFEST, "metadata": {}}


def node(
    node_id: str,
    *,
    digest: str = OUTPUT,
    manifest: str = MANIFEST,
    parents: tuple[str, ...] = (),
    artifact_type: str = "artifact",
) -> LineageNode:
    return LineageNode(node_id, artifact_type, digest, manifest, parents)


def request(
    request_id: str = "job-1",
    *,
    story_slug: str = "demo",
    seconds: float = 100.0,
    calls: int = 2,
    memory: int = 512,
    priority: int = 80,
    cache: float = 0.8,
    dependency: str = "renderer",
) -> ResourceRequest:
    return ResourceRequest(
        request_id,
        story_slug,
        "review",
        seconds,
        calls,
        memory,
        priority,
        cache,
        dependency,
    )


def envelope(*, dependencies: dict[str, str] | None = None) -> RunEnvelope:
    return RunEnvelope(
        "run-1",
        "demo",
        MANIFEST,
        INPUT,
        POLICY,
        dependencies or {"renderer": "1.0"},
        42,
        ("research", "render"),
    )


def stage(name: str, *, output: str = OUTPUT, decision: str = "pass", duration: int = 100) -> StageRecord:
    return StageRecord(name, INPUT, output, decision, duration_ms=duration)


def passed_checkpoint(stage_name: str, key: str, *, attempt: int = 1) -> Checkpoint:
    return Checkpoint(stage_name, MANIFEST, INPUT, StageState.PASSED, attempt, key, OUTPUT)


class SchemaCompatibilityTests(unittest.TestCase):
    def test_valid_payload_passes(self) -> None:
        result = validate_payload(schema_v1(), valid_payload())
        self.assertTrue(result.valid)

    def test_missing_required_field_fails(self) -> None:
        result = validate_payload(schema_v1(), {"story_slug": "demo"})
        self.assertFalse(result.valid)
        self.assertEqual(result.missing_fields, ("manifest_sha256",))

    def test_wrong_type_fails(self) -> None:
        payload = valid_payload()
        payload["manifest_sha256"] = 123
        result = validate_payload(schema_v1(), payload)
        self.assertFalse(result.valid)
        self.assertIn("manifest_sha256:expected_sha256", result.type_errors)

    def test_sensitive_field_is_reported(self) -> None:
        schema = SchemaDefinition("secret", 1, (SchemaField("token", "str", sensitive=True),))
        result = validate_payload(schema, {"token": "value"})
        self.assertTrue(result.valid)
        self.assertEqual(result.sensitive_fields_present, ("token",))

    def test_backward_compatibility_blocks_new_required_field(self) -> None:
        new = SchemaDefinition(
            "story-package",
            2,
            schema_v1().fields + (SchemaField("judge_version", "str"),),
        )
        result = compare_schemas(schema_v1(), new, mode=CompatibilityMode.BACKWARD)
        self.assertFalse(result.compatible)
        self.assertIn("new_required_field_without_default:judge_version", result.blockers)

    def test_full_compatibility_allows_optional_field_when_old_reader_allows_unknown(self) -> None:
        old = schema_v1(allow_unknown=True)
        new = SchemaDefinition(
            "story-package",
            2,
            old.fields + (SchemaField("judge_version", "str", required=False),),
            allow_unknown_fields=True,
        )
        result = compare_schemas(old, new, mode=CompatibilityMode.FULL)
        self.assertTrue(result.compatible)

    def test_registry_rejects_duplicate_version(self) -> None:
        registry = SchemaRegistry((schema_v1(),))
        with self.assertRaises(ValueError):
            registry.register(schema_v1())


class MigrationTests(unittest.TestCase):
    def test_complete_reversible_path_is_ready(self) -> None:
        catalog = MigrationCatalog((
            MigrationStep("story", 1, 2, "one-to-two"),
            MigrationStep("story", 2, 3, "two-to-three"),
        ))
        plan = plan_migration(catalog, schema_name="story", source_version=1, target_version=3)
        self.assertEqual(plan.decision, MigrationDecision.READY)
        self.assertEqual([item.migration_id for item in plan.steps], ["one-to-two", "two-to-three"])

    def test_lossy_step_is_blocked_by_default(self) -> None:
        catalog = MigrationCatalog((MigrationStep("story", 1, 2, "lossy", reversible=False, lossy=True),))
        plan = plan_migration(catalog, schema_name="story", source_version=1, target_version=2)
        self.assertEqual(plan.decision, MigrationDecision.BLOCKED)
        self.assertIn("lossy_step_not_allowed:lossy", plan.blockers)

    def test_manual_review_step_returns_review(self) -> None:
        catalog = MigrationCatalog((MigrationStep("story", 1, 2, "review", requires_manual_review=True),))
        plan = plan_migration(catalog, schema_name="story", source_version=1, target_version=2)
        self.assertEqual(plan.decision, MigrationDecision.REVIEW)

    def test_missing_path_is_blocked(self) -> None:
        plan = plan_migration(MigrationCatalog(), schema_name="story", source_version=1, target_version=4)
        self.assertEqual(plan.decision, MigrationDecision.BLOCKED)
        self.assertEqual(plan.blockers, ("no_complete_migration_path",))


class LineageTests(unittest.TestCase):
    def test_valid_graph_passes(self) -> None:
        graph = LineageGraph((node("script", artifact_type="script"), node("video", parents=("script",), artifact_type="video")))
        self.assertTrue(graph.validate().valid)

    def test_missing_parent_is_reported(self) -> None:
        graph = LineageGraph((node("video", parents=("missing",)),))
        result = graph.validate()
        self.assertFalse(result.valid)
        self.assertEqual(result.missing_parents, ("missing",))

    def test_cycle_is_reported(self) -> None:
        graph = LineageGraph((node("a", parents=("b",)), node("b", parents=("a",))))
        result = graph.validate()
        self.assertFalse(result.valid)
        self.assertTrue(result.cycles)

    def test_manifest_mismatch_is_reported(self) -> None:
        graph = LineageGraph((node("a"), node("b", manifest=OTHER_MANIFEST, parents=("a",))))
        result = graph.validate()
        self.assertFalse(result.valid)
        self.assertEqual(result.manifest_mismatches, ("a->b",))

    def test_impact_includes_all_descendants(self) -> None:
        graph = LineageGraph((
            node("script", artifact_type="script"),
            node("shot", parents=("script",), artifact_type="shot"),
            node("video", parents=("shot",), artifact_type="video"),
            node("report", parents=("video",), artifact_type="report"),
        ))
        impact = graph.impact(("script",))
        self.assertEqual(impact.affected_nodes, ("report", "script", "shot", "video"))
        self.assertEqual(impact.terminal_nodes, ("report",))

    def test_stale_root_marks_descendants_stale(self) -> None:
        graph = LineageGraph((node("script"), node("video", parents=("script",))))
        stale = graph.stale_nodes({"script": INPUT})
        self.assertEqual(stale, ("script", "video"))


class ReplayTests(unittest.TestCase):
    def test_identical_replay_is_deterministic(self) -> None:
        baseline = RunRecord(envelope(), (stage("research"), stage("render")))
        candidate = RunRecord(envelope(), (stage("research"), stage("render")))
        self.assertTrue(compare_replay(baseline, candidate).deterministic)

    def test_output_drift_is_detected(self) -> None:
        baseline = RunRecord(envelope(), (stage("research"), stage("render")))
        candidate = RunRecord(envelope(), (stage("research"), stage("render", output=INPUT)))
        result = compare_replay(baseline, candidate)
        self.assertFalse(result.deterministic)
        self.assertEqual(result.output_mismatches, ("render",))

    def test_dependency_version_drift_is_detected(self) -> None:
        baseline = RunRecord(envelope(), (stage("research"), stage("render")))
        candidate = RunRecord(envelope(dependencies={"renderer": "2.0"}), (stage("research"), stage("render")))
        result = compare_replay(baseline, candidate)
        self.assertIn("dependency_versions", result.envelope_mismatches)

    def test_order_drift_is_detected(self) -> None:
        baseline = RunRecord(envelope(), (stage("research"), stage("render")))
        candidate = RunRecord(envelope(), (stage("render"), stage("research")))
        self.assertTrue(compare_replay(baseline, candidate).order_mismatch)

    def test_duration_regression_does_not_change_determinism(self) -> None:
        baseline = RunRecord(envelope(), (stage("research", duration=100), stage("render", duration=1000)))
        candidate = RunRecord(envelope(), (stage("research", duration=100), stage("render", duration=2000)))
        result = compare_replay(baseline, candidate)
        self.assertTrue(result.deterministic)
        self.assertEqual(result.duration_regressions, ("render",))


class CheckpointTests(unittest.TestCase):
    def test_all_passed_stages_are_complete(self) -> None:
        ledger = CheckpointLedger((passed_checkpoint("research", "k1"), passed_checkpoint("render", "k2")))
        plan = ledger.plan_resume(("research", "render"), manifest_sha256=MANIFEST)
        self.assertEqual(plan.decision, ResumeDecision.COMPLETE)

    def test_failed_stage_is_retried(self) -> None:
        failed = Checkpoint("render", MANIFEST, INPUT, StageState.FAILED, 1, "k1", reason="timeout")
        ledger = CheckpointLedger((failed,))
        plan = ledger.plan_resume(("render",), manifest_sha256=MANIFEST)
        self.assertEqual(plan.decision, ResumeDecision.RETRY)
        self.assertEqual(plan.attempt, 2)

    def test_exhausted_retry_budget_blocks(self) -> None:
        failed = Checkpoint("render", MANIFEST, INPUT, StageState.FAILED, 3, "k1", reason="timeout")
        ledger = CheckpointLedger((failed,), max_attempts=3)
        plan = ledger.plan_resume(("render",), manifest_sha256=MANIFEST)
        self.assertEqual(plan.decision, ResumeDecision.BLOCKED)
        self.assertIn("retry_budget_exhausted:render", plan.blockers)

    def test_changed_input_blocks_resume(self) -> None:
        ledger = CheckpointLedger((passed_checkpoint("research", "k1"),))
        plan = ledger.plan_resume(
            ("research",),
            manifest_sha256=MANIFEST,
            expected_inputs={"research": OTHER_MANIFEST},
        )
        self.assertEqual(plan.decision, ResumeDecision.BLOCKED)
        self.assertEqual(plan.stale_stages, ("research",))

    def test_passed_idempotency_key_cannot_be_reused(self) -> None:
        ledger = CheckpointLedger((passed_checkpoint("research", "same"),))
        with self.assertRaises(ValueError):
            ledger.append(passed_checkpoint("render", "same"))

    def test_quarantined_stage_blocks_resume(self) -> None:
        quarantined = Checkpoint("render", MANIFEST, INPUT, StageState.QUARANTINED, 1, "k1", reason="corrupt")
        ledger = CheckpointLedger((quarantined,))
        plan = ledger.plan_resume(("render",), manifest_sha256=MANIFEST)
        self.assertEqual(plan.decision, ResumeDecision.BLOCKED)
        self.assertIn("stage_quarantined:render", plan.blockers)


class CircuitBreakerTests(unittest.TestCase):
    def breaker(self) -> CircuitBreaker:
        return CircuitBreaker(
            "renderer",
            policy=BreakerPolicy(
                failure_threshold=2,
                recovery_timeout_seconds=10,
                half_open_max_probes=1,
                success_threshold_to_close=1,
            ),
        )

    def test_failure_threshold_opens_circuit(self) -> None:
        breaker = self.breaker()
        breaker.record_failure(now=0)
        snapshot = breaker.record_failure(now=1)
        self.assertEqual(snapshot.state, BreakerState.OPEN)
        self.assertFalse(breaker.admit(now=5).allowed)

    def test_timeout_moves_open_circuit_to_half_open(self) -> None:
        breaker = self.breaker()
        breaker.record_failure(now=0)
        breaker.record_failure(now=1)
        admission = breaker.admit(now=11)
        self.assertTrue(admission.allowed)
        self.assertEqual(admission.state, BreakerState.HALF_OPEN)

    def test_half_open_probe_budget_is_enforced(self) -> None:
        breaker = self.breaker()
        breaker.record_failure(now=0)
        breaker.record_failure(now=1)
        self.assertTrue(breaker.admit(now=11).allowed)
        second = breaker.admit(now=11)
        self.assertFalse(second.allowed)
        self.assertEqual(second.reason, "half_open_probe_budget_exhausted")

    def test_successful_probe_closes_circuit(self) -> None:
        breaker = self.breaker()
        breaker.record_failure(now=0)
        breaker.record_failure(now=1)
        breaker.admit(now=11)
        snapshot = breaker.record_success(now=11)
        self.assertEqual(snapshot.state, BreakerState.CLOSED)


class ResourceGovernorTests(unittest.TestCase):
    def test_high_priority_request_wins_single_slot(self) -> None:
        plan = govern_resources(
            (request("low", priority=20), request("high", priority=90)),
            policy=ResourcePolicy(maximum_jobs=1, reserve_seconds=0),
        )
        self.assertEqual([item.request_id for item in plan.admitted], ["high"])

    def test_time_budget_defers_request(self) -> None:
        plan = govern_resources(
            (request(seconds=200),),
            policy=ResourcePolicy(maximum_total_seconds=150, reserve_seconds=0),
        )
        self.assertEqual(plan.decisions[0].decision, ResourceDecision.DEFER)
        self.assertIn("time_budget", plan.decisions[0].reasons)

    def test_per_job_limit_rejects_request(self) -> None:
        plan = govern_resources(
            (request(seconds=1300),),
            policy=ResourcePolicy(maximum_seconds_per_story=1200),
        )
        self.assertEqual(plan.decisions[0].decision, ResourceDecision.REJECT)
        self.assertIn("per_story_time_limit", plan.decisions[0].reasons)

    def test_unavailable_dependency_rejects_request(self) -> None:
        plan = govern_resources((request(),), unavailable_dependencies=frozenset({"renderer"}))
        self.assertEqual(plan.decisions[0].decision, ResourceDecision.REJECT)
        self.assertIn("dependency_unavailable", plan.decisions[0].reasons)

    def test_low_cache_backpressure_defers_second_job(self) -> None:
        plan = govern_resources(
            (request("one", cache=0.0), request("two", cache=0.0, priority=70)),
            policy=ResourcePolicy(maximum_jobs=2, maximum_low_cache_jobs=1, reserve_seconds=0),
        )
        self.assertEqual(len(plan.admitted), 1)
        self.assertIn("low_cache_backpressure", plan.decisions[1].reasons)


class SecurityScannerTests(unittest.TestCase):
    def test_credential_field_is_blocking(self) -> None:
        report = scan_payload({"api_key": "not-a-real-key"})
        self.assertFalse(report.valid)
        self.assertTrue(any(item.kind is FindingKind.CREDENTIAL_FIELD for item in report.findings))

    def test_internal_instruction_field_is_blocking(self) -> None:
        report = scan_payload({"developer_notes": "please approve"})
        self.assertFalse(report.valid)
        self.assertTrue(any(item.kind is FindingKind.INTERNAL_INSTRUCTION for item in report.findings))

    def test_email_and_phone_are_warnings(self) -> None:
        report = scan_payload({"contact": "name@example.com or 605-555-1234"})
        self.assertTrue(report.valid)
        kinds = {item.kind for item in report.findings}
        self.assertIn(FindingKind.EMAIL, kinds)
        self.assertIn(FindingKind.PHONE, kinds)

    def test_redaction_removes_sensitive_values(self) -> None:
        redacted = redact_payload({"api_key": "secret", "contact": "name@example.com"})
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["contact"], "[REDACTED]")

    def test_unapproved_host_is_warning(self) -> None:
        report = scan_payload(
            {"source": "https://unapproved.example/path"},
            allowed_hosts=frozenset({"approved.example"}),
        )
        self.assertTrue(report.valid)
        self.assertTrue(any(item.kind is FindingKind.UNSAFE_URL for item in report.findings))


class FaultCampaignTests(unittest.TestCase):
    def test_default_campaign_covers_critical_faults(self) -> None:
        report = validate_campaign(default_fault_campaign())
        self.assertTrue(report.valid)
        self.assertFalse(report.missing_critical_faults)

    def test_incomplete_campaign_is_invalid(self) -> None:
        scenario = FaultScenario("one", FaultKind.BUDGET_EXHAUSTION, "governor", ExpectedDecision.DEFER, "budget", critical=False)
        report = validate_campaign((scenario,))
        self.assertFalse(report.valid)
        self.assertTrue(report.missing_critical_faults)

    def test_matching_observation_passes(self) -> None:
        scenario = FaultScenario("duplicate", FaultKind.DUPLICATE_PUBLISH, "approval", ExpectedDecision.FREEZE, "consumed")
        observation = FaultObservation("duplicate", "freeze", ("approval already consumed",), True)
        self.assertTrue(evaluate_observation(scenario, observation).passed)

    def test_freeze_expectation_requires_frozen_state(self) -> None:
        scenario = FaultScenario("duplicate", FaultKind.DUPLICATE_PUBLISH, "approval", ExpectedDecision.FREEZE, "consumed")
        observation = FaultObservation("duplicate", "freeze", ("approval consumed",), False)
        result = evaluate_observation(scenario, observation)
        self.assertFalse(result.passed)
        self.assertIn("publishing_not_frozen", result.failures)


class ResilienceLabTests(unittest.TestCase):
    def inputs(self, **overrides: object) -> ResilienceInput:
        values: dict[str, object] = {
            "schema": schema_v1(),
            "payload": valid_payload(),
            "lineage": LineageGraph((node("script", artifact_type="script"),)),
            "checkpoint_ledger": CheckpointLedger(),
            "required_stages": ("research", "render"),
            "manifest_sha256": MANIFEST,
            "resource_request": request(),
            "circuit_breaker": CircuitBreaker("renderer"),
            "now": 100,
        }
        values.update(overrides)
        return ResilienceInput(**values)

    def test_clean_preflight_is_ready(self) -> None:
        result = simulate_resilience_preflight(self.inputs())
        self.assertEqual(result.decision, ResilienceDecision.READY)
        self.assertFalse(result.blockers)

    def test_secret_field_quarantines(self) -> None:
        payload = valid_payload()
        payload["api_key"] = "not-real"
        result = simulate_resilience_preflight(self.inputs(payload=payload))
        self.assertEqual(result.decision, ResilienceDecision.QUARANTINE)
        self.assertTrue(any(item.startswith("security:") for item in result.blockers))

    def test_open_dependency_circuit_holds(self) -> None:
        breaker = CircuitBreaker("renderer")
        breaker.force_open(now=0)
        result = simulate_resilience_preflight(self.inputs(circuit_breaker=breaker, now=1))
        self.assertEqual(result.decision, ResilienceDecision.HOLD)
        self.assertIn("dependency:dependency_circuit_open", result.warnings)

    def test_invalid_schema_quarantines(self) -> None:
        result = simulate_resilience_preflight(self.inputs(payload={"story_slug": "demo"}))
        self.assertEqual(result.decision, ResilienceDecision.QUARANTINE)
        self.assertTrue(any(item.startswith("schema:") for item in result.blockers))

    def test_resource_defer_holds(self) -> None:
        policy = ResourcePolicy(maximum_total_seconds=50, reserve_seconds=0)
        result = simulate_resilience_preflight(self.inputs(resource_policy=policy))
        self.assertEqual(result.decision, ResilienceDecision.HOLD)
        self.assertIn("resource:time_budget", result.warnings)

    def test_retryable_checkpoint_remains_ready_with_warning(self) -> None:
        failed = Checkpoint("research", MANIFEST, INPUT, StageState.FAILED, 1, "k1", reason="timeout")
        ledger = CheckpointLedger((failed,))
        result = simulate_resilience_preflight(self.inputs(checkpoint_ledger=ledger))
        self.assertEqual(result.decision, ResilienceDecision.READY)
        self.assertIn("checkpoint_retry:research:attempt_2", result.warnings)


if __name__ == "__main__":
    unittest.main()
