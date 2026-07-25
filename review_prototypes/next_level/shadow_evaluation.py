"""Review-only post-90 shadow evaluation and drift detection prototype.

NOT WIRED INTO THE PIPELINE.

Once benchmark performance is strong, the next risk is overfitting. This module
models holdout/shadow comparisons and distribution drift without publishing or
invoking any external system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Mapping, Sequence


@dataclass(frozen=True)
class DistributionSnapshot:
    window_id: str
    story_shapes: Mapping[str, int]
    topics: Mapping[str, int]
    performance_families: Mapping[str, int]
    failure_classes: Mapping[str, int]
    scores: tuple[float, ...]
    narration_seconds: tuple[float, ...] = ()


@dataclass(frozen=True)
class DriftThresholds:
    categorical_total_variation: float = 0.25
    score_mean_change: float = 5.0
    narration_mean_change_seconds: float = 4.0
    new_failure_class_count: int = 1


@dataclass(frozen=True)
class DriftSignal:
    category: str
    magnitude: float
    threshold: float
    detail: str


@dataclass(frozen=True)
class DriftReport:
    drifted: bool
    signals: tuple[DriftSignal, ...]


def _normalize(counts: Mapping[str, int]) -> Mapping[str, float]:
    total = sum(max(0, value) for value in counts.values())
    if total <= 0:
        return {}
    return {key: max(0, value) / total for key, value in counts.items()}


def total_variation(left: Mapping[str, int], right: Mapping[str, int]) -> float:
    """Return categorical total-variation distance in the range 0..1."""

    p = _normalize(left)
    q = _normalize(right)
    keys = set(p).union(q)
    return 0.5 * sum(abs(p.get(key, 0.0) - q.get(key, 0.0)) for key in keys)


def detect_drift(
    baseline: DistributionSnapshot,
    current: DistributionSnapshot,
    thresholds: DriftThresholds = DriftThresholds(),
) -> DriftReport:
    signals: list[DriftSignal] = []

    for category, before, after in (
        ("story_shapes", baseline.story_shapes, current.story_shapes),
        ("topics", baseline.topics, current.topics),
        (
            "performance_families",
            baseline.performance_families,
            current.performance_families,
        ),
    ):
        magnitude = total_variation(before, after)
        if magnitude > thresholds.categorical_total_variation:
            signals.append(
                DriftSignal(
                    category=category,
                    magnitude=round(magnitude, 4),
                    threshold=thresholds.categorical_total_variation,
                    detail=f"{category} distribution moved materially",
                )
            )

    if baseline.scores and current.scores:
        score_change = abs(mean(current.scores) - mean(baseline.scores))
        if score_change > thresholds.score_mean_change:
            signals.append(
                DriftSignal(
                    category="score_mean",
                    magnitude=round(score_change, 4),
                    threshold=thresholds.score_mean_change,
                    detail="mean judge score changed beyond calibrated range",
                )
            )

    if baseline.narration_seconds and current.narration_seconds:
        narration_change = abs(
            mean(current.narration_seconds) - mean(baseline.narration_seconds)
        )
        if narration_change > thresholds.narration_mean_change_seconds:
            signals.append(
                DriftSignal(
                    category="narration_length",
                    magnitude=round(narration_change, 4),
                    threshold=thresholds.narration_mean_change_seconds,
                    detail="average narration length changed materially",
                )
            )

    new_failure_classes = set(current.failure_classes).difference(
        baseline.failure_classes
    )
    meaningful_new = [
        label
        for label in new_failure_classes
        if current.failure_classes.get(label, 0) >= thresholds.new_failure_class_count
    ]
    if meaningful_new:
        signals.append(
            DriftSignal(
                category="new_failure_classes",
                magnitude=float(len(meaningful_new)),
                threshold=float(thresholds.new_failure_class_count),
                detail="new failures: " + ", ".join(sorted(meaningful_new)),
            )
        )

    return DriftReport(drifted=bool(signals), signals=tuple(signals))


@dataclass(frozen=True)
class ShadowCandidate:
    candidate_id: str
    score: float
    lowest_dimension: float
    hard_failures: tuple[str, ...]
    adversarial_objections: tuple[str, ...]
    artifact_manifest_hash: str

    @property
    def eligible(self) -> bool:
        return bool(self.artifact_manifest_hash) and not (
            self.hard_failures or self.adversarial_objections
        )


@dataclass(frozen=True)
class ShadowPair:
    story_slug: str
    canonical: ShadowCandidate
    experimental: ShadowCandidate
    unseen_story_shape: bool = False
    new_performance_family: bool = False
    judge_disagreement: bool = False


@dataclass(frozen=True)
class ShadowDecision:
    winner: str
    experimental_wins: bool
    publish_experimental: bool
    reasons: tuple[str, ...]
    human_review_recommended: bool


def compare_shadow(pair: ShadowPair) -> ShadowDecision:
    """Compare an experiment while always keeping publication disabled.

    Shadow evaluation measures transfer. It never grants permission to publish
    the experimental output automatically.
    """

    reasons: list[str] = []
    experimental_wins = False

    if not pair.experimental.eligible:
        reasons.append("experimental candidate is not independently eligible")
    elif not pair.canonical.eligible:
        experimental_wins = True
        reasons.append("canonical candidate is ineligible while experiment passes")
    elif pair.experimental.score > pair.canonical.score:
        if pair.experimental.lowest_dimension >= pair.canonical.lowest_dimension:
            experimental_wins = True
            reasons.append("experiment improves score without lowering weakest dimension")
        else:
            reasons.append("experiment raises total score but weakens lowest dimension")
    else:
        reasons.append("experiment does not beat canonical score")

    human_review = bool(
        pair.unseen_story_shape
        or pair.new_performance_family
        or pair.judge_disagreement
        or abs(pair.experimental.score - pair.canonical.score) <= 2.0
    )
    if human_review:
        reasons.append("pair matches calibrated human-review sampling criteria")

    return ShadowDecision(
        winner=(pair.experimental.candidate_id if experimental_wins else pair.canonical.candidate_id),
        experimental_wins=experimental_wins,
        publish_experimental=False,
        reasons=tuple(reasons),
        human_review_recommended=human_review,
    )


def sample_for_human_review(
    pairs: Sequence[ShadowPair],
    *,
    limit: int = 10,
) -> tuple[ShadowPair, ...]:
    """Prioritize unfamiliar, disputed, and close shadow comparisons."""

    def priority(pair: ShadowPair) -> tuple[int, int, int, float]:
        closeness = -abs(pair.experimental.score - pair.canonical.score)
        return (
            int(pair.judge_disagreement),
            int(pair.unseen_story_shape),
            int(pair.new_performance_family),
            closeness,
        )

    return tuple(sorted(pairs, key=priority, reverse=True)[:limit])
