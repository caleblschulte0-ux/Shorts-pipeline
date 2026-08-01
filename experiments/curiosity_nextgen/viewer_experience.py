from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class ExperienceArea(str, Enum):
    HOOK = "hook"
    CURIOSITY = "curiosity"
    NARRATION = "narration"
    VISUAL_GRAMMAR = "visual_grammar"
    CHOREOGRAPHY = "choreography"
    AUDIO = "audio"
    PERSONALITY = "personality"
    PAYOFF = "payoff"
    PACKAGING = "packaging"
    FACTUAL = "factual"
    TECHNICAL = "technical"


DEFAULT_WEIGHTS: Mapping[ExperienceArea, float] = {
    ExperienceArea.HOOK: 1.4,
    ExperienceArea.CURIOSITY: 1.3,
    ExperienceArea.NARRATION: 1.0,
    ExperienceArea.VISUAL_GRAMMAR: 1.2,
    ExperienceArea.CHOREOGRAPHY: 0.9,
    ExperienceArea.AUDIO: 0.8,
    ExperienceArea.PERSONALITY: 1.1,
    ExperienceArea.PAYOFF: 1.3,
    ExperienceArea.PACKAGING: 0.9,
    ExperienceArea.FACTUAL: 1.4,
    ExperienceArea.TECHNICAL: 1.2,
}


@dataclass(frozen=True)
class ExperienceObservation:
    area: ExperienceArea
    score: float
    defects: tuple[str, ...] = ()
    hard_failure: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 10:
            raise ValueError("score must be between 0 and 10")


@dataclass(frozen=True)
class ExperiencePolicy:
    pass_score: float = 7.5
    hard_floor: float = 5.5
    mandatory_areas: frozenset[ExperienceArea] = frozenset({
        ExperienceArea.HOOK,
        ExperienceArea.CURIOSITY,
        ExperienceArea.VISUAL_GRAMMAR,
        ExperienceArea.PAYOFF,
        ExperienceArea.FACTUAL,
        ExperienceArea.TECHNICAL,
    })
    weights: Mapping[ExperienceArea, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.weights is None:
            object.__setattr__(self, "weights", dict(DEFAULT_WEIGHTS))


@dataclass(frozen=True)
class ExperienceRepair:
    area: ExperienceArea
    priority: float
    target_score: float
    defects: tuple[str, ...]


@dataclass(frozen=True)
class ExperienceResult:
    decision: str
    overall_score: float
    area_scores: dict[str, float]
    blockers: tuple[str, ...]
    prioritized_repairs: tuple[ExperienceRepair, ...]


def evaluate_viewer_experience(observations: Iterable[ExperienceObservation], *, policy: ExperiencePolicy | None = None) -> ExperienceResult:
    policy = policy or ExperiencePolicy()
    items = tuple(observations)
    if len({item.area for item in items}) != len(items):
        raise ValueError("duplicate experience area")
    by_area = {item.area: item for item in items}
    blockers: list[str] = []
    missing = sorted(area.value for area in policy.mandatory_areas if area not in by_area)
    if missing:
        blockers.append("missing_areas:" + ",".join(missing))

    numerator = 0.0
    denominator = 0.0
    repairs: list[ExperienceRepair] = []
    for item in items:
        weight = float(policy.weights.get(item.area, 1.0))
        numerator += item.score * weight
        denominator += weight
        if item.hard_failure:
            blockers.append(f"hard_failure:{item.area.value}")
        if item.area in policy.mandatory_areas and item.score < policy.hard_floor:
            blockers.append(f"below_floor:{item.area.value}")
        if item.score < policy.pass_score:
            gap = policy.pass_score - item.score
            repairs.append(ExperienceRepair(item.area, round(gap * weight, 3), policy.pass_score, item.defects))

    overall = numerator / denominator if denominator else 0.0
    if blockers or overall < 6.5:
        decision = "reject"
    elif overall < policy.pass_score:
        decision = "revise"
    else:
        decision = "pass"

    repairs.sort(key=lambda item: (-item.priority, item.area.value))
    return ExperienceResult(
        decision,
        round(overall, 3),
        {area.value: observation.score for area, observation in sorted(by_area.items(), key=lambda item: item[0].value)},
        tuple(sorted(set(blockers))),
        tuple(repairs),
    )
