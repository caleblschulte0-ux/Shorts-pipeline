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

    unknown_dependencies = sorted({dependency for task in by_id.values() for dependency in task.depends_on if dependency not in by_id})
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


def money_goes_reference_tasks() -> tuple[CreativeTask, ...]:
    """Known, evidence-backed dormant repair blueprint from the recovery report."""
    return (
        CreativeTask(
            task_id="restore_hook_composition",
            area=CreativeArea.HOOK,
            description="Compare the earlier 8/10 paycheck opening with the current 7/10 version and restore the strongest scale, contrast, readability, and motion without reintroducing clipping.",
            expected_score_gain=0.55,
            confidence=0.78,
            estimated_effort=2.0,
            target_beats=("hook", "paycheck_open"),
            acceptance_checks=("hook_score>=8", "first_visual<=1s", "no_text_clipping"),
        ),
        CreativeTask(
            task_id="replace_transport_media",
            area=CreativeArea.MEDIA,
            description="Replace the Japanese gas-station image with geographically neutral or narratively correct transport media and retain the candidate/rejection trail.",
            expected_score_gain=0.45,
            confidence=0.95,
            estimated_effort=1.0,
            target_beats=("transport",),
            acceptance_checks=("no_wrong_region_asset", "media_relevance>=8"),
        ),
        CreativeTask(
            task_id="upgrade_bill_counting_fallback",
            area=CreativeArea.MEDIA,
            description="Replace the hands-counting-bills statement card with licensed footage, a designed mechanism, or a character interaction that visibly communicates money changing hands.",
            expected_score_gain=0.5,
            confidence=0.85,
            estimated_effort=1.75,
            target_beats=("beat_6",),
            acceptance_checks=("fallback!=degraded", "visible_action", "no_text_only_substitution"),
        ),
        CreativeTask(
            task_id="design_transition_families",
            area=CreativeArea.VISUAL_VARIETY,
            description="Create at least three chapter-transition families tied to chapter meaning rather than repeating the same dark-starfield card.",
            expected_score_gain=0.7,
            confidence=0.9,
            estimated_effort=2.5,
            acceptance_checks=("transition_families>=3", "dominant_family_share<=0.4", "no_consecutive_duplicate_family"),
        ),
        CreativeTask(
            task_id="break_real_media_run",
            area=CreativeArea.PACING,
            description="Break the three-beat real-media run with a meaningful mechanism, comparison, evidence transformation, or character consequence.",
            expected_score_gain=0.35,
            confidence=0.8,
            estimated_effort=1.2,
            target_beats=("beat_17",),
            acceptance_checks=("same_family_run<=2", "novelty_delta>=1.25"),
        ),
        CreativeTask(
            task_id="build_character_attempt_failure_payoff",
            area=CreativeArea.PERSONALITY,
            description="Give the central character a concrete attempt, obstacle, reaction, changed strategy, and callback payoff instead of mostly explanatory staging.",
            expected_score_gain=0.8,
            confidence=0.72,
            estimated_effort=3.0,
            acceptance_checks=("personality>=4/5", "distinct_actions>=3", "state_changes>=2", "callback_resolved"),
        ),
        CreativeTask(
            task_id="strengthen_final_callback",
            area=CreativeArea.PAYOFF,
            description="Return to the opening paycheck image in the final answer and show the exact mechanism and human consequence promised by the hook.",
            expected_score_gain=0.55,
            confidence=0.82,
            estimated_effort=1.75,
            depends_on=("restore_hook_composition",),
            acceptance_checks=("major_question_answered", "visual_callback", "consequence_shown", "payoff>=7.5"),
        ),
    )
