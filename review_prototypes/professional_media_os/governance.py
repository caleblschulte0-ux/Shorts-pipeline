"""Governance and authority controls for the isolated Professional Media OS prototype."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional, Sequence, Tuple

from .contracts import ContractError, ExperimentSpec, ExperimentState, Maturity


class AuthorityStage(str, Enum):
    RECORD_ONLY = "record_only"
    RETROSPECTIVE_BENCHMARK = "retrospective_benchmark"
    SHADOW_RECOMMENDATION = "shadow_recommendation"
    ROUGH_CUT_SELECTION = "rough_cut_selection"
    CANARY_RECOMMENDATION = "canary_recommendation"
    BOUNDED_PORTFOLIO = "bounded_portfolio"


_AUTHORITY_ORDER = {
    AuthorityStage.RECORD_ONLY: 0,
    AuthorityStage.RETROSPECTIVE_BENCHMARK: 1,
    AuthorityStage.SHADOW_RECOMMENDATION: 2,
    AuthorityStage.ROUGH_CUT_SELECTION: 3,
    AuthorityStage.CANARY_RECOMMENDATION: 4,
    AuthorityStage.BOUNDED_PORTFOLIO: 5,
}


@dataclass(frozen=True)
class LearningEligibility:
    eligible: bool
    reasons: Tuple[str, ...]
    mature_video_count: int
    minimum_video_count: int
    minimum_views_per_video: int
    metric_definition_consistent: bool


@dataclass(frozen=True)
class AuthorityEvidence:
    benchmark_cases: int
    false_rejection_rate: Optional[float]
    false_approval_rate: Optional[float]
    shadow_decisions: int
    completed_canaries: int
    rollback_tested: bool
    kill_switch_tested: bool
    lineage_complete: bool
    channel_identity_protected: bool
    production_files_modified_by_prototype: int
    publishing_enabled_by_prototype: bool

    def __post_init__(self) -> None:
        for name in (
            "benchmark_cases",
            "shadow_decisions",
            "completed_canaries",
            "production_files_modified_by_prototype",
        ):
            if getattr(self, name) < 0:
                raise ContractError(f"{name} must be non-negative")
        for name in ("false_rejection_rate", "false_approval_rate"):
            value = getattr(self, name)
            if value is not None and not 0.0 <= value <= 1.0:
                raise ContractError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class AuthorityDecision:
    current_stage: AuthorityStage
    requested_stage: AuthorityStage
    allowed: bool
    reasons: Tuple[str, ...]


@dataclass(frozen=True)
class RuleChangeProposal:
    proposal_id: str
    rule_key: str
    current_value: object
    proposed_value: object
    scope: Tuple[str, ...]
    exclusions: Tuple[str, ...]
    evidence_ids: Tuple[str, ...]
    maturity: Maturity
    reversible: bool
    feature_flag: str
    maximum_allocation_shift: float
    canary_count: int
    rollback_instruction: str

    def __post_init__(self) -> None:
        if not self.proposal_id or not self.rule_key or not self.feature_flag:
            raise ContractError("rule proposals require ids, rule keys, and feature flags")
        if not 0.0 <= self.maximum_allocation_shift <= 1.0:
            raise ContractError("maximum_allocation_shift must be between 0 and 1")
        if self.canary_count < 1:
            raise ContractError("rule proposals require at least one canary")
        if not self.rollback_instruction.strip():
            raise ContractError("rule proposals require an explicit rollback instruction")
        if self.maturity in (Maturity.ANECDOTE, Maturity.DEPRECATED):
            raise ContractError("anecdotal or deprecated evidence cannot propose automatic rules")
        if not self.evidence_ids:
            raise ContractError("rule proposals require evidence")
        if not self.reversible:
            raise ContractError("prototype rule changes must be reversible")


def assess_learning_eligibility(
    *,
    video_view_counts: Sequence[int],
    minimum_video_count: int,
    minimum_views_per_video: int,
    metric_definition_versions: Sequence[str],
) -> LearningEligibility:
    if minimum_video_count < 1 or minimum_views_per_video < 1:
        raise ContractError("learning thresholds must be positive")
    mature_count = sum(count >= minimum_views_per_video for count in video_view_counts)
    definition_consistent = len(set(metric_definition_versions)) <= 1
    reasons = []
    if mature_count < minimum_video_count:
        reasons.append(
            f"only {mature_count} videos meet the {minimum_views_per_video}-view floor; "
            f"{minimum_video_count} are required"
        )
    if not definition_consistent:
        reasons.append("metric definition versions are mixed")
    return LearningEligibility(
        eligible=not reasons,
        reasons=tuple(reasons),
        mature_video_count=mature_count,
        minimum_video_count=minimum_video_count,
        minimum_views_per_video=minimum_views_per_video,
        metric_definition_consistent=definition_consistent,
    )


def assess_authority_transition(
    current: AuthorityStage,
    requested: AuthorityStage,
    evidence: AuthorityEvidence,
) -> AuthorityDecision:
    reasons = []
    current_rank = _AUTHORITY_ORDER[current]
    requested_rank = _AUTHORITY_ORDER[requested]

    if requested_rank > current_rank + 1:
        reasons.append("authority stages may advance only one step at a time")
    if requested_rank < current_rank:
        return AuthorityDecision(current, requested, True, ("rollback is always allowed",))

    if evidence.production_files_modified_by_prototype != 0:
        reasons.append("prototype has modified production files")
    if evidence.publishing_enabled_by_prototype:
        reasons.append("prototype has enabled publishing")
    if not evidence.lineage_complete:
        reasons.append("decision lineage is incomplete")
    if not evidence.channel_identity_protected:
        reasons.append("channel identity boundaries are not proven")

    if requested_rank >= _AUTHORITY_ORDER[AuthorityStage.RETROSPECTIVE_BENCHMARK]:
        if evidence.benchmark_cases < 20:
            reasons.append("at least 20 representative benchmark cases are required")

    if requested_rank >= _AUTHORITY_ORDER[AuthorityStage.SHADOW_RECOMMENDATION]:
        if evidence.false_rejection_rate is None or evidence.false_approval_rate is None:
            reasons.append("benchmark error rates are unknown")
        else:
            if evidence.false_rejection_rate > 0.20:
                reasons.append("false rejection rate exceeds 20%")
            if evidence.false_approval_rate > 0.25:
                reasons.append("false approval rate exceeds 25%")

    if requested_rank >= _AUTHORITY_ORDER[AuthorityStage.ROUGH_CUT_SELECTION]:
        if evidence.shadow_decisions < 30:
            reasons.append("at least 30 shadow decisions are required")
        if not evidence.kill_switch_tested:
            reasons.append("kill switch has not been tested")

    if requested_rank >= _AUTHORITY_ORDER[AuthorityStage.CANARY_RECOMMENDATION]:
        if not evidence.rollback_tested:
            reasons.append("rollback has not been tested")

    if requested_rank >= _AUTHORITY_ORDER[AuthorityStage.BOUNDED_PORTFOLIO]:
        if evidence.completed_canaries < 10:
            reasons.append("at least 10 completed canaries are required")

    return AuthorityDecision(
        current_stage=current,
        requested_stage=requested,
        allowed=not reasons,
        reasons=tuple(reasons),
    )


def validate_experiment_for_canary(spec: ExperimentSpec) -> Tuple[str, ...]:
    reasons = []
    if spec.state not in (ExperimentState.SHADOW, ExperimentState.CANARY):
        reasons.append("experiment must be in shadow or canary state")
    if spec.maximum_allocation > 0.20:
        reasons.append("canary allocation exceeds the 20% prototype cap")
    if spec.minimum_eligible_videos < 3:
        reasons.append("at least three eligible videos are required")
    if not spec.guardrail_metrics:
        reasons.append("at least one guardrail metric is required")
    if not spec.stop_conditions:
        reasons.append("explicit stop conditions are required")
    return tuple(reasons)
