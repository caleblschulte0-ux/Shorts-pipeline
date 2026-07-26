from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Mapping, Sequence


@dataclass(frozen=True)
class StoryProof:
    slug: str
    score: float
    dimensions: Mapping[str, float]
    hard_failures: tuple[str, ...]
    effective_fps: float
    duplicate_ratio: float
    decorative_mascot_failures: int
    video_sha256: str
    verdict_sha256: str
    watched_video: bool

    def validate(self) -> None:
        if not self.slug:
            raise ValueError("story proof requires slug")
        if not 0 <= self.score <= 100:
            raise ValueError("score must be within [0, 100]")
        if self.effective_fps <= 0:
            raise ValueError("effective_fps must be positive")
        if not 0 <= self.duplicate_ratio <= 1:
            raise ValueError("duplicate_ratio must be within [0, 1]")
        if self.decorative_mascot_failures < 0:
            raise ValueError("decorative mascot failures cannot be negative")
        if not self.video_sha256 or not self.verdict_sha256:
            raise ValueError("proof requires artifact hashes")
        if not self.watched_video:
            raise ValueError("proof requires completed-video vision review")

    @property
    def lowest_dimension(self) -> float:
        return min((float(value) for value in self.dimensions.values()), default=0.0)


@dataclass(frozen=True)
class SuiteRunProof:
    run_id: str
    suite_version: str
    judge_version: str
    renderer_commit: str
    stories: tuple[StoryProof, ...]
    artifact_manifest_sha256: str

    def validate(self, expected_slugs: Sequence[str] | None = None) -> None:
        if not all((self.run_id, self.suite_version, self.judge_version, self.renderer_commit)):
            raise ValueError("run proof is missing version identity")
        if not self.artifact_manifest_sha256:
            raise ValueError("run proof requires manifest hash")
        if len(self.stories) == 0:
            raise ValueError("run proof requires stories")
        for story in self.stories:
            story.validate()
        slugs = tuple(story.slug for story in self.stories)
        if len(slugs) != len(set(slugs)):
            raise ValueError("run proof contains duplicate slugs")
        if expected_slugs is not None and tuple(expected_slugs) != slugs:
            raise ValueError(f"suite slug order mismatch: expected {tuple(expected_slugs)}, got {slugs}")

    @property
    def median_score(self) -> float:
        return float(median(story.score for story in self.stories))

    @property
    def lowest_score(self) -> float:
        return min(story.score for story in self.stories)

    @property
    def hard_failure_count(self) -> int:
        return sum(len(story.hard_failures) for story in self.stories)

    @property
    def decorative_failure_count(self) -> int:
        return sum(story.decorative_mascot_failures for story in self.stories)


@dataclass(frozen=True)
class ProofAssessment:
    passed: bool
    phase: int
    reasons: tuple[str, ...]
    run_ids: tuple[str, ...]
    median_floor_observed: float
    lowest_score_observed: float
