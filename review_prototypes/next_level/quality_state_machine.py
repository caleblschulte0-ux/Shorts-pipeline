"""Review-only evidence-based quality phase state machine.

NOT WIRED INTO THE PIPELINE.

A quality phase should be calculated from complete benchmark evidence, not raised
by an environment variable. This prototype evaluates two consecutive full-suite
runs and reports the highest phase they jointly qualify for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class StoryResult:
    slug: str
    score: float
    lowest_dimension: float
    hard_failures: tuple[str, ...] = ()
    effective_fps: float = 30.0
    duplicate_ratio: float = 0.0
    decorative_mascot_failures: int = 0
    hook_score: float = 0.0
    payoff_score: float = 0.0
    performance_family_counts: Mapping[str, int] = field(default_factory=dict)
    artifact_manifest_hash: str = ""


@dataclass(frozen=True)
class BenchmarkRun:
    run_id: str
    suite_version: str
    judge_version: str
    renderer_commit: str
    stories: tuple[StoryResult, ...]
    manually_modified_between_stories: bool = False
    complete_video_count: int = 0

    @property
    def scores(self) -> tuple[float, ...]:
        return tuple(story.score for story in self.stories)

    @property
    def median_score(self) -> float:
        return float(median(self.scores)) if self.stories else 0.0

    @property
    def lowest_score(self) -> float:
        return min(self.scores, default=0.0)

    @property
    def hard_failure_count(self) -> int:
        return sum(len(story.hard_failures) for story in self.stories)

    @property
    def lowest_effective_fps(self) -> float:
        return min((story.effective_fps for story in self.stories), default=0.0)

    @property
    def maximum_duplicate_ratio(self) -> float:
        return max((story.duplicate_ratio for story in self.stories), default=1.0)

    @property
    def decorative_mascot_failure_count(self) -> int:
        return sum(story.decorative_mascot_failures for story in self.stories)

    @property
    def minimum_hook_score(self) -> float:
        return min((story.hook_score for story in self.stories), default=0.0)

    @property
    def minimum_payoff_score(self) -> float:
        return min((story.payoff_score for story in self.stories), default=0.0)

    @property
    def artifact_manifests_complete(self) -> bool:
        return bool(self.stories) and all(
            story.artifact_manifest_hash for story in self.stories
        )

    def performance_family_share(self, family: str) -> float:
        total = 0
        chosen = 0
        for story in self.stories:
            for name, count in story.performance_family_counts.items():
                total += count
                if name == family:
                    chosen += count
        return chosen / total if total else 0.0

    @property
    def maximum_performance_family_share(self) -> float:
        families = {
            name
            for story in self.stories
            for name in story.performance_family_counts
        }
        return max((self.performance_family_share(name) for name in families), default=0.0)


@dataclass(frozen=True)
class PhaseRequirement:
    phase: int
    minimum_stories: int
    minimum_consecutive_runs: int
    median_score: float
    lowest_score: float
    lowest_dimension: float
    maximum_hard_failures: int
    minimum_effective_fps: float
    maximum_duplicate_ratio: float
    maximum_decorative_mascot_failures: int
    minimum_hook_score: float = 0.0
    minimum_payoff_score: float = 0.0
    maximum_performance_family_share: float = 1.0
    require_artifact_manifests: bool = True


REQUIREMENTS: Mapping[int, PhaseRequirement] = {
    0: PhaseRequirement(
        phase=0,
        minimum_stories=1,
        minimum_consecutive_runs=1,
        median_score=0.0,
        lowest_score=0.0,
        lowest_dimension=0.0,
        maximum_hard_failures=0,
        minimum_effective_fps=24.0,
        maximum_duplicate_ratio=0.15,
        maximum_decorative_mascot_failures=999,
    ),
    1: PhaseRequirement(
        phase=1,
        minimum_stories=6,
        minimum_consecutive_runs=2,
        median_score=70.0,
        lowest_score=65.0,
        lowest_dimension=6.0,
        maximum_hard_failures=0,
        minimum_effective_fps=24.0,
        maximum_duplicate_ratio=0.15,
        maximum_decorative_mascot_failures=0,
    ),
    2: PhaseRequirement(
        phase=2,
        minimum_stories=6,
        minimum_consecutive_runs=2,
        median_score=80.0,
        lowest_score=75.0,
        lowest_dimension=7.0,
        maximum_hard_failures=0,
        minimum_effective_fps=24.0,
        maximum_duplicate_ratio=0.12,
        maximum_decorative_mascot_failures=0,
        minimum_hook_score=7.0,
        minimum_payoff_score=7.0,
        maximum_performance_family_share=0.25,
    ),
    3: PhaseRequirement(
        phase=3,
        minimum_stories=6,
        minimum_consecutive_runs=2,
        median_score=90.0,
        lowest_score=85.0,
        lowest_dimension=8.0,
        maximum_hard_failures=0,
        minimum_effective_fps=24.0,
        maximum_duplicate_ratio=0.10,
        maximum_decorative_mascot_failures=0,
        minimum_hook_score=8.0,
        minimum_payoff_score=8.0,
        maximum_performance_family_share=0.25,
    ),
}


@dataclass(frozen=True)
class PhaseAssessment:
    phase: int
    passed: bool
    reasons: tuple[str, ...]
    run_ids: tuple[str, ...]


@dataclass(frozen=True)
class StateAssessment:
    highest_phase: int | None
    assessments: tuple[PhaseAssessment, ...]


def _validate_run(run: BenchmarkRun, requirement: PhaseRequirement) -> list[str]:
    failures: list[str] = []
    if len(run.stories) < requirement.minimum_stories:
        failures.append(
            f"{run.run_id}: only {len(run.stories)} stories; "
            f"requires {requirement.minimum_stories}"
        )
    if run.complete_video_count < requirement.minimum_stories:
        failures.append(
            f"{run.run_id}: complete-video count {run.complete_video_count} is too low"
        )
    if run.manually_modified_between_stories:
        failures.append(f"{run.run_id}: manual modification occurred during suite")
    if run.median_score < requirement.median_score:
        failures.append(
            f"{run.run_id}: median {run.median_score:.1f} < {requirement.median_score:.1f}"
        )
    if run.lowest_score < requirement.lowest_score:
        failures.append(
            f"{run.run_id}: lowest score {run.lowest_score:.1f} < "
            f"{requirement.lowest_score:.1f}"
        )
    low_dimension = min(
        (story.lowest_dimension for story in run.stories),
        default=0.0,
    )
    if low_dimension < requirement.lowest_dimension:
        failures.append(
            f"{run.run_id}: lowest dimension {low_dimension:.1f} < "
            f"{requirement.lowest_dimension:.1f}"
        )
    if run.hard_failure_count > requirement.maximum_hard_failures:
        failures.append(
            f"{run.run_id}: {run.hard_failure_count} hard failures"
        )
    if run.lowest_effective_fps < requirement.minimum_effective_fps:
        failures.append(
            f"{run.run_id}: effective FPS floor {run.lowest_effective_fps:.1f} < "
            f"{requirement.minimum_effective_fps:.1f}"
        )
    if run.maximum_duplicate_ratio > requirement.maximum_duplicate_ratio:
        failures.append(
            f"{run.run_id}: duplicate ratio {run.maximum_duplicate_ratio:.1%} > "
            f"{requirement.maximum_duplicate_ratio:.1%}"
        )
    if (
        run.decorative_mascot_failure_count
        > requirement.maximum_decorative_mascot_failures
    ):
        failures.append(
            f"{run.run_id}: decorative mascot failures = "
            f"{run.decorative_mascot_failure_count}"
        )
    if run.minimum_hook_score < requirement.minimum_hook_score:
        failures.append(
            f"{run.run_id}: minimum hook score {run.minimum_hook_score:.1f} < "
            f"{requirement.minimum_hook_score:.1f}"
        )
    if run.minimum_payoff_score < requirement.minimum_payoff_score:
        failures.append(
            f"{run.run_id}: minimum payoff score {run.minimum_payoff_score:.1f} < "
            f"{requirement.minimum_payoff_score:.1f}"
        )
    if (
        run.maximum_performance_family_share
        > requirement.maximum_performance_family_share
    ):
        failures.append(
            f"{run.run_id}: dominant performance family share "
            f"{run.maximum_performance_family_share:.1%} > "
            f"{requirement.maximum_performance_family_share:.1%}"
        )
    if requirement.require_artifact_manifests and not run.artifact_manifests_complete:
        failures.append(f"{run.run_id}: missing artifact manifest hashes")
    return failures


def assess_phase(runs: Sequence[BenchmarkRun], phase: int) -> PhaseAssessment:
    requirement = REQUIREMENTS[phase]
    selected = tuple(runs[-requirement.minimum_consecutive_runs :])
    reasons: list[str] = []

    if len(selected) < requirement.minimum_consecutive_runs:
        reasons.append(
            f"requires {requirement.minimum_consecutive_runs} consecutive runs"
        )
        return PhaseAssessment(
            phase=phase,
            passed=False,
            reasons=tuple(reasons),
            run_ids=tuple(run.run_id for run in selected),
        )

    suite_versions = {run.suite_version for run in selected}
    judge_versions = {run.judge_version for run in selected}
    commits = {run.renderer_commit for run in selected}
    if len(suite_versions) != 1:
        reasons.append("suite version changed between consecutive runs")
    if len(judge_versions) != 1:
        reasons.append("judge version changed between consecutive runs")
    if len(commits) != 1:
        reasons.append("renderer commit changed between consecutive runs")

    for run in selected:
        reasons.extend(_validate_run(run, requirement))

    return PhaseAssessment(
        phase=phase,
        passed=not reasons,
        reasons=tuple(reasons),
        run_ids=tuple(run.run_id for run in selected),
    )


def assess_state(runs: Sequence[BenchmarkRun]) -> StateAssessment:
    assessments = tuple(
        assess_phase(runs, phase) for phase in sorted(REQUIREMENTS)
    )
    passed = [assessment.phase for assessment in assessments if assessment.passed]
    return StateAssessment(
        highest_phase=max(passed) if passed else None,
        assessments=assessments,
    )


@dataclass(frozen=True)
class RegressionReport:
    passed: bool
    reasons: tuple[str, ...]


def compare_regression(
    baseline: BenchmarkRun,
    challenger: BenchmarkRun,
    *,
    median_tolerance: float = 1.0,
    lowest_story_tolerance: float = 2.0,
    per_story_tolerance: float = 3.0,
) -> RegressionReport:
    """Detect hidden local regressions even when the median looks acceptable."""

    reasons: list[str] = []
    if challenger.median_score < baseline.median_score - median_tolerance:
        reasons.append(
            f"median regressed {baseline.median_score:.1f} -> "
            f"{challenger.median_score:.1f}"
        )
    if challenger.lowest_score < baseline.lowest_score - lowest_story_tolerance:
        reasons.append(
            f"lowest story regressed {baseline.lowest_score:.1f} -> "
            f"{challenger.lowest_score:.1f}"
        )

    baseline_by_slug = {story.slug: story for story in baseline.stories}
    challenger_by_slug = {story.slug: story for story in challenger.stories}
    for slug in sorted(set(baseline_by_slug).intersection(challenger_by_slug)):
        before = baseline_by_slug[slug]
        after = challenger_by_slug[slug]
        if after.score < before.score - per_story_tolerance:
            reasons.append(
                f"{slug} regressed {before.score:.1f} -> {after.score:.1f}"
            )
        new_failures = set(after.hard_failures).difference(before.hard_failures)
        if new_failures:
            reasons.append(
                f"{slug} introduced hard failures: {', '.join(sorted(new_failures))}"
            )

    return RegressionReport(passed=not reasons, reasons=tuple(reasons))


def summarize_failures(assessments: Iterable[PhaseAssessment]) -> Mapping[int, tuple[str, ...]]:
    return {
        assessment.phase: assessment.reasons
        for assessment in assessments
        if not assessment.passed
    }
