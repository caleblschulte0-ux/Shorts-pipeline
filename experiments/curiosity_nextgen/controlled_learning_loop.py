"""Dormant bounded learning loop for evidence-backed policy proposals."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class PerformanceObservation:
    story_id: str
    experiment_id: str
    variant: str
    policy_version: str
    impressions: int
    average_watch_ratio: float
    completion_rate: float
    negative_feedback_rate: float
    hard_blocker: bool = False

    def __post_init__(self) -> None:
        if not self.story_id or not self.experiment_id or not self.variant or not self.policy_version:
            raise ValueError("observation identity fields are required")
        if self.impressions < 0:
            raise ValueError("impressions cannot be negative")
        for name in ("average_watch_ratio", "completion_rate", "negative_feedback_rate"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class LearningPolicy:
    minimum_total_impressions: int = 10_000
    minimum_stories_per_variant: int = 5
    minimum_watch_ratio_lift: float = 0.02
    minimum_completion_lift: float = 0.015
    maximum_negative_feedback_increase: float = 0.005
    maximum_parameter_delta: float = 0.10
    required_canary_batches: int = 2

    def __post_init__(self) -> None:
        if self.minimum_total_impressions < 1 or self.minimum_stories_per_variant < 1:
            raise ValueError("sample requirements must be positive")
        if self.maximum_parameter_delta <= 0 or self.maximum_parameter_delta > 1:
            raise ValueError("maximum_parameter_delta must be in (0, 1]")
        if self.required_canary_batches < 1:
            raise ValueError("required_canary_batches must be positive")


@dataclass(frozen=True)
class PolicyProposal:
    experiment_id: str
    base_policy_version: str
    winning_variant: str | None
    proposed_parameters: tuple[tuple[str, float], ...]
    evidence_digest: str | None
    status: str
    blockers: tuple[str, ...]
    required_canary_batches: int


def _variant_summary(observations: Iterable[PerformanceObservation]) -> dict[str, tuple[int, int, float, float, float, bool]]:
    grouped: dict[str, list[PerformanceObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.variant, []).append(observation)
    summary: dict[str, tuple[int, int, float, float, float, bool]] = {}
    for variant, items in grouped.items():
        summary[variant] = (
            sum(item.impressions for item in items),
            len({item.story_id for item in items}),
            mean(item.average_watch_ratio for item in items),
            mean(item.completion_rate for item in items),
            mean(item.negative_feedback_rate for item in items),
            any(item.hard_blocker for item in items),
        )
    return summary


def propose_policy_update(
    observations: Iterable[PerformanceObservation],
    *,
    control_variant: str,
    candidate_parameters: dict[str, float],
    policy: LearningPolicy,
) -> PolicyProposal:
    items = tuple(observations)
    blockers: list[str] = []
    if not items:
        return PolicyProposal("", "", None, (), None, "hold", ("no_observations",), policy.required_canary_batches)
    experiment_ids = {item.experiment_id for item in items}
    policy_versions = {item.policy_version for item in items}
    if len(experiment_ids) != 1:
        blockers.append("mixed_experiments")
    if len(policy_versions) != 1:
        blockers.append("mixed_policy_versions")
    if len({(item.story_id, item.variant) for item in items}) != len(items):
        blockers.append("duplicate_story_variant_observation")

    summary = _variant_summary(items)
    if control_variant not in summary:
        blockers.append("missing_control_variant")
    if len(summary) < 2:
        blockers.append("missing_treatment_variant")
    if sum(item.impressions for item in items) < policy.minimum_total_impressions:
        blockers.append("insufficient_total_impressions")
    for variant, (_, story_count, _, _, _, hard_blocker) in summary.items():
        if story_count < policy.minimum_stories_per_variant:
            blockers.append(f"insufficient_story_count:{variant}")
        if hard_blocker:
            blockers.append(f"hard_blocker:{variant}")

    winner: str | None = None
    if not blockers:
        control = summary[control_variant]
        candidates = []
        for variant, metrics in summary.items():
            if variant == control_variant:
                continue
            watch_lift = metrics[2] - control[2]
            completion_lift = metrics[3] - control[3]
            negative_delta = metrics[4] - control[4]
            if (
                watch_lift >= policy.minimum_watch_ratio_lift
                and completion_lift >= policy.minimum_completion_lift
                and negative_delta <= policy.maximum_negative_feedback_increase
            ):
                candidates.append((watch_lift + completion_lift - max(0.0, negative_delta), variant))
        if candidates:
            winner = sorted(candidates, key=lambda item: (-item[0], item[1]))[0][1]
        else:
            blockers.append("no_variant_clears_guardrails")

    bounded_parameters: list[tuple[str, float]] = []
    for name, delta in sorted(candidate_parameters.items()):
        if abs(delta) > policy.maximum_parameter_delta:
            blockers.append(f"parameter_delta_exceeds_limit:{name}")
        else:
            bounded_parameters.append((name, delta))

    evidence_digest: str | None = None
    if not blockers:
        evidence = [
            {
                "story_id": item.story_id,
                "experiment_id": item.experiment_id,
                "variant": item.variant,
                "policy_version": item.policy_version,
                "impressions": item.impressions,
                "average_watch_ratio": item.average_watch_ratio,
                "completion_rate": item.completion_rate,
                "negative_feedback_rate": item.negative_feedback_rate,
                "hard_blocker": item.hard_blocker,
            }
            for item in sorted(items, key=lambda value: (value.variant, value.story_id))
        ]
        evidence_digest = sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    return PolicyProposal(
        experiment_id=sorted(experiment_ids)[0] if len(experiment_ids) == 1 else "",
        base_policy_version=sorted(policy_versions)[0] if len(policy_versions) == 1 else "",
        winning_variant=winner,
        proposed_parameters=tuple(bounded_parameters) if winner else (),
        evidence_digest=evidence_digest,
        status="canary_required" if not blockers else "hold",
        blockers=tuple(sorted(set(blockers))),
        required_canary_batches=policy.required_canary_batches,
    )


def approve_learning_canary(proposal: PolicyProposal, *, passed_batches: int, rollback_ready: bool) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if proposal.status != "canary_required" or proposal.blockers:
        blockers.append("proposal_not_canary_ready")
    if passed_batches < proposal.required_canary_batches:
        blockers.append("insufficient_canary_batches")
    if not rollback_ready:
        blockers.append("rollback_not_ready")
    if not proposal.evidence_digest:
        blockers.append("missing_evidence_digest")
    return not blockers, tuple(blockers)
