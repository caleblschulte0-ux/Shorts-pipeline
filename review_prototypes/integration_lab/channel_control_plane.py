from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence

from review_prototypes.channel_operations.models import PortfolioResult, ReleaseCandidate, ScheduleResult
from review_prototypes.channel_operations.portfolio import PortfolioPlanner
from review_prototypes.channel_operations.scheduler import ReleaseScheduler
from review_prototypes.retention_system.compiler import RetentionCompiler
from review_prototypes.retention_system.models import Beat, RetentionPackage


@dataclass(frozen=True)
class StoryInput:
    slug: str
    claim: str
    consequential_number: str
    expectation: str
    consequence: str
    mascot_goal: str
    beats: tuple[Beat, ...]
    topic_family: str
    story_shape: str
    performance_families: tuple[str, ...]
    source_verified: bool
    showrunner_decision: str
    quality_score: float
    lowest_dimension: float
    artifact_manifest_hash: str
    experiment_id: str | None = None


@dataclass(frozen=True)
class ControlPlaneResult:
    retention_packages: tuple[RetentionPackage, ...]
    portfolio: PortfolioResult
    schedule: ScheduleResult


class ChannelControlPlane:
    """Concrete review-only composition of content-quality subsystems."""

    def __init__(self) -> None:
        self.retention = RetentionCompiler()
        self.portfolio = PortfolioPlanner()
        self.scheduler = ReleaseScheduler()

    def prepare_release_day(
        self,
        stories: Sequence[StoryInput],
        *,
        batch_size: int,
        publish_date: date,
    ) -> ControlPlaneResult:
        packages: list[RetentionPackage] = []
        release_candidates: list[ReleaseCandidate] = []
        for story in stories:
            package = self.retention.compile(
                story_slug=story.slug,
                claim=story.claim,
                consequential_number=story.consequential_number,
                expectation=story.expectation,
                consequence=story.consequence,
                mascot_goal=story.mascot_goal,
                beats=story.beats,
            )
            packages.append(package)
            release_candidates.append(
                ReleaseCandidate(
                    slug=story.slug,
                    topic_family=story.topic_family,
                    story_shape=story.story_shape,
                    hook_pattern=package.hook.pattern_key,
                    performance_families=story.performance_families,
                    quality_score=story.quality_score,
                    lowest_dimension=story.lowest_dimension,
                    source_verified=story.source_verified,
                    retention_passed=package.report.passed,
                    showrunner_decision=story.showrunner_decision,
                    hard_failures=package.report.hard_failures,
                    experiment_id=story.experiment_id,
                    freshness_score=0.9,
                    reaction_prediction=0.6,
                    artifact_manifest_hash=story.artifact_manifest_hash,
                )
            )
        portfolio = self.portfolio.select(release_candidates, batch_size=batch_size)
        schedule = self.scheduler.schedule(
            portfolio.selected,
            publish_date=publish_date,
        )
        return ControlPlaneResult(tuple(packages), portfolio, schedule)
