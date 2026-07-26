from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class StoryCandidate:
    slug: str
    topic_family: str
    emotional_tone: str
    visual_family: str
    factual_complexity: int
    estimated_cost: float
    readiness_score: float
    novelty_score: float
    audience_value: float
    exploration: bool = False
    blocked: bool = False


@dataclass(frozen=True)
class PortfolioPolicy:
    maximum_stories: int
    maximum_total_cost: float
    maximum_per_topic_family: int = 1
    maximum_per_visual_family: int = 1
    minimum_exploration_slots: int = 1
    minimum_readiness: float = 70.0


@dataclass(frozen=True)
class PortfolioSelection:
    selected: tuple[StoryCandidate, ...]
    deferred: tuple[tuple[str, str], ...]
    total_cost: float
    exploration_count: int
    valid: bool
    blockers: tuple[str, ...]


def _value(candidate: StoryCandidate) -> float:
    cost_penalty = max(1.0, candidate.estimated_cost)
    raw = (
        candidate.readiness_score * 0.35
        + candidate.novelty_score * 100 * 0.25
        + candidate.audience_value * 100 * 0.25
        + (10 if candidate.exploration else 0)
        - candidate.factual_complexity * 1.5
    )
    return raw / cost_penalty


def build_portfolio(candidates: Iterable[StoryCandidate], policy: PortfolioPolicy) -> PortfolioSelection:
    items = tuple(candidates)
    blockers: list[str] = []
    if policy.maximum_stories < 1:
        blockers.append("invalid_story_limit")
    if policy.maximum_total_cost <= 0:
        blockers.append("invalid_cost_limit")
    if policy.minimum_exploration_slots > policy.maximum_stories:
        blockers.append("exploration_slots_exceed_capacity")
    if len({item.slug for item in items}) != len(items):
        blockers.append("duplicate_story_slug")

    selected: list[StoryCandidate] = []
    deferred: list[tuple[str, str]] = []
    topic_counts: dict[str, int] = {}
    visual_counts: dict[str, int] = {}
    total_cost = 0.0

    ranked = sorted(items, key=lambda item: (-_value(item), item.slug))
    exploration_candidates = [item for item in ranked if item.exploration and not item.blocked]
    ordered = exploration_candidates + [item for item in ranked if item not in exploration_candidates]

    for candidate in ordered:
        if candidate.blocked:
            deferred.append((candidate.slug, "blocked"))
            continue
        if candidate.readiness_score < policy.minimum_readiness:
            deferred.append((candidate.slug, "below_readiness_floor"))
            continue
        if len(selected) >= policy.maximum_stories:
            deferred.append((candidate.slug, "story_limit"))
            continue
        if total_cost + candidate.estimated_cost > policy.maximum_total_cost:
            deferred.append((candidate.slug, "cost_limit"))
            continue
        if topic_counts.get(candidate.topic_family, 0) >= policy.maximum_per_topic_family:
            deferred.append((candidate.slug, "topic_family_limit"))
            continue
        if visual_counts.get(candidate.visual_family, 0) >= policy.maximum_per_visual_family:
            deferred.append((candidate.slug, "visual_family_limit"))
            continue
        selected.append(candidate)
        total_cost += candidate.estimated_cost
        topic_counts[candidate.topic_family] = topic_counts.get(candidate.topic_family, 0) + 1
        visual_counts[candidate.visual_family] = visual_counts.get(candidate.visual_family, 0) + 1

    exploration_count = sum(item.exploration for item in selected)
    if exploration_count < policy.minimum_exploration_slots:
        blockers.append("exploration_quota_unmet")
    if not selected:
        blockers.append("empty_portfolio")

    return PortfolioSelection(
        selected=tuple(selected),
        deferred=tuple(deferred),
        total_cost=round(total_cost, 3),
        exploration_count=exploration_count,
        valid=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
