from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Iterable


class ResonanceDecision(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    BLOCK = "block"


class EmotionalFunction(str, Enum):
    RELATABILITY = "relatability"
    STAKES = "stakes"
    EMPATHY = "empathy"
    TENSION = "tension"
    WONDER = "wonder"
    RELIEF = "relief"
    CONSEQUENCE = "consequence"
    CALLBACK = "callback"


@dataclass(frozen=True)
class EmotionalBeat:
    beat_id: str
    function: EmotionalFunction
    human_specificity: float
    visible_consequence: float
    emotional_change: float
    story_relevance: float
    authenticity: float
    setup_strength: float = 0.0
    payoff_strength: float = 0.0
    manipulative_language: bool = False
    unsupported_stakes: bool = False
    repeated_emotion_recently: bool = False

    def __post_init__(self) -> None:
        if not self.beat_id:
            raise ValueError("beat_id is required")
        for name in (
            "human_specificity",
            "visible_consequence",
            "emotional_change",
            "story_relevance",
            "authenticity",
            "setup_strength",
            "payoff_strength",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"{name} must be between 0 and 10")


@dataclass(frozen=True)
class ResonanceDefect:
    beat_id: str
    code: str
    severity: float
    explanation: str
    repair: str


@dataclass(frozen=True)
class EmotionalBeatReport:
    beat_id: str
    score: float
    defects: tuple[ResonanceDefect, ...]


@dataclass(frozen=True)
class EmotionalResonanceReport:
    decision: ResonanceDecision
    average_score: float
    emotional_range: float
    strongest_beats: tuple[str, ...]
    weak_beats: tuple[str, ...]
    beat_reports: tuple[EmotionalBeatReport, ...]
    repairs: tuple[str, ...]


def _defect(beat: EmotionalBeat, code: str, severity: float, explanation: str, repair: str) -> ResonanceDefect:
    return ResonanceDefect(beat.beat_id, code, round(severity, 2), explanation, repair)


def evaluate_emotional_beat(beat: EmotionalBeat) -> EmotionalBeatReport:
    score = mean(
        (
            beat.human_specificity,
            beat.visible_consequence,
            beat.emotional_change,
            beat.story_relevance,
            beat.authenticity,
        )
    ) * 10.0
    defects: list[ResonanceDefect] = []

    if beat.human_specificity < 5.0:
        severity = 5.0 - beat.human_specificity
        score -= severity * 6
        defects.append(_defect(beat, "abstract_human_stakes", severity, "The beat describes importance without grounding it in a person, choice, object, or consequence.", "Show who is affected, what changes for them, and what they can or cannot do afterward."))
    if beat.visible_consequence < 5.0 and beat.function in {EmotionalFunction.STAKES, EmotionalFunction.CONSEQUENCE, EmotionalFunction.RELIEF}:
        severity = 5.0 - beat.visible_consequence
        score -= severity * 7
        defects.append(_defect(beat, "consequence_not_visible", severity, "The emotional claim is narrated but not demonstrated.", "Show the changed amount, behavior, environment, expression, or available choice."))
    if beat.emotional_change < 4.0:
        severity = 4.0 - beat.emotional_change
        score -= severity * 5
        defects.append(_defect(beat, "emotionally_static", severity, "The beat does not change the viewer's or character's emotional state.", "Add a discovery, obstacle, reversal, consequence, or release."))
    if beat.story_relevance < 6.0:
        severity = 6.0 - beat.story_relevance
        score -= severity * 7
        defects.append(_defect(beat, "detached_emotion", severity, "The emotional beat feels added on rather than caused by the story.", "Tie the feeling to the central mechanism, question, or payoff."))
    if beat.authenticity < 5.0:
        severity = 5.0 - beat.authenticity
        score -= severity * 8
        defects.append(_defect(beat, "inauthentic_emphasis", severity, "The emotional intensity exceeds what the evidence or situation supports.", "Reduce the language and let the visible consequence carry the emotion."))
    if beat.manipulative_language:
        score -= 24
        defects.append(_defect(beat, "manipulative_language", 5.0, "The beat pressures the viewer to feel rather than earning the reaction.", "Replace emotional commands with specific evidence, behavior, and consequence."))
    if beat.unsupported_stakes:
        score -= 30
        defects.append(_defect(beat, "unsupported_stakes", 6.0, "The stakes are stronger than the factual or narrative evidence.", "Scale the claim back or add sourced, visible support."))
    if beat.repeated_emotion_recently:
        score -= 12
        defects.append(_defect(beat, "repeated_emotional_note", 2.5, "The same emotional note repeats without progression.", "Change the emotion through confusion, tension, realization, determination, or relief."))
    if beat.setup_strength >= 5.0 and beat.payoff_strength < 4.0:
        severity = beat.setup_strength - beat.payoff_strength
        score -= severity * 5
        defects.append(_defect(beat, "emotional_setup_without_payoff", severity, "The beat establishes emotional stakes that are not later satisfied.", "Return to the same person, object, or consequence during the payoff."))

    return EmotionalBeatReport(beat.beat_id, round(max(0.0, min(100.0, score)), 2), tuple(sorted(defects, key=lambda item: item.severity, reverse=True)))


def analyze_emotional_resonance(beats: Iterable[EmotionalBeat]) -> EmotionalResonanceReport:
    ordered = tuple(beats)
    if not ordered:
        raise ValueError("at least one emotional beat is required")
    ids = [beat.beat_id for beat in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate beat_id")

    reports = tuple(evaluate_emotional_beat(beat) for beat in ordered)
    average_score = round(mean(report.score for report in reports), 2)
    emotional_range = round(len({beat.function for beat in ordered}) / len(EmotionalFunction) * 100.0, 2)
    strongest = tuple(report.beat_id for report in sorted(reports, key=lambda item: item.score, reverse=True)[:3])
    weak = tuple(report.beat_id for report in reports if report.score < 60)
    repairs = tuple(
        dict.fromkeys(
            defect.repair
            for report in sorted(reports, key=lambda item: item.score)
            for defect in report.defects
        )
    )

    has_blocker = any(
        defect.code in {"unsupported_stakes", "manipulative_language"} and defect.severity >= 5.0
        for report in reports
        for defect in report.defects
    )
    if has_blocker or average_score < 40:
        decision = ResonanceDecision.BLOCK
    elif average_score < 72 or emotional_range < 25:
        decision = ResonanceDecision.REVISE
    else:
        decision = ResonanceDecision.PASS

    return EmotionalResonanceReport(decision, average_score, emotional_range, strongest, weak, reports, repairs)
