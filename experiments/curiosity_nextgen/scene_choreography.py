from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class CameraMove(str, Enum):
    STATIC = "static"
    PUSH = "push"
    PULL = "pull"
    PAN = "pan"
    TRACK = "track"
    ORBIT = "orbit"
    CUT = "cut"


class ScreenDirection(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    NONE = "none"


@dataclass(frozen=True)
class ChoreographyBeat:
    beat_id: str
    subject_action: str
    camera_move: CameraMove
    movement_direction: ScreenDirection = ScreenDirection.NONE
    duration_seconds: float = 4.0
    focal_change: bool = True
    cause_key: str | None = None
    effect_key: str | None = None
    continuity_reset: bool = False
    character_present: bool = False

    def __post_init__(self) -> None:
        if not self.beat_id.strip() or not self.subject_action.strip():
            raise ValueError("beat_id and subject_action are required")
        if self.duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")


@dataclass(frozen=True)
class ChoreographyDefect:
    code: str
    beat_id: str
    severity: int
    detail: str


@dataclass(frozen=True)
class ChoreographyReport:
    score: float
    defects: tuple[ChoreographyDefect, ...]
    action_counts: dict[str, int]
    camera_counts: dict[str, int]
    purposeful_action_ratio: float


def analyze_choreography(beats: Iterable[ChoreographyBeat]) -> ChoreographyReport:
    items = tuple(beats)
    if len({item.beat_id for item in items}) != len(items):
        raise ValueError("duplicate beat_id")
    if not items:
        return ChoreographyReport(0.0, (ChoreographyDefect("missing_choreography", "story", 4, "no scene actions supplied"),), {}, {}, 0.0)

    defects: list[ChoreographyDefect] = []
    penalty = 0.0
    actions = Counter(item.subject_action.strip().lower() for item in items)
    cameras = Counter(item.camera_move for item in items)

    for action, count in actions.items():
        if count >= 3:
            first = next(item.beat_id for item in items if item.subject_action.strip().lower() == action)
            defects.append(ChoreographyDefect("repeated_subject_action", first, 2, f"'{action}' appears {count} times"))
            penalty += min(1.2, 0.3 * (count - 2))

    for index in range(len(items) - 2):
        window = items[index:index + 3]
        if all(item.camera_move is CameraMove.STATIC for item in window):
            defects.append(ChoreographyDefect("static_camera_run", window[0].beat_id, 3, "three consecutive scenes use a static camera"))
            penalty += 0.8
        if all(not item.focal_change for item in window):
            defects.append(ChoreographyDefect("no_focal_progression", window[0].beat_id, 3, "three scenes retain the same focal target"))
            penalty += 0.7

    previous: ChoreographyBeat | None = None
    for item in items:
        if previous and not item.continuity_reset:
            if (
                previous.movement_direction not in {ScreenDirection.NONE, ScreenDirection.CENTER}
                and item.movement_direction not in {ScreenDirection.NONE, ScreenDirection.CENTER}
                and previous.movement_direction is not item.movement_direction
            ):
                defects.append(ChoreographyDefect("screen_direction_flip", item.beat_id, 2, "movement reverses without a continuity reset"))
                penalty += 0.45
        previous = item

    causes: dict[str, str] = {}
    effects: set[str] = set()
    for item in items:
        if item.cause_key:
            causes[item.cause_key] = item.beat_id
        if item.effect_key:
            effects.add(item.effect_key)
            if item.effect_key not in causes:
                defects.append(ChoreographyDefect("effect_without_setup", item.beat_id, 2, f"effect '{item.effect_key}' has no prior cause"))
                penalty += 0.4
    for key, beat_id in causes.items():
        if key not in effects:
            defects.append(ChoreographyDefect("cause_without_consequence", beat_id, 3, f"cause '{key}' never produces a visible consequence"))
            penalty += 0.7

    purposeful = sum(
        1
        for item in items
        if item.focal_change or item.cause_key or item.effect_key or item.camera_move not in {CameraMove.STATIC, CameraMove.CUT}
    )
    ratio = purposeful / len(items)
    if ratio < 0.6:
        defects.append(ChoreographyDefect("low_purposeful_motion", "story", 3, "too much motion is absent or decorative"))
        penalty += 0.8
    if len(cameras) < 3 and len(items) >= 6:
        defects.append(ChoreographyDefect("limited_camera_vocabulary", "story", 2, "camera language lacks variety"))
        penalty += 0.45

    defects.sort(key=lambda item: (-item.severity, item.beat_id, item.code))
    return ChoreographyReport(
        round(max(0.0, 10.0 - penalty), 3),
        tuple(defects),
        dict(sorted(actions.items())),
        {move.value: count for move, count in sorted(cameras.items(), key=lambda item: item[0].value)},
        round(ratio, 3),
    )
