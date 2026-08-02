from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import ProofAssessment, SuiteRunProof


@dataclass(frozen=True)
class PhaseThreshold:
    phase: int
    median_score: float
    lowest_score: float
    lowest_dimension: float
    minimum_effective_fps: float = 24.0
    maximum_duplicate_ratio: float = 0.20
    consecutive_runs: int = 2


THRESHOLDS = {
    1: PhaseThreshold(1, 70, 65, 6.0),
    2: PhaseThreshold(2, 80, 75, 7.0),
    3: PhaseThreshold(3, 90, 85, 8.0),
}


def assess_runs(
    runs: Sequence[SuiteRunProof],
    phase: int,
    expected_slugs: Sequence[str],
) -> ProofAssessment:
    if phase not in THRESHOLDS:
        raise ValueError(f"unsupported phase: {phase}")
    threshold = THRESHOLDS[phase]
    reasons: list[str] = []
    selected = tuple(runs[-threshold.consecutive_runs :])
    if len(selected) < threshold.consecutive_runs:
        reasons.append(f"requires {threshold.consecutive_runs} consecutive full-suite runs")
    if selected:
        versions = {(r.suite_version, r.judge_version, r.renderer_commit) for r in selected}
        if len(versions) != 1:
            reasons.append("suite, judge, and renderer versions must remain locked")
    for run in selected:
        try:
            run.validate(expected_slugs)
        except ValueError as exc:
            reasons.append(f"{run.run_id}: {exc}")
            continue
        if run.median_score < threshold.median_score:
            reasons.append(f"{run.run_id}: median {run.median_score:.1f} < {threshold.median_score:.1f}")
        if run.lowest_score < threshold.lowest_score:
            reasons.append(f"{run.run_id}: lowest score {run.lowest_score:.1f} < {threshold.lowest_score:.1f}")
        if run.hard_failure_count:
            reasons.append(f"{run.run_id}: {run.hard_failure_count} hard failures")
        if run.decorative_failure_count:
            reasons.append(f"{run.run_id}: decorative mascot failures present")
        for story in run.stories:
            if story.lowest_dimension < threshold.lowest_dimension:
                reasons.append(
                    f"{run.run_id}/{story.slug}: lowest dimension {story.lowest_dimension:.1f} < {threshold.lowest_dimension:.1f}"
                )
            if story.effective_fps < threshold.minimum_effective_fps:
                reasons.append(
                    f"{run.run_id}/{story.slug}: effective FPS {story.effective_fps:.1f} < {threshold.minimum_effective_fps:.1f}"
                )
            if story.duplicate_ratio > threshold.maximum_duplicate_ratio:
                reasons.append(
                    f"{run.run_id}/{story.slug}: duplicate ratio {story.duplicate_ratio:.3f} > {threshold.maximum_duplicate_ratio:.3f}"
                )
    medians = [run.median_score for run in selected] or [0.0]
    lows = [run.lowest_score for run in selected] or [0.0]
    return ProofAssessment(
        passed=not reasons,
        phase=phase,
        reasons=tuple(reasons),
        run_ids=tuple(run.run_id for run in selected),
        median_floor_observed=min(medians),
        lowest_score_observed=min(lows),
    )
