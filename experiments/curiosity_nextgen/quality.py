"""Deterministic quality-score contracts for dormant review experiments."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class QualityDimension(str, Enum):
    PREMISE = "premise"
    HOOK = "hook"
    VISUAL_RELEVANCE = "visual_relevance"
    VISUAL_VARIETY = "visual_variety"
    FACTUAL_CONFIDENCE = "factual_confidence"
    PACING = "pacing"
    PERSONALITY = "personality"
    PAYOFF = "payoff"
    ORIGINALITY = "originality"
    TECHNICAL = "technical"


DEFAULT_WEIGHTS: Mapping[QualityDimension, float] = {
    QualityDimension.PREMISE: 1.2,
    QualityDimension.HOOK: 1.4,
    QualityDimension.VISUAL_RELEVANCE: 1.4,
    QualityDimension.VISUAL_VARIETY: 0.8,
    QualityDimension.FACTUAL_CONFIDENCE: 1.5,
    QualityDimension.PACING: 1.0,
    QualityDimension.PERSONALITY: 1.0,
    QualityDimension.PAYOFF: 1.1,
    QualityDimension.ORIGINALITY: 0.8,
    QualityDimension.TECHNICAL: 1.3,
}


class QualityDecision(str, Enum):
    PASS = "pass"
    BORDERLINE = "borderline"
    REJECT = "reject"


@dataclass(frozen=True)
class QualityObservation:
    dimension: QualityDimension
    score: float
    notes: tuple[str, ...] = ()
    hard_failure: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 10:
            raise ValueError("score must be between 0 and 10")


@dataclass(frozen=True)
class QualityPolicy:
    pass_score: float = 7.5
    borderline_score: float = 6.5
    hard_floor: float = 5.0
    mandatory_dimensions: frozenset[QualityDimension] = frozenset({
        QualityDimension.HOOK,
        QualityDimension.VISUAL_RELEVANCE,
        QualityDimension.FACTUAL_CONFIDENCE,
        QualityDimension.TECHNICAL,
    })
    weights: Mapping[QualityDimension, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))


@dataclass(frozen=True)
class QualityResult:
    decision: QualityDecision
    overall_score: float
    dimension_scores: Mapping[str, float]
    reasons: tuple[str, ...]
    required_repairs: tuple[str, ...]


def evaluate_quality(observations: Iterable[QualityObservation],
                     *, policy: QualityPolicy | None = None) -> QualityResult:
    policy = policy or QualityPolicy()
    by_dimension: dict[QualityDimension, QualityObservation] = {}
    for observation in observations:
        if observation.dimension in by_dimension:
            raise ValueError(f"duplicate score for {observation.dimension.value}")
        by_dimension[observation.dimension] = observation

    reasons: list[str] = []
    repairs: list[str] = []
    missing = sorted(dim.value for dim in policy.mandatory_dimensions if dim not in by_dimension)
    hard_reject = bool(missing)
    if missing:
        reasons.append("missing mandatory dimensions: " + ", ".join(missing))

    numerator = 0.0
    denominator = 0.0
    for dimension, observation in by_dimension.items():
        weight = float(policy.weights.get(dimension, 1.0))
        numerator += observation.score * weight
        denominator += weight
        if observation.hard_failure:
            hard_reject = True
            reasons.append(f"{dimension.value}: hard failure")
        if dimension in policy.mandatory_dimensions and observation.score < policy.hard_floor:
            hard_reject = True
            reasons.append(f"{dimension.value}: below hard floor")
        if observation.score < policy.pass_score:
            repairs.append(f"raise {dimension.value} from {observation.score:.1f} to {policy.pass_score:.1f}")
        reasons.extend(f"{dimension.value}: {note}" for note in observation.notes)

    overall = numerator / denominator if denominator else 0.0
    if hard_reject or overall < policy.borderline_score:
        decision = QualityDecision.REJECT
    elif overall < policy.pass_score:
        decision = QualityDecision.BORDERLINE
    else:
        decision = QualityDecision.PASS

    return QualityResult(
        decision=decision,
        overall_score=round(overall, 3),
        dimension_scores={dim.value: obs.score for dim, obs in sorted(by_dimension.items(), key=lambda item: item[0].value)},
        reasons=tuple(reasons),
        required_repairs=tuple(repairs),
    )
