from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .production_stage_graph import StageName


class StageVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    HOLD = "hold"
    ERROR = "error"


class NextAction(str, Enum):
    ADVANCE = "advance"
    RETRY_STAGE = "retry_stage"
    WAIT_FOR_EVIDENCE = "wait_for_evidence"
    RESEARCH_MORE = "research_more"
    REAUTHOR = "reauthor"
    REPAIR = "repair"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class StageOutcome:
    story_id: str
    stage: StageName
    verdict: StageVerdict
    severity: float
    confidence: float
    defect_categories: tuple[str, ...] = ()
    evidence_complete: bool = True
    artifact_hash_bound: bool = True
    retryable: bool = False
    repairable: bool = False
    factual_gap: bool = False
    policy_violation: bool = False
    cost_delta: float = 0.0

    def __post_init__(self) -> None:
        if not self.story_id.strip():
            raise ValueError("story_id is required")
        for name in ("severity", "confidence"):
            value = getattr(self, name)
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")
        if self.cost_delta < 0:
            raise ValueError("cost_delta cannot be negative")
        if len(self.defect_categories) != len(set(self.defect_categories)):
            raise ValueError("duplicate defect category")


@dataclass(frozen=True)
class DecisionPolicy:
    minimum_pass_confidence: float = 7.0
    maximum_retries_per_stage: int = 2
    maximum_repairs_per_story: int = 2
    maximum_reauthors_per_story: int = 1
    quarantine_severity: float = 9.0
    require_hash_binding_after_render: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.minimum_pass_confidence <= 10:
            raise ValueError("minimum_pass_confidence must be between 0 and 10")
        if self.maximum_retries_per_stage < 0 or self.maximum_repairs_per_story < 0 or self.maximum_reauthors_per_story < 0:
            raise ValueError("decision limits cannot be negative")
        if not 0 <= self.quarantine_severity <= 10:
            raise ValueError("quarantine_severity must be between 0 and 10")


@dataclass(frozen=True)
class StoryDecisionState:
    stage_attempts: int = 0
    repair_count: int = 0
    reauthor_count: int = 0


@dataclass(frozen=True)
class AutonomousDecision:
    action: NextAction
    reason: str
    rewind_to: StageName | None = None
    consumes_retry: bool = False
    consumes_repair: bool = False
    consumes_reauthor: bool = False


_RENDER_OR_LATER = {
    StageName.DRAFT_RENDER,
    StageName.TECHNICAL_REVIEW,
    StageName.EDITORIAL_REVIEW,
    StageName.FACT_REVIEW,
    StageName.GATE_AGGREGATION,
    StageName.REPAIR,
    StageName.FINAL_RENDER,
    StageName.PACKAGE,
    StageName.APPROVAL,
    StageName.PUBLISH,
}


def decide_next_action(
    outcome: StageOutcome,
    state: StoryDecisionState,
    policy: DecisionPolicy = DecisionPolicy(),
) -> AutonomousDecision:
    if outcome.policy_violation:
        return AutonomousDecision(NextAction.QUARANTINE, "policy_violation")
    if outcome.severity >= policy.quarantine_severity and not outcome.repairable:
        return AutonomousDecision(NextAction.QUARANTINE, "unrepairable_high_severity_failure")
    if not outcome.evidence_complete:
        return AutonomousDecision(NextAction.WAIT_FOR_EVIDENCE, "evidence_incomplete")
    if policy.require_hash_binding_after_render and outcome.stage in _RENDER_OR_LATER and not outcome.artifact_hash_bound:
        return AutonomousDecision(NextAction.WAIT_FOR_EVIDENCE, "artifact_not_hash_bound")

    if outcome.verdict is StageVerdict.PASS:
        if outcome.confidence < policy.minimum_pass_confidence:
            return AutonomousDecision(NextAction.WAIT_FOR_EVIDENCE, "pass_confidence_below_floor")
        return AutonomousDecision(NextAction.ADVANCE, "stage_passed")

    if outcome.factual_gap:
        return AutonomousDecision(
            NextAction.RESEARCH_MORE,
            "factual_gap_requires_research",
            rewind_to=StageName.RESEARCH,
        )

    if outcome.verdict is StageVerdict.ERROR and outcome.retryable:
        if state.stage_attempts < policy.maximum_retries_per_stage:
            return AutonomousDecision(NextAction.RETRY_STAGE, "retryable_stage_error", consumes_retry=True)

    if outcome.repairable and state.repair_count < policy.maximum_repairs_per_story:
        return AutonomousDecision(
            NextAction.REPAIR,
            "repairable_quality_failure",
            rewind_to=StageName.REPAIR,
            consumes_repair=True,
        )

    authoring_stages = {StageName.SCRIPT, StageName.STORYBOARD, StageName.MEDIA}
    if outcome.stage in authoring_stages and state.reauthor_count < policy.maximum_reauthors_per_story:
        return AutonomousDecision(
            NextAction.REAUTHOR,
            "authoring_contract_failed",
            rewind_to=StageName.SCRIPT,
            consumes_reauthor=True,
        )

    if outcome.verdict is StageVerdict.HOLD:
        return AutonomousDecision(NextAction.WAIT_FOR_EVIDENCE, "stage_held")

    return AutonomousDecision(NextAction.QUARANTINE, "bounded_recovery_exhausted")
