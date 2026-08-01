from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class BatchDecision(str, Enum):
    PASS = "pass"
    REVISE = "revise"
    REJECT = "reject"


@dataclass(frozen=True)
class StoryAcceptance:
    story_id: str
    topic_family: str
    format_family: str
    completed: bool
    quarantined: bool
    quality_score: float | None
    artifact_hash_bound: bool
    factual_evidence_complete: bool
    technical_pass: bool
    editorial_pass: bool
    hard_blockers: tuple[str, ...] = ()
    hook_family: str = ""
    visual_family: str = ""

    def __post_init__(self) -> None:
        if not self.story_id.strip():
            raise ValueError("story_id is required")
        if self.quality_score is not None and not 0 <= self.quality_score <= 10:
            raise ValueError("quality_score must be between 0 and 10")
        if self.completed and self.quarantined:
            raise ValueError("story cannot be completed and quarantined")


@dataclass(frozen=True)
class BatchAcceptancePolicy:
    minimum_completion_rate: float = 0.8
    maximum_quarantine_rate: float = 0.2
    minimum_quality_score: float = 7.5
    minimum_topic_families: int = 4
    minimum_format_families: int = 3
    maximum_hook_family_share: float = 0.3
    maximum_visual_family_share: float = 0.4
    require_hash_binding: bool = True
    require_factual_evidence: bool = True

    def __post_init__(self) -> None:
        for name in ("minimum_completion_rate", "maximum_quarantine_rate", "maximum_hook_family_share", "maximum_visual_family_share"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if not 0 <= self.minimum_quality_score <= 10:
            raise ValueError("minimum_quality_score must be between 0 and 10")
        if self.minimum_topic_families < 1 or self.minimum_format_families < 1:
            raise ValueError("diversity requirements must be positive")


@dataclass(frozen=True)
class BatchAcceptanceReport:
    decision: BatchDecision
    completion_rate: float
    quarantine_rate: float
    mean_quality: float
    topic_families: int
    format_families: int
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]


def _largest_share(values: Iterable[str]) -> float:
    items = [value for value in values if value]
    if not items:
        return 0.0
    counts: dict[str, int] = {}
    for value in items:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.values()) / len(items)


def evaluate_batch_acceptance(stories: Iterable[StoryAcceptance], policy: BatchAcceptancePolicy = BatchAcceptancePolicy()) -> BatchAcceptanceReport:
    items = tuple(stories)
    if not items:
        raise ValueError("at least one story record is required")
    ids = [item.story_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate story acceptance record")

    completed = [item for item in items if item.completed]
    quarantined = [item for item in items if item.quarantined]
    completion_rate = len(completed) / len(items)
    quarantine_rate = len(quarantined) / len(items)
    quality_values = [item.quality_score for item in completed if item.quality_score is not None]
    mean_quality = sum(quality_values) / len(quality_values) if quality_values else 0.0

    blockers: list[str] = []
    warnings: list[str] = []
    if completion_rate < policy.minimum_completion_rate:
        blockers.append("completion_rate_below_floor")
    if quarantine_rate > policy.maximum_quarantine_rate:
        blockers.append("quarantine_rate_above_ceiling")
    if any(item.hard_blockers for item in completed):
        blockers.append("completed_story_has_hard_blocker")
    if any(not item.technical_pass or not item.editorial_pass for item in completed):
        blockers.append("completed_story_missing_required_judge_pass")
    if any(item.quality_score is None or item.quality_score < policy.minimum_quality_score for item in completed):
        blockers.append("completed_story_below_quality_floor")
    if policy.require_hash_binding and any(not item.artifact_hash_bound for item in completed):
        blockers.append("completed_story_not_hash_bound")
    if policy.require_factual_evidence and any(not item.factual_evidence_complete for item in completed):
        blockers.append("completed_story_missing_factual_evidence")

    topic_families = len({item.topic_family for item in completed})
    format_families = len({item.format_family for item in completed})
    if topic_families < min(policy.minimum_topic_families, len(completed)):
        warnings.append("topic_diversity_below_target")
    if format_families < min(policy.minimum_format_families, len(completed)):
        warnings.append("format_diversity_below_target")
    if _largest_share(item.hook_family for item in completed) > policy.maximum_hook_family_share:
        warnings.append("hook_family_overconcentrated")
    if _largest_share(item.visual_family for item in completed) > policy.maximum_visual_family_share:
        warnings.append("visual_family_overconcentrated")
    if mean_quality < policy.minimum_quality_score:
        warnings.append("mean_quality_below_target")

    decision = BatchDecision.REJECT if blockers else BatchDecision.REVISE if warnings else BatchDecision.PASS
    return BatchAcceptanceReport(
        decision=decision,
        completion_rate=round(completion_rate, 4),
        quarantine_rate=round(quarantine_rate, 4),
        mean_quality=round(mean_quality, 3),
        topic_families=topic_families,
        format_families=format_families,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
    )
