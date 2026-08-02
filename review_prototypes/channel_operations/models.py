from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping


@dataclass(frozen=True)
class ReleaseCandidate:
    slug: str
    topic_family: str
    story_shape: str
    hook_pattern: str
    performance_families: tuple[str, ...]
    quality_score: float
    lowest_dimension: float
    source_verified: bool
    retention_passed: bool
    showrunner_decision: str
    hard_failures: tuple[str, ...] = ()
    experiment_id: str | None = None
    estimated_minutes: float = 1.0
    freshness_score: float = 1.0
    reaction_prediction: float = 0.0
    artifact_manifest_hash: str = ""

    def validate(self) -> None:
        if not self.slug:
            raise ValueError("release candidate requires slug")
        if not 0.0 <= self.quality_score <= 100.0:
            raise ValueError("quality_score must be in [0, 100]")
        if not 0.0 <= self.lowest_dimension <= 10.0:
            raise ValueError("lowest_dimension must be in [0, 10]")
        if self.showrunner_decision not in {"ship", "hold", "reject"}:
            raise ValueError("unsupported showrunner decision")
        if self.estimated_minutes <= 0:
            raise ValueError("estimated_minutes must be positive")
        if not 0.0 <= self.freshness_score <= 1.0:
            raise ValueError("freshness_score must be in [0, 1]")


@dataclass(frozen=True)
class ReleaseDecision:
    slug: str
    eligible: bool
    reasons: tuple[str, ...]
    readiness_score: float


@dataclass(frozen=True)
class ReleaseSlot:
    slug: str
    publish_at: datetime
    experiment_id: str | None
    sequence_index: int


@dataclass(frozen=True)
class PortfolioResult:
    selected: tuple[ReleaseCandidate, ...]
    rejected: Mapping[str, tuple[str, ...]]
    diversity_score: float
    active_experiment_id: str | None


@dataclass(frozen=True)
class ScheduleResult:
    slots: tuple[ReleaseSlot, ...]
    warnings: tuple[str, ...]
