from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class EvidenceLevel(str, Enum):
    NONE = "none"
    DOCUMENTED = "documented"
    PROTOTYPED = "prototyped"
    TESTED = "tested"
    PRODUCTION_PROVEN = "production_proven"


_LEVEL_MULTIPLIER = {
    EvidenceLevel.NONE: 0.0,
    EvidenceLevel.DOCUMENTED: 0.25,
    EvidenceLevel.PROTOTYPED: 0.5,
    EvidenceLevel.TESTED: 0.75,
    EvidenceLevel.PRODUCTION_PROVEN: 1.0,
}


@dataclass(frozen=True)
class CapabilityStatus:
    capability: str
    target_weight: float
    implementation_percent: float
    evidence: EvidenceLevel
    blocking: bool = False

    @property
    def earned(self) -> float:
        implementation = min(100.0, max(0.0, self.implementation_percent)) / 100.0
        return self.target_weight * implementation * _LEVEL_MULTIPLIER[self.evidence]


@dataclass(frozen=True)
class PipelineStatus:
    implementation_score: float
    evidence_score: float
    weighted_readiness: float
    blocking_gaps: tuple[str, ...]
    next_priorities: tuple[str, ...]


def summarize_pipeline(capabilities: Iterable[CapabilityStatus]) -> PipelineStatus:
    items = tuple(capabilities)
    total_weight = sum(max(0.0, item.target_weight) for item in items) or 1.0
    implementation = sum(
        item.target_weight * min(100.0, max(0.0, item.implementation_percent)) / 100.0
        for item in items
    ) / total_weight * 100
    evidence = sum(
        item.target_weight * _LEVEL_MULTIPLIER[item.evidence]
        for item in items
    ) / total_weight * 100
    weighted = sum(item.earned for item in items) / total_weight * 100
    blocking = tuple(sorted(
        item.capability
        for item in items
        if item.blocking and item.implementation_percent < 100
    ))
    priorities = tuple(
        item.capability
        for item in sorted(
            items,
            key=lambda item: (
                item.earned / item.target_weight if item.target_weight else 1.0,
                -item.target_weight,
                item.capability,
            ),
        )[:5]
    )
    return PipelineStatus(
        round(implementation, 1),
        round(evidence, 1),
        round(weighted, 1),
        blocking,
        priorities,
    )
