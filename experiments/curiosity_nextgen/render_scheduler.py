"""Budget-aware render queue planning for the dormant laboratory.

The scheduler is intentionally detached from GitHub Actions and the active
producer.  It ranks candidate jobs, enforces readiness floors and time budgets,
and preserves topic diversity so an unattended queue cannot spend the entire
window on one expensive story family.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .render_budget import RenderProfile


class DeferralReason(str, Enum):
    BLOCKED = "blocked"
    LOW_READINESS = "low_readiness"
    TIME_BUDGET = "time_budget"
    SLOT_LIMIT = "slot_limit"
    FAMILY_LIMIT = "family_limit"
    INVALID_COST = "invalid_cost"


@dataclass(frozen=True)
class RenderJob:
    slug: str
    profile: RenderProfile
    priority: int
    readiness_score: float
    estimated_seconds: float
    expected_cache_hit_rate: float
    novelty_score: float
    topic_family: str
    blocked: bool = False
    blocking_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.slug.strip():
            raise ValueError("slug must be nonempty")
        if not 0 <= self.priority <= 100:
            raise ValueError("priority must be between 0 and 100")
        if not 0 <= self.readiness_score <= 100:
            raise ValueError("readiness_score must be between 0 and 100")
        if not 0 <= self.expected_cache_hit_rate <= 1:
            raise ValueError("expected_cache_hit_rate must be between 0 and 1")
        if not 0 <= self.novelty_score <= 1:
            raise ValueError("novelty_score must be between 0 and 1")

    @property
    def effective_seconds(self) -> float:
        if self.estimated_seconds < 0:
            return self.estimated_seconds
        cache_discount = min(0.75, self.expected_cache_hit_rate * 0.65)
        return round(self.estimated_seconds * (1.0 - cache_discount), 2)

    @property
    def queue_score(self) -> float:
        cost = max(30.0, self.effective_seconds)
        value = (
            self.priority * 0.38
            + self.readiness_score * 0.34
            + self.novelty_score * 100 * 0.18
            + self.expected_cache_hit_rate * 100 * 0.10
        )
        return round(value / (cost ** 0.32), 4)


@dataclass(frozen=True)
class SchedulePolicy:
    maximum_jobs: int = 4
    maximum_total_seconds: float = 2400.0
    minimum_readiness: float = 60.0
    maximum_per_topic_family: int = 2
    reserve_seconds: float = 120.0
    allow_production_profile: bool = False


@dataclass(frozen=True)
class DeferredJob:
    slug: str
    reason: DeferralReason
    detail: str


@dataclass(frozen=True)
class RenderSchedule:
    scheduled: tuple[RenderJob, ...]
    deferred: tuple[DeferredJob, ...]
    estimated_seconds: float
    remaining_seconds: float
    family_counts: tuple[tuple[str, int], ...]
    average_readiness: float
    average_cache_hit_rate: float


def build_render_schedule(
    jobs: Iterable[RenderJob],
    *,
    policy: SchedulePolicy | None = None,
) -> RenderSchedule:
    policy = policy or SchedulePolicy()
    available = max(0.0, policy.maximum_total_seconds - max(0.0, policy.reserve_seconds))
    scheduled: list[RenderJob] = []
    deferred: list[DeferredJob] = []
    family_counts: dict[str, int] = {}
    consumed = 0.0

    candidates = sorted(
        tuple(jobs),
        key=lambda item: (-item.queue_score, -item.priority, -item.readiness_score, item.slug),
    )

    for job in candidates:
        if job.blocked or job.blocking_reasons:
            detail = ",".join(job.blocking_reasons) if job.blocking_reasons else "blocked=true"
            deferred.append(DeferredJob(job.slug, DeferralReason.BLOCKED, detail))
            continue
        if job.estimated_seconds < 0:
            deferred.append(DeferredJob(job.slug, DeferralReason.INVALID_COST, str(job.estimated_seconds)))
            continue
        if job.readiness_score < policy.minimum_readiness:
            deferred.append(
                DeferredJob(job.slug, DeferralReason.LOW_READINESS, f"{job.readiness_score:.1f}<{policy.minimum_readiness:.1f}")
            )
            continue
        if job.profile is RenderProfile.PRODUCTION and not policy.allow_production_profile:
            deferred.append(DeferredJob(job.slug, DeferralReason.BLOCKED, "production_profile_disabled"))
            continue
        if len(scheduled) >= policy.maximum_jobs:
            deferred.append(DeferredJob(job.slug, DeferralReason.SLOT_LIMIT, str(policy.maximum_jobs)))
            continue
        family_count = family_counts.get(job.topic_family, 0)
        if family_count >= policy.maximum_per_topic_family:
            deferred.append(
                DeferredJob(job.slug, DeferralReason.FAMILY_LIMIT, f"{job.topic_family}:{family_count}")
            )
            continue
        if consumed + job.effective_seconds > available:
            deferred.append(
                DeferredJob(
                    job.slug,
                    DeferralReason.TIME_BUDGET,
                    f"needed={job.effective_seconds:.2f},remaining={max(0.0, available-consumed):.2f}",
                )
            )
            continue

        scheduled.append(job)
        consumed += job.effective_seconds
        family_counts[job.topic_family] = family_count + 1

    average_readiness = 0.0 if not scheduled else sum(item.readiness_score for item in scheduled) / len(scheduled)
    average_cache = 0.0 if not scheduled else sum(item.expected_cache_hit_rate for item in scheduled) / len(scheduled)
    return RenderSchedule(
        scheduled=tuple(scheduled),
        deferred=tuple(sorted(deferred, key=lambda item: (item.reason.value, item.slug))),
        estimated_seconds=round(consumed, 2),
        remaining_seconds=round(max(0.0, available - consumed), 2),
        family_counts=tuple(sorted(family_counts.items())),
        average_readiness=round(average_readiness, 1),
        average_cache_hit_rate=round(average_cache, 4),
    )
