from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Iterable


class LoadDecision(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    BLOCK = "block"


@dataclass(frozen=True)
class InformationBeat:
    beat_id: str
    duration_seconds: float
    spoken_words: int
    visible_words: int
    new_concepts: int
    numeric_values: int
    named_entities: int
    simultaneous_visual_elements: int
    jargon_terms: int = 0
    requires_prior_context: bool = False
    includes_example: bool = False
    includes_visual_mapping: bool = False
    pause_after_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.beat_id:
            raise ValueError("beat_id is required")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        for name in (
            "spoken_words",
            "visible_words",
            "new_concepts",
            "numeric_values",
            "named_entities",
            "simultaneous_visual_elements",
            "jargon_terms",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.pause_after_seconds < 0:
            raise ValueError("pause_after_seconds cannot be negative")


@dataclass(frozen=True)
class LoadDefect:
    beat_id: str
    code: str
    severity: float
    explanation: str
    repair: str


@dataclass(frozen=True)
class BeatLoad:
    beat_id: str
    load_score: float
    defects: tuple[LoadDefect, ...]


@dataclass(frozen=True)
class CognitiveLoadReport:
    decision: LoadDecision
    average_load: float
    peak_load: float
    overloaded_beats: tuple[str, ...]
    consecutive_overload_runs: tuple[tuple[str, ...], ...]
    beat_loads: tuple[BeatLoad, ...]
    repairs: tuple[str, ...]


def _defect(beat: InformationBeat, code: str, severity: float, explanation: str, repair: str) -> LoadDefect:
    return LoadDefect(beat.beat_id, code, round(severity, 2), explanation, repair)


def evaluate_information_beat(beat: InformationBeat) -> BeatLoad:
    defects: list[LoadDefect] = []
    spoken_wps = beat.spoken_words / beat.duration_seconds
    visible_wps = beat.visible_words / beat.duration_seconds

    load = 0.0
    load += min(25.0, spoken_wps * 7.5)
    load += min(18.0, visible_wps * 9.0)
    load += beat.new_concepts * 8.0
    load += beat.numeric_values * 4.0
    load += beat.named_entities * 3.0
    load += max(0, beat.simultaneous_visual_elements - 2) * 4.5
    load += beat.jargon_terms * 6.0
    if beat.requires_prior_context:
        load += 7.0

    if beat.includes_example:
        load -= 8.0
    if beat.includes_visual_mapping:
        load -= 8.0
    if beat.pause_after_seconds >= 0.6:
        load -= min(8.0, beat.pause_after_seconds * 5.0)

    if spoken_wps > 3.2:
        defects.append(_defect(beat, "speech_too_dense", spoken_wps, "Narration delivers too many words for the available time.", "Shorten the sentence or extend the beat with a meaningful visual change."))
    if visible_wps > 2.2:
        defects.append(_defect(beat, "text_reading_conflict", visible_wps, "On-screen reading competes with the narration.", "Cut visible words, reveal them sequentially, or let the narrator pause."))
    if beat.new_concepts >= 3:
        defects.append(_defect(beat, "concept_stack", beat.new_concepts, "Several new ideas are introduced before the viewer can organize them.", "Use one concept per beat and connect each concept to a visible example."))
    if beat.numeric_values >= 4:
        defects.append(_defect(beat, "number_stack", beat.numeric_values, "Too many numeric values appear in one beat.", "Keep the comparison-defining values and move supporting figures to later beats."))
    if beat.simultaneous_visual_elements >= 6:
        defects.append(_defect(beat, "visual_element_overload", beat.simultaneous_visual_elements, "The frame asks the viewer to scan too many objects at once.", "Establish a single focal object, then reveal supporting elements in sequence."))
    if beat.jargon_terms >= 2 and not beat.includes_example:
        defects.append(_defect(beat, "untranslated_jargon", beat.jargon_terms, "Multiple technical terms appear without a concrete example.", "Translate the terms into an action, object, or analogy before using them again."))
    if beat.requires_prior_context and beat.new_concepts >= 2:
        defects.append(_defect(beat, "context_dependency_spike", beat.new_concepts, "The beat depends on earlier information while introducing more new material.", "Restate the one prerequisite relationship the viewer needs."))

    return BeatLoad(beat.beat_id, round(max(0.0, min(100.0, load)), 2), tuple(sorted(defects, key=lambda item: item.severity, reverse=True)))


def _runs(overloaded: list[bool], beats: list[InformationBeat]) -> tuple[tuple[str, ...], ...]:
    runs: list[tuple[str, ...]] = []
    current: list[str] = []
    for flag, beat in zip(overloaded, beats):
        if flag:
            current.append(beat.beat_id)
        elif current:
            if len(current) >= 2:
                runs.append(tuple(current))
            current = []
    if len(current) >= 2:
        runs.append(tuple(current))
    return tuple(runs)


def analyze_cognitive_load(beats: Iterable[InformationBeat]) -> CognitiveLoadReport:
    ordered = tuple(beats)
    if not ordered:
        raise ValueError("at least one information beat is required")
    ids = [beat.beat_id for beat in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate beat_id")

    results = tuple(evaluate_information_beat(beat) for beat in ordered)
    # A beat participates in an overload RUN when it crosses the score bar OR
    # carries an overload-class defect: back-to-back concept/number/speech/
    # visual stacking fatigues viewers even when each beat's aggregate score
    # stays under the single-beat ceiling. Wider detection, never narrower.
    _OVERLOAD_DEFECTS = {"concept_stack", "number_stack", "speech_too_dense",
                         "visual_element_overload", "text_reading_conflict"}
    overloaded_flags = [
        result.load_score >= 65.0
        or any(d.code in _OVERLOAD_DEFECTS for d in result.defects)
        for result in results
    ]
    overloaded = tuple(result.beat_id for result in results if result.load_score >= 65.0)
    runs = _runs(overloaded_flags, list(ordered))
    average = round(mean(result.load_score for result in results), 2)
    peak = round(max(result.load_score for result in results), 2)

    repairs: list[str] = []
    if runs:
        repairs.append("break consecutive overload runs with a recap, example, reaction, or proof beat")
    if any(any(defect.code == "text_reading_conflict" for defect in result.defects) for result in results):
        repairs.append("separate narration from dense on-screen reading")
    if any(any(defect.code == "concept_stack" for defect in result.defects) for result in results):
        repairs.append("limit new concepts to one or two per beat")
    if any(any(defect.code == "number_stack" for defect in result.defects) for result in results):
        repairs.append("convert number clusters into comparisons, scale, or sequential reveals")

    if peak >= 85 or len(runs) >= 2:
        decision = LoadDecision.BLOCK
    elif peak >= 65 or average >= 55:
        decision = LoadDecision.REVISE
    else:
        decision = LoadDecision.PASS

    return CognitiveLoadReport(decision, average, peak, overloaded, runs, results, tuple(dict.fromkeys(repairs)))
