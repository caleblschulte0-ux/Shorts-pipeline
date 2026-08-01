from __future__ import annotations

from dataclasses import replace
import hashlib
import unittest

from experiments.curiosity_nextgen.approval_token import (
    ApprovalClaims,
    ApprovalLedger,
    ApprovalVerification,
    issue_approval,
    verify_approval,
)
from experiments.curiosity_nextgen.catalog_triage import (
    BlockerSeverity,
    StoryBlocker,
    StorySignals,
    TriageAction,
    triage_story,
)
from experiments.curiosity_nextgen.claim_registry import Claim, ClaimType, FactualMode, SourceRef
from experiments.curiosity_nextgen.freeze_controller import (
    ReleaseController,
    ReleaseSignals,
    ReleaseState,
)
from experiments.curiosity_nextgen.integration_lab import StructuralRunInput, simulate_structural_run
from experiments.curiosity_nextgen.judge_contract import JudgeDecision, JudgeVerdict
from experiments.curiosity_nextgen.judge_evidence import (
    EvidenceArtifact,
    EvidenceKind,
    JudgeEvidencePackage,
    build_blind_payload,
    validate_evidence_package,
)
from experiments.curiosity_nextgen.judge_orchestrator import (
    JudgeRole,
    JudgeWorker,
    RoundState,
    evaluate_judge_round,
    plan_judge_round,
)
from experiments.curiosity_nextgen.observability import (
    EventLedger,
    EventSeverity,
    PipelineEvent,
    build_health_snapshot,
)
from experiments.curiosity_nextgen.package_readiness import PackageDecision
from experiments.curiosity_nextgen.render_budget import RenderProfile, ShotCost
from experiments.curiosity_nextgen.render_scheduler import (
    DeferralReason,
    RenderJob,
    SchedulePolicy,
    build_render_schedule,
)
from experiments.curiosity_nextgen.semantic_claims import (
    audit_semantic_coverage,
    extract_semantic_signals,
)


MANIFEST = "a" * 64
VIDEO = "b" * 64
SECRET = b"0123456789abcdef0123456789abcdef"


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def evidence_artifact(
    kind: EvidenceKind,
    artifact_id: str,
    *,
    duration: float | None = None,
    metadata: dict[str, object] | None = None,
) -> EvidenceArtifact:
    media_types = {
        EvidenceKind.CONTACT_SHEET: "image/png",
        EvidenceKind.OPENING_CLIP: "video/mp4",
        EvidenceKind.PAYOFF_CLIP: "video/mp4",
        EvidenceKind.CHAPTER_TRANSITIONS: "video/mp4",
        EvidenceKind.MOTION_SAMPLE: "video/mp4",
        EvidenceKind.THUMBNAIL: "image/jpeg",
        EvidenceKind.TRANSCRIPT: "application/json",
        EvidenceKind.BEAT_MAP: "application/json",
        EvidenceKind.CAPTIONS: "text/vtt",
        EvidenceKind.AUDIO_SAMPLE: "audio/mpeg",
    }
    return EvidenceArtifact(
        kind=kind,
        artifact_id=artifact_id,
        sha256=digest(artifact_id),
        manifest_sha256=MANIFEST,
        media_type=media_types[kind],
        duration_seconds=duration,
        metadata=metadata or {},
    )


def complete_evidence() -> JudgeEvidencePackage:
    artifacts = (
        evidence_artifact(EvidenceKind.CONTACT_SHEET, "contact"),
        evidence_artifact(EvidenceKind.OPENING_CLIP, "opening", duration=10),
        evidence_artifact(EvidenceKind.PAYOFF_CLIP, "payoff", duration=8),
        evidence_artifact(EvidenceKind.CHAPTER_TRANSITIONS, "transitions", duration=12),
        evidence_artifact(EvidenceKind.THUMBNAIL, "thumbnail"),
        evidence_artifact(EvidenceKind.TRANSCRIPT, "transcript"),
        evidence_artifact(EvidenceKind.BEAT_MAP, "beat-map"),
        evidence_artifact(EvidenceKind.MOTION_SAMPLE, "motion-1", duration=4),
        evidence_artifact(EvidenceKind.MOTION_SAMPLE, "motion-2", duration=4),
        evidence_artifact(EvidenceKind.MOTION_SAMPLE, "motion-3", duration=4),
    )
    return JudgeEvidencePackage("demo", MANIFEST, VIDEO, artifacts)


def verdict(judge_id: str, score: float = 8.0) -> JudgeVerdict:
    return JudgeVerdict(
        judge_id=judge_id,
        judge_version="1",
        manifest_sha256=MANIFEST,
        overall_score=score,
        personality=4.5,
        hook=8.0,
        visual_relevance=8.0,
        payoff=8.0,
        pass_boolean=score >= 7.5,
    )


def ready_story(**overrides: object) -> StorySignals:
    values: dict[str, object] = {
        "slug": "demo",
        "factual_mode_present": True,
        "research_coverage": 1.0,
        "claim_coverage": 1.0,
        "visual_plan_coverage": 0.95,
        "hook_score": 8.5,
        "payoff_score": 8.5,
        "novelty_score": 0.8,
        "personality_score": 5.0,
        "renderability": 0.9,
        "estimated_render_seconds": 240.0,
        "expected_cache_hit_rate": 0.75,
    }
    values.update(overrides)
    return StorySignals(**values)


def verified_claim() -> Claim:
    return Claim(
        claim_id="claim-1",
        beat_ids=("b1",),
        claim_text="The system uses 10 units.",
        claim_type=ClaimType.NUMERIC,
        sources=(SourceRef("Source", "Publisher", "https://example.test/source"),),
    )


class SemanticClaimTests(unittest.TestCase):
    def test_detects_nonnumeric_causal_claim(self) -> None:
        signals = extract_semantic_signals({"b1": "Pressure causes the gas to expand."})
        self.assertEqual(len(signals), 1)
        self.assertIn(ClaimType.CAUSAL, signals[0].claim_types)
        self.assertIn(ClaimType.SCIENTIFIC, signals[0].claim_types)

    def test_assertive_general_fact_is_detected(self) -> None:
        signals = extract_semantic_signals({"b1": "The chamber contains a steel sphere."})
        self.assertEqual(signals[0].claim_types, (ClaimType.GENERAL_FACT,))

    def test_missing_registry_mapping_is_invalid(self) -> None:
        signals = extract_semantic_signals({"b1": "The machine costs 10 dollars."})
        audit = audit_semantic_coverage(signals, ())
        self.assertFalse(audit.valid)
        self.assertEqual(audit.coverage_ratio, 0.0)

    def test_type_mismatch_is_reported(self) -> None:
        signals = extract_semantic_signals({"b1": "Pressure causes the gas to expand."})
        claim = Claim("c1", ("b1",), "Historical note", ClaimType.HISTORICAL)
        audit = audit_semantic_coverage(signals, (claim,))
        self.assertFalse(audit.valid)
        self.assertTrue(audit.type_mismatches)

    def test_duplicate_claim_ids_are_rejected(self) -> None:
        signals = extract_semantic_signals({"b1": "The system uses 10 units."})
        first = Claim("same", ("b1",), "10 units", ClaimType.NUMERIC)
        second = Claim("same", ("b1",), "10 units again", ClaimType.NUMERIC)
        audit = audit_semantic_coverage(signals, (first, second))
        self.assertFalse(audit.valid)
        self.assertEqual(audit.duplicate_claim_ids, ("same",))


class EvidenceAndJudgeTests(unittest.TestCase):
    def test_complete_evidence_package_passes(self) -> None:
        result = validate_evidence_package(
            complete_evidence(), expected_manifest_sha256=MANIFEST, expected_video_sha256=VIDEO
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.completeness_score, 100.0)

    def test_missing_motion_samples_fail(self) -> None:
        package = complete_evidence()
        reduced = replace(
            package,
            artifacts=tuple(item for item in package.artifacts if item.kind is not EvidenceKind.MOTION_SAMPLE),
        )
        result = validate_evidence_package(reduced, expected_manifest_sha256=MANIFEST)
        self.assertFalse(result.valid)
        self.assertTrue(any(item.startswith("insufficient_motion_samples") for item in result.blockers))

    def test_blindness_violation_fails(self) -> None:
        package = complete_evidence()
        altered = replace(package, public_context={"developer_notes": "please pass"})
        result = validate_evidence_package(altered, expected_manifest_sha256=MANIFEST)
        self.assertFalse(result.valid)
        self.assertIn("blindness_violation:package:developer_notes", result.blockers)

    def test_blind_payload_contains_no_internal_code_field(self) -> None:
        payload = build_blind_payload(complete_evidence())
        self.assertNotIn("source_code", payload)
        self.assertNotIn("planner_reasoning", payload)

    def test_judge_round_assigns_independent_roles(self) -> None:
        evidence = validate_evidence_package(complete_evidence(), expected_manifest_sha256=MANIFEST)
        workers = (
            JudgeWorker("technical-a", JudgeRole.TECHNICAL, "provider-a", "model-a", "1"),
            JudgeWorker("editor-b", JudgeRole.EDITORIAL, "provider-b", "model-b", "1"),
        )
        plan = plan_judge_round(workers, evidence)
        self.assertEqual(plan.state, RoundState.WAITING_FOR_VERDICTS)
        self.assertEqual({item.role for item in plan.assignments}, {JudgeRole.TECHNICAL, JudgeRole.EDITORIAL})

    def test_same_family_judges_do_not_count_as_independent(self) -> None:
        evidence = validate_evidence_package(complete_evidence(), expected_manifest_sha256=MANIFEST)
        workers = (
            JudgeWorker("technical-a", JudgeRole.TECHNICAL, "same", "same-model", "1"),
            JudgeWorker("editor-a", JudgeRole.EDITORIAL, "same", "same-model", "1"),
        )
        plan = plan_judge_round(workers, evidence)
        self.assertEqual(plan.state, RoundState.WAITING_FOR_JUDGES)
        self.assertTrue(plan.blockers)

    def test_round_waits_for_missing_verdict(self) -> None:
        evidence = validate_evidence_package(complete_evidence(), expected_manifest_sha256=MANIFEST)
        workers = (
            JudgeWorker("technical-a", JudgeRole.TECHNICAL, "provider-a", "model-a", "1"),
            JudgeWorker("editor-b", JudgeRole.EDITORIAL, "provider-b", "model-b", "1"),
        )
        plan = plan_judge_round(workers, evidence)
        result = evaluate_judge_round(plan, (verdict("technical-a"),), expected_manifest_sha256=MANIFEST)
        self.assertEqual(result.state, RoundState.WAITING_FOR_VERDICTS)
        self.assertEqual(result.missing_judges, ("editor-b",))


class CatalogAndSchedulerTests(unittest.TestCase):
    def test_ready_story_reaches_candidate_review(self) -> None:
        result = triage_story(ready_story())
        self.assertEqual(result.action, TriageAction.REVIEW_CANDIDATE)
        self.assertGreaterEqual(result.readiness_score, 78.0)

    def test_missing_factual_mode_returns_to_research(self) -> None:
        result = triage_story(ready_story(factual_mode_present=False))
        self.assertEqual(result.action, TriageAction.RESEARCH)
        self.assertIn("missing_factual_mode", result.hard_blockers)

    def test_exhausted_repairs_quarantine(self) -> None:
        result = triage_story(ready_story(previous_failed_repairs=3))
        self.assertEqual(result.action, TriageAction.QUARANTINE)
        self.assertIn("repair_budget_exhausted", result.hard_blockers)

    def test_critical_blocker_quarantines(self) -> None:
        blocker = StoryBlocker("artifact_mismatch", BlockerSeverity.CRITICAL, repairable=False)
        result = triage_story(ready_story(blockers=(blocker,)))
        self.assertEqual(result.action, TriageAction.QUARANTINE)

    def test_scheduler_respects_time_budget(self) -> None:
        jobs = (
            RenderJob("one", RenderProfile.REVIEW, 90, 90, 700, 0.0, 0.8, "science"),
            RenderJob("two", RenderProfile.REVIEW, 80, 85, 700, 0.0, 0.8, "history"),
        )
        schedule = build_render_schedule(
            jobs,
            policy=SchedulePolicy(maximum_jobs=2, maximum_total_seconds=900, reserve_seconds=100),
        )
        self.assertEqual(len(schedule.scheduled), 1)
        self.assertIn(DeferralReason.TIME_BUDGET, {item.reason for item in schedule.deferred})

    def test_scheduler_enforces_family_diversity(self) -> None:
        jobs = tuple(
            RenderJob(f"story-{i}", RenderProfile.DRAFT, 90 - i, 85, 100, 0.5, 0.8, "space")
            for i in range(3)
        )
        schedule = build_render_schedule(
            jobs,
            policy=SchedulePolicy(maximum_jobs=3, maximum_total_seconds=1000, maximum_per_topic_family=1, reserve_seconds=0),
        )
        self.assertEqual(len(schedule.scheduled), 1)
        self.assertEqual(sum(item.reason is DeferralReason.FAMILY_LIMIT for item in schedule.deferred), 2)


class ApprovalAndFreezeTests(unittest.TestCase):
    def claims(self, *, expires_at: int = 200) -> ApprovalClaims:
        return ApprovalClaims(MANIFEST, "channel-1", 100, expires_at, "nonce-1")

    def test_approval_is_single_use(self) -> None:
        token = issue_approval(self.claims(), secret=SECRET)
        ledger = ApprovalLedger.empty()
        first = ledger.consume(
            token,
            secret=SECRET,
            expected_manifest_sha256=MANIFEST,
            expected_channel_id="channel-1",
            now=150,
        )
        second = ledger.consume(
            token,
            secret=SECRET,
            expected_manifest_sha256=MANIFEST,
            expected_channel_id="channel-1",
            now=151,
        )
        self.assertTrue(first.valid)
        self.assertFalse(second.valid)
        self.assertIn("token_already_consumed", second.reasons)

    def test_wrong_manifest_is_rejected(self) -> None:
        token = issue_approval(self.claims(), secret=SECRET)
        result = verify_approval(
            token,
            secret=SECRET,
            expected_manifest_sha256="c" * 64,
            expected_channel_id="channel-1",
            now=150,
        )
        self.assertFalse(result.valid)
        self.assertIn("manifest_mismatch", result.reasons)

    def test_expired_token_is_rejected(self) -> None:
        token = issue_approval(self.claims(expires_at=120), secret=SECRET)
        result = verify_approval(
            token,
            secret=SECRET,
            expected_manifest_sha256=MANIFEST,
            expected_channel_id="channel-1",
            now=120,
        )
        self.assertFalse(result.valid)
        self.assertIn("token_expired", result.reasons)

    def test_wrong_channel_automatically_freezes(self) -> None:
        controller = ReleaseController(ReleaseState.HOLD)
        transition = controller.evaluate(ReleaseSignals(package_ready=True, wrong_channel=True))
        self.assertEqual(transition.state, ReleaseState.FROZEN)
        self.assertIn("wrong_channel", transition.reasons)

    def test_canary_refreezes_after_one_attempt(self) -> None:
        claims = self.claims()
        approval = ApprovalVerification(True, claims, ())
        controller = ReleaseController(ReleaseState.HOLD)
        armed = controller.arm(approval, ReleaseSignals(package_ready=True))
        started = controller.begin_upload()
        finished = controller.finish_upload(verified=True)
        self.assertEqual(armed.state, ReleaseState.ARMED)
        self.assertEqual(started.state, ReleaseState.UPLOADING)
        self.assertEqual(finished.state, ReleaseState.FROZEN)
        self.assertEqual(controller.upload_attempts, 1)


class ObservabilityTests(unittest.TestCase):
    def test_health_snapshot_reports_outcomes(self) -> None:
        ledger = EventLedger((
            PipelineEvent("e1", "r1", "one", "render", "render_complete", EventSeverity.INFO, duration_seconds=10),
            PipelineEvent("e2", "r1", "one", "package", "run_passed", EventSeverity.INFO, duration_seconds=2),
            PipelineEvent("e3", "r2", "two", "facts", "run_quarantined", EventSeverity.ERROR, reason="facts_failed", duration_seconds=3),
        ))
        snapshot = build_health_snapshot(ledger)
        self.assertEqual(snapshot.run_count, 2)
        self.assertEqual(snapshot.pass_rate, 50.0)
        self.assertEqual(snapshot.quarantine_rate, 50.0)
        self.assertEqual(snapshot.top_reasons[0], ("facts_failed", 1))

    def test_duplicate_event_ids_raise(self) -> None:
        ledger = EventLedger()
        event = PipelineEvent("same", "r1", "one", "render", "started", EventSeverity.INFO)
        ledger.append(event)
        with self.assertRaises(ValueError):
            ledger.append(event)
        self.assertEqual(ledger.duplicate_attempts, 1)


class IntegrationLabTests(unittest.TestCase):
    def happy_input(self) -> StructuralRunInput:
        return StructuralRunInput(
            slug="demo",
            manifest_sha256=MANIFEST,
            video_sha256=VIDEO,
            factual_mode=FactualMode.VERIFIED,
            beat_texts={"b1": "The system uses 10 units."},
            claims=(verified_claim(),),
            evidence_package=complete_evidence(),
            judge_verdicts=(verdict("technical-a"), verdict("editor-b")),
            shot_costs=(ShotCost("s1", "chart", 10, 1.0, cache_hit=True),),
            render_profile=RenderProfile.REVIEW,
            story_signals=ready_story(),
            publishing_enabled=False,
        )

    def test_structurally_ready_run_is_held_and_frozen(self) -> None:
        report = simulate_structural_run(self.happy_input())
        self.assertEqual(report.package.decision, PackageDecision.HOLD)
        self.assertEqual(report.package.readiness_score, 100.0)
        self.assertEqual(report.release_transition.state, ReleaseState.FROZEN)
        self.assertFalse(report.blockers)
        self.assertGreaterEqual(report.structural_score, 85.0)

    def test_missing_claims_quarantine_package(self) -> None:
        report = simulate_structural_run(replace(self.happy_input(), claims=()))
        self.assertEqual(report.package.decision, PackageDecision.QUARANTINE)
        self.assertTrue(any(item.startswith("facts:") or "facts" in item for item in report.blockers))
        self.assertLess(report.structural_score, 85.0)

    def test_stale_evidence_quarantines_package(self) -> None:
        package = complete_evidence()
        stale = replace(package, manifest_sha256="c" * 64)
        report = simulate_structural_run(replace(self.happy_input(), evidence_package=stale))
        self.assertEqual(report.package.decision, PackageDecision.QUARANTINE)
        self.assertTrue(any(item.startswith("evidence:") for item in report.blockers))

    def test_over_budget_render_quarantines_package(self) -> None:
        expensive = (ShotCost("s1", "simulation", 1000, 3.0, cache_hit=False),)
        report = simulate_structural_run(replace(self.happy_input(), shot_costs=expensive))
        self.assertEqual(report.package.decision, PackageDecision.QUARANTINE)
        self.assertTrue(any(item.startswith("render:") for item in report.blockers))


if __name__ == "__main__":
    unittest.main()
