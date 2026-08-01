from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class QuestionLoop:
    loop_id: str
    opened_at: float
    importance: float
    promised_answer_by: float
    resolved_at: float | None = None
    answer_specificity: float = 0.0
    visual_proof: bool = False

    def __post_init__(self) -> None:
        if not self.loop_id.strip():
            raise ValueError("loop_id is required")
        if self.opened_at < 0 or self.promised_answer_by < self.opened_at:
            raise ValueError("invalid loop timing")
        if self.resolved_at is not None and self.resolved_at < self.opened_at:
            raise ValueError("resolved_at cannot precede opened_at")
        for value, name in ((self.importance, "importance"), (self.answer_specificity, "answer_specificity")):
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")


@dataclass(frozen=True)
class CuriosityBeat:
    beat_id: str
    start_seconds: float
    novelty: float
    stakes: float
    revelation_value: float

    def __post_init__(self) -> None:
        if not self.beat_id.strip():
            raise ValueError("beat_id is required")
        if self.start_seconds < 0:
            raise ValueError("start_seconds must be nonnegative")
        for value, name in ((self.novelty, "novelty"), (self.stakes, "stakes"), (self.revelation_value, "revelation_value")):
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")


@dataclass(frozen=True)
class CuriosityDefect:
    code: str
    subject_id: str
    severity: int
    detail: str


@dataclass(frozen=True)
class CuriosityReport:
    score: float
    defects: tuple[CuriosityDefect, ...]
    unresolved_loops: tuple[str, ...]
    peak_open_loops: int
    strongest_revelations: tuple[str, ...]


def _concurrent_peak(loops: tuple[QuestionLoop, ...]) -> int:
    events: list[tuple[float, int]] = []
    for loop in loops:
        events.append((loop.opened_at, 1))
        if loop.resolved_at is not None:
            events.append((loop.resolved_at, -1))
    current = 0
    peak = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        current += delta
        peak = max(peak, current)
    return peak


def analyze_curiosity_curve(loops: Iterable[QuestionLoop], beats: Iterable[CuriosityBeat]) -> CuriosityReport:
    loop_items = tuple(loops)
    beat_items = tuple(sorted(beats, key=lambda item: item.start_seconds))
    if len({item.loop_id for item in loop_items}) != len(loop_items):
        raise ValueError("duplicate loop_id")
    if len({item.beat_id for item in beat_items}) != len(beat_items):
        raise ValueError("duplicate beat_id")

    defects: list[CuriosityDefect] = []
    unresolved: list[str] = []
    penalty = 0.0

    for loop in loop_items:
        if loop.resolved_at is None:
            unresolved.append(loop.loop_id)
            severity = 4 if loop.importance >= 8 else 2
            defects.append(CuriosityDefect("unresolved_loop", loop.loop_id, severity, "question never receives an answer"))
            penalty += 1.8 if severity == 4 else 0.8
            continue
        if loop.resolved_at > loop.promised_answer_by:
            defects.append(CuriosityDefect("late_resolution", loop.loop_id, 2, "answer arrives after the promised window"))
            penalty += 0.7
        if loop.answer_specificity < 6:
            defects.append(CuriosityDefect("vague_resolution", loop.loop_id, 3, "answer is not specific enough to satisfy the setup"))
            penalty += 1.0
        if loop.importance >= 8 and not loop.visual_proof:
            defects.append(CuriosityDefect("major_loop_without_visual_proof", loop.loop_id, 3, "major answer lacks visible evidence"))
            penalty += 1.0

    peak = _concurrent_peak(loop_items)
    if peak > 4:
        defects.append(CuriosityDefect("open_loop_overload", "story", 3, f"{peak} questions are open at once"))
        penalty += min(2.0, 0.45 * (peak - 4))

    for index in range(len(beat_items) - 3):
        window = beat_items[index:index + 4]
        if all(item.novelty <= 4 for item in window):
            defects.append(CuriosityDefect("low_novelty_run", window[0].beat_id, 2, "four consecutive beats add little novelty"))
            penalty += 0.7
        if all(item.revelation_value <= 3 for item in window):
            defects.append(CuriosityDefect("revelation_drought", window[0].beat_id, 3, "four consecutive beats provide no meaningful answer"))
            penalty += 0.9

    if len(beat_items) >= 4:
        stakes = [item.stakes for item in beat_items]
        if max(stakes) - min(stakes) < 2:
            defects.append(CuriosityDefect("flat_stakes", "story", 2, "stakes do not materially change across the story"))
            penalty += 0.7

    strongest = tuple(
        item.beat_id
        for item in sorted(beat_items, key=lambda beat: (-beat.revelation_value, -beat.novelty, beat.start_seconds))[:3]
        if item.revelation_value >= 7
    )
    score = max(0.0, min(10.0, 10.0 - penalty))
    defects.sort(key=lambda item: (-item.severity, item.subject_id, item.code))
    return CuriosityReport(round(score, 3), tuple(defects), tuple(sorted(unresolved)), peak, strongest)
