from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import erfc, sqrt
from typing import Iterable


class ExperimentDecision(str, Enum):
    PROMOTE = "promote"
    CONTINUE = "continue"
    REJECT = "reject"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class RateMetric:
    name: str
    successes: int
    trials: int

    @property
    def rate(self) -> float:
        return 0.0 if self.trials <= 0 else self.successes / self.trials


@dataclass(frozen=True)
class MetricComparison:
    name: str
    control_rate: float
    treatment_rate: float
    absolute_lift: float
    relative_lift: float | None
    p_value: float


@dataclass(frozen=True)
class ExperimentResult:
    decision: ExperimentDecision
    primary: MetricComparison | None
    guardrails: tuple[MetricComparison, ...]
    reasons: tuple[str, ...]


def compare_rates(control: RateMetric, treatment: RateMetric) -> MetricComparison:
    if control.name != treatment.name:
        raise ValueError("metric names must match")
    if control.trials <= 0 or treatment.trials <= 0:
        return MetricComparison(control.name, control.rate, treatment.rate, treatment.rate - control.rate, None, 1.0)
    pooled = (control.successes + treatment.successes) / (control.trials + treatment.trials)
    variance = pooled * (1 - pooled) * (1 / control.trials + 1 / treatment.trials)
    if variance <= 0:
        p_value = 1.0 if control.rate == treatment.rate else 0.0
    else:
        z = abs(treatment.rate - control.rate) / sqrt(variance)
        p_value = erfc(z / sqrt(2))
    relative = None if control.rate == 0 else (treatment.rate - control.rate) / control.rate
    return MetricComparison(
        name=control.name,
        control_rate=round(control.rate, 6),
        treatment_rate=round(treatment.rate, 6),
        absolute_lift=round(treatment.rate - control.rate, 6),
        relative_lift=None if relative is None else round(relative, 6),
        p_value=round(p_value, 6),
    )


def evaluate_experiment(
    control_primary: RateMetric,
    treatment_primary: RateMetric,
    *,
    guardrail_pairs: Iterable[tuple[RateMetric, RateMetric]] = (),
    min_trials_per_arm: int = 1000,
    significance: float = 0.05,
    minimum_absolute_lift: float = 0.01,
    max_guardrail_harm: float = 0.01,
) -> ExperimentResult:
    reasons: list[str] = []
    primary = compare_rates(control_primary, treatment_primary)
    guardrails = tuple(compare_rates(control, treatment) for control, treatment in guardrail_pairs)

    if control_primary.trials < min_trials_per_arm or treatment_primary.trials < min_trials_per_arm:
        return ExperimentResult(ExperimentDecision.CONTINUE, primary, guardrails, ("insufficient_sample",))

    harmed = [metric.name for metric in guardrails if metric.absolute_lift < -max_guardrail_harm]
    if harmed:
        reasons.extend(f"guardrail_harmed:{name}" for name in harmed)
        return ExperimentResult(ExperimentDecision.REJECT, primary, guardrails, tuple(reasons))

    if primary.p_value > significance:
        return ExperimentResult(ExperimentDecision.INCONCLUSIVE, primary, guardrails, ("not_statistically_clear",))
    if primary.absolute_lift >= minimum_absolute_lift:
        return ExperimentResult(ExperimentDecision.PROMOTE, primary, guardrails, ())
    if primary.absolute_lift <= -minimum_absolute_lift:
        return ExperimentResult(ExperimentDecision.REJECT, primary, guardrails, ("primary_metric_regressed",))
    return ExperimentResult(ExperimentDecision.INCONCLUSIVE, primary, guardrails, ("effect_too_small",))
