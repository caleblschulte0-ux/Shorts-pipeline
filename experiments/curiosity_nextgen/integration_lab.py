"""End-to-end structural simulation for the dormant next-generation lab.

This module composes the prototype contracts without importing the active
renderer, producer, scheduler, or publisher.  It lets reviewers exercise the
control plane from factual coverage through release freeze decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .catalog_triage import StorySignals, StoryTriage, TriageAction, triage_story
from .claim_registry import Claim, ClaimCoverageResult, FactualMode, evaluate_claim_coverage
from .freeze_controller import ReleaseController, ReleaseSignals, ReleaseState, ReleaseTransition
from .judge_contract import ConsensusResult, JudgeDecision, JudgeVerdict, decide_consensus
from .judge_evidence import JudgeEvidencePackage, EvidenceValidation, validate_evidence_package
from .package_readiness import (
    GateResult,
    GateState,
    PackageDecision,
    PackageReadiness,
    evaluate_package,
)
from .render_budget import BudgetDecision, RenderEstimate, RenderProfile, ShotCost, estimate_render
from .semantic_claims import (
    SemanticCoverageAudit,
    audit_semantic_coverage,
    extract_semantic_signals,
)


@dataclass(frozen=True)
class StructuralRunInput:
    slug: str
    manifest_sha256: str
    video_sha256: str
    factual_mode: FactualMode | None
    beat_texts: Mapping[str, str]
    claims: tuple[Claim, ...]
    evidence_package: JudgeEvidencePackage
    judge_verdicts: tuple[JudgeVerdict, ...]
    shot_costs: tuple[ShotCost, ...]
    render_profile: RenderProfile
    story_signals: StorySignals
    technical_passed: bool = True
    fallbacks_passed: bool = True
    channel_guard_passed: bool = True
    publishing_enabled: bool = False
    peak_rss_mb: int | None = None


@dataclass(frozen=True)
class StructuralRunReport:
    slug: str
    structural_score: float
    facts: ClaimCoverageResult
    semantic_facts: SemanticCoverageAudit
    evidence: EvidenceValidation
    judges: ConsensusResult
    render: RenderEstimate
    triage: StoryTriage
    package: PackageReadiness
    release_transition: ReleaseTransition
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    gate_states: tuple[tuple[str, str], ...]



def _gate_state(passed: bool) -> GateState:
    return GateState.PASS if passed else GateState.FAIL


def _performance_gate(render: RenderEstimate) -> GateState:
    if render.decision is BudgetDecision.PASS:
        return GateState.PASS
    if render.decision is BudgetDecision.WARN:
        return GateState.WARN
    return GateState.FAIL


def _judge_gate(evidence: EvidenceValidation, judges: ConsensusResult) -> GateState:
    if not evidence.valid:
        return GateState.FAIL
    if judges.decision is JudgeDecision.PASS:
        return GateState.PASS
    if judges.decision is JudgeDecision.SECOND_REVIEW:
        return GateState.WARN
    return GateState.FAIL


def _catalog_gate(triage: StoryTriage) -> GateState:
    if triage.action is TriageAction.REVIEW_CANDIDATE:
        return GateState.PASS
    if triage.action is TriageAction.RENDER_DRAFT:
        return GateState.WARN
    return GateState.FAIL


def _score_component(value: bool | float) -> float:
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    return max(0.0, min(100.0, float(value)))


def simulate_structural_run(run: StructuralRunInput) -> StructuralRunReport:
    facts = evaluate_claim_coverage(run.beat_texts, run.claims, factual_mode=run.factual_mode)
    semantic_signals = extract_semantic_signals(run.beat_texts)
    semantic_facts = audit_semantic_coverage(semantic_signals, run.claims)
    evidence = validate_evidence_package(
        run.evidence_package,
        expected_manifest_sha256=run.manifest_sha256,
        expected_video_sha256=run.video_sha256,
    )
    judges = decide_consensus(
        run.judge_verdicts,
        expected_manifest_sha256=run.manifest_sha256,
    )
    render = estimate_render(
        run.shot_costs,
        profile=run.render_profile,
        peak_rss_mb=run.peak_rss_mb,
    )
    triage = triage_story(run.story_signals)

    facts_passed = facts.valid and semantic_facts.valid
    judge_state = _judge_gate(evidence, judges)
    catalog_state = _catalog_gate(triage)
    gates = (
        GateResult("manifest", GateState.PASS, manifest_sha256=run.manifest_sha256),
        GateResult("facts", _gate_state(facts_passed), manifest_sha256=run.manifest_sha256),
        GateResult("visual_judge", judge_state, manifest_sha256=run.manifest_sha256, score=judges.score),
        GateResult("fallbacks", _gate_state(run.fallbacks_passed), manifest_sha256=run.manifest_sha256),
        GateResult("performance", _performance_gate(render), manifest_sha256=run.manifest_sha256),
        GateResult("technical", _gate_state(run.technical_passed), manifest_sha256=run.manifest_sha256),
        GateResult("catalog", catalog_state, manifest_sha256=run.manifest_sha256, score=triage.readiness_score),
        GateResult("channel_guard", _gate_state(run.channel_guard_passed), manifest_sha256=run.manifest_sha256),
    )
    package = evaluate_package(
        gates,
        expected_manifest_sha256=run.manifest_sha256,
        publishing_enabled=run.publishing_enabled,
    )

    controller = ReleaseController(ReleaseState.FROZEN)
    release_signals = ReleaseSignals(
        package_ready=(not package.blockers and package.readiness_score == 100.0),
        wrong_channel=not run.channel_guard_passed,
        facts_failed=not facts_passed,
        visual_failed=judge_state is GateState.FAIL,
        verdict_invalid=judges.decision is JudgeDecision.QUARANTINE,
        render_over_budget=render.decision is BudgetDecision.REJECT,
    )
    release_transition = controller.evaluate(release_signals)

    component_weights = {
        "facts": 20.0,
        "evidence": 12.0,
        "judges": 13.0,
        "render": 12.0,
        "catalog": 15.0,
        "package": 18.0,
        "release_safety": 10.0,
    }
    judge_score = 100.0 if judges.decision is JudgeDecision.PASS else 65.0 if judges.decision is JudgeDecision.SECOND_REVIEW else 0.0
    render_score = 100.0 if render.decision is BudgetDecision.PASS else 70.0 if render.decision is BudgetDecision.WARN else 0.0
    release_safety_score = 100.0 if release_transition.state in {ReleaseState.FROZEN, ReleaseState.HOLD} else 80.0
    components = {
        "facts": _score_component(facts_passed),
        "evidence": evidence.completeness_score if evidence.valid else min(60.0, evidence.completeness_score),
        "judges": judge_score,
        "render": render_score,
        "catalog": triage.readiness_score,
        "package": package.readiness_score,
        "release_safety": release_safety_score,
    }
    structural_score = sum(component_weights[name] * components[name] for name in component_weights) / sum(component_weights.values())

    blockers: set[str] = set(package.blockers)
    blockers.update(f"facts:{item}" for item in facts.uncovered_beats)
    blockers.update(f"semantic:{item}" for item in semantic_facts.uncovered_signals)
    blockers.update(f"evidence:{item}" for item in evidence.blockers)
    blockers.update(f"catalog:{item}" for item in triage.hard_blockers)
    if judges.decision in {JudgeDecision.REJECT, JudgeDecision.QUARANTINE}:
        blockers.update(f"judge:{item}" for item in judges.reasons or (judges.decision.value,))
    if render.decision is BudgetDecision.REJECT:
        blockers.update(f"render:{item}" for item in render.reasons)

    warnings: set[str] = set(package.warnings)
    warnings.update(f"facts:{item}" for item in facts.warnings)
    warnings.update(f"semantic:{item}" for item in semantic_facts.warnings)
    warnings.update(f"evidence:{item}" for item in evidence.warnings)
    warnings.update(f"catalog:{item}" for item in triage.soft_gaps)
    if render.decision is BudgetDecision.WARN:
        warnings.update(f"render:{item}" for item in render.reasons)
    if judges.decision is JudgeDecision.SECOND_REVIEW:
        warnings.add("judge:second_review_required")

    return StructuralRunReport(
        slug=run.slug,
        structural_score=round(structural_score, 1),
        facts=facts,
        semantic_facts=semantic_facts,
        evidence=evidence,
        judges=judges,
        render=render,
        triage=triage,
        package=package,
        release_transition=release_transition,
        blockers=tuple(sorted(blockers)),
        warnings=tuple(sorted(warnings)),
        gate_states=tuple((gate.gate, gate.state.value) for gate in gates),
    )
