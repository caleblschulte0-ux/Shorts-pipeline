"""Review-only benchmark laboratory prototype.

NOT WIRED INTO THE PIPELINE.

This module plans reproducible full-suite runs and summarizes supplied results.
It intentionally does not call renderers, workflows, subprocesses, or network
services. Claude can adapt the contracts later into the real benchmark path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from statistics import median, pstdev
from typing import Mapping, Sequence


@dataclass(frozen=True)
class StoryFixture:
    slug: str
    archetype: str
    narration_hash: str
    data_hash: str
    expected_takeaway: str
    forbidden_distortions: tuple[str, ...] = ()
    known_failure_classes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SuiteSpec:
    version: str
    stories: tuple[StoryFixture, ...]
    minimum_story_count: int = 6

    def validate(self) -> tuple[str, ...]:
        errors: list[str] = []
        if len(self.stories) < self.minimum_story_count:
            errors.append(
                f"suite contains {len(self.stories)} stories; "
                f"requires {self.minimum_story_count}"
            )
        slugs = [story.slug for story in self.stories]
        if len(slugs) != len(set(slugs)):
            errors.append("suite contains duplicate slugs")
        archetypes = {story.archetype for story in self.stories}
        required = {
            "trend",
            "ranking",
            "part_to_whole",
            "comparison",
            "scale",
            "money",
        }
        missing = required.difference(archetypes)
        if missing:
            errors.append("missing archetypes: " + ", ".join(sorted(missing)))
        for story in self.stories:
            if not story.narration_hash or not story.data_hash:
                errors.append(f"{story.slug}: missing fixed-input hashes")
            if not story.expected_takeaway:
                errors.append(f"{story.slug}: missing expected takeaway")
        return tuple(errors)

    @property
    def fingerprint(self) -> str:
        payload = {
            "version": self.version,
            "stories": [story.__dict__ for story in self.stories],
        }
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RunPlan:
    run_id: str
    suite_version: str
    suite_fingerprint: str
    judge_version: str
    renderer_commit: str
    story_slugs: tuple[str, ...]
    require_complete_video: bool = True
    permit_manual_intervention: bool = False
    retain_artifacts: bool = True


def plan_run(
    suite: SuiteSpec,
    *,
    run_id: str,
    judge_version: str,
    renderer_commit: str,
) -> RunPlan:
    errors = suite.validate()
    if errors:
        raise ValueError("invalid suite: " + "; ".join(errors))
    if not judge_version:
        raise ValueError("judge version is required")
    if not renderer_commit:
        raise ValueError("renderer commit is required")
    return RunPlan(
        run_id=run_id,
        suite_version=suite.version,
        suite_fingerprint=suite.fingerprint,
        judge_version=judge_version,
        renderer_commit=renderer_commit,
        story_slugs=tuple(story.slug for story in suite.stories),
    )


@dataclass(frozen=True)
class StoryObservation:
    slug: str
    completed: bool
    score: float
    dimensions: Mapping[str, float]
    hard_failures: tuple[str, ...]
    effective_fps: float
    duplicate_ratio: float
    output_manifest_hash: str
    failure_classes: tuple[str, ...] = ()

    @property
    def lowest_dimension(self) -> float:
        return min(self.dimensions.values(), default=0.0)


@dataclass(frozen=True)
class RunObservation:
    plan: RunPlan
    stories: tuple[StoryObservation, ...]
    manual_intervention_occurred: bool = False


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    complete: bool
    median_score: float
    lowest_score: float
    score_stddev: float
    lowest_dimension: float
    hard_failure_count: int
    lowest_effective_fps: float
    highest_duplicate_ratio: float
    failure_class_counts: Mapping[str, int]
    reasons: tuple[str, ...] = ()


def summarize(observation: RunObservation) -> RunSummary:
    reasons: list[str] = []
    expected = set(observation.plan.story_slugs)
    actual = {story.slug for story in observation.stories}
    missing = sorted(expected.difference(actual))
    extra = sorted(actual.difference(expected))
    if missing:
        reasons.append("missing stories: " + ", ".join(missing))
    if extra:
        reasons.append("unexpected stories: " + ", ".join(extra))
    if observation.manual_intervention_occurred:
        reasons.append("manual intervention occurred during benchmark")

    for story in observation.stories:
        if not story.completed:
            reasons.append(f"{story.slug}: incomplete full video")
        if not story.output_manifest_hash:
            reasons.append(f"{story.slug}: missing output manifest hash")

    scores = [story.score for story in observation.stories]
    failure_counts: dict[str, int] = {}
    for story in observation.stories:
        for label in story.failure_classes:
            failure_counts[label] = failure_counts.get(label, 0) + 1

    return RunSummary(
        run_id=observation.plan.run_id,
        complete=not reasons,
        median_score=float(median(scores)) if scores else 0.0,
        lowest_score=min(scores, default=0.0),
        score_stddev=float(pstdev(scores)) if len(scores) > 1 else 0.0,
        lowest_dimension=min(
            (story.lowest_dimension for story in observation.stories),
            default=0.0,
        ),
        hard_failure_count=sum(
            len(story.hard_failures) for story in observation.stories
        ),
        lowest_effective_fps=min(
            (story.effective_fps for story in observation.stories),
            default=0.0,
        ),
        highest_duplicate_ratio=max(
            (story.duplicate_ratio for story in observation.stories),
            default=1.0,
        ),
        failure_class_counts=failure_counts,
        reasons=tuple(reasons),
    )


@dataclass(frozen=True)
class ConsistencyReport:
    passed: bool
    reasons: tuple[str, ...]
    run_ids: tuple[str, ...]


def assess_consecutive_runs(
    observations: Sequence[RunObservation],
    *,
    minimum_median: float,
    minimum_lowest: float,
    minimum_lowest_dimension: float,
    maximum_hard_failures: int = 0,
    minimum_effective_fps: float = 24.0,
    maximum_duplicate_ratio: float = 0.15,
) -> ConsistencyReport:
    if len(observations) < 2:
        return ConsistencyReport(
            passed=False,
            reasons=("two consecutive runs are required",),
            run_ids=tuple(item.plan.run_id for item in observations),
        )

    selected = tuple(observations[-2:])
    reasons: list[str] = []
    if len({item.plan.suite_fingerprint for item in selected}) != 1:
        reasons.append("suite fingerprint changed between runs")
    if len({item.plan.judge_version for item in selected}) != 1:
        reasons.append("judge version changed between runs")
    if len({item.plan.renderer_commit for item in selected}) != 1:
        reasons.append("renderer commit changed between runs")

    for observation in selected:
        summary = summarize(observation)
        reasons.extend(summary.reasons)
        if summary.median_score < minimum_median:
            reasons.append(
                f"{summary.run_id}: median {summary.median_score:.1f} < "
                f"{minimum_median:.1f}"
            )
        if summary.lowest_score < minimum_lowest:
            reasons.append(
                f"{summary.run_id}: lowest {summary.lowest_score:.1f} < "
                f"{minimum_lowest:.1f}"
            )
        if summary.lowest_dimension < minimum_lowest_dimension:
            reasons.append(
                f"{summary.run_id}: lowest dimension "
                f"{summary.lowest_dimension:.1f} < {minimum_lowest_dimension:.1f}"
            )
        if summary.hard_failure_count > maximum_hard_failures:
            reasons.append(
                f"{summary.run_id}: hard failures = {summary.hard_failure_count}"
            )
        if summary.lowest_effective_fps < minimum_effective_fps:
            reasons.append(
                f"{summary.run_id}: effective FPS floor "
                f"{summary.lowest_effective_fps:.1f} < {minimum_effective_fps:.1f}"
            )
        if summary.highest_duplicate_ratio > maximum_duplicate_ratio:
            reasons.append(
                f"{summary.run_id}: duplicate ratio "
                f"{summary.highest_duplicate_ratio:.1%} > "
                f"{maximum_duplicate_ratio:.1%}"
            )

    return ConsistencyReport(
        passed=not reasons,
        reasons=tuple(reasons),
        run_ids=tuple(item.plan.run_id for item in selected),
    )


def default_suite() -> SuiteSpec:
    """Illustrative six-archetype fixture using placeholder stable hashes."""

    fixtures = (
        StoryFixture(
            slug="carbon-climb",
            archetype="trend",
            narration_hash="fixed:carbon-climb:narration",
            data_hash="fixed:carbon-climb:data",
            expected_takeaway="The measured value rises substantially over time.",
            forbidden_distortions=("hide time axis", "imply categorical ranking"),
        ),
        StoryFixture(
            slug="population-giants",
            archetype="ranking",
            narration_hash="fixed:population-giants:narration",
            data_hash="fixed:population-giants:data",
            expected_takeaway="The largest entries tower over the rest.",
        ),
        StoryFixture(
            slug="world-power-mix",
            archetype="part_to_whole",
            narration_hash="fixed:world-power-mix:narration",
            data_hash="fixed:world-power-mix:data",
            expected_takeaway="One source remains dominant within the whole.",
        ),
        StoryFixture(
            slug="two-americas-cost",
            archetype="comparison",
            narration_hash="fixed:two-americas-cost:narration",
            data_hash="fixed:two-americas-cost:data",
            expected_takeaway="The same expense differs sharply between groups.",
        ),
        StoryFixture(
            slug="ocean-unexplored",
            archetype="scale",
            narration_hash="fixed:ocean-unexplored:narration",
            data_hash="fixed:ocean-unexplored:data",
            expected_takeaway="The unexplored portion is enormous relative to the known portion.",
        ),
        StoryFixture(
            slug="grocery-squeeze",
            archetype="money",
            narration_hash="fixed:grocery-squeeze:narration",
            data_hash="fixed:grocery-squeeze:data",
            expected_takeaway="Household grocery costs consume more of the budget.",
        ),
    )
    return SuiteSpec(version="explainer-review-v2", stories=fixtures)
