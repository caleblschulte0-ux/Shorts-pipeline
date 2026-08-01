from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Iterable


class CaptionDecision(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    BLOCK = "block"


@dataclass(frozen=True)
class CaptionCue:
    cue_id: str
    start_seconds: float
    end_seconds: float
    text: str
    line_count: int
    max_line_characters: int
    contrast_ratio: float
    font_height_percent: float
    bottom_safe_margin_percent: float
    speaker_overlap: bool = False
    important_visual_overlap: bool = False
    hard_line_break_mid_phrase: bool = False
    emphasized_word_count: int = 0

    def __post_init__(self) -> None:
        if not self.cue_id:
            raise ValueError("cue_id is required")
        if self.start_seconds < 0 or self.end_seconds <= self.start_seconds:
            raise ValueError("invalid caption timing")
        if not self.text.strip():
            raise ValueError("caption text is required")
        if self.line_count <= 0 or self.max_line_characters <= 0:
            raise ValueError("line metrics must be positive")
        if self.contrast_ratio <= 0:
            raise ValueError("contrast_ratio must be positive")
        if self.font_height_percent <= 0 or self.bottom_safe_margin_percent < 0:
            raise ValueError("caption geometry is invalid")
        if self.emphasized_word_count < 0:
            raise ValueError("emphasized_word_count cannot be negative")


@dataclass(frozen=True)
class CaptionDefect:
    cue_id: str
    code: str
    severity: float
    explanation: str
    repair: str


@dataclass(frozen=True)
class CueReadability:
    cue_id: str
    characters_per_second: float
    score: float
    defects: tuple[CaptionDefect, ...]


@dataclass(frozen=True)
class CaptionReadabilityReport:
    decision: CaptionDecision
    average_score: float
    minimum_score: float
    unreadable_cues: tuple[str, ...]
    safe_area_violations: tuple[str, ...]
    cue_reports: tuple[CueReadability, ...]
    repairs: tuple[str, ...]


def _defect(cue: CaptionCue, code: str, severity: float, explanation: str, repair: str) -> CaptionDefect:
    return CaptionDefect(cue.cue_id, code, round(severity, 2), explanation, repair)


def evaluate_caption(cue: CaptionCue) -> CueReadability:
    duration = cue.end_seconds - cue.start_seconds
    visible_characters = len("".join(character for character in cue.text if not character.isspace()))
    cps = visible_characters / duration
    score = 100.0
    defects: list[CaptionDefect] = []

    if cps > 20:
        severity = min(10.0, (cps - 20) / 2)
        score -= 22 + severity * 3
        defects.append(_defect(cue, "reading_speed_excess", severity, "The caption disappears faster than many viewers can comfortably read it.", "Shorten the wording, extend the cue, or split it at a natural phrase boundary."))
    elif cps > 17:
        severity = cps - 17
        score -= severity * 5
        defects.append(_defect(cue, "reading_speed_high", severity, "The caption reading speed is demanding.", "Remove filler words or slightly extend the cue."))

    if cue.line_count > 2:
        severity = cue.line_count - 2
        score -= severity * 15
        defects.append(_defect(cue, "too_many_lines", severity, "The caption occupies too many vertical lines.", "Use at most two lines and reveal secondary wording later."))
    if cue.max_line_characters > 42:
        severity = (cue.max_line_characters - 42) / 5
        score -= min(20.0, severity * 5)
        defects.append(_defect(cue, "line_too_long", severity, "The caption line is difficult to scan on a phone.", "Rebreak the phrase into shorter semantic units."))
    if cue.contrast_ratio < 4.5:
        severity = 4.5 - cue.contrast_ratio
        score -= 25 + severity * 5
        defects.append(_defect(cue, "insufficient_contrast", severity, "Foreground and background contrast are too weak.", "Use a stronger outline, shadow, plate, or contrasting text treatment."))
    if cue.font_height_percent < 4.2:
        severity = 4.2 - cue.font_height_percent
        score -= 18 + severity * 4
        defects.append(_defect(cue, "caption_too_small", severity, "Caption text may be too small on mobile screens.", "Increase rendered text height while preserving safe margins."))
    if cue.bottom_safe_margin_percent < 8.0:
        severity = 8.0 - cue.bottom_safe_margin_percent
        score -= 18 + severity * 2
        defects.append(_defect(cue, "unsafe_bottom_margin", severity, "Platform controls may cover the caption.", "Move the caption into the protected vertical safe area."))
    if cue.important_visual_overlap:
        score -= 24
        defects.append(_defect(cue, "focal_visual_overlap", 5.0, "The caption covers the evidence or focal action.", "Reposition the caption or recompose the shot around a clear caption zone."))
    if cue.speaker_overlap:
        score -= 10
        defects.append(_defect(cue, "speaker_face_overlap", 2.5, "The caption competes with the speaking character's face.", "Move captions below or beside the face without entering platform-control zones."))
    if cue.hard_line_break_mid_phrase:
        score -= 12
        defects.append(_defect(cue, "semantic_line_break", 2.5, "The line break splits a phrase that should be read together.", "Break after punctuation, clauses, or complete noun and verb phrases."))
    if cue.emphasized_word_count > 3:
        severity = cue.emphasized_word_count - 3
        score -= min(15, severity * 4)
        defects.append(_defect(cue, "emphasis_overload", severity, "Too many emphasized words flatten the hierarchy.", "Emphasize only the single word or number carrying the beat's turn."))

    return CueReadability(cue.cue_id, round(cps, 2), round(max(0.0, score), 2), tuple(sorted(defects, key=lambda item: item.severity, reverse=True)))


def analyze_caption_readability(cues: Iterable[CaptionCue]) -> CaptionReadabilityReport:
    ordered = sorted(tuple(cues), key=lambda cue: (cue.start_seconds, cue.cue_id))
    if not ordered:
        raise ValueError("at least one caption cue is required")
    ids = [cue.cue_id for cue in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate cue_id")
    for previous, current in zip(ordered, ordered[1:]):
        if current.start_seconds < previous.end_seconds - 0.001:
            raise ValueError("caption cues cannot overlap")

    reports = tuple(evaluate_caption(cue) for cue in ordered)
    unreadable = tuple(report.cue_id for report in reports if report.score < 55)
    safe_area = tuple(
        cue.cue_id
        for cue in ordered
        if cue.bottom_safe_margin_percent < 8.0 or cue.important_visual_overlap or cue.speaker_overlap
    )
    average_score = round(mean(report.score for report in reports), 2)
    minimum_score = round(min(report.score for report in reports), 2)

    repairs: list[str] = []
    codes = {defect.code for report in reports for defect in report.defects}
    if "reading_speed_excess" in codes or "reading_speed_high" in codes:
        repairs.append("reduce caption reading speed before adding visual decoration")
    if "unsafe_bottom_margin" in codes:
        repairs.append("move all cues into the mobile platform safe area")
    if "focal_visual_overlap" in codes:
        repairs.append("reserve a caption zone during scene composition")
    if "insufficient_contrast" in codes:
        repairs.append("use a consistent high-contrast caption treatment")
    if "semantic_line_break" in codes:
        repairs.append("rebreak captions by meaning rather than character count alone")

    if minimum_score < 35 or len(unreadable) >= max(2, len(reports) // 3):
        decision = CaptionDecision.BLOCK
    elif minimum_score < 70 or average_score < 78:
        decision = CaptionDecision.REVISE
    else:
        decision = CaptionDecision.PASS

    return CaptionReadabilityReport(decision, average_score, minimum_score, unreadable, safe_area, reports, tuple(dict.fromkeys(repairs)))
