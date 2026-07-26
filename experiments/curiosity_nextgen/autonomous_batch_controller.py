from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from .autonomous_decision_engine import (
    AutonomousDecision,
    DecisionPolicy,
    NextAction,
    StageOutcome,
    StoryDecisionState,
    decide_next_action,
)
from .production_stage_graph import ProductionGraph, StageName
from .story_intake_contract import StoryBrief


class RunState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    HELD = "held"
    QUARANTINED = "quarantined"
    COMPLETE = "complete"


@dataclass(frozen=True)
class BatchPolicy:
    maximum_stories: int = 50
    maximum_active_stories: int = 8
    maximum_total_cost: float = 500.0
    maximum_cost_per_story: float = 25.0
    maximum_concurrent_per_topic: int = 3
    maximum_concurrent_per_format: int = 4
    maximum_quarantine_share: float = 0.25

    def __post_init__(self) -> None:
        if not 1 <= self.maximum_stories <= 50:
            raise ValueError("maximum_stories must be between 1 and 50")
        if not 1 <= self.maximum_active_stories <= self.maximum_stories:
            raise ValueError("maximum_active_stories must fit within story capacity")
        if self.maximum_total_cost <= 0 or self.maximum_cost_per_story <= 0:
            raise ValueError("cost budgets must be positive")
        if self.maximum_concurrent_per_topic < 1 or self.maximum_concurrent_per_format < 1:
            raise ValueError("family concurrency limits must be positive")
        if not 0 <= self.maximum_quarantine_share <= 1:
            raise ValueError("maximum_quarantine_share must be between 0 and 1")


@dataclass
class StoryRun:
    brief: StoryBrief
    state: RunState = RunState.PENDING
    completed: set[StageName] = field(default_factory=set)
    in_progress: set[StageName] = field(default_factory=set)
    attempts: dict[StageName, int] = field(default_factory=dict)
    repair_count: int = 0
    reauthor_count: int = 0
    cost_spent: float = 0.0
    hold_reason: str | None = None
    quarantine_reason: str | None = None
    forced_stages: list[StageName] = field(default_factory=list)
    decision_history: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def story_id(self) -> str:
        return self.brief.story_id


@dataclass(frozen=True)
class WorkAssignment:
    story_id: str
    stage: StageName
    priority: int


@dataclass(frozen=True)
class BatchSnapshot:
    total: int
    pending: int
    active: int
    held: int
    quarantined: int
    complete: int
    total_cost: float
    quarantine_share: float
    healthy: bool
    warnings: tuple[str, ...]


class AutonomousBatchController:
    def __init__(
        self,
        graph: ProductionGraph,
        *,
        batch_policy: BatchPolicy = BatchPolicy(),
        decision_policy: DecisionPolicy = DecisionPolicy(),
    ) -> None:
        self.graph = graph
        self.batch_policy = batch_policy
        self.decision_policy = decision_policy
        self._runs: dict[str, StoryRun] = {}

    def register(self, briefs: Iterable[StoryBrief]) -> None:
        items = tuple(briefs)
        if len(self._runs) + len(items) > self.batch_policy.maximum_stories:
            raise ValueError("batch registration exceeds story capacity")
        for brief in items:
            if brief.story_id in self._runs:
                raise ValueError(f"duplicate story_id: {brief.story_id}")
            self._runs[brief.story_id] = StoryRun(brief)

    def get(self, story_id: str) -> StoryRun:
        return self._runs[story_id]

    @property
    def total_cost(self) -> float:
        return round(sum(run.cost_spent for run in self._runs.values()), 3)

    def admit_pending(self) -> tuple[str, ...]:
        active = [run for run in self._runs.values() if run.state is RunState.ACTIVE]
        slots = self.batch_policy.maximum_active_stories - len(active)
        if slots <= 0:
            return ()
        topic_counts: dict[str, int] = {}
        format_counts: dict[str, int] = {}
        for run in active:
            topic_counts[run.brief.topic_family] = topic_counts.get(run.brief.topic_family, 0) + 1
            format_counts[run.brief.format_family] = format_counts.get(run.brief.format_family, 0) + 1

        admitted: list[str] = []
        candidates = sorted(
            (run for run in self._runs.values() if run.state is RunState.PENDING),
            key=lambda run: (-run.brief.priority, not run.brief.exploration, run.story_id),
        )
        for run in candidates:
            if len(admitted) >= slots or self.total_cost >= self.batch_policy.maximum_total_cost:
                break
            if topic_counts.get(run.brief.topic_family, 0) >= self.batch_policy.maximum_concurrent_per_topic:
                continue
            if format_counts.get(run.brief.format_family, 0) >= self.batch_policy.maximum_concurrent_per_format:
                continue
            run.state = RunState.ACTIVE
            admitted.append(run.story_id)
            topic_counts[run.brief.topic_family] = topic_counts.get(run.brief.topic_family, 0) + 1
            format_counts[run.brief.format_family] = format_counts.get(run.brief.format_family, 0) + 1
        return tuple(admitted)

    def claim_work(self, stage_capacities: dict[StageName, int]) -> tuple[WorkAssignment, ...]:
        if any(capacity < 0 for capacity in stage_capacities.values()):
            raise ValueError("stage capacity cannot be negative")
        assignments: list[WorkAssignment] = []
        remaining = dict(stage_capacities)
        runs = sorted(
            (run for run in self._runs.values() if run.state is RunState.ACTIVE),
            key=lambda run: (-run.brief.priority, sum(run.attempts.values()), run.story_id),
        )
        for run in runs:
            ready: list[StageName] = []
            if run.forced_stages:
                ready.append(run.forced_stages[0])
            ready.extend(stage for stage in self.graph.ready_stages(run.completed, run.in_progress) if stage not in ready)
            for stage in ready:
                if remaining.get(stage, 0) <= 0:
                    continue
                run.in_progress.add(stage)
                remaining[stage] -= 1
                assignments.append(WorkAssignment(run.story_id, stage, run.brief.priority))
                if stage in run.forced_stages:
                    run.forced_stages.remove(stage)
                break
        return tuple(assignments)

    def record_outcome(self, outcome: StageOutcome) -> AutonomousDecision:
        run = self.get(outcome.story_id)
        if run.state is not RunState.ACTIVE:
            raise ValueError("outcomes can only be recorded for active stories")
        if outcome.stage not in run.in_progress:
            raise ValueError("outcome stage was not claimed")
        run.in_progress.remove(outcome.stage)
        run.attempts[outcome.stage] = run.attempts.get(outcome.stage, 0) + 1
        run.cost_spent += outcome.cost_delta

        decision = decide_next_action(
            outcome,
            StoryDecisionState(
                stage_attempts=run.attempts[outcome.stage] - 1,
                repair_count=run.repair_count,
                reauthor_count=run.reauthor_count,
            ),
            self.decision_policy,
        )
        run.decision_history.append((outcome.stage.value, decision.action.value, decision.reason))

        if run.cost_spent > self.batch_policy.maximum_cost_per_story:
            self._quarantine(run, "per_story_cost_budget_exceeded")
            return AutonomousDecision(NextAction.QUARANTINE, "per_story_cost_budget_exceeded")
        if self.total_cost > self.batch_policy.maximum_total_cost:
            self._quarantine(run, "batch_cost_budget_exceeded")
            return AutonomousDecision(NextAction.QUARANTINE, "batch_cost_budget_exceeded")

        if decision.action is NextAction.ADVANCE:
            run.completed.add(outcome.stage)
            if outcome.stage is StageName.PUBLISH:
                run.state = RunState.COMPLETE
        elif decision.action is NextAction.RETRY_STAGE:
            pass
        elif decision.action is NextAction.WAIT_FOR_EVIDENCE:
            run.state = RunState.HELD
            run.hold_reason = decision.reason
        elif decision.action is NextAction.RESEARCH_MORE:
            self._rewind(run, StageName.RESEARCH)
        elif decision.action is NextAction.REAUTHOR:
            run.reauthor_count += 1
            self._rewind(run, StageName.SCRIPT)
        elif decision.action is NextAction.REPAIR:
            run.repair_count += 1
            run.completed.add(outcome.stage)
            if StageName.REPAIR not in run.completed and StageName.REPAIR not in run.forced_stages:
                run.forced_stages.append(StageName.REPAIR)
        elif decision.action is NextAction.QUARANTINE:
            self._quarantine(run, decision.reason)
        return decision

    def resume_held(self, story_id: str) -> None:
        run = self.get(story_id)
        if run.state is not RunState.HELD:
            raise ValueError("story is not held")
        run.state = RunState.ACTIVE
        run.hold_reason = None

    def _rewind(self, run: StoryRun, target: StageName) -> None:
        descendants = set(self.graph.descendants(target))
        run.completed.difference_update(descendants | {target})
        run.in_progress.clear()
        run.forced_stages.clear()
        run.state = RunState.ACTIVE

    @staticmethod
    def _quarantine(run: StoryRun, reason: str) -> None:
        run.state = RunState.QUARANTINED
        run.quarantine_reason = reason
        run.in_progress.clear()
        run.forced_stages.clear()

    def snapshot(self) -> BatchSnapshot:
        counts = {state: 0 for state in RunState}
        for run in self._runs.values():
            counts[run.state] += 1
        total = len(self._runs)
        quarantine_share = counts[RunState.QUARANTINED] / total if total else 0.0
        warnings: list[str] = []
        if quarantine_share > self.batch_policy.maximum_quarantine_share:
            warnings.append("quarantine_share_exceeds_policy")
        if self.total_cost > self.batch_policy.maximum_total_cost:
            warnings.append("batch_cost_exceeded")
        if total == 0:
            warnings.append("empty_batch")
        return BatchSnapshot(
            total=total,
            pending=counts[RunState.PENDING],
            active=counts[RunState.ACTIVE],
            held=counts[RunState.HELD],
            quarantined=counts[RunState.QUARANTINED],
            complete=counts[RunState.COMPLETE],
            total_cost=self.total_cost,
            quarantine_share=round(quarantine_share, 4),
            healthy=not warnings,
            warnings=tuple(warnings),
        )

    def audit_invariants(self) -> tuple[str, ...]:
        defects: list[str] = []
        if len(self._runs) > self.batch_policy.maximum_stories:
            defects.append("story_capacity_exceeded")
        if sum(run.state is RunState.ACTIVE for run in self._runs.values()) > self.batch_policy.maximum_active_stories:
            defects.append("active_capacity_exceeded")
        for run in self._runs.values():
            if run.completed & run.in_progress:
                defects.append(f"{run.story_id}:stage_both_complete_and_in_progress")
            if run.state in {RunState.QUARANTINED, RunState.COMPLETE} and run.in_progress:
                defects.append(f"{run.story_id}:terminal_story_has_in_progress_work")
            if run.cost_spent < 0:
                defects.append(f"{run.story_id}:negative_cost")
        return tuple(sorted(defects))
