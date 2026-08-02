"""Review-only semantic scene planning prototype.

NOT WIRED INTO THE PIPELINE.

The live repair prototype currently chooses from chart/performance pairs mostly by
shape. This module demonstrates a stricter contract: story meaning comes first,
and a candidate is renderable only when both the visualization and performance
can preserve that meaning.

Only Python's standard library is used. Importing this module has no side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class StoryIntent:
    claim: str
    data_shape: str
    relationship: str
    direction: str
    required_takeaway: str
    emotional_read: str = "neutral"
    required_affordances: frozenset[str] = frozenset()
    forbidden_distortions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class VisualizationCapability:
    name: str
    supported_shapes: frozenset[str]
    supported_relationships: frozenset[str]
    affordances: frozenset[str]
    implied_distortions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PerformanceCapability:
    family: str
    supported_relationships: frozenset[str]
    supported_emotions: frozenset[str]
    required_affordances: frozenset[str]
    meaning: str
    timeline_phases: tuple[str, ...] = (
        "setup",
        "commitment",
        "effort",
        "reversal",
        "consequence",
        "payoff",
        "recovery",
    )


@dataclass(frozen=True)
class CandidatePlan:
    visualization: str
    performance_family: str
    camera_purpose: str
    payoff: str
    semantic_score: float
    diversity_penalty: float
    final_score: float
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiversityWindow:
    """Recent usage counts supplied by an external history store.

    Counts are intentionally plain mappings so this prototype does not know where
    production history lives.
    """

    total_scenes: int
    performance_counts: Mapping[str, int] = field(default_factory=dict)
    visualization_counts: Mapping[str, int] = field(default_factory=dict)
    signature_counts: Mapping[str, int] = field(default_factory=dict)

    def share(self, counts: Mapping[str, int], key: str) -> float:
        if self.total_scenes <= 0:
            return 0.0
        return counts.get(key, 0) / self.total_scenes


class IncompatibleCandidate(ValueError):
    """Raised only by strict callers that request a single invalid candidate."""


def _missing(required: frozenset[str], offered: frozenset[str]) -> list[str]:
    return sorted(required.difference(offered))


def compatibility(
    intent: StoryIntent,
    viz: VisualizationCapability,
    perf: PerformanceCapability,
) -> tuple[bool, tuple[str, ...], tuple[str, ...], float]:
    """Return compatibility, reasons, warnings, and a 0..1 semantic score.

    Hard incompatibilities cannot be compensated for by diversity. This prevents
    the system from choosing a novel but misleading visual merely because a more
    suitable primitive has been used recently.
    """

    reasons: list[str] = []
    warnings: list[str] = []
    score = 1.0

    if intent.data_shape not in viz.supported_shapes:
        return False, (), (
            f"{viz.name} does not support data shape {intent.data_shape}",
        ), 0.0
    reasons.append(f"visualization supports {intent.data_shape}")

    if intent.relationship not in viz.supported_relationships:
        return False, (), (
            f"{viz.name} cannot preserve relationship {intent.relationship}",
        ), 0.0
    reasons.append(f"visualization preserves {intent.relationship}")

    if intent.relationship not in perf.supported_relationships:
        return False, (), (
            f"{perf.family} does not communicate {intent.relationship}",
        ), 0.0
    reasons.append(f"performance communicates {intent.relationship}")

    missing_viz = _missing(intent.required_affordances, viz.affordances)
    if missing_viz:
        return False, (), (
            "visualization lacks required affordances: " + ", ".join(missing_viz),
        ), 0.0

    missing_perf = _missing(perf.required_affordances, viz.affordances)
    if missing_perf:
        return False, (), (
            "performance cannot attach to visualization; missing: "
            + ", ".join(missing_perf),
        ), 0.0
    reasons.append("performance attachment requirements are available")

    distortions = sorted(
        intent.forbidden_distortions.intersection(viz.implied_distortions)
    )
    if distortions:
        return False, (), (
            "candidate introduces forbidden distortions: " + ", ".join(distortions),
        ), 0.0

    if (
        intent.emotional_read != "neutral"
        and intent.emotional_read not in perf.supported_emotions
    ):
        score -= 0.20
        warnings.append(
            f"performance emotion does not directly match {intent.emotional_read}"
        )
    else:
        reasons.append(f"performance supports emotional read {intent.emotional_read}")

    if len(perf.timeline_phases) < 5:
        score -= 0.25
        warnings.append("performance lacks a full narrative progression")
    else:
        reasons.append("performance has setup, reversal, and consequence phases")

    return True, tuple(reasons), tuple(warnings), max(0.0, min(1.0, score))


def diversity_penalty(
    viz: VisualizationCapability,
    perf: PerformanceCapability,
    history: DiversityWindow | None,
    *,
    payoff: str,
) -> tuple[float, tuple[str, ...]]:
    """Apply a soft penalty after semantic compatibility has passed.

    Diversity never makes an incompatible candidate valid. Severe repetition is
    reported so an orchestrator may choose to generate additional candidates.
    """

    if history is None or history.total_scenes <= 0:
        return 0.0, ()

    warnings: list[str] = []
    penalty = 0.0

    perf_share = history.share(history.performance_counts, perf.family)
    if perf_share > 0.25:
        penalty += min(0.30, (perf_share - 0.25) * 0.8)
        warnings.append(f"performance family recent share is {perf_share:.0%}")

    viz_share = history.share(history.visualization_counts, viz.name)
    if viz_share > 0.40:
        penalty += min(0.20, (viz_share - 0.40) * 0.5)
        warnings.append(f"visualization recent share is {viz_share:.0%}")

    signature = f"{viz.name}|{perf.family}|{payoff}"
    repeated = history.signature_counts.get(signature, 0)
    if repeated:
        penalty += min(0.25, repeated * 0.10)
        warnings.append(f"exact structural signature appeared {repeated} time(s)")

    return min(0.60, penalty), tuple(warnings)


def rank_candidates(
    intent: StoryIntent,
    visualizations: Iterable[VisualizationCapability],
    performances: Iterable[PerformanceCapability],
    history: DiversityWindow | None = None,
    *,
    camera_purposes: Mapping[tuple[str, str], str] | None = None,
    payoffs: Mapping[tuple[str, str], str] | None = None,
) -> list[CandidatePlan]:
    """Build and rank all semantically valid chart/performance combinations."""

    camera_purposes = camera_purposes or {}
    payoffs = payoffs or {}
    plans: list[CandidatePlan] = []

    for viz in visualizations:
        for perf in performances:
            ok, reasons, warnings, semantic = compatibility(intent, viz, perf)
            if not ok:
                continue

            key = (viz.name, perf.family)
            camera = camera_purposes.get(
                key,
                f"clarify {intent.relationship} without decorative drift",
            )
            payoff = payoffs.get(key, perf.meaning)
            penalty, diversity_warnings = diversity_penalty(
                viz,
                perf,
                history,
                payoff=payoff,
            )
            final = max(0.0, semantic - penalty)
            plans.append(
                CandidatePlan(
                    visualization=viz.name,
                    performance_family=perf.family,
                    camera_purpose=camera,
                    payoff=payoff,
                    semantic_score=round(semantic, 4),
                    diversity_penalty=round(penalty, 4),
                    final_score=round(final, 4),
                    reasons=reasons,
                    warnings=warnings + diversity_warnings,
                )
            )

    return sorted(
        plans,
        key=lambda plan: (
            plan.final_score,
            plan.semantic_score,
            -len(plan.warnings),
            plan.visualization,
            plan.performance_family,
        ),
        reverse=True,
    )


def require_candidate(
    intent: StoryIntent,
    viz: VisualizationCapability,
    perf: PerformanceCapability,
) -> CandidatePlan:
    """Strict helper useful for unit tests or explicit operator choices."""

    plans = rank_candidates(intent, [viz], [perf])
    if not plans:
        ok, _reasons, warnings, _score = compatibility(intent, viz, perf)
        assert not ok
        raise IncompatibleCandidate("; ".join(warnings))
    return plans[0]


def default_capabilities() -> tuple[
    Sequence[VisualizationCapability], Sequence[PerformanceCapability]
]:
    """Small illustrative library; not intended as a production registry."""

    visualizations = (
        VisualizationCapability(
            name="trend_line",
            supported_shapes=frozenset({"trend", "timeline"}),
            supported_relationships=frozenset({"increase", "decrease", "acceleration"}),
            affordances=frozenset({"moving_endpoint", "line_path", "baseline"}),
        ),
        VisualizationCapability(
            name="weighted_balance",
            supported_shapes=frozenset({"part_to_whole", "two_value"}),
            supported_relationships=frozenset({"dominance", "imbalance", "comparison"}),
            affordances=frozenset({"beam", "left_platform", "right_platform", "pivot"}),
        ),
        VisualizationCapability(
            name="ranked_bars",
            supported_shapes=frozenset({"ranking", "two_value"}),
            supported_relationships=frozenset({"ranking", "overtake", "comparison"}),
            affordances=frozenset({"bar_face", "bar_top", "baseline"}),
        ),
    )

    performances = (
        PerformanceCapability(
            family="resisted_growth",
            supported_relationships=frozenset({"increase", "acceleration"}),
            supported_emotions=frozenset({"alarming", "overwhelming"}),
            required_affordances=frozenset({"moving_endpoint", "baseline"}),
            meaning="the value overpowers the mascot despite visible resistance",
        ),
        PerformanceCapability(
            family="overwhelmed_balance",
            supported_relationships=frozenset({"dominance", "imbalance"}),
            supported_emotions=frozenset({"overwhelming", "surprising"}),
            required_affordances=frozenset({"beam", "left_platform", "right_platform"}),
            meaning="the dominant side tips the system and dislodges the mascot",
        ),
        PerformanceCapability(
            family="finish_line_overtake",
            supported_relationships=frozenset({"ranking", "overtake"}),
            supported_emotions=frozenset({"competitive", "surprising"}),
            required_affordances=frozenset({"bar_face", "baseline"}),
            meaning="one category visibly passes another at the payoff",
        ),
    )
    return visualizations, performances
