from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Sequence

from .analytics_models import VideoObservation


@dataclass(frozen=True)
class PatternResult:
    name: str
    videos: int
    views: int
    viewed_rate: float
    completion_rate: float
    share_rate: float
    subscriber_rate: float
    conservative_score: float
    recent_use_ratio: float
    last_used_at: datetime


def _lower_bound(successes: int, opportunities: int, z: float = 1.645) -> float:
    if opportunities <= 0:
        return 0.0
    p = successes / opportunities
    denominator = 1.0 + z * z / opportunities
    center = p + z * z / (2 * opportunities)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * opportunities)) / opportunities)
    return max(0.0, (center - margin) / denominator)


def summarize_patterns(
    videos: Sequence[VideoObservation],
    *,
    pattern_type: str,
) -> tuple[PatternResult, ...]:
    if pattern_type not in {"premise", "visual", "performance"}:
        raise ValueError("pattern_type must be premise, visual, or performance")
    grouped: dict[str, list[VideoObservation]] = {}
    for video in videos:
        video.validate()
        if pattern_type == "premise":
            names = (video.premise_pattern,)
        elif pattern_type == "visual":
            names = (video.visual_pattern,)
        else:
            names = video.performance_families
        for name in names:
            grouped.setdefault(name, []).append(video)

    now = max((video.published_at for video in videos), default=datetime.now(timezone.utc))
    results: list[PatternResult] = []
    for name, items in grouped.items():
        views = sum(item.views for item in items)
        shown = sum(item.shown_in_feed for item in items)
        completions = sum(item.completed_views for item in items)
        shares = sum(item.shares for item in items)
        subscribers = sum(item.subscribers_gained for item in items)
        recent_uses = sum((now - item.published_at).days <= 14 for item in items)
        viewed_lower = _lower_bound(views, shown)
        completion_lower = _lower_bound(completions, views)
        share_lower = _lower_bound(shares, views)
        subscriber_lower = _lower_bound(subscribers, views)
        utility = 0.25 * viewed_lower + 0.35 * completion_lower + 2.5 * share_lower + 4.0 * subscriber_lower
        fatigue = min(1.0, recent_uses / 5.0)
        conservative = max(0.0, utility * 100 - 25 * fatigue)
        results.append(
            PatternResult(
                name=name,
                videos=len(items),
                views=views,
                viewed_rate=views / shown if shown else 0.0,
                completion_rate=completions / views if views else 0.0,
                share_rate=shares / views if views else 0.0,
                subscriber_rate=subscribers / views if views else 0.0,
                conservative_score=round(conservative, 3),
                recent_use_ratio=fatigue,
                last_used_at=max(item.published_at for item in items),
            )
        )
    return tuple(sorted(results, key=lambda item: item.conservative_score, reverse=True))
