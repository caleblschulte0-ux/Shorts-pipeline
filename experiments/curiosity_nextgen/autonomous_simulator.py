"""Dormant deterministic simulator for heterogeneous autonomous story batches."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class SimulatedStory:
    story_id: str
    topic_family: str
    format_family: str
    factual_risk: str
    estimated_stage_cost: float = 1.0

    def __post_init__(self) -> None:
        if not self.story_id or not self.topic_family or not self.format_family:
            raise ValueError("story identity and families are required")
        if self.factual_risk not in {"low", "medium", "high"}:
            raise ValueError("invalid factual_risk")
        if self.estimated_stage_cost <= 0:
            raise ValueError("estimated_stage_cost must be positive")


@dataclass(frozen=True)
class InjectedFault:
    story_id: str
    stage: str
    category: str
    occurrences: int = 1

    def __post_init__(self) -> None:
        if self.occurrences < 1:
            raise ValueError("occurrences must be positive")
        if self.category not in {"transient", "factual", "repairable", "fatal", "missing_evidence"}:
            raise ValueError("unsupported fault category")


@dataclass(frozen=True)
class SimulationPolicy:
    stages: tuple[str, ...]
    maximum_stories: int = 50
    maximum_attempts_per_stage: int = 3
    maximum_repairs_per_story: int = 2
    maximum_total_cost: float = 5_000.0
    minimum_completion_rate: float = 0.90
    maximum_quarantine_rate: float = 0.10

    def __post_init__(self) -> None:
        if not self.stages or len(set(self.stages)) != len(self.stages):
            raise ValueError("stages must be nonempty and unique")
        if not 1 <= self.maximum_stories <= 50:
            raise ValueError("maximum_stories must be between 1 and 50")
        if self.maximum_attempts_per_stage < 1 or self.maximum_repairs_per_story < 0:
            raise ValueError("invalid recovery limits")
        if self.maximum_total_cost <= 0:
            raise ValueError("maximum_total_cost must be positive")
        if not 0 <= self.minimum_completion_rate <= 1 or not 0 <= self.maximum_quarantine_rate <= 1:
            raise ValueError("rate thresholds must be between 0 and 1")


@dataclass(frozen=True)
class StorySimulationResult:
    story_id: str
    status: str
    completed_stages: tuple[str, ...]
    attempts: tuple[tuple[str, int], ...]
    repairs: int
    cost: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class BatchSimulationResult:
    stories: tuple[StorySimulationResult, ...]
    completed_count: int
    quarantined_count: int
    held_count: int
    total_cost: float
    valid: bool
    blockers: tuple[str, ...]


def simulate_batch(
    stories: Iterable[SimulatedStory],
    faults: Iterable[InjectedFault],
    policy: SimulationPolicy,
) -> BatchSimulationResult:
    story_items = tuple(stories)
    if len(story_items) > policy.maximum_stories:
        raise ValueError("story capacity exceeded")
    if len({story.story_id for story in story_items}) != len(story_items):
        raise ValueError("duplicate story_id")

    fault_budget: dict[tuple[str, str, str], int] = {}
    for fault in faults:
        key = (fault.story_id, fault.stage, fault.category)
        fault_budget[key] = fault_budget.get(key, 0) + fault.occurrences

    results: list[StorySimulationResult] = []
    total_cost = 0.0
    batch_budget_exhausted = False

    for story in sorted(story_items, key=lambda item: item.story_id):
        completed: list[str] = []
        attempts: dict[str, int] = {}
        reasons: list[str] = []
        repairs = 0
        status = "running"
        story_cost = 0.0
        stage_index = 0

        while stage_index < len(policy.stages):
            stage = policy.stages[stage_index]
            attempts[stage] = attempts.get(stage, 0) + 1
            story_cost += story.estimated_stage_cost
            total_cost += story.estimated_stage_cost
            if total_cost > policy.maximum_total_cost:
                status = "held"
                reasons.append("batch_budget_exhausted")
                batch_budget_exhausted = True
                break

            active_category: str | None = None
            for category in ("fatal", "factual", "repairable", "missing_evidence", "transient"):
                key = (story.story_id, stage, category)
                if fault_budget.get(key, 0) > 0:
                    active_category = category
                    fault_budget[key] -= 1
                    break

            if active_category is None:
                completed.append(stage)
                stage_index += 1
                continue
            if active_category == "fatal":
                status = "quarantined"
                reasons.append(f"fatal:{stage}")
                break
            if active_category == "missing_evidence":
                status = "held"
                reasons.append(f"missing_evidence:{stage}")
                break
            if active_category == "factual":
                research_index = policy.stages.index("research") if "research" in policy.stages else 0
                completed = completed[:research_index]
                stage_index = research_index
                reasons.append(f"factual_rewind:{stage}")
                if attempts[stage] >= policy.maximum_attempts_per_stage:
                    status = "quarantined"
                    reasons.append(f"factual_attempts_exhausted:{stage}")
                    break
                continue
            if active_category == "repairable":
                repairs += 1
                reasons.append(f"repair:{stage}")
                if repairs > policy.maximum_repairs_per_story:
                    status = "quarantined"
                    reasons.append("repair_budget_exhausted")
                    break
                continue
            if active_category == "transient":
                reasons.append(f"retry:{stage}")
                if attempts[stage] >= policy.maximum_attempts_per_stage:
                    status = "quarantined"
                    reasons.append(f"attempts_exhausted:{stage}")
                    break
                continue

        if stage_index >= len(policy.stages):
            status = "completed"
        results.append(
            StorySimulationResult(
                story_id=story.story_id,
                status=status,
                completed_stages=tuple(completed),
                attempts=tuple(sorted(attempts.items())),
                repairs=repairs,
                cost=round(story_cost, 3),
                reasons=tuple(reasons),
            )
        )
        if batch_budget_exhausted:
            remaining_ids = {item.story_id for item in story_items} - {item.story_id for item in results}
            for story_id in sorted(remaining_ids):
                results.append(
                    StorySimulationResult(
                        story_id=story_id,
                        status="held",
                        completed_stages=(),
                        attempts=(),
                        repairs=0,
                        cost=0.0,
                        reasons=("batch_budget_exhausted",),
                    )
                )
            break

    completed_count = sum(item.status == "completed" for item in results)
    quarantined_count = sum(item.status == "quarantined" for item in results)
    held_count = sum(item.status == "held" for item in results)
    denominator = max(1, len(results))
    completion_rate = completed_count / denominator
    quarantine_rate = quarantined_count / denominator
    blockers: list[str] = []
    if completion_rate < policy.minimum_completion_rate:
        blockers.append("completion_rate_below_floor")
    if quarantine_rate > policy.maximum_quarantine_rate:
        blockers.append("quarantine_rate_above_ceiling")
    if held_count:
        blockers.append("held_stories_remaining")
    if total_cost > policy.maximum_total_cost:
        blockers.append("total_cost_exceeded")

    return BatchSimulationResult(
        stories=tuple(sorted(results, key=lambda item: item.story_id)),
        completed_count=completed_count,
        quarantined_count=quarantined_count,
        held_count=held_count,
        total_cost=round(total_cost, 3),
        valid=not blockers,
        blockers=tuple(blockers),
    )
