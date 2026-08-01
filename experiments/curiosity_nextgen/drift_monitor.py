from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import mean, pstdev
from typing import Iterable


class DriftSeverity(str, Enum):
    NONE = "none"
    WATCH = "watch"
    HOLD = "hold"
    FREEZE = "freeze"


@dataclass(frozen=True)
class MetricBaseline:
    metric: str
    mean_value: float
    standard_deviation: float
    minimum_value: float | None = None
    maximum_value: float | None = None
    higher_is_better: bool = True


@dataclass(frozen=True)
class MetricObservation:
    metric: str
    value: float
    timestamp: int


@dataclass(frozen=True)
class DriftFinding:
    metric: str
    severity: DriftSeverity
    observed_mean: float
    z_score: float
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class DriftReport:
    severity: DriftSeverity
    findings: tuple[DriftFinding, ...]
    freeze_required: bool


_SEVERITY_RANK = {
    DriftSeverity.NONE: 0,
    DriftSeverity.WATCH: 1,
    DriftSeverity.HOLD: 2,
    DriftSeverity.FREEZE: 3,
}


def build_baseline(metric: str, values: Iterable[float], *, higher_is_better: bool = True) -> MetricBaseline:
    items = tuple(float(value) for value in values)
    if len(items) < 3:
        raise ValueError("at least three values are required")
    return MetricBaseline(
        metric=metric,
        mean_value=mean(items),
        standard_deviation=pstdev(items),
        minimum_value=min(items),
        maximum_value=max(items),
        higher_is_better=higher_is_better,
    )


def evaluate_metric(
    baseline: MetricBaseline,
    observations: Iterable[MetricObservation],
    *,
    watch_z: float = 1.5,
    hold_z: float = 2.5,
    freeze_z: float = 4.0,
) -> DriftFinding:
    items = tuple(item for item in observations if item.metric == baseline.metric)
    if not items:
        return DriftFinding(baseline.metric, DriftSeverity.HOLD, 0.0, 0.0, ("missing_observations",))
    observed = mean(item.value for item in items)
    deviation = baseline.standard_deviation
    if deviation <= 0:
        z_score = 0.0 if observed == baseline.mean_value else float("inf")
    else:
        direction = baseline.mean_value - observed if baseline.higher_is_better else observed - baseline.mean_value
        z_score = direction / deviation

    blockers: list[str] = []
    if baseline.minimum_value is not None and observed < baseline.minimum_value:
        blockers.append("below_historical_minimum")
    if baseline.maximum_value is not None and observed > baseline.maximum_value and not baseline.higher_is_better:
        blockers.append("above_historical_maximum")

    harmful_z = max(0.0, z_score)
    if harmful_z >= freeze_z:
        severity = DriftSeverity.FREEZE
    elif harmful_z >= hold_z or blockers:
        severity = DriftSeverity.HOLD
    elif harmful_z >= watch_z:
        severity = DriftSeverity.WATCH
    else:
        severity = DriftSeverity.NONE
    return DriftFinding(baseline.metric, severity, observed, round(z_score, 3), tuple(blockers))


def evaluate_drift(
    baselines: Iterable[MetricBaseline],
    observations: Iterable[MetricObservation],
) -> DriftReport:
    observation_items = tuple(observations)
    findings = tuple(evaluate_metric(baseline, observation_items) for baseline in baselines)
    severity = max((finding.severity for finding in findings), key=lambda item: _SEVERITY_RANK[item], default=DriftSeverity.HOLD)
    return DriftReport(severity, findings, severity is DriftSeverity.FREEZE)
