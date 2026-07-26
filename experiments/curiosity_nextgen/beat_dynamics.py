from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class BeatRole(str, Enum):
    HOOK = "hook"
    SETUP = "setup"
    EVIDENCE = "evidence"
    MECHANISM = "mechanism"
    ESCALATION = "escalation"
    CONSEQUENCE = "consequence"
    CALLBACK = "callback"
    PAYOFF = "payoff"


@dataclass(frozen=True)
class BeatSignal:
    beat_id: str
    start_seconds: float
    duration_seconds: float
    role: BeatRole
    visual_family: str
    energy: float
    novelty: float
    information_density: float
    emotional_intensity: float
    motion_score: float
    has_character_action: bool = False
    has_new_question: bool = False
    resolves_question: bool = False

    def __post_init__(self) -> None:
        if not self.beat_id.strip():
            raise ValueError("beat_id is required")
        if self.start_seconds < 0 or self.duration_seconds <= 0:
            raise ValueError("invalid beat timing")
        if not self.visual_family.strip():
            raise ValueError("visual_family is required")
        for name in (
            "energy",
            "novelty",
            "information_density",
            "emotional_intensity",
            "motion_score",
        ):
            value = float(getattr(self, name))
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")


@dataclass(frozen=True)
class DynamicsPolicy:
    max_same_family_run: int = 2
    max_low_energy_run: int = 2
    low_energy_threshold: float = 4.5
    max_high_density_run: int = 2
    high_density_threshold: float = 7.5
    max_no_character_run: int = 4
    max_question_gap_seconds: float = 35.0
    minimum_energy_change: float = 1.25


@dataclass(frozen=True)
class DynamicsDefect:
    code: str
    beat_ids: tuple[str, ...]
    severity: int
    explanation: str
    suggested_change: str


@dataclass(frozen=True)
class DynamicsReport:
    score: float
    defects: tuple[DynamicsDefect, ...]
    strongest_turns: tuple[str, ...]
    weakest_beats: tuple[str, ...]


def _runs(items: tuple[BeatSignal, ...], key) -> Iterable[tuple[BeatSignal, ...]]:
    if not items:
        return ()
    groups: list[tuple[BeatSignal, ...]] = []
    current: list[BeatSignal] = [items[0]]
    current_key = key(items[0])
    for item in items[1:]:
        item_key = key(item)
        if item_key == current_key:
            current.append(item)
        else:
            groups.append(tuple(current))
            current = [item]
            current_key = item_key
    groups.append(tuple(current))
    return tuple(groups)


def analyze_dynamics(beats: Iterable[BeatSignal], *, policy: DynamicsPolicy | None = None) -> DynamicsReport:
    policy = policy or DynamicsPolicy()
    ordered = tuple(sorted(beats, key=lambda beat: (beat.start_seconds, beat.beat_id)))
    if not ordered:
        return DynamicsReport(0.0, (), (), ())
    if len({beat.beat_id for beat in ordered}) != len(ordered):
        raise ValueError("duplicate beat_id")

    defects: list[DynamicsDefect] = []

    for run in _runs(ordered, lambda beat: beat.visual_family):
        if len(run) > policy.max_same_family_run:
            defects.append(DynamicsDefect(
                "visual_family_run",
                tuple(beat.beat_id for beat in run),
                min(4, len(run) - policy.max_same_family_run + 1),
                f"{len(run)} consecutive beats use {run[0].visual_family}",
                "replace one or more beats with a mechanism, character consequence, comparison, or alternate media family",
            ))

    low_energy = tuple(beat for beat in ordered if beat.energy < policy.low_energy_threshold)
    low_ids = {beat.beat_id for beat in low_energy}
    for run in _runs(ordered, lambda beat: beat.beat_id in low_ids):
        if run and run[0].beat_id in low_ids and len(run) > policy.max_low_energy_run:
            defects.append(DynamicsDefect(
                "flat_energy_run",
                tuple(beat.beat_id for beat in run),
                min(4, len(run) - 1),
                "energy remains low across multiple consecutive beats",
                "insert a reveal, visible transformation, consequence, escalation, or faster contrast",
            ))

    high_density_ids = {beat.beat_id for beat in ordered if beat.information_density > policy.high_density_threshold}
    for run in _runs(ordered, lambda beat: beat.beat_id in high_density_ids):
        if run and run[0].beat_id in high_density_ids and len(run) > policy.max_high_density_run:
            defects.append(DynamicsDefect(
                "dense_explanation_run",
                tuple(beat.beat_id for beat in run),
                3,
                "multiple dense beats arrive without a visual or emotional reset",
                "split the explanation with a demonstration, human consequence, analogy, or silent visual beat",
            ))

    no_character_ids = {beat.beat_id for beat in ordered if not beat.has_character_action}
    for run in _runs(ordered, lambda beat: beat.beat_id in no_character_ids):
        if run and run[0].beat_id in no_character_ids and len(run) > policy.max_no_character_run:
            defects.append(DynamicsDefect(
                "character_absence_run",
                tuple(beat.beat_id for beat in run),
                2,
                "the viewer goes too long without a human-scale action or consequence",
                "add a character choice, reaction, attempt, mistake, cost, or payoff",
            ))

    last_question_time = ordered[0].start_seconds if ordered[0].has_new_question else 0.0
    for beat in ordered:
        if beat.has_new_question:
            last_question_time = beat.start_seconds
        gap = beat.start_seconds - last_question_time
        if gap > policy.max_question_gap_seconds and not beat.resolves_question:
            defects.append(DynamicsDefect(
                "curiosity_gap_dormant",
                (beat.beat_id,),
                3,
                f"no new or resolving question for {gap:.1f} seconds",
                "introduce a sharper sub-question, contradiction, or withheld consequence",
            ))
            last_question_time = beat.start_seconds

    turns: list[tuple[float, str]] = []
    for previous, current in zip(ordered, ordered[1:]):
        delta = abs(current.energy - previous.energy) + abs(current.emotional_intensity - previous.emotional_intensity)
        if delta >= policy.minimum_energy_change:
            turns.append((delta, current.beat_id))

    weak = sorted(
        ordered,
        key=lambda beat: (
            beat.energy + beat.novelty + beat.motion_score + beat.emotional_intensity,
            beat.beat_id,
        ),
    )[:5]

    penalty = sum(defect.severity * 0.45 for defect in defects)
    baseline = sum(
        beat.energy * 0.25
        + beat.novelty * 0.25
        + beat.motion_score * 0.2
        + beat.emotional_intensity * 0.2
        + (1.0 if beat.has_new_question or beat.resolves_question else 0.0)
        for beat in ordered
    ) / len(ordered)
    score = max(0.0, min(10.0, baseline - penalty))

    return DynamicsReport(
        score=round(score, 3),
        defects=tuple(sorted(defects, key=lambda defect: (-defect.severity, defect.code, defect.beat_ids))),
        strongest_turns=tuple(beat_id for _, beat_id in sorted(turns, key=lambda item: (-item[0], item[1]))[:5]),
        weakest_beats=tuple(beat.beat_id for beat in weak),
    )
