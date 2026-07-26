from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Iterable


class RetentionRiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class RetentionMoment:
    moment_id: str
    start_seconds: float
    duration_seconds: float
    novelty: float
    curiosity: float
    clarity: float
    emotional_relevance: float
    visual_change: float
    audio_change: float
    proof_strength: float
    cognitive_load: float
    static_seconds: float = 0.0
    repeated_visual_family: bool = False
    unresolved_loop_count: int = 0
    jargon_count: int = 0
    payoff_moment: bool = False

    def __post_init__(self) -> None:
        if not self.moment_id:
            raise ValueError("moment_id is required")
        if self.start_seconds < 0 or self.duration_seconds <= 0:
            raise ValueError("moment timing must be positive")
        for field_name in (
            "novelty",
            "curiosity",
            "clarity",
            "emotional_relevance",
            "visual_change",
            "audio_change",
            "proof_strength",
            "cognitive_load",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"{field_name} must be between 0 and 10")
        if self.static_seconds < 0:
            raise ValueError("static_seconds cannot be negative")
        if self.unresolved_loop_count < 0 or self.jargon_count < 0:
            raise ValueError("counts cannot be negative")


@dataclass(frozen=True)
class RetentionDefect:
    moment_id: str
    code: str
    severity: float
    explanation: str
    suggested_action: str


@dataclass(frozen=True)
class MomentRisk:
    moment_id: str
    risk_score: float
    level: RetentionRiskLevel
    defects: tuple[RetentionDefect, ...]


@dataclass(frozen=True)
class RetentionRiskReport:
    overall_risk_score: float
    risk_level: RetentionRiskLevel
    moment_risks: tuple[MomentRisk, ...]
    highest_risk_moments: tuple[str, ...]
    early_risk_score: float
    middle_risk_score: float
    ending_risk_score: float
    disclaimer: str = (
        "Heuristic editorial risk only; this does not predict actual audience retention "
        "and must be calibrated against channel analytics."
    )


def _level(score: float) -> RetentionRiskLevel:
    if score >= 75:
        return RetentionRiskLevel.CRITICAL
    if score >= 55:
        return RetentionRiskLevel.HIGH
    if score >= 35:
        return RetentionRiskLevel.MODERATE
    return RetentionRiskLevel.LOW


def _defect(moment: RetentionMoment, code: str, severity: float, explanation: str, action: str) -> RetentionDefect:
    return RetentionDefect(moment.moment_id, code, round(severity, 2), explanation, action)


def evaluate_moment(moment: RetentionMoment) -> MomentRisk:
    defects: list[RetentionDefect] = []
    risk = 0.0

    weak_interest = max(0.0, 6.5 - mean((moment.novelty, moment.curiosity, moment.emotional_relevance)))
    risk += weak_interest * 5.0
    if weak_interest >= 2.0:
        defects.append(_defect(moment, "weak_interest_signal", weak_interest, "The moment lacks novelty, curiosity, or human stakes.", "Replace explanation with a question, consequence, contradiction, or surprising proof."))

    clarity_gap = max(0.0, 6.0 - moment.clarity)
    risk += clarity_gap * 4.0
    if clarity_gap >= 1.5:
        defects.append(_defect(moment, "clarity_gap", clarity_gap, "The viewer may not understand what changed or why it matters.", "Simplify the sentence and show one concrete relationship at a time."))

    overload = max(0.0, moment.cognitive_load - 6.5)
    risk += overload * 5.5
    if overload >= 1.0:
        defects.append(_defect(moment, "cognitive_overload", overload, "The moment asks the viewer to process too much at once.", "Split the idea, remove labels, or move secondary detail to a later beat."))

    sensory_stasis = max(0.0, 5.5 - mean((moment.visual_change, moment.audio_change)))
    risk += sensory_stasis * 3.5
    if sensory_stasis >= 1.5:
        defects.append(_defect(moment, "sensory_stasis", sensory_stasis, "Visual and audio change are both weak.", "Add a purposeful focal, camera, sound, or evidence change rather than decorative motion."))

    proof_gap = max(0.0, 5.0 - moment.proof_strength)
    if moment.payoff_moment:
        proof_gap *= 1.8
    risk += proof_gap * 3.0
    if proof_gap >= 2.0:
        defects.append(_defect(moment, "weak_visible_proof", proof_gap, "The claim or payoff is not strongly demonstrated on screen.", "Show the causal change, source evidence, comparison, or resulting consequence."))

    if moment.static_seconds > min(4.5, moment.duration_seconds * 0.75):
        severity = min(5.0, moment.static_seconds / 2.0)
        risk += severity * 4.0
        defects.append(_defect(moment, "long_static_hold", severity, "The frame remains materially unchanged for too long.", "Introduce a meaningful state change before the narration finishes the thought."))

    if moment.repeated_visual_family:
        risk += 9.0
        defects.append(_defect(moment, "repeated_visual_family", 2.5, "The moment repeats the visual language of adjacent beats.", "Switch from illustration to evidence, character action, scale, comparison, or consequence."))

    if moment.unresolved_loop_count > 3:
        severity = min(5.0, (moment.unresolved_loop_count - 3) * 1.25)
        risk += severity * 3.5
        defects.append(_defect(moment, "loop_overload", severity, "Too many unanswered questions are competing for attention.", "Resolve or restate the oldest open loop before introducing another."))

    if moment.jargon_count > 1:
        severity = min(5.0, moment.jargon_count * 0.9)
        risk += severity * 3.0
        defects.append(_defect(moment, "jargon_cluster", severity, "Multiple unfamiliar terms appear in one moment.", "Replace jargon with a concrete object, action, or one-sentence definition."))

    if moment.start_seconds <= 15:
        risk *= 1.25
    elif moment.payoff_moment:
        risk *= 1.15

    score = round(min(100.0, risk), 2)
    return MomentRisk(moment.moment_id, score, _level(score), tuple(sorted(defects, key=lambda item: item.severity, reverse=True)))


def _segment_score(results: list[MomentRisk], moments: list[RetentionMoment], start_fraction: float, end_fraction: float) -> float:
    total_duration = max(moment.start_seconds + moment.duration_seconds for moment in moments)
    selected = [
        result.risk_score
        for result, moment in zip(results, moments)
        if start_fraction * total_duration <= moment.start_seconds < end_fraction * total_duration
    ]
    return round(mean(selected), 2) if selected else 0.0


def analyze_retention_risk(moments: Iterable[RetentionMoment]) -> RetentionRiskReport:
    ordered = sorted(tuple(moments), key=lambda item: (item.start_seconds, item.moment_id))
    if not ordered:
        raise ValueError("at least one retention moment is required")
    ids = [item.moment_id for item in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate moment_id")
    for previous, current in zip(ordered, ordered[1:]):
        if current.start_seconds < previous.start_seconds + previous.duration_seconds - 0.001:
            raise ValueError("retention moments cannot overlap")

    results = [evaluate_moment(moment) for moment in ordered]
    weights = [1.35 if moment.start_seconds <= 15 else 1.15 if moment.payoff_moment else 1.0 for moment in ordered]
    overall = round(sum(result.risk_score * weight for result, weight in zip(results, weights)) / sum(weights), 2)
    highest = tuple(result.moment_id for result in sorted(results, key=lambda item: item.risk_score, reverse=True)[:5])

    return RetentionRiskReport(
        overall_risk_score=overall,
        risk_level=_level(overall),
        moment_risks=tuple(results),
        highest_risk_moments=highest,
        early_risk_score=_segment_score(results, ordered, 0.0, 0.2),
        middle_risk_score=_segment_score(results, ordered, 0.2, 0.8),
        ending_risk_score=_segment_score(results, ordered, 0.8, 1.01),
    )
