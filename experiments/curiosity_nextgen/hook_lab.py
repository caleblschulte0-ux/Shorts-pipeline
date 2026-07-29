from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class HookDecision(str, Enum):
    STRONG = "strong"
    REVISE = "revise"
    REJECT = "reject"


@dataclass(frozen=True)
class HookCandidate:
    hook_id: str
    text: str
    duration_seconds: float
    first_visual_seconds: float
    clarity: float
    curiosity_gap: float
    stakes: float
    specificity: float
    surprise: float
    visualizability: float
    payoff_promise: float
    generic_phrase_count: int = 0
    opens_with_explanation: bool = False

    def __post_init__(self) -> None:
        if not self.hook_id.strip():
            raise ValueError("hook_id is required")
        if not self.text.strip():
            raise ValueError("hook text is required")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if self.first_visual_seconds < 0:
            raise ValueError("first_visual_seconds cannot be negative")
        for name in (
            "clarity",
            "curiosity_gap",
            "stakes",
            "specificity",
            "surprise",
            "visualizability",
            "payoff_promise",
        ):
            value = float(getattr(self, name))
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")
        if self.generic_phrase_count < 0:
            raise ValueError("generic_phrase_count cannot be negative")


@dataclass(frozen=True)
class HookPolicy:
    pass_score: float = 7.5
    revise_score: float = 6.25
    max_duration_seconds: float = 9.0
    max_first_visual_seconds: float = 1.0
    minimum_specificity: float = 6.5
    minimum_visualizability: float = 6.5
    minimum_payoff_promise: float = 6.5


@dataclass(frozen=True)
class HookResult:
    hook_id: str
    decision: HookDecision
    score: float
    strengths: tuple[str, ...]
    defects: tuple[str, ...]
    repair_prompts: tuple[str, ...]


_WEIGHTS = {
    "clarity": 1.15,
    "curiosity_gap": 1.4,
    "stakes": 1.0,
    "specificity": 1.3,
    "surprise": 1.1,
    "visualizability": 1.35,
    "payoff_promise": 1.35,
}


def evaluate_hook(candidate: HookCandidate, *, policy: HookPolicy | None = None) -> HookResult:
    policy = policy or HookPolicy()
    weighted = 0.0
    total_weight = 0.0
    strengths: list[str] = []
    defects: list[str] = []
    repairs: list[str] = []

    for field_name, weight in _WEIGHTS.items():
        value = float(getattr(candidate, field_name))
        weighted += value * weight
        total_weight += weight
        if value >= 8.0:
            strengths.append(field_name)

    score = weighted / total_weight

    if candidate.duration_seconds > policy.max_duration_seconds:
        over = candidate.duration_seconds - policy.max_duration_seconds
        score -= min(1.5, over * 0.15)
        defects.append("hook_too_long")
        repairs.append("compress the hook so the central question lands before the setup expands")
    if candidate.first_visual_seconds > policy.max_first_visual_seconds:
        score -= min(1.5, (candidate.first_visual_seconds - policy.max_first_visual_seconds) * 0.35)
        defects.append("visual_arrives_late")
        repairs.append("put the strongest visual contradiction or consequence in the first second")
    if candidate.generic_phrase_count:
        score -= min(1.5, candidate.generic_phrase_count * 0.3)
        defects.append("generic_language")
        repairs.append("replace generic phrases with a concrete object, number, place, action, or consequence")
    if candidate.opens_with_explanation:
        score -= 0.75
        defects.append("opens_with_explanation")
        repairs.append("open on the surprising result or unresolved contradiction, then explain")
    if candidate.specificity < policy.minimum_specificity:
        defects.append("low_specificity")
        repairs.append("name the exact thing the viewer will see or learn")
    if candidate.visualizability < policy.minimum_visualizability:
        defects.append("weak_first_image")
        repairs.append("rewrite around an action, transformation, comparison, or visible mechanism")
    if candidate.payoff_promise < policy.minimum_payoff_promise:
        defects.append("unclear_payoff")
        repairs.append("state or imply the precise question the ending will answer")

    score = max(0.0, min(10.0, score))
    hard_defect = any(
        defect in {"weak_first_image", "unclear_payoff"}
        for defect in defects
    )
    if score >= policy.pass_score and not hard_defect:
        decision = HookDecision.STRONG
    elif score >= policy.revise_score:
        decision = HookDecision.REVISE
    else:
        decision = HookDecision.REJECT

    return HookResult(
        hook_id=candidate.hook_id,
        decision=decision,
        score=round(score, 3),
        strengths=tuple(sorted(strengths)),
        defects=tuple(dict.fromkeys(defects)),
        repair_prompts=tuple(dict.fromkeys(repairs)),
    )


def rank_hooks(candidates: Iterable[HookCandidate], *, policy: HookPolicy | None = None) -> tuple[HookResult, ...]:
    results = [evaluate_hook(candidate, policy=policy) for candidate in candidates]
    decision_rank = {HookDecision.STRONG: 2, HookDecision.REVISE: 1, HookDecision.REJECT: 0}
    return tuple(sorted(results, key=lambda result: (-decision_rank[result.decision], -result.score, result.hook_id)))
