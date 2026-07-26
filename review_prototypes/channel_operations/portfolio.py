from __future__ import annotations

from collections import Counter
from typing import Iterable

from .models import PortfolioResult, ReleaseCandidate
from .readiness import ReadinessGate


class PortfolioPlanner:
    """Choose a publish batch without letting one topic or mechanic dominate."""

    def __init__(
        self,
        *,
        readiness_gate: ReadinessGate | None = None,
        max_topic_share: float = 0.40,
        max_shape_share: float = 0.50,
        max_performance_share: float = 0.35,
    ) -> None:
        self.gate = readiness_gate or ReadinessGate()
        self.max_topic_share = max_topic_share
        self.max_shape_share = max_shape_share
        self.max_performance_share = max_performance_share

    def select(
        self,
        candidates: Iterable[ReleaseCandidate],
        *,
        batch_size: int,
    ) -> PortfolioResult:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        candidates = tuple(candidates)
        decisions = {item.slug: self.gate.evaluate(item) for item in candidates}
        eligible = [item for item in candidates if decisions[item.slug].eligible]
        rejected = {
            slug: decision.reasons
            for slug, decision in decisions.items()
            if not decision.eligible
        }
        selected: list[ReleaseCandidate] = []
        active_experiment: str | None = None

        while eligible and len(selected) < batch_size:
            ranked = sorted(
                eligible,
                key=lambda item: self._marginal_score(selected, item),
                reverse=True,
            )
            chosen = None
            for candidate in ranked:
                if candidate.experiment_id:
                    if active_experiment and candidate.experiment_id != active_experiment:
                        continue
                if self._would_violate_share(selected, candidate):
                    continue
                chosen = candidate
                break
            if chosen is None:
                for candidate in ranked:
                    rejected.setdefault(candidate.slug, ("portfolio diversity constraint",))
                break
            selected.append(chosen)
            eligible.remove(chosen)
            if chosen.experiment_id:
                active_experiment = chosen.experiment_id

        for candidate in eligible:
            rejected.setdefault(candidate.slug, ("not selected within batch capacity",))
        return PortfolioResult(
            selected=tuple(selected),
            rejected=rejected,
            diversity_score=round(self._diversity_score(selected), 3),
            active_experiment_id=active_experiment,
        )

    def _marginal_score(
        self,
        selected: list[ReleaseCandidate],
        candidate: ReleaseCandidate,
    ) -> float:
        base = (
            candidate.quality_score * 0.58
            + candidate.lowest_dimension * 3.0
            + candidate.freshness_score * 12.0
            + candidate.reaction_prediction * 12.0
        )
        if not selected:
            return base
        topics = Counter(item.topic_family for item in selected)
        shapes = Counter(item.story_shape for item in selected)
        performances = Counter(
            family for item in selected for family in item.performance_families
        )
        penalty = topics[candidate.topic_family] * 8.0
        penalty += shapes[candidate.story_shape] * 5.0
        penalty += sum(performances[family] * 3.0 for family in candidate.performance_families)
        if candidate.experiment_id:
            penalty += 3.0
        return base - penalty

    def _would_violate_share(
        self,
        selected: list[ReleaseCandidate],
        candidate: ReleaseCandidate,
    ) -> bool:
        tentative = [*selected, candidate]
        size = len(tentative)
        topics = Counter(item.topic_family for item in tentative)
        shapes = Counter(item.story_shape for item in tentative)
        performances = Counter(
            family for item in tentative for family in item.performance_families
        )
        perf_total = sum(performances.values()) or 1
        if size >= 3 and max(topics.values()) / size > self.max_topic_share:
            return True
        if size >= 3 and max(shapes.values()) / size > self.max_shape_share:
            return True
        if perf_total >= 4 and max(performances.values()) / perf_total > self.max_performance_share:
            return True
        return False

    @staticmethod
    def _diversity_score(selected: list[ReleaseCandidate]) -> float:
        if not selected:
            return 0.0
        topics = len({item.topic_family for item in selected}) / len(selected)
        shapes = len({item.story_shape for item in selected}) / len(selected)
        performances = [family for item in selected for family in item.performance_families]
        performance_diversity = len(set(performances)) / max(1, len(performances))
        return (topics + shapes + performance_diversity) / 3.0
