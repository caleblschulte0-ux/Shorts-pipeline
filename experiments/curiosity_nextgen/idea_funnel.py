"""Dormant generic idea scoring and portfolio admission for up to 50 stories."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class IdeaCandidate:
    candidate_id: str
    premise: str
    topic_family: str
    format_family: str
    duplicate_key: str
    audience_value: float
    novelty: float
    evidence_feasibility: float
    visual_feasibility: float
    sensitivity_risk: float
    estimated_cost: float
    source_count: int
    exploration: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.premise.strip():
            raise ValueError("candidate_id and premise are required")
        if not self.topic_family or not self.format_family or not self.duplicate_key:
            raise ValueError("topic, format, and duplicate key are required")
        for name in (
            "audience_value",
            "novelty",
            "evidence_feasibility",
            "visual_feasibility",
            "sensitivity_risk",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.estimated_cost <= 0:
            raise ValueError("estimated_cost must be positive")
        if self.source_count < 0:
            raise ValueError("source_count cannot be negative")


@dataclass(frozen=True)
class IdeaFunnelPolicy:
    maximum_selected: int = 50
    maximum_total_cost: float = 500.0
    maximum_per_topic_family: int = 8
    maximum_per_format_family: int = 10
    minimum_audience_value: float = 0.45
    minimum_evidence_feasibility: float = 0.55
    minimum_visual_feasibility: float = 0.45
    maximum_sensitivity_risk: float = 0.70
    minimum_sources: int = 2
    minimum_exploration_slots: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.maximum_selected <= 50:
            raise ValueError("maximum_selected must be between 1 and 50")
        if self.maximum_total_cost <= 0:
            raise ValueError("maximum_total_cost must be positive")
        if self.maximum_per_topic_family < 1 or self.maximum_per_format_family < 1:
            raise ValueError("family limits must be positive")
        if self.minimum_exploration_slots < 0 or self.minimum_exploration_slots > self.maximum_selected:
            raise ValueError("invalid exploration quota")


@dataclass(frozen=True)
class IdeaFunnelResult:
    selected: tuple[IdeaCandidate, ...]
    deferred: tuple[tuple[str, str], ...]
    rejected: tuple[tuple[str, str], ...]
    total_cost: float
    exploration_count: int
    valid: bool
    blockers: tuple[str, ...]


def _score(candidate: IdeaCandidate) -> float:
    benefit = (
        candidate.audience_value * 0.28
        + candidate.novelty * 0.22
        + candidate.evidence_feasibility * 0.20
        + candidate.visual_feasibility * 0.20
        + (0.10 if candidate.exploration else 0.0)
        - candidate.sensitivity_risk * 0.18
    )
    return benefit / max(candidate.estimated_cost, 0.25)


def run_idea_funnel(candidates: Iterable[IdeaCandidate], policy: IdeaFunnelPolicy) -> IdeaFunnelResult:
    items = tuple(candidates)
    blockers: list[str] = []
    if len({item.candidate_id for item in items}) != len(items):
        blockers.append("duplicate_candidate_id")

    best_by_duplicate_key: dict[str, IdeaCandidate] = {}
    rejected: list[tuple[str, str]] = []
    for item in sorted(items, key=lambda value: (-_score(value), value.candidate_id)):
        if item.audience_value < policy.minimum_audience_value:
            rejected.append((item.candidate_id, "low_audience_value"))
            continue
        if item.evidence_feasibility < policy.minimum_evidence_feasibility or item.source_count < policy.minimum_sources:
            rejected.append((item.candidate_id, "insufficient_evidence_feasibility"))
            continue
        if item.visual_feasibility < policy.minimum_visual_feasibility:
            rejected.append((item.candidate_id, "insufficient_visual_feasibility"))
            continue
        if item.sensitivity_risk > policy.maximum_sensitivity_risk:
            rejected.append((item.candidate_id, "sensitivity_risk"))
            continue
        if item.duplicate_key in best_by_duplicate_key:
            rejected.append((item.candidate_id, "duplicate_premise"))
            continue
        best_by_duplicate_key[item.duplicate_key] = item

    eligible = sorted(best_by_duplicate_key.values(), key=lambda value: (-_score(value), value.candidate_id))
    exploration = [item for item in eligible if item.exploration]
    ordered = exploration + [item for item in eligible if not item.exploration]

    selected: list[IdeaCandidate] = []
    deferred: list[tuple[str, str]] = []
    topic_counts: dict[str, int] = {}
    format_counts: dict[str, int] = {}
    total_cost = 0.0

    for item in ordered:
        if len(selected) >= policy.maximum_selected:
            deferred.append((item.candidate_id, "story_capacity"))
            continue
        if total_cost + item.estimated_cost > policy.maximum_total_cost:
            deferred.append((item.candidate_id, "budget_capacity"))
            continue
        if topic_counts.get(item.topic_family, 0) >= policy.maximum_per_topic_family:
            deferred.append((item.candidate_id, "topic_family_capacity"))
            continue
        if format_counts.get(item.format_family, 0) >= policy.maximum_per_format_family:
            deferred.append((item.candidate_id, "format_family_capacity"))
            continue
        selected.append(item)
        total_cost += item.estimated_cost
        topic_counts[item.topic_family] = topic_counts.get(item.topic_family, 0) + 1
        format_counts[item.format_family] = format_counts.get(item.format_family, 0) + 1

    exploration_count = sum(item.exploration for item in selected)
    if exploration_count < policy.minimum_exploration_slots:
        blockers.append("exploration_quota_unmet")
    if not selected:
        blockers.append("empty_selection")

    return IdeaFunnelResult(
        selected=tuple(selected),
        deferred=tuple(deferred),
        rejected=tuple(rejected),
        total_cost=round(total_cost, 3),
        exploration_count=exploration_count,
        valid=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
