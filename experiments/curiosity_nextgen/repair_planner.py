from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Iterable


class DefectType(str, Enum):
    HOOK = "hook"
    MEDIA_RELEVANCE = "media_relevance"
    REPETITION = "repetition"
    EMOTIONAL = "emotional"
    INFORMATION_DENSITY = "information_density"
    PACING = "pacing"
    PAYOFF = "payoff"
    FACTUAL = "factual"
    TECHNICAL = "technical"


class Severity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    BLOCKING = 4


class RepairAction(str, Enum):
    REWRITE_HOOK = "rewrite_hook"
    REPLACE_MEDIA = "replace_media"
    CHANGE_VISUAL_FAMILY = "change_visual_family"
    ADD_CHARACTER_BEAT = "add_character_beat"
    SPLIT_BEAT = "split_beat"
    RETIME_SCENE = "retime_scene"
    REBUILD_PAYOFF = "rebuild_payoff"
    CORRECT_OR_REMOVE_CLAIM = "correct_or_remove_claim"
    REBUILD_SCENE = "rebuild_scene"
    HUMAN_REAUTHOR = "human_reauthor"


@dataclass(frozen=True)
class DefectEvidence:
    defect_id: str
    beat_id: str
    defect_type: DefectType
    severity: Severity
    evidence: str
    location_seconds: float | None = None
    previous_actions: tuple[RepairAction, ...] = ()
    repair_round: int = 0


@dataclass(frozen=True)
class RepairStep:
    defect_id: str
    beat_id: str
    action: RepairAction
    priority: int
    rationale: str


@dataclass(frozen=True)
class RepairPlan:
    steps: tuple[RepairStep, ...]
    requires_human_reauthor: bool
    quarantine: bool
    reasons: tuple[str, ...]


_DEFAULT_ACTIONS: dict[DefectType, tuple[RepairAction, ...]] = {
    DefectType.HOOK: (RepairAction.REWRITE_HOOK, RepairAction.REBUILD_SCENE),
    DefectType.MEDIA_RELEVANCE: (RepairAction.REPLACE_MEDIA, RepairAction.REBUILD_SCENE),
    DefectType.REPETITION: (RepairAction.CHANGE_VISUAL_FAMILY, RepairAction.REBUILD_SCENE),
    DefectType.EMOTIONAL: (RepairAction.ADD_CHARACTER_BEAT, RepairAction.REBUILD_SCENE),
    DefectType.INFORMATION_DENSITY: (RepairAction.SPLIT_BEAT, RepairAction.REBUILD_SCENE),
    DefectType.PACING: (RepairAction.RETIME_SCENE, RepairAction.SPLIT_BEAT),
    DefectType.PAYOFF: (RepairAction.REBUILD_PAYOFF, RepairAction.REBUILD_SCENE),
    DefectType.FACTUAL: (RepairAction.CORRECT_OR_REMOVE_CLAIM,),
    DefectType.TECHNICAL: (RepairAction.REBUILD_SCENE,),
}


def _choose_action(defect: DefectEvidence) -> RepairAction:
    if defect.repair_round >= 2:
        return RepairAction.HUMAN_REAUTHOR
    for action in _DEFAULT_ACTIONS[defect.defect_type]:
        if action not in defect.previous_actions:
            return action
    return RepairAction.HUMAN_REAUTHOR


def _priority(defect: DefectEvidence) -> int:
    score = int(defect.severity) * 100
    if defect.location_seconds is not None and defect.location_seconds <= 30:
        score += 40
    if defect.defect_type in {DefectType.HOOK, DefectType.PAYOFF, DefectType.FACTUAL}:
        score += 25
    score += defect.repair_round * 10
    return score


def plan_repairs(defects: Iterable[DefectEvidence]) -> RepairPlan:
    unique: dict[str, DefectEvidence] = {}
    for defect in defects:
        current = unique.get(defect.defect_id)
        if current is None or _priority(defect) > _priority(current):
            unique[defect.defect_id] = defect

    steps: list[RepairStep] = []
    reasons: list[str] = []
    requires_human = False
    quarantine = False

    for defect in unique.values():
        action = _choose_action(defect)
        if action is RepairAction.HUMAN_REAUTHOR:
            requires_human = True
            quarantine = True
            reasons.append(f"repair_exhausted:{defect.defect_id}")
        if defect.severity is Severity.BLOCKING:
            quarantine = True
            reasons.append(f"blocking_defect:{defect.defect_id}")
        steps.append(
            RepairStep(
                defect_id=defect.defect_id,
                beat_id=defect.beat_id,
                action=action,
                priority=_priority(defect),
                rationale=f"{defect.defect_type.value}: {defect.evidence.strip()}",
            )
        )

    steps.sort(key=lambda step: (-step.priority, step.beat_id, step.defect_id))
    return RepairPlan(tuple(steps), requires_human, quarantine, tuple(sorted(set(reasons))))
