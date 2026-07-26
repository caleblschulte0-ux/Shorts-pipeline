from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ContinuityDecision(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    BLOCK = "block"


@dataclass(frozen=True)
class ContinuityShot:
    shot_id: str
    order: int
    subject_id: str
    location: str
    geography: str
    era: str
    time_of_day: str
    wardrobe: str
    dominant_prop: str
    screen_direction: str
    lighting_family: str
    factual_context: str
    intentional_break: bool = False
    break_explanation: str = ""

    def __post_init__(self) -> None:
        if not self.shot_id or not self.subject_id:
            raise ValueError("shot_id and subject_id are required")
        if self.order < 0:
            raise ValueError("order cannot be negative")
        if self.intentional_break and not self.break_explanation.strip():
            raise ValueError("intentional continuity breaks require an explanation")


@dataclass(frozen=True)
class ContinuityDefect:
    from_shot: str
    to_shot: str
    code: str
    severity: float
    explanation: str
    repair: str


@dataclass(frozen=True)
class ContinuityReport:
    decision: ContinuityDecision
    score: float
    defects: tuple[ContinuityDefect, ...]
    blocked_transitions: tuple[tuple[str, str], ...]
    repairs: tuple[str, ...]


def _defect(previous: ContinuityShot, current: ContinuityShot, code: str, severity: float, explanation: str, repair: str) -> ContinuityDefect:
    return ContinuityDefect(previous.shot_id, current.shot_id, code, severity, explanation, repair)


def _changed(previous: ContinuityShot, current: ContinuityShot, attribute: str) -> bool:
    return getattr(previous, attribute).strip().lower() != getattr(current, attribute).strip().lower()


def analyze_continuity(shots: Iterable[ContinuityShot]) -> ContinuityReport:
    ordered = sorted(tuple(shots), key=lambda shot: (shot.order, shot.shot_id))
    if len(ordered) < 2:
        raise ValueError("at least two continuity shots are required")
    ids = [shot.shot_id for shot in ordered]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate shot_id")
    orders = [shot.order for shot in ordered]
    if len(orders) != len(set(orders)):
        raise ValueError("duplicate shot order")

    defects: list[ContinuityDefect] = []
    for previous, current in zip(ordered, ordered[1:]):
        if current.intentional_break:
            continue

        same_subject = previous.subject_id == current.subject_id
        same_context = previous.factual_context == current.factual_context

        if same_subject and _changed(previous, current, "wardrobe"):
            defects.append(_defect(previous, current, "wardrobe_jump", 4.0, "The same subject changes wardrobe without a motivated transition.", "Restore wardrobe continuity or insert a clear time/location transition."))
        if same_subject and _changed(previous, current, "dominant_prop") and previous.dominant_prop and current.dominant_prop:
            defects.append(_defect(previous, current, "prop_jump", 2.5, "The subject's dominant prop changes without visible handoff or explanation.", "Show the prop transfer, removal, or replacement."))
        if same_context and _changed(previous, current, "geography"):
            defects.append(_defect(previous, current, "geography_mismatch", 5.0, "The visual geography changes while the factual context remains the same.", "Use region-appropriate media or explicitly label the shot as illustrative."))
        if same_context and _changed(previous, current, "era"):
            defects.append(_defect(previous, current, "era_mismatch", 5.0, "The shot changes historical era without signaling a time jump.", "Use era-correct media or add an explicit reconstruction/time transition."))
        if previous.location == current.location and _changed(previous, current, "time_of_day"):
            defects.append(_defect(previous, current, "time_of_day_jump", 3.0, "Lighting implies a large time jump inside the same location.", "Match the lighting/time treatment or motivate the passage of time."))
        if previous.location == current.location and _changed(previous, current, "lighting_family"):
            defects.append(_defect(previous, current, "lighting_discontinuity", 2.0, "Lighting style changes abruptly within the same place.", "Normalize exposure and color temperature or use a motivated transition."))
        directions = {previous.screen_direction.lower(), current.screen_direction.lower()}
        if directions == {"left", "right"} and same_subject:
            defects.append(_defect(previous, current, "screen_direction_flip", 2.5, "The subject reverses screen direction without a neutral reset.", "Insert a neutral shot, motivated turn, or maintain the established direction."))
        if _changed(previous, current, "factual_context") and previous.location == current.location and previous.subject_id == current.subject_id:
            defects.append(_defect(previous, current, "context_change_without_signal", 3.5, "The factual example changes while the visual setup appears continuous.", "Mark the new example with a visual, narration, or chapter transition."))

    score = max(0.0, 100.0 - sum(defect.severity * 6.0 for defect in defects))
    blocked = tuple((defect.from_shot, defect.to_shot) for defect in defects if defect.severity >= 5.0)
    repairs = tuple(dict.fromkeys(defect.repair for defect in sorted(defects, key=lambda item: item.severity, reverse=True)))

    if blocked or score < 45:
        decision = ContinuityDecision.BLOCK
    elif defects or score < 80:
        decision = ContinuityDecision.REVISE
    else:
        decision = ContinuityDecision.PASS

    return ContinuityReport(decision, round(score, 2), tuple(defects), blocked, repairs)
