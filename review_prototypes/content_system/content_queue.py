from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

from .content_models import ContentDomain, StoryPackage


def _tokens(text: str) -> frozenset[str]:
    stop = {"the", "a", "an", "why", "how", "what", "this", "that", "is", "of", "to", "in", "and"}
    return frozenset(token for token in re.findall(r"[a-z0-9]+", text.lower()) if token not in stop)


def similarity(left: str, right: str) -> float:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class QueueHistoryItem:
    slug: str
    title: str
    domain: ContentDomain
    visual_form: str
    performance_families: tuple[str, ...]
    dataset_keys: tuple[str, ...]


@dataclass(frozen=True)
class QueueScore:
    story: StoryPackage
    score: float
    reasons: tuple[str, ...]
    rejected: bool


@dataclass(frozen=True)
class QueuePlan:
    selected: tuple[QueueScore, ...]
    rejected: tuple[QueueScore, ...]


@dataclass(frozen=True)
class QueuePolicy:
    maximum_items: int = 6
    maximum_per_domain: int = 2
    duplicate_title_threshold: float = 0.58
    recent_dataset_penalty: float = 22.0
    repeated_visual_penalty: float = 12.0
    repeated_performance_penalty: float = 8.0


def score_story(
    story: StoryPackage,
    *,
    history: Sequence[QueueHistoryItem],
    policy: QueuePolicy,
) -> QueueScore:
    reasons: list[str] = []
    score = story.premise.score
    rejected = False
    recent_datasets = {key for item in history for key in item.dataset_keys}
    story_datasets = {dataset.key for dataset in story.datasets}
    overlap = story_datasets & recent_datasets
    if overlap:
        score -= policy.recent_dataset_penalty
        reasons.append(f"recent dataset reuse: {sorted(overlap)}")

    repeated_visuals = sum(item.visual_form == story.premise.visual_form for item in history)
    if repeated_visuals:
        score -= min(24.0, repeated_visuals * policy.repeated_visual_penalty)
        reasons.append(f"visual pattern repeated {repeated_visuals} time(s)")

    story_performances = {beat.visual.mascot_objective for beat in story.beats}
    recent_performances = {family for item in history for family in item.performance_families}
    performance_overlap = story_performances & recent_performances
    if performance_overlap:
        score -= min(20.0, len(performance_overlap) * policy.repeated_performance_penalty)
        reasons.append("reuses recent performance family")

    for item in history:
        title_similarity = similarity(story.premise.title, item.title)
        if title_similarity >= policy.duplicate_title_threshold:
            rejected = True
            reasons.append(
                f"title is too similar to recent story {item.slug!r} ({title_similarity:.2f})"
            )
            break

    if story.estimated_seconds > 55:
        score -= 8.0
        reasons.append("estimated video is longer than the preferred Shorts range")
    if len(story.datasets) >= 2:
        score += 4.0
        reasons.append("uses multiple source-backed beats")
    return QueueScore(story=story, score=round(score, 2), reasons=tuple(reasons), rejected=rejected)


class QueuePlanner:
    def __init__(self, *, policy: QueuePolicy | None = None) -> None:
        self.policy = policy or QueuePolicy()

    def plan(
        self,
        stories: Iterable[StoryPackage],
        *,
        history: Sequence[QueueHistoryItem] = (),
    ) -> QueuePlan:
        scored = [score_story(story, history=history, policy=self.policy) for story in stories]
        ranked = sorted(scored, key=lambda item: (not item.rejected, item.score), reverse=True)
        selected: list[QueueScore] = []
        rejected: list[QueueScore] = []
        domain_counts: dict[ContentDomain, int] = {}
        for item in ranked:
            domain = item.story.premise.domain
            if item.rejected:
                rejected.append(item)
                continue
            if len(selected) >= self.policy.maximum_items:
                rejected.append(
                    QueueScore(
                        story=item.story,
                        score=item.score,
                        reasons=(*item.reasons, "daily queue is full"),
                        rejected=True,
                    )
                )
                continue
            if domain_counts.get(domain, 0) >= self.policy.maximum_per_domain:
                rejected.append(
                    QueueScore(
                        story=item.story,
                        score=item.score,
                        reasons=(*item.reasons, f"domain cap reached for {domain.value}"),
                        rejected=True,
                    )
                )
                continue
            selected.append(item)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        return QueuePlan(selected=tuple(selected), rejected=tuple(rejected))
