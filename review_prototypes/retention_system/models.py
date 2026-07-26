from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence


class HookStrategy(str, Enum):
    CONSEQUENCE_FIRST = "consequence_first"
    CONTRADICTION = "contradiction"
    SCALE_REVEAL = "scale_reveal"
    FAILED_ATTEMPT = "failed_attempt"


@dataclass(frozen=True)
class HookPlan:
    hook_id: str
    strategy: HookStrategy
    spoken_line: str
    visual_action: str
    promise: str
    number_present: bool
    action_start_seconds: float
    reveal_seconds: float
    pattern_key: str

    def validate(self) -> None:
        if not self.hook_id or not self.spoken_line or not self.visual_action:
            raise ValueError("hook requires id, spoken line, and visual action")
        if not self.promise.strip():
            raise ValueError("hook requires an explicit viewer promise")
        if self.action_start_seconds < 0 or self.reveal_seconds < 0:
            raise ValueError("hook timing cannot be negative")
        if self.action_start_seconds > 0.5:
            raise ValueError("hook action must begin by 0.5 seconds")
        if self.reveal_seconds > 1.5:
            raise ValueError("hook core reveal must land by 1.5 seconds")


@dataclass(frozen=True)
class Beat:
    beat_id: str
    start_seconds: float
    end_seconds: float
    role: str
    new_information: str
    visual_change: str
    mascot_action: str
    tension: float
    static_hold_seconds: float = 0.0
    caption_density: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_seconds - self.start_seconds

    def validate(self) -> None:
        if not self.beat_id:
            raise ValueError("beat requires an id")
        if self.start_seconds < 0 or self.end_seconds <= self.start_seconds:
            raise ValueError(f"invalid beat timing for {self.beat_id}")
        if not self.new_information.strip():
            raise ValueError(f"{self.beat_id} adds no new information")
        if not self.visual_change.strip():
            raise ValueError(f"{self.beat_id} requires a visual change")
        if not 0.0 <= self.tension <= 1.0:
            raise ValueError(f"{self.beat_id} tension must be in [0, 1]")
        if self.static_hold_seconds < 0:
            raise ValueError("static hold cannot be negative")
        if not 0.0 <= self.caption_density <= 1.0:
            raise ValueError("caption density must be in [0, 1]")


@dataclass(frozen=True)
class EndingPlan:
    ending_id: str
    spoken_line: str
    synthesis: str
    consequence: str
    mascot_resolution: str
    visual_payoff: str
    duration_seconds: float
    generic_cta: bool = False

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("ending_id", self.ending_id),
                ("spoken_line", self.spoken_line),
                ("synthesis", self.synthesis),
                ("consequence", self.consequence),
                ("mascot_resolution", self.mascot_resolution),
                ("visual_payoff", self.visual_payoff),
            )
            if not value.strip()
        ]
        if missing:
            raise ValueError("ending missing: " + ", ".join(missing))
        if not 1.2 <= self.duration_seconds <= 3.0:
            raise ValueError("ending must last between 1.2 and 3.0 seconds")


@dataclass(frozen=True)
class RetentionReport:
    passed: bool
    score: float
    hard_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    dimensions: Mapping[str, float]


@dataclass(frozen=True)
class RetentionPackage:
    story_slug: str
    hook: HookPlan
    beats: tuple[Beat, ...]
    ending: EndingPlan
    report: RetentionReport
    version: str = "retention-v1"

    def validate(self) -> None:
        if not self.story_slug:
            raise ValueError("retention package requires story slug")
        self.hook.validate()
        self.ending.validate()
        if len(self.beats) < 3:
            raise ValueError("retention package requires at least three beats")
        previous_end = 0.0
        for beat in self.beats:
            beat.validate()
            if beat.start_seconds < previous_end - 1e-6:
                raise ValueError("beats overlap or are out of order")
            previous_end = beat.end_seconds
        if not self.report.passed:
            raise ValueError("cannot validate a failed retention package")


def total_duration(beats: Sequence[Beat], ending: EndingPlan) -> float:
    return max((beat.end_seconds for beat in beats), default=0.0) + ending.duration_seconds
