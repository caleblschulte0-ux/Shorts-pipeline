from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Mapping, Sequence

from .analytics_models import AggregateObservation, ExperimentDefinition, VideoObservation


@dataclass(frozen=True)
class BetaPosterior:
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)


@dataclass(frozen=True)
class MetricComparison:
    metric: str
    control_mean: float
    treatment_mean: float
    absolute_lift: float
    relative_lift: float
    probability_treatment_better: float


@dataclass(frozen=True)
class ExperimentDecision:
    decision: str
    reason: str
    comparisons: tuple[MetricComparison, ...]
    control: AggregateObservation
    treatment: AggregateObservation
    confidence: float


@dataclass(frozen=True)
class EvaluationPolicy:
    confidence_to_promote: float = 0.95
    confidence_to_reject: float = 0.95
    minimum_relative_lift: float = 0.05
    maximum_guardrail_regression: float = 0.04
    posterior_draws: int = 12000
    prior_strength: float = 80.0
    priors: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        if self.priors is None:
            object.__setattr__(
                self,
                "priors",
                {
                    "viewed_rate": 0.65,
                    "completion_rate": 0.55,
                    "like_rate": 0.035,
                    "comment_rate": 0.002,
                    "share_rate": 0.004,
                    "subscriber_rate": 0.001,
                },
            )


def _posterior(successes: int, opportunities: int, prior_rate: float, prior_strength: float) -> BetaPosterior:
    if opportunities < successes or successes < 0:
        raise ValueError("invalid binomial counts")
    return BetaPosterior(
        alpha=successes + prior_rate * prior_strength,
        beta=(opportunities - successes) + (1.0 - prior_rate) * prior_strength,
    )


def _metric_counts(metric: str, aggregate: AggregateObservation) -> tuple[int, int]:
    mapping = {
        "viewed_rate": (aggregate.views, aggregate.shown_in_feed),
        "completion_rate": (aggregate.completed_views, aggregate.views),
        "like_rate": (aggregate.likes, aggregate.views),
        "comment_rate": (aggregate.comments, aggregate.views),
        "share_rate": (aggregate.shares, aggregate.views),
        "subscriber_rate": (aggregate.subscribers_gained, aggregate.views),
    }
    try:
        return mapping[metric]
    except KeyError as exc:
        raise ValueError(f"unsupported binomial metric: {metric}") from exc


def compare_metric(
    metric: str,
    control: AggregateObservation,
    treatment: AggregateObservation,
    *,
    policy: EvaluationPolicy,
    seed: int,
) -> MetricComparison:
    if metric == "average_percentage_viewed":
        c = control.average_percentage_viewed
        t = treatment.average_percentage_viewed
        c_se = max(0.01, 0.35 / math.sqrt(max(control.views, 1)))
        t_se = max(0.01, 0.35 / math.sqrt(max(treatment.views, 1)))
        diff = t - c
        z = diff / math.sqrt(c_se * c_se + t_se * t_se)
        probability = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        return MetricComparison(
            metric=metric,
            control_mean=c,
            treatment_mean=t,
            absolute_lift=diff,
            relative_lift=diff / max(abs(c), 1e-9),
            probability_treatment_better=probability,
        )

    c_success, c_opp = _metric_counts(metric, control)
    t_success, t_opp = _metric_counts(metric, treatment)
    prior = (policy.priors or {}).get(metric, 0.01)
    c_post = _posterior(c_success, c_opp, prior, policy.prior_strength)
    t_post = _posterior(t_success, t_opp, prior, policy.prior_strength)
    rng = random.Random(seed)
    wins = 0
    for _ in range(policy.posterior_draws):
        if rng.betavariate(t_post.alpha, t_post.beta) > rng.betavariate(c_post.alpha, c_post.beta):
            wins += 1
    probability = wins / policy.posterior_draws
    diff = t_post.mean - c_post.mean
    return MetricComparison(
        metric=metric,
        control_mean=c_post.mean,
        treatment_mean=t_post.mean,
        absolute_lift=diff,
        relative_lift=diff / max(abs(c_post.mean), 1e-9),
        probability_treatment_better=probability,
    )


def evaluate_experiment(
    definition: ExperimentDefinition,
    control_videos: Sequence[VideoObservation],
    treatment_videos: Sequence[VideoObservation],
    *,
    policy: EvaluationPolicy | None = None,
) -> ExperimentDecision:
    definition.validate()
    policy = policy or EvaluationPolicy()
    control = AggregateObservation.from_videos(tuple(control_videos))
    treatment = AggregateObservation.from_videos(tuple(treatment_videos))

    if control.videos < definition.minimum_videos_per_arm or treatment.videos < definition.minimum_videos_per_arm:
        return ExperimentDecision("continue", "not enough videos per arm", (), control, treatment, 0.0)
    if control.views < definition.minimum_views_per_arm or treatment.views < definition.minimum_views_per_arm:
        return ExperimentDecision("continue", "not enough views per arm", (), control, treatment, 0.0)

    metrics = (definition.primary_metric, *definition.guardrail_metrics)
    comparisons = tuple(
        compare_metric(
            metric,
            control,
            treatment,
            policy=policy,
            seed=hash((definition.experiment_id, metric)) & 0xFFFFFFFF,
        )
        for metric in metrics
    )
    primary = comparisons[0]
    guardrail_failures = [
        comparison
        for comparison in comparisons[1:]
        if comparison.relative_lift < -policy.maximum_guardrail_regression
        and comparison.probability_treatment_better < 0.20
    ]
    if guardrail_failures:
        names = ", ".join(item.metric for item in guardrail_failures)
        return ExperimentDecision(
            "reject",
            f"treatment violates guardrails: {names}",
            comparisons,
            control,
            treatment,
            max(1.0 - item.probability_treatment_better for item in guardrail_failures),
        )

    if (
        primary.probability_treatment_better >= policy.confidence_to_promote
        and primary.relative_lift >= policy.minimum_relative_lift
    ):
        return ExperimentDecision(
            "promote",
            f"treatment improves {definition.primary_metric} with sufficient confidence",
            comparisons,
            control,
            treatment,
            primary.probability_treatment_better,
        )
    if (
        primary.probability_treatment_better <= 1.0 - policy.confidence_to_reject
        and primary.relative_lift <= -policy.minimum_relative_lift
    ):
        return ExperimentDecision(
            "reject",
            f"treatment meaningfully reduces {definition.primary_metric}",
            comparisons,
            control,
            treatment,
            1.0 - primary.probability_treatment_better,
        )
    return ExperimentDecision(
        "continue",
        "evidence is not yet decisive",
        comparisons,
        control,
        treatment,
        max(primary.probability_treatment_better, 1.0 - primary.probability_treatment_better),
    )
