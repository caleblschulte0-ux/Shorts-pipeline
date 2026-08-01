from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class AudienceLevel(str, Enum):
    GENERAL = "general"
    ENTHUSIAST = "enthusiast"
    EXPERT = "expert"


class FactualRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MediaMode(str, Enum):
    ANIMATION = "animation"
    REAL_MEDIA = "real_media"
    MIXED = "mixed"
    DATA_VISUALIZATION = "data_visualization"


@dataclass(frozen=True)
class StoryBrief:
    story_id: str
    topic_family: str
    format_family: str
    core_question: str
    target_seconds: int
    audience: AudienceLevel
    factual_risk: FactualRisk
    media_mode: MediaMode
    priority: int = 50
    exploration: bool = False
    required_claim_types: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        text_fields = {
            "story_id": self.story_id,
            "topic_family": self.topic_family,
            "format_family": self.format_family,
            "core_question": self.core_question,
        }
        for name, value in text_fields.items():
            if not value.strip():
                raise ValueError(f"{name} is required")
        if "/" in self.story_id or "\\" in self.story_id:
            raise ValueError("story_id must be an opaque identifier, not a path")
        if not 0 <= self.priority <= 100:
            raise ValueError("priority must be between 0 and 100")
        for field_name in ("required_claim_types", "constraints", "tags"):
            values = getattr(self, field_name)
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} cannot contain duplicates")


@dataclass(frozen=True)
class IntakePolicy:
    maximum_stories: int = 50
    minimum_seconds: int = 20
    maximum_seconds: int = 600
    supported_formats: frozenset[str] = frozenset()
    allowed_media_modes: frozenset[MediaMode] = frozenset(MediaMode)
    maximum_high_risk_share: float = 0.4
    require_claim_types_for_high_risk: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.maximum_stories <= 50:
            raise ValueError("maximum_stories must be between 1 and 50")
        if self.minimum_seconds <= 0 or self.maximum_seconds < self.minimum_seconds:
            raise ValueError("invalid duration bounds")
        if not 0 <= self.maximum_high_risk_share <= 1:
            raise ValueError("maximum_high_risk_share must be between 0 and 1")
        if not self.allowed_media_modes:
            raise ValueError("at least one media mode must be allowed")


@dataclass(frozen=True)
class StoryRejection:
    story_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class IntakeReport:
    accepted: tuple[StoryBrief, ...]
    rejected: tuple[StoryRejection, ...]
    warnings: tuple[str, ...]
    valid: bool


def validate_story_batch(
    briefs: Iterable[StoryBrief],
    policy: IntakePolicy = IntakePolicy(),
) -> IntakeReport:
    items = tuple(briefs)
    ids = [item.story_id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate story_id in intake batch")
    if len(items) > policy.maximum_stories:
        raise ValueError("intake batch exceeds configured story capacity")

    accepted: list[StoryBrief] = []
    rejected: list[StoryRejection] = []
    for brief in items:
        reasons: list[str] = []
        if not policy.minimum_seconds <= brief.target_seconds <= policy.maximum_seconds:
            reasons.append("duration_out_of_policy")
        if policy.supported_formats and brief.format_family not in policy.supported_formats:
            reasons.append("unsupported_format")
        if brief.media_mode not in policy.allowed_media_modes:
            reasons.append("media_mode_not_allowed")
        if brief.factual_risk is FactualRisk.HIGH and policy.require_claim_types_for_high_risk and not brief.required_claim_types:
            reasons.append("high_risk_without_claim_contract")
        if len(brief.core_question.split()) < 3:
            reasons.append("core_question_too_vague")
        if reasons:
            rejected.append(StoryRejection(brief.story_id, tuple(sorted(set(reasons)))))
        else:
            accepted.append(brief)

    accepted.sort(key=lambda item: (-item.priority, not item.exploration, item.story_id))
    high_risk = sum(item.factual_risk is FactualRisk.HIGH for item in accepted)
    high_risk_share = high_risk / len(accepted) if accepted else 0.0
    warnings: list[str] = []
    if high_risk_share > policy.maximum_high_risk_share:
        warnings.append("high_risk_share_exceeds_policy")
    if not accepted:
        warnings.append("no_stories_accepted")
    topic_count = len({item.topic_family for item in accepted})
    format_count = len({item.format_family for item in accepted})
    if len(accepted) >= 4 and topic_count < 2:
        warnings.append("topic_diversity_low")
    if len(accepted) >= 4 and format_count < 2:
        warnings.append("format_diversity_low")

    return IntakeReport(
        accepted=tuple(accepted),
        rejected=tuple(sorted(rejected, key=lambda item: item.story_id)),
        warnings=tuple(sorted(warnings)),
        valid=bool(accepted) and high_risk_share <= policy.maximum_high_risk_share,
    )
