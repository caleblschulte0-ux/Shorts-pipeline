"""Review-only multi-judge adjudication prototype.

NOT WIRED INTO THE PIPELINE.

This module demonstrates how objective evidence, a primary vision judge, and an
adversarial vision judge can remain independent. It deliberately prevents code
metrics from declaring creative success and prevents missing vision evidence from
failing open.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class Decision(str, Enum):
    REJECT = "reject"
    HOLD = "hold"
    ELIGIBLE = "eligible"
    SHIP = "ship"


@dataclass(frozen=True)
class TemporalEvidence:
    effective_fps: float
    duplicate_ratio: float
    longest_duplicate_run: int
    longest_unmarked_static_seconds: float


@dataclass(frozen=True)
class ObjectiveEvidence:
    render_complete: bool
    audio_present: bool
    text_overflow: bool
    clipping: bool
    safe_area_violations: int
    temporal: TemporalEvidence
    artifact_hashes_present: bool
    notes: tuple[str, ...] = ()

    def hard_failures(
        self,
        *,
        minimum_effective_fps: float = 24.0,
        maximum_duplicate_ratio: float = 0.15,
        maximum_duplicate_run: int = 4,
        maximum_static_seconds: float = 0.40,
    ) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.render_complete:
            failures.append("incomplete_render")
        if not self.audio_present:
            failures.append("missing_audio")
        if self.text_overflow:
            failures.append("text_overflow")
        if self.clipping:
            failures.append("visual_clipping")
        if self.safe_area_violations:
            failures.append("safe_area_violation")
        if not self.artifact_hashes_present:
            failures.append("missing_artifact_hashes")
        if self.temporal.effective_fps < minimum_effective_fps:
            failures.append("effective_fps")
        if self.temporal.duplicate_ratio > maximum_duplicate_ratio:
            failures.append("duplicate_ratio")
        if self.temporal.longest_duplicate_run > maximum_duplicate_run:
            failures.append("duplicate_run")
        if self.temporal.longest_unmarked_static_seconds > maximum_static_seconds:
            failures.append("unmarked_static_hold")
        return tuple(failures)


@dataclass(frozen=True)
class SceneDiagnosis:
    scene_id: str
    scene_index: int
    start_seconds: float
    end_seconds: float
    failure_class: str
    visible_evidence: str
    root_cause: str
    repair_goal: str

    def is_structured(self) -> bool:
        return bool(
            self.scene_id
            and self.scene_index >= 0
            and self.end_seconds > self.start_seconds
            and self.failure_class
            and self.visible_evidence
            and self.repair_goal
        )


@dataclass(frozen=True)
class VisionVerdict:
    score: float
    dimensions: Mapping[str, float]
    hard_failure_labels: tuple[str, ...]
    evidence_timestamps: tuple[float, ...]
    weakest_scene: SceneDiagnosis | None
    watched_video: bool
    judge_version: str
    explanation: str = ""

    @property
    def lowest_dimension(self) -> float:
        return min(self.dimensions.values(), default=0.0)


@dataclass(frozen=True)
class AdversarialVerdict:
    objection_labels: tuple[str, ...]
    confidence: float
    watched_video: bool
    judge_version: str
    explanation: str = ""

    @property
    def credible_objection(self) -> bool:
        return bool(self.objection_labels) and self.confidence >= 0.70


@dataclass(frozen=True)
class CombinedVerdict:
    decision: Decision
    score: float | None
    lowest_dimension: float | None
    reasons: tuple[str, ...]
    objective_failures: tuple[str, ...]
    primary: VisionVerdict | None
    adversarial: AdversarialVerdict | None
    disagreements: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhasePolicy:
    score_floor: float
    lowest_dimension_floor: float
    require_structured_diagnosis_on_block: bool = True
    maximum_adversarial_confidence: float = 0.69
    minimum_effective_fps: float = 24.0
    maximum_duplicate_ratio: float = 0.15
    maximum_duplicate_run: int = 4
    maximum_static_seconds: float = 0.40


PHASE_POLICIES: Mapping[int, PhasePolicy] = {
    0: PhasePolicy(score_floor=0.0, lowest_dimension_floor=0.0),
    1: PhasePolicy(score_floor=70.0, lowest_dimension_floor=6.0),
    2: PhasePolicy(score_floor=80.0, lowest_dimension_floor=7.0),
    3: PhasePolicy(score_floor=90.0, lowest_dimension_floor=8.0),
}


def adjudicate(
    objective: ObjectiveEvidence,
    primary: VisionVerdict | None,
    adversarial: AdversarialVerdict | None,
    *,
    phase: int,
) -> CombinedVerdict:
    """Combine independent evidence without averaging away hard failures."""

    policy = PHASE_POLICIES[phase]
    objective_failures = objective.hard_failures(
        minimum_effective_fps=policy.minimum_effective_fps,
        maximum_duplicate_ratio=policy.maximum_duplicate_ratio,
        maximum_duplicate_run=policy.maximum_duplicate_run,
        maximum_static_seconds=policy.maximum_static_seconds,
    )
    reasons: list[str] = []
    disagreements: list[str] = []

    if objective_failures:
        return CombinedVerdict(
            decision=Decision.REJECT,
            score=primary.score if primary else None,
            lowest_dimension=primary.lowest_dimension if primary else None,
            reasons=("objective gate rejected candidate",),
            objective_failures=objective_failures,
            primary=primary,
            adversarial=adversarial,
        )

    if primary is None or not primary.watched_video:
        return CombinedVerdict(
            decision=Decision.HOLD,
            score=None,
            lowest_dimension=None,
            reasons=("missing primary vision evidence",),
            objective_failures=(),
            primary=primary,
            adversarial=adversarial,
        )

    if adversarial is None or not adversarial.watched_video:
        return CombinedVerdict(
            decision=Decision.HOLD,
            score=primary.score,
            lowest_dimension=primary.lowest_dimension,
            reasons=("missing adversarial vision evidence",),
            objective_failures=(),
            primary=primary,
            adversarial=adversarial,
        )

    if primary.hard_failure_labels:
        reasons.append(
            "primary judge reported hard failures: "
            + ", ".join(primary.hard_failure_labels)
        )

    if primary.score < policy.score_floor:
        reasons.append(
            f"score {primary.score:.1f} is below phase floor {policy.score_floor:.1f}"
        )

    if primary.lowest_dimension < policy.lowest_dimension_floor:
        reasons.append(
            "lowest dimension "
            f"{primary.lowest_dimension:.1f} is below floor "
            f"{policy.lowest_dimension_floor:.1f}"
        )

    if adversarial.credible_objection:
        reasons.append(
            "credible adversarial objection: "
            + ", ".join(adversarial.objection_labels)
        )
        if primary.score >= policy.score_floor:
            disagreements.append(
                "primary score passes while adversarial judge reports rubric gaming"
            )

    blocked = bool(reasons)
    if blocked and policy.require_structured_diagnosis_on_block:
        diagnosis = primary.weakest_scene
        if diagnosis is None or not diagnosis.is_structured():
            reasons.append("blocked verdict lacks structured weakest-scene diagnosis")

    if reasons:
        return CombinedVerdict(
            decision=Decision.HOLD,
            score=primary.score,
            lowest_dimension=primary.lowest_dimension,
            reasons=tuple(reasons),
            objective_failures=(),
            primary=primary,
            adversarial=adversarial,
            disagreements=tuple(disagreements),
        )

    return CombinedVerdict(
        decision=Decision.SHIP,
        score=primary.score,
        lowest_dimension=primary.lowest_dimension,
        reasons=("all independent gates passed",),
        objective_failures=(),
        primary=primary,
        adversarial=adversarial,
    )


def compare_combined(
    incumbent: CombinedVerdict,
    challenger: CombinedVerdict,
) -> CombinedVerdict:
    """Choose the stronger complete verdict using an explicit decision order.

    This function compares verdicts only. A transaction store must separately
    promote the complete artifact state belonging to the returned verdict.
    """

    decision_rank = {
        Decision.REJECT: 0,
        Decision.HOLD: 1,
        Decision.ELIGIBLE: 2,
        Decision.SHIP: 3,
    }

    def rank(verdict: CombinedVerdict) -> tuple[float, float, float, float]:
        return (
            float(decision_rank[verdict.decision]),
            1.0 if not verdict.objective_failures else 0.0,
            verdict.score if verdict.score is not None else -1.0,
            verdict.lowest_dimension
            if verdict.lowest_dimension is not None
            else -1.0,
        )

    return challenger if rank(challenger) > rank(incumbent) else incumbent


def disagreement_summary(verdicts: Sequence[CombinedVerdict]) -> Mapping[str, int]:
    counts: dict[str, int] = {}
    for verdict in verdicts:
        for disagreement in verdict.disagreements:
            counts[disagreement] = counts.get(disagreement, 0) + 1
    return counts
