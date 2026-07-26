"""Budget, concurrency, and backpressure admission-control prototype."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ResourceDecision(str, Enum):
    ADMIT = "admit"
    DEFER = "defer"
    REJECT = "reject"


@dataclass(frozen=True)
class ResourceRequest:
    request_id: str
    story_slug: str
    profile: str
    estimated_seconds: float
    provider_calls: int
    peak_memory_mb: int
    priority: int
    cache_hit_rate: float
    dependency: str = "renderer"

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.story_slug.strip() or not self.dependency.strip():
            raise ValueError("request_id, story_slug, and dependency must be nonempty")
        if self.estimated_seconds < 0 or self.provider_calls < 0 or self.peak_memory_mb < 0:
            raise ValueError("resource estimates must be nonnegative")
        if not 0 <= self.priority <= 100:
            raise ValueError("priority must be between 0 and 100")
        if not 0 <= self.cache_hit_rate <= 1:
            raise ValueError("cache_hit_rate must be between 0 and 1")

    @property
    def value_density(self) -> float:
        effective_cost = max(1.0, self.estimated_seconds * (1.0 - 0.5 * self.cache_hit_rate))
        return self.priority / effective_cost


@dataclass(frozen=True)
class ResourcePolicy:
    maximum_jobs: int = 3
    maximum_total_seconds: float = 1800.0
    maximum_provider_calls: int = 30
    maximum_peak_memory_mb: int = 3200
    maximum_seconds_per_story: float = 1200.0
    maximum_provider_calls_per_job: int = 12
    maximum_low_cache_jobs: int = 1
    low_cache_threshold: float = 0.25
    reserve_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.maximum_jobs < 1:
            raise ValueError("maximum_jobs must be >= 1")
        numeric = (
            self.maximum_total_seconds,
            self.maximum_provider_calls,
            self.maximum_peak_memory_mb,
            self.maximum_seconds_per_story,
            self.maximum_provider_calls_per_job,
            self.maximum_low_cache_jobs,
            self.reserve_seconds,
        )
        if any(value < 0 for value in numeric):
            raise ValueError("resource policy values must be nonnegative")
        if not 0 <= self.low_cache_threshold <= 1:
            raise ValueError("low_cache_threshold must be between 0 and 1")


@dataclass(frozen=True)
class AdmissionResult:
    request: ResourceRequest
    decision: ResourceDecision
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ResourcePlan:
    admitted: tuple[ResourceRequest, ...]
    decisions: tuple[AdmissionResult, ...]
    total_seconds: float
    total_provider_calls: int
    peak_memory_mb: int
    utilization_ratio: float


def govern_resources(
    requests: Iterable[ResourceRequest],
    *,
    policy: ResourcePolicy | None = None,
    unavailable_dependencies: frozenset[str] = frozenset(),
) -> ResourcePlan:
    policy = policy or ResourcePolicy()
    items = tuple(requests)
    ids = [item.request_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("request IDs must be unique")

    ordered = sorted(
        items,
        key=lambda item: (-item.priority, -item.value_density, item.estimated_seconds, item.request_id),
    )
    admitted: list[ResourceRequest] = []
    decisions: list[AdmissionResult] = []
    total_seconds = 0.0
    total_calls = 0
    peak_memory = 0
    low_cache_jobs = 0
    available_seconds = max(0.0, policy.maximum_total_seconds - policy.reserve_seconds)

    for request in ordered:
        hard: list[str] = []
        soft: list[str] = []
        if request.dependency in unavailable_dependencies:
            hard.append("dependency_unavailable")
        if request.estimated_seconds > policy.maximum_seconds_per_story:
            hard.append("per_story_time_limit")
        if request.provider_calls > policy.maximum_provider_calls_per_job:
            hard.append("per_job_provider_call_limit")
        if request.peak_memory_mb > policy.maximum_peak_memory_mb:
            hard.append("per_job_memory_limit")
        if hard:
            decisions.append(AdmissionResult(request, ResourceDecision.REJECT, tuple(sorted(hard))))
            continue

        would_be_low_cache = request.cache_hit_rate < policy.low_cache_threshold
        if len(admitted) >= policy.maximum_jobs:
            soft.append("concurrency_limit")
        if total_seconds + request.estimated_seconds > available_seconds:
            soft.append("time_budget")
        if total_calls + request.provider_calls > policy.maximum_provider_calls:
            soft.append("provider_call_budget")
        if would_be_low_cache and low_cache_jobs >= policy.maximum_low_cache_jobs:
            soft.append("low_cache_backpressure")

        if soft:
            decisions.append(AdmissionResult(request, ResourceDecision.DEFER, tuple(sorted(soft))))
            continue

        admitted.append(request)
        total_seconds += request.estimated_seconds
        total_calls += request.provider_calls
        peak_memory = max(peak_memory, request.peak_memory_mb)
        if would_be_low_cache:
            low_cache_jobs += 1
        decisions.append(AdmissionResult(request, ResourceDecision.ADMIT, ()))

    utilization = 0.0 if available_seconds == 0 else min(1.0, total_seconds / available_seconds)
    return ResourcePlan(
        admitted=tuple(admitted),
        decisions=tuple(decisions),
        total_seconds=round(total_seconds, 2),
        total_provider_calls=total_calls,
        peak_memory_mb=peak_memory,
        utilization_ratio=round(utilization, 4),
    )
