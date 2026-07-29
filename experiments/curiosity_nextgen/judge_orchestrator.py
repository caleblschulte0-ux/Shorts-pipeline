"""Independent visual-judge assignment and review-round orchestration.

This module does not call any model or service.  It defines the structural
requirements for independent technical/editorial review, prevents same-family
judge duplication, and decides when a round is ready for consensus.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .judge_contract import ConsensusResult, JudgeDecision, JudgeVerdict, decide_consensus
from .judge_evidence import EvidenceValidation


class JudgeRole(str, Enum):
    TECHNICAL = "technical"
    EDITORIAL = "editorial"
    TIEBREAKER = "tiebreaker"


class RoundState(str, Enum):
    WAITING_FOR_EVIDENCE = "waiting_for_evidence"
    WAITING_FOR_JUDGES = "waiting_for_judges"
    WAITING_FOR_VERDICTS = "waiting_for_verdicts"
    SECOND_REVIEW = "second_review"
    COMPLETE = "complete"
    QUARANTINED = "quarantined"


@dataclass(frozen=True)
class JudgeWorker:
    judge_id: str
    role: JudgeRole
    provider_family: str
    model_family: str
    version: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.judge_id.strip() or not self.provider_family.strip() or not self.model_family.strip():
            raise ValueError("judge identifiers and families must be nonempty")


@dataclass(frozen=True)
class JudgeAssignment:
    role: JudgeRole
    judge_id: str
    provider_family: str
    model_family: str


@dataclass(frozen=True)
class JudgeRoundPlan:
    state: RoundState
    assignments: tuple[JudgeAssignment, ...]
    blockers: tuple[str, ...]
    required_verdict_count: int


@dataclass(frozen=True)
class JudgeRoundResult:
    state: RoundState
    consensus: ConsensusResult | None
    missing_judges: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class JudgeOrchestrationPolicy:
    require_distinct_provider_families: bool = True
    require_distinct_model_families: bool = True
    require_technical_and_editorial: bool = True
    allow_tiebreaker: bool = True
    maximum_assignments: int = 3


def _pick_distinct(
    workers: Iterable[JudgeWorker],
    selected: list[JudgeWorker],
    *,
    role: JudgeRole,
    policy: JudgeOrchestrationPolicy,
) -> JudgeWorker | None:
    candidates = sorted(
        (worker for worker in workers if worker.enabled and worker.role is role),
        key=lambda item: (item.provider_family, item.model_family, item.judge_id),
    )
    for worker in candidates:
        if policy.require_distinct_provider_families and any(
            item.provider_family == worker.provider_family for item in selected
        ):
            continue
        if policy.require_distinct_model_families and any(
            item.model_family == worker.model_family for item in selected
        ):
            continue
        return worker
    return None


def plan_judge_round(
    workers: Iterable[JudgeWorker],
    evidence: EvidenceValidation,
    *,
    policy: JudgeOrchestrationPolicy | None = None,
    needs_tiebreaker: bool = False,
) -> JudgeRoundPlan:
    policy = policy or JudgeOrchestrationPolicy()
    if not evidence.valid:
        return JudgeRoundPlan(
            state=RoundState.WAITING_FOR_EVIDENCE,
            assignments=(),
            blockers=tuple(f"evidence:{item}" for item in evidence.blockers),
            required_verdict_count=0,
        )

    worker_list = tuple(workers)
    selected: list[JudgeWorker] = []
    blockers: list[str] = []
    required_roles = [JudgeRole.TECHNICAL, JudgeRole.EDITORIAL] if policy.require_technical_and_editorial else [JudgeRole.EDITORIAL]
    if needs_tiebreaker and policy.allow_tiebreaker:
        required_roles.append(JudgeRole.TIEBREAKER)

    for role in required_roles[: policy.maximum_assignments]:
        worker = _pick_distinct(worker_list, selected, role=role, policy=policy)
        if worker is None:
            blockers.append(f"missing_independent_judge:{role.value}")
        else:
            selected.append(worker)

    assignments = tuple(
        JudgeAssignment(worker.role, worker.judge_id, worker.provider_family, worker.model_family)
        for worker in selected
    )
    state = RoundState.WAITING_FOR_JUDGES if blockers else RoundState.WAITING_FOR_VERDICTS
    return JudgeRoundPlan(state, assignments, tuple(sorted(blockers)), len(assignments))


def evaluate_judge_round(
    plan: JudgeRoundPlan,
    verdicts: Iterable[JudgeVerdict],
    *,
    expected_manifest_sha256: str,
) -> JudgeRoundResult:
    if plan.blockers:
        return JudgeRoundResult(RoundState.QUARANTINED, None, (), plan.blockers)

    verdict_map = {verdict.judge_id: verdict for verdict in verdicts}
    expected_ids = {assignment.judge_id for assignment in plan.assignments}
    missing = tuple(sorted(expected_ids - set(verdict_map)))
    unexpected = tuple(sorted(set(verdict_map) - expected_ids))
    if missing:
        reasons = ["missing_verdicts"]
        if unexpected:
            reasons.append("unexpected_verdicts:" + ",".join(unexpected))
        return JudgeRoundResult(RoundState.WAITING_FOR_VERDICTS, None, missing, tuple(reasons))

    selected_verdicts = [verdict_map[judge_id] for judge_id in sorted(expected_ids)]
    consensus = decide_consensus(selected_verdicts, expected_manifest_sha256=expected_manifest_sha256)
    if consensus.decision is JudgeDecision.SECOND_REVIEW:
        state = RoundState.SECOND_REVIEW
    elif consensus.decision is JudgeDecision.QUARANTINE:
        state = RoundState.QUARANTINED
    else:
        state = RoundState.COMPLETE
    return JudgeRoundResult(state, consensus, (), consensus.reasons)
