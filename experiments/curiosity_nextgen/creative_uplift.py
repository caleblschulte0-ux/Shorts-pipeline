from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class CreativeArea(str, Enum):
    HOOK = "hook"
    MEDIA = "media"
    VISUAL_VARIETY = "visual_variety"
    PACING = "pacing"
    PERSONALITY = "personality"
    PAYOFF = "payoff"
    CONTINUITY = "continuity"


@dataclass(frozen=True)
class CreativeSignal:
    signal_id: str
    area: CreativeArea
    description: str
    recommended_action: str
    severity: float
    expected_score_gain: float
    confidence: float
    estimated_effort: float
    target_ids: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    acceptance_checks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.signal_id.strip() or not self.description.strip() or not self.recommended_action.strip():
            raise ValueError("signal_id, description, and recommended_action are required")
        if not 0 <= self.severity <= 10:
            raise ValueError("severity must be between 0 and 10")
        if not 0 <= self.expected_score_gain <= 10:
            raise ValueError("expected_score_gain must be between 0 and 10")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.estimated_effort <= 0:
            raise ValueError("estimated_effort must be positive")


@dataclass(frozen=True)
class CreativeTask:
    task_id: str
    area: CreativeArea
    description: str
    expected_score_gain: float
    confidence: float
    estimated_effort: float
    target_beats: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    acceptance_checks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.description.strip():
            raise ValueError("task_id and description are required")
        if not 0 <= self.expected_score_gain <= 10:
            raise ValueError("expected_score_gain must be between 0 and 10")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.estimated_effort <= 0:
            raise ValueError("estimated_effort must be positive")

    @property
    def leverage(self) -> float:
        return self.expected_score_gain * self.confidence / self.estimated_effort


@dataclass(frozen=True)
class UpliftPlan:
    ordered_tasks: tuple[CreativeTask, ...]
    projected_score_gain: float
    projected_overall_score: float
    blocked_tasks: tuple[str, ...]
    coverage: dict[str, int]


def tasks_from_signals(
    signals: Iterable[CreativeSignal],
    *,
    minimum_severity: float = 0.0,
) -> tuple[CreativeTask, ...]:
    """Convert arbitrary story-analysis findings into story-agnostic repair tasks."""
    if not 0 <= minimum_severity <= 10:
        raise ValueError("minimum_severity must be between 0 and 10")

    by_id: dict[str, CreativeSignal] = {}
    for signal in signals:
        if signal.signal_id in by_id:
            raise ValueError(f"duplicate signal_id: {signal.signal_id}")
        by_id[signal.signal_id] = signal

    unknown_dependencies = sorted(
        dependency
        for signal in by_id.values()
        for dependency in signal.depends_on
        if dependency not in by_id
    )
    if unknown_dependencies:
        raise ValueError("unknown signal dependencies: " + ", ".join(unknown_dependencies))

    tasks = []
    for signal in by_id.values():
        if signal.severity < minimum_severity:
            continue
        tasks.append(
            CreativeTask(
                task_id=signal.signal_id,
                area=signal.area,
                description=signal.recommended_action,
                expected_score_gain=signal.expected_score_gain,
                confidence=signal.confidence,
                estimated_effort=signal.estimated_effort,
                target_beats=signal.target_ids,
                depends_on=signal.depends_on,
                acceptance_checks=signal.acceptance_checks,
            )
        )
    return tuple(sorted(tasks, key=lambda task: task.task_id))


def plan_uplift(
    tasks: Iterable[CreativeTask],
    *,
    current_score: float,
    effort_budget: float,
) -> UpliftPlan:
    if not 0 <= current_score <= 10:
        raise ValueError("current_score must be between 0 and 10")
    if effort_budget <= 0:
        raise ValueError("effort_budget must be positive")

    by_id: dict[str, CreativeTask] = {}
    for task in tasks:
        if task.task_id in by_id:
            raise ValueError(f"duplicate task_id: {task.task_id}")
        by_id[task.task_id] = task

    unknown_dependencies = sorted(
        dependency
        for task in by_id.values()
        for dependency in task.depends_on
        if dependency not in by_id
    )
    if unknown_dependencies:
        raise ValueError("unknown dependencies: " + ", ".join(unknown_dependencies))

    remaining = set(by_id)
    selected: list[CreativeTask] = []
    selected_ids: set[str] = set()
    spent = 0.0

    while remaining:
        eligible = [
            by_id[task_id]
            for task_id in remaining
            if set(by_id[task_id].depends_on).issubset(selected_ids)
        ]
        if not eligible:
            break
        eligible.sort(key=lambda task: (-task.leverage, -task.expected_score_gain, task.estimated_effort, task.task_id))
        progressed = False
        for task in eligible:
            if spent + task.estimated_effort <= effort_budget:
                selected.append(task)
                selected_ids.add(task.task_id)
                remaining.remove(task.task_id)
                spent += task.estimated_effort
                progressed = True
                break
            remaining.remove(task.task_id)
            progressed = True
        if not progressed:
            break

    projected_gain = sum(task.expected_score_gain * task.confidence for task in selected)
    coverage: dict[str, int] = {}
    for task in selected:
        coverage[task.area.value] = coverage.get(task.area.value, 0) + 1

    return UpliftPlan(
        ordered_tasks=tuple(selected),
        projected_score_gain=round(projected_gain, 3),
        projected_overall_score=round(min(10.0, current_score + projected_gain), 3),
        blocked_tasks=tuple(sorted(remaining)),
        coverage=dict(sorted(coverage.items())),
    )
