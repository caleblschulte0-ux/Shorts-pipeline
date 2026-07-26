from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Iterable


class HumorDecision(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    REMOVE = "remove"


class HumorDevice(str, Enum):
    MISDIRECTION = "misdirection"
    CONTRAST = "contrast"
    CALLBACK = "callback"
    CHARACTER_REACTION = "character_reaction"
    UNDERSTATEMENT = "understatement"
    EXAGGERATION = "exaggeration"
    VISUAL_GAG = "visual_gag"
    WORDPLAY = "wordplay"


@dataclass(frozen=True)
class HumorBeat:
    beat_id: str
    device: HumorDevice
    setup_clarity: float
    surprise: float
    relevance: float
    tone_fit: float
    character_specificity: float
    punchline_speed_seconds: float
    interrupts_fact_delivery: bool = False
    targets_vulnerable_group: bool = False
    repeated_device_recently: bool = False
    callback_key: str = ""
    callback_resolved: bool = False

    def __post_init__(self) -> None:
        if not self.beat_id:
            raise ValueError("beat_id is required")
        for name in ("setup_clarity", "surprise", "relevance", "tone_fit", "character_specificity"):
            value = getattr(self, name)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"{name} must be between 0 and 10")
        if self.punchline_speed_seconds < 0:
            raise ValueError("punchline_speed_seconds cannot be negative")
        if self.callback_resolved and not self.callback_key:
            raise ValueError("resolved callbacks require callback_key")


@dataclass(frozen=True)
class HumorDefect:
    beat_id: str
    code: str
    severity: float
    explanation: str
    repair: str


@dataclass(frozen=True)
class HumorBeatReport:
    beat_id: str
    score: float
    decision: HumorDecision
    defects: tuple[HumorDefect, ...]


@dataclass(frozen=True)
class HumorPersonalityReport:
    decision: HumorDecision
    average_score: float
    device_diversity: float
    removable_beats: tuple[str, ...]
    unresolved_callbacks: tuple[str, ...]
    beat_reports: tuple[HumorBeatReport, ...]
    repairs: tuple[str, ...]


def _defect(beat: HumorBeat, code: str, severity: float, explanation: str, repair: str) -> HumorDefect:
    return HumorDefect(beat.beat_id, code, round(severity, 2), explanation, repair)


def evaluate_humor_beat(beat: HumorBeat) -> HumorBeatReport:
    defects: list[HumorDefect] = []
    score = mean((beat.setup_clarity, beat.surprise, beat.relevance, beat.tone_fit, beat.character_specificity)) * 10.0

    if beat.targets_vulnerable_group:
        score = 0.0
        defects.append(_defect(beat, "harmful_target", 10.0, "The joke targets a vulnerable group rather than the situation, character, or idea.", "Remove the joke or redirect it toward the absurd situation or the protagonist's own misunderstanding."))
    if beat.relevance < 5.0:
        severity = 5.0 - beat.relevance
        score -= severity * 8
        defects.append(_defect(beat, "story_irrelevant_joke", severity, "The joke does not strengthen the explanation, character, or emotional turn.", "Cut it or rewrite it so the joke reveals character or clarifies the mechanism."))
    if beat.tone_fit < 5.0:
        severity = 5.0 - beat.tone_fit
        score -= severity * 8
        defects.append(_defect(beat, "tone_break", severity, "The joke clashes with the surrounding emotional or factual tone.", "Use a lighter reaction, understatement, or visual contrast that preserves the scene's stakes."))
    if beat.character_specificity < 4.5:
        severity = 4.5 - beat.character_specificity
        score -= severity * 6
        defects.append(_defect(beat, "generic_voice", severity, "The line could be said by any generic narrator or mascot.", "Tie the joke to the character's goal, flaw, prior action, or established callback."))
    if beat.punchline_speed_seconds > 5.0:
        severity = beat.punchline_speed_seconds - 5.0
        score -= min(25.0, severity * 4)
        defects.append(_defect(beat, "slow_punchline", severity, "The setup takes too long relative to the payoff.", "Compress the setup and land the visual or verbal turn sooner."))
    if beat.interrupts_fact_delivery:
        score -= 18
        defects.append(_defect(beat, "fact_interruption", 4.0, "The joke interrupts a fact the viewer still needs to understand.", "Move the joke after the fact is visually established or use the joke as the example itself."))
    if beat.repeated_device_recently:
        score -= 14
        defects.append(_defect(beat, "repeated_humor_device", 3.0, "The same comedy mechanism was used too recently.", "Switch to reaction, contrast, callback, understatement, or a visual gag."))
    if beat.callback_key and not beat.callback_resolved:
        score -= 12
        defects.append(_defect(beat, "unresolved_humor_callback", 2.5, "The beat sets up a comedy callback that never returns.", "Resolve the callback near the payoff or remove the setup."))

    score = round(max(0.0, min(100.0, score)), 2)
    if score < 35 or beat.targets_vulnerable_group:
        decision = HumorDecision.REMOVE
    elif score < 70:
        decision = HumorDecision.REVISE
    else:
        decision = HumorDecision.PASS
    return HumorBeatReport(beat.beat_id, score, decision, tuple(sorted(defects, key=lambda item: item.severity, reverse=True)))


def analyze_humor_personality(beats: Iterable[HumorBeat]) -> HumorPersonalityReport:
    ordered = tuple(beats)
    if not ordered:
        raise ValueError("at least one humor beat is required")
    ids = [beat.beat_id for beat in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate beat_id")

    reports = tuple(evaluate_humor_beat(beat) for beat in ordered)
    average_score = round(mean(report.score for report in reports), 2)
    unique_devices = len({beat.device for beat in ordered})
    device_diversity = round(unique_devices / len(ordered) * 100.0, 2)
    removable = tuple(report.beat_id for report in reports if report.decision is HumorDecision.REMOVE)
    unresolved = tuple(beat.callback_key for beat in ordered if beat.callback_key and not beat.callback_resolved)
    repairs = tuple(
        dict.fromkeys(
            defect.repair
            for report in sorted(reports, key=lambda item: item.score)
            for defect in report.defects
        )
    )

    if removable:
        decision = HumorDecision.REMOVE
    elif average_score < 72 or device_diversity < 35:
        decision = HumorDecision.REVISE
    else:
        decision = HumorDecision.PASS

    return HumorPersonalityReport(decision, average_score, device_diversity, removable, unresolved, reports, repairs)
