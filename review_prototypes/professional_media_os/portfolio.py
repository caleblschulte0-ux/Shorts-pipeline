"""Bounded, deterministic portfolio planning for the isolated prototype."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import (
    Candidate,
    ContractError,
    PortfolioConstraints,
    PortfolioPlan,
    stable_hash,
)


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    utility: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.utility <= 1.0:
            raise ContractError("portfolio utility must be between 0 and 1")


class PortfolioPlanner:
    """Select a slate while preserving explicit rejection reasons.

    This is a deterministic reference algorithm, not an optimal solver. Its value is the
    constraint contract and audit trail. A later production implementation may replace the
    search strategy without changing the observable record shape.
    """

    def plan(
        self,
        scored_candidates: Sequence[ScoredCandidate],
        constraints: PortfolioConstraints,
        *,
        plan_id: Optional[str] = None,
    ) -> PortfolioPlan:
        if not scored_candidates:
            raise ContractError("portfolio planning requires at least one candidate")

        ids = [item.candidate.candidate_id for item in scored_candidates]
        if len(ids) != len(set(ids)):
            raise ContractError("candidate ids must be unique within a portfolio run")

        sorted_items = sorted(
            scored_candidates,
            key=lambda item: (
                -item.utility,
                item.candidate.genome.estimated_cost,
                item.candidate.genome.estimated_runtime_seconds,
                item.candidate.candidate_id,
            ),
        )

        rejected: Dict[str, Tuple[str, ...]] = {}
        preeligible: List[ScoredCandidate] = []
        for item in sorted_items:
            reasons = self._static_rejections(item.candidate, constraints)
            if reasons:
                rejected[item.candidate.candidate_id] = tuple(reasons)
            else:
                preeligible.append(item)

        selected: List[ScoredCandidate] = []
        channel_counts: Counter[str] = Counter()
        topic_counts: Counter[str] = Counter()
        total_cost = 0.0
        total_runtime = 0.0

        exploration_pool = [item for item in preeligible if item.candidate.exploration]
        exploitation_pool = [item for item in preeligible if not item.candidate.exploration]

        for item in exploration_pool:
            if len(selected) >= constraints.minimum_exploration:
                break
            reasons = self._dynamic_rejections(
                item.candidate,
                constraints,
                channel_counts,
                topic_counts,
                total_cost,
                total_runtime,
            )
            if reasons:
                rejected[item.candidate.candidate_id] = tuple(reasons)
                continue
            selected.append(item)
            channel_counts[item.candidate.genome.channel_id] += 1
            topic_counts[item.candidate.genome.event_type] += 1
            total_cost += item.candidate.genome.estimated_cost
            total_runtime += item.candidate.genome.estimated_runtime_seconds

        remaining = [
            item
            for item in sorted_items
            if item.candidate.candidate_id not in {entry.candidate.candidate_id for entry in selected}
            and item.candidate.candidate_id not in rejected
        ]

        for item in remaining:
            if len(selected) >= constraints.target_count:
                rejected[item.candidate.candidate_id] = ("portfolio.target-filled",)
                continue
            reasons = self._dynamic_rejections(
                item.candidate,
                constraints,
                channel_counts,
                topic_counts,
                total_cost,
                total_runtime,
            )
            if reasons:
                rejected[item.candidate.candidate_id] = tuple(reasons)
                continue
            selected.append(item)
            channel_counts[item.candidate.genome.channel_id] += 1
            topic_counts[item.candidate.genome.event_type] += 1
            total_cost += item.candidate.genome.estimated_cost
            total_runtime += item.candidate.genome.estimated_runtime_seconds

        exploration_count = sum(item.candidate.exploration for item in selected)
        if exploration_count < constraints.minimum_exploration:
            missing = constraints.minimum_exploration - exploration_count
            rejected["__portfolio__"] = (
                f"portfolio.exploration-floor-unmet:{missing}",
            )

        if len(selected) < constraints.target_count:
            rejected.setdefault("__portfolio__", tuple())
            rejected["__portfolio__"] = rejected["__portfolio__"] + (
                f"portfolio.target-count-unmet:{constraints.target_count - len(selected)}",
            )

        final_id = plan_id or f"portfolio-{stable_hash({'ids': ids, 'constraints': constraints})[:16]}"
        return PortfolioPlan(
            plan_id=final_id,
            selected_candidate_ids=tuple(item.candidate.candidate_id for item in selected),
            rejected_reasons=rejected,
            total_cost=round(total_cost, 6),
            total_runtime_seconds=round(total_runtime, 3),
            exploration_count=exploration_count,
            constraint_hash=stable_hash(constraints),
        )

    @staticmethod
    def _static_rejections(
        candidate: Candidate,
        constraints: PortfolioConstraints,
    ) -> List[str]:
        genome = candidate.genome
        reasons: List[str] = []
        if genome.rights_risk not in constraints.allowed_rights_risks:
            reasons.append("rights.risk-disallowed")
        if genome.evidence_completeness < constraints.minimum_evidence_completeness:
            reasons.append("evidence.completeness-below-floor")
        if genome.media_feasibility < constraints.minimum_media_feasibility:
            reasons.append("media.feasibility-below-floor")
        if genome.channel_id not in constraints.maximum_per_channel:
            reasons.append("channel.capacity-undefined")
        return reasons

    @staticmethod
    def _dynamic_rejections(
        candidate: Candidate,
        constraints: PortfolioConstraints,
        channel_counts: Mapping[str, int],
        topic_counts: Mapping[str, int],
        total_cost: float,
        total_runtime: float,
    ) -> List[str]:
        genome = candidate.genome
        reasons: List[str] = []
        channel_limit = constraints.maximum_per_channel.get(genome.channel_id, 0)
        if channel_counts.get(genome.channel_id, 0) >= channel_limit:
            reasons.append("channel.capacity-reached")
        if topic_counts.get(genome.event_type, 0) >= constraints.maximum_per_topic:
            reasons.append("topic.diversity-cap-reached")
        if total_cost + genome.estimated_cost > constraints.maximum_total_cost:
            reasons.append("budget.cost-cap-exceeded")
        if (
            total_runtime + genome.estimated_runtime_seconds
            > constraints.maximum_total_runtime_seconds
        ):
            reasons.append("budget.runtime-cap-exceeded")
        return reasons
