from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Mapping


class AnalyticsValidationError(ValueError):
    pass


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class VideoObservation:
    slug: str
    published_at: datetime
    duration_seconds: float
    views: int
    shown_in_feed: int
    swiped_away: int
    completed_views: int
    watched_seconds: float
    likes: int
    comments: int
    shares: int
    subscribers_gained: int
    premise_pattern: str
    visual_pattern: str
    performance_families: tuple[str, ...]
    domain: str
    relationship: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.slug.strip():
            raise AnalyticsValidationError("slug is required")
        if self.published_at.tzinfo is None:
            raise AnalyticsValidationError("published_at must be timezone-aware")
        if not math.isfinite(self.duration_seconds) or self.duration_seconds <= 0:
            raise AnalyticsValidationError("duration_seconds must be positive")
        count_fields = {
            "views": self.views,
            "shown_in_feed": self.shown_in_feed,
            "swiped_away": self.swiped_away,
            "completed_views": self.completed_views,
            "likes": self.likes,
            "comments": self.comments,
            "shares": self.shares,
            "subscribers_gained": self.subscribers_gained,
        }
        for name, value in count_fields.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise AnalyticsValidationError(f"{name} must be a non-negative integer")
        if self.shown_in_feed and self.views > self.shown_in_feed:
            raise AnalyticsValidationError("views cannot exceed shown_in_feed")
        if self.shown_in_feed and self.swiped_away > self.shown_in_feed:
            raise AnalyticsValidationError("swiped_away cannot exceed shown_in_feed")
        if self.completed_views > self.views:
            raise AnalyticsValidationError("completed_views cannot exceed views")
        if any(value > self.views for value in (self.likes, self.comments, self.shares, self.subscribers_gained)):
            raise AnalyticsValidationError("engagement counts cannot exceed views")
        if not math.isfinite(self.watched_seconds) or self.watched_seconds < 0:
            raise AnalyticsValidationError("watched_seconds must be non-negative")
        if not self.premise_pattern or not self.visual_pattern:
            raise AnalyticsValidationError("premise_pattern and visual_pattern are required")

    @property
    def viewed_rate(self) -> float:
        return self.views / self.shown_in_feed if self.shown_in_feed else 0.0

    @property
    def completion_rate(self) -> float:
        return self.completed_views / self.views if self.views else 0.0

    @property
    def average_percentage_viewed(self) -> float:
        if not self.views:
            return 0.0
        return self.watched_seconds / (self.views * self.duration_seconds)

    @property
    def like_rate(self) -> float:
        return self.likes / self.views if self.views else 0.0

    @property
    def comment_rate(self) -> float:
        return self.comments / self.views if self.views else 0.0

    @property
    def share_rate(self) -> float:
        return self.shares / self.views if self.views else 0.0

    @property
    def subscriber_rate(self) -> float:
        return self.subscribers_gained / self.views if self.views else 0.0

    @property
    def reaction_rate(self) -> float:
        if not self.views:
            return 0.0
        weighted = self.likes + 3 * self.comments + 4 * self.shares + 6 * self.subscribers_gained
        return weighted / self.views


@dataclass(frozen=True)
class AggregateObservation:
    videos: int
    views: int
    shown_in_feed: int
    completed_views: int
    watched_seconds: float
    total_duration_view_opportunities: float
    likes: int
    comments: int
    shares: int
    subscribers_gained: int

    @classmethod
    def from_videos(cls, videos: tuple[VideoObservation, ...]) -> "AggregateObservation":
        for video in videos:
            video.validate()
        return cls(
            videos=len(videos),
            views=sum(video.views for video in videos),
            shown_in_feed=sum(video.shown_in_feed for video in videos),
            completed_views=sum(video.completed_views for video in videos),
            watched_seconds=sum(video.watched_seconds for video in videos),
            total_duration_view_opportunities=sum(video.duration_seconds * video.views for video in videos),
            likes=sum(video.likes for video in videos),
            comments=sum(video.comments for video in videos),
            shares=sum(video.shares for video in videos),
            subscribers_gained=sum(video.subscribers_gained for video in videos),
        )

    @property
    def average_percentage_viewed(self) -> float:
        if not self.total_duration_view_opportunities:
            return 0.0
        return self.watched_seconds / self.total_duration_view_opportunities


@dataclass(frozen=True)
class ExperimentDefinition:
    experiment_id: str
    hypothesis: str
    control_label: str
    treatment_label: str
    isolated_variable: str
    primary_metric: str
    guardrail_metrics: tuple[str, ...]
    minimum_views_per_arm: int
    minimum_videos_per_arm: int
    created_at: datetime
    status: ExperimentStatus = ExperimentStatus.DRAFT

    def validate(self) -> None:
        required = {
            "experiment_id": self.experiment_id,
            "hypothesis": self.hypothesis,
            "control_label": self.control_label,
            "treatment_label": self.treatment_label,
            "isolated_variable": self.isolated_variable,
            "primary_metric": self.primary_metric,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise AnalyticsValidationError("experiment missing: " + ", ".join(missing))
        if self.control_label == self.treatment_label:
            raise AnalyticsValidationError("control and treatment labels must differ")
        if self.minimum_views_per_arm < 100:
            raise AnalyticsValidationError("minimum_views_per_arm must be at least 100")
        if self.minimum_videos_per_arm < 1:
            raise AnalyticsValidationError("minimum_videos_per_arm must be positive")
        if self.created_at.tzinfo is None:
            raise AnalyticsValidationError("created_at must be timezone-aware")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
