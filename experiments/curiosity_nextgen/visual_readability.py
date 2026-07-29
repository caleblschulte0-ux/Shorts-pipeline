from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean
from typing import Iterable


class ReadabilityDecision(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    BLOCK = "block"


@dataclass(frozen=True)
class FrameReadability:
    frame_id: str
    focal_object_count: int
    competing_object_count: int
    text_element_count: int
    smallest_important_detail_percent: float
    subject_background_contrast: float
    focal_separation: float
    motion_competition: float
    caption_zone_clear: bool
    evidence_legible: bool
    hierarchy_explicit: bool
    decorative_element_count: int = 0

    def __post_init__(self) -> None:
        if not self.frame_id:
            raise ValueError("frame_id is required")
        for name in (
            "focal_object_count",
            "competing_object_count",
            "text_element_count",
            "decorative_element_count",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        for name in (
            "smallest_important_detail_percent",
            "subject_background_contrast",
            "focal_separation",
            "motion_competition",
        ):
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True)
class ReadabilityDefect:
    frame_id: str
    code: str
    severity: float
    explanation: str
    repair: str


@dataclass(frozen=True)
class FrameReport:
    frame_id: str
    score: float
    defects: tuple[ReadabilityDefect, ...]


@dataclass(frozen=True)
class VisualReadabilityReport:
    decision: ReadabilityDecision
    average_score: float
    minimum_score: float
    blocked_frames: tuple[str, ...]
    frame_reports: tuple[FrameReport, ...]
    repairs: tuple[str, ...]


def _defect(frame: FrameReadability, code: str, severity: float, explanation: str, repair: str) -> ReadabilityDefect:
    return ReadabilityDefect(frame.frame_id, code, round(severity, 2), explanation, repair)


def evaluate_frame(frame: FrameReadability) -> FrameReport:
    score = 100.0
    defects: list[ReadabilityDefect] = []

    if frame.focal_object_count == 0:
        score -= 30
        defects.append(_defect(frame, "missing_focal_object", 5.0, "The frame has no obvious first place to look.", "Choose one focal object and suppress secondary elements."))
    elif frame.focal_object_count > 1:
        severity = frame.focal_object_count - 1
        score -= min(25, severity * 10)
        defects.append(_defect(frame, "multiple_focal_objects", severity, "Several elements compete to be the main subject.", "Establish one primary focal object through size, contrast, timing, or position."))

    if frame.competing_object_count > 4:
        severity = frame.competing_object_count - 4
        score -= min(25, severity * 5)
        defects.append(_defect(frame, "object_clutter", severity, "Too many objects compete for attention.", "Remove decorative or redundant objects and reveal supporting items sequentially."))

    if frame.text_element_count > 3:
        severity = frame.text_element_count - 3
        score -= min(22, severity * 6)
        defects.append(_defect(frame, "text_fragmentation", severity, "The viewer must scan too many independent text elements.", "Combine related labels and keep one text hierarchy."))

    if frame.smallest_important_detail_percent < 2.5:
        severity = 2.5 - frame.smallest_important_detail_percent
        score -= 22 + severity * 5
        defects.append(_defect(frame, "important_detail_too_small", severity, "Important evidence may be illegible on a phone screen.", "Crop tighter, enlarge the evidence, or isolate it in a dedicated insert."))

    if frame.subject_background_contrast < 4.0:
        severity = 4.0 - frame.subject_background_contrast
        score -= 18 + severity * 4
        defects.append(_defect(frame, "weak_subject_contrast", severity, "The focal subject blends into the background.", "Increase luminance, color, edge, or depth separation."))

    if frame.focal_separation < 5.0:
        severity = 5.0 - frame.focal_separation
        score -= severity * 4
        defects.append(_defect(frame, "weak_focal_separation", severity, "The focal object is not clearly separated from surrounding elements.", "Use spacing, depth, masking, or local contrast to isolate it."))

    if frame.motion_competition > 6.0:
        severity = frame.motion_competition - 6.0
        score -= severity * 5
        defects.append(_defect(frame, "competing_motion", severity, "Multiple moving elements pull attention away from the intended action.", "Freeze secondary motion or time movements sequentially."))

    if not frame.caption_zone_clear:
        score -= 18
        defects.append(_defect(frame, "caption_zone_blocked", 4.0, "The frame leaves no clean place for captions.", "Recompose the frame with a protected caption zone."))
    if not frame.evidence_legible:
        score -= 28
        defects.append(_defect(frame, "evidence_not_legible", 5.0, "The proof cannot be clearly read or interpreted.", "Use a closer crop, highlight, annotation, or simplified reconstruction."))
    if not frame.hierarchy_explicit:
        score -= 14
        defects.append(_defect(frame, "implicit_hierarchy", 3.0, "The relationship among elements is not visually obvious.", "Show sequence, grouping, direction, or cause-and-effect explicitly."))
    if frame.decorative_element_count > 5:
        severity = frame.decorative_element_count - 5
        score -= min(15, severity * 3)
        defects.append(_defect(frame, "decorative_noise", severity, "Decoration adds scanning cost without supporting the story.", "Remove decorative elements that do not explain, prove, or emotionally strengthen the beat."))

    return FrameReport(frame.frame_id, round(max(0.0, score), 2), tuple(sorted(defects, key=lambda item: item.severity, reverse=True)))


def analyze_visual_readability(frames: Iterable[FrameReadability]) -> VisualReadabilityReport:
    ordered = tuple(frames)
    if not ordered:
        raise ValueError("at least one frame is required")
    ids = [frame.frame_id for frame in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate frame_id")

    reports = tuple(evaluate_frame(frame) for frame in ordered)
    average_score = round(mean(report.score for report in reports), 2)
    minimum_score = round(min(report.score for report in reports), 2)
    blocked = tuple(report.frame_id for report in reports if report.score < 45)
    repairs = tuple(
        dict.fromkeys(
            defect.repair
            for report in sorted(reports, key=lambda item: item.score)
            for defect in report.defects
        )
    )

    if blocked or minimum_score < 35:
        decision = ReadabilityDecision.BLOCK
    elif minimum_score < 72 or average_score < 80:
        decision = ReadabilityDecision.REVISE
    else:
        decision = ReadabilityDecision.PASS

    return VisualReadabilityReport(decision, average_score, minimum_score, blocked, reports, repairs)
