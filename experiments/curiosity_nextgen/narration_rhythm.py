from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable


_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")


@dataclass(frozen=True)
class NarrationSegment:
    segment_id: str
    start_seconds: float
    duration_seconds: float
    text: str
    pause_after_seconds: float = 0.0
    emphasis_count: int = 0

    def __post_init__(self) -> None:
        if not self.segment_id.strip():
            raise ValueError("segment_id is required")
        if self.start_seconds < 0 or self.duration_seconds <= 0 or self.pause_after_seconds < 0:
            raise ValueError("invalid narration timing")
        if not self.text.strip():
            raise ValueError("text is required")
        if self.emphasis_count < 0:
            raise ValueError("emphasis_count must be nonnegative")

    @property
    def word_count(self) -> int:
        return len(_WORD_RE.findall(self.text))

    @property
    def words_per_minute(self) -> float:
        return self.word_count / self.duration_seconds * 60.0

    @property
    def sentence_lengths(self) -> tuple[int, ...]:
        values = []
        for sentence in _SENTENCE_RE.findall(self.text):
            count = len(_WORD_RE.findall(sentence))
            if count:
                values.append(count)
        return tuple(values)


@dataclass(frozen=True)
class NarrationDefect:
    code: str
    segment_id: str
    severity: int
    detail: str


@dataclass(frozen=True)
class NarrationReport:
    score: float
    defects: tuple[NarrationDefect, ...]
    average_wpm: float
    sentence_length_variation: float
    total_pause_seconds: float


def _coefficient_of_variation(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance) / mean


def analyze_narration(segments: Iterable[NarrationSegment]) -> NarrationReport:
    items = tuple(sorted(segments, key=lambda item: item.start_seconds))
    if len({item.segment_id for item in items}) != len(items):
        raise ValueError("duplicate segment_id")
    if not items:
        return NarrationReport(0.0, (NarrationDefect("missing_narration", "story", 4, "no narration segments supplied"),), 0.0, 0.0, 0.0)

    defects: list[NarrationDefect] = []
    penalty = 0.0
    all_lengths: list[int] = []
    total_words = 0
    total_duration = 0.0

    for item in items:
        total_words += item.word_count
        total_duration += item.duration_seconds
        all_lengths.extend(item.sentence_lengths)
        wpm = item.words_per_minute
        if wpm > 195:
            defects.append(NarrationDefect("segment_too_fast", item.segment_id, 3, f"{wpm:.0f} words per minute"))
            penalty += 0.8
        elif wpm < 105:
            defects.append(NarrationDefect("segment_too_slow", item.segment_id, 2, f"{wpm:.0f} words per minute"))
            penalty += 0.45
        if any(length > 28 for length in item.sentence_lengths):
            defects.append(NarrationDefect("overlong_sentence", item.segment_id, 2, "sentence exceeds 28 words"))
            penalty += 0.45
        if item.start_seconds <= 15 and item.word_count > 45:
            defects.append(NarrationDefect("dense_opening", item.segment_id, 3, "opening asks the viewer to process too much language"))
            penalty += 0.7

    for index in range(len(items) - 2):
        window = items[index:index + 3]
        if all(item.words_per_minute > 180 and item.pause_after_seconds < 0.15 for item in window):
            defects.append(NarrationDefect("breathless_run", window[0].segment_id, 3, "three fast segments provide no breathing room"))
            penalty += 0.8
        if all(item.emphasis_count == 0 for item in window):
            defects.append(NarrationDefect("flat_delivery_run", window[0].segment_id, 2, "three segments have no planned emphasis"))
            penalty += 0.45

    variation = _coefficient_of_variation(all_lengths)
    if len(all_lengths) >= 5 and variation < 0.18:
        defects.append(NarrationDefect("monotone_sentence_cadence", "story", 3, "sentence lengths are too uniform"))
        penalty += 0.8

    first_30 = " ".join(item.text for item in items if item.start_seconds <= 30)
    if "?" not in first_30:
        defects.append(NarrationDefect("no_early_question", "story", 2, "first 30 seconds contain no spoken question"))
        penalty += 0.4

    total_pause = sum(item.pause_after_seconds for item in items)
    runtime = max(item.start_seconds + item.duration_seconds for item in items)
    if runtime >= 45 and total_pause < runtime / 120:
        defects.append(NarrationDefect("insufficient_pause_budget", "story", 2, "narration rarely allows an idea to land"))
        penalty += 0.5

    average_wpm = total_words / total_duration * 60.0 if total_duration else 0.0
    defects.sort(key=lambda item: (-item.severity, item.segment_id, item.code))
    return NarrationReport(round(max(0.0, 10.0 - penalty), 3), tuple(defects), round(average_wpm, 2), round(variation, 3), round(total_pause, 3))
