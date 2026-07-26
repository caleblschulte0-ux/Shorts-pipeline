from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Iterable, Mapping


STAGE_WEIGHTS: Mapping[str, float] = {
    "designed": 0.10,
    "implemented": 0.25,
    "unit_tested": 0.15,
    "integration_tested": 0.15,
    "production_wired": 0.20,
    "production_proven": 0.15,
}


@dataclass(frozen=True)
class CapabilityStatus:
    name: str
    importance: float
    designed: float
    implemented: float
    unit_tested: float
    integration_tested: float
    production_wired: float
    production_proven: float
    evidence: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.name:
            raise ValueError("capability requires a name")
        if self.importance <= 0:
            raise ValueError("importance must be positive")
        for stage in STAGE_WEIGHTS:
            value = float(getattr(self, stage))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{self.name}.{stage} must be in [0, 1]")
        if self.production_proven > self.production_wired:
            raise ValueError("production proof cannot exceed production wiring")
        if self.integration_tested > self.implemented:
            raise ValueError("integration tests cannot exceed implementation")

    @property
    def completion(self) -> float:
        self.validate()
        return sum(float(getattr(self, stage)) * weight for stage, weight in STAGE_WEIGHTS.items())


@dataclass(frozen=True)
class ScorecardReport:
    overall_percent: float
    stage_percentages: Mapping[str, float]
    capability_percentages: Mapping[str, float]
    critical_gaps: tuple[str, ...]
    evidence_coverage_percent: float


class SystemScorecard:
    def evaluate(self, capabilities: Iterable[CapabilityStatus]) -> ScorecardReport:
        items = tuple(capabilities)
        if not items:
            raise ValueError("scorecard requires at least one capability")
        for item in items:
            item.validate()
        total_importance = sum(item.importance for item in items)
        overall = sum(item.completion * item.importance for item in items) / total_importance
        stage_scores = {
            stage: sum(float(getattr(item, stage)) * item.importance for item in items)
            / total_importance
            for stage in STAGE_WEIGHTS
        }
        capability_scores = {item.name: item.completion for item in items}
        gaps: list[str] = []
        for item in items:
            if item.importance >= 8 and item.production_wired < 0.5:
                gaps.append(f"{item.name}: not materially wired into production")
            if item.importance >= 8 and item.production_proven < 0.25:
                gaps.append(f"{item.name}: lacks production evidence")
            if item.implemented >= 0.8 and item.integration_tested < 0.5:
                gaps.append(f"{item.name}: implementation outruns integration testing")
        evidence_coverage = fmean(1.0 if item.evidence else 0.0 for item in items)
        return ScorecardReport(
            overall_percent=round(overall * 100.0, 1),
            stage_percentages={key: round(value * 100.0, 1) for key, value in stage_scores.items()},
            capability_percentages={
                key: round(value * 100.0, 1) for key, value in capability_scores.items()
            },
            critical_gaps=tuple(gaps),
            evidence_coverage_percent=round(evidence_coverage * 100.0, 1),
        )
