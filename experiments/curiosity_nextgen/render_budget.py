from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class RenderProfile(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PRODUCTION = "production"


class BudgetDecision(str, Enum):
    PASS = "pass"
    WARN = "warn"
    REJECT = "reject"


@dataclass(frozen=True)
class ProfileBudget:
    target_seconds: float
    hard_limit_seconds: float
    max_peak_rss_mb: int


DEFAULT_BUDGETS: dict[RenderProfile, ProfileBudget] = {
    RenderProfile.DRAFT: ProfileBudget(300, 480, 1500),
    RenderProfile.REVIEW: ProfileBudget(600, 900, 2200),
    RenderProfile.PRODUCTION: ProfileBudget(1200, 1800, 3200),
}


@dataclass(frozen=True)
class ShotCost:
    shot_id: str
    scene_kind: str
    planned_duration_seconds: float
    estimated_cost_ratio: float
    cache_hit: bool = False

    @property
    def estimated_seconds(self) -> float:
        if self.cache_hit:
            return 0.15
        return max(0.0, self.planned_duration_seconds * self.estimated_cost_ratio)


@dataclass(frozen=True)
class RenderEstimate:
    profile: RenderProfile
    estimated_seconds: float
    cache_hit_rate: float
    decision: BudgetDecision
    reasons: tuple[str, ...]
    slowest_shots: tuple[tuple[str, float], ...]


def estimate_render(
    shots: Iterable[ShotCost],
    *,
    profile: RenderProfile,
    assembly_seconds: float = 20.0,
    judge_package_seconds: float = 10.0,
    peak_rss_mb: int | None = None,
    budgets: dict[RenderProfile, ProfileBudget] = DEFAULT_BUDGETS,
) -> RenderEstimate:
    shot_list = tuple(shots)
    shot_times = [(shot.shot_id, shot.estimated_seconds) for shot in shot_list]
    total = sum(value for _, value in shot_times) + max(0.0, assembly_seconds) + max(0.0, judge_package_seconds)
    hit_rate = 0.0 if not shot_list else sum(shot.cache_hit for shot in shot_list) / len(shot_list)
    budget = budgets[profile]
    reasons: list[str] = []

    if total > budget.hard_limit_seconds:
        decision = BudgetDecision.REJECT
        reasons.append("hard_time_limit_exceeded")
    elif total > budget.target_seconds:
        decision = BudgetDecision.WARN
        reasons.append("target_time_exceeded")
    else:
        decision = BudgetDecision.PASS

    if peak_rss_mb is not None and peak_rss_mb > budget.max_peak_rss_mb:
        reasons.append("memory_budget_exceeded")
        decision = BudgetDecision.REJECT

    if hit_rate < 0.5 and any(shot.cache_hit for shot in shot_list):
        reasons.append("low_cache_reuse")
        if decision is BudgetDecision.PASS:
            decision = BudgetDecision.WARN

    slowest = tuple(sorted(shot_times, key=lambda item: item[1], reverse=True)[:5])
    return RenderEstimate(profile, round(total, 2), round(hit_rate, 4), decision, tuple(reasons), slowest)
