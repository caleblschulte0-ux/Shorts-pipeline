#!/usr/bin/env python3
"""Typed review contracts for the next quality-system iteration.

NOT WIRED INTO THE PIPELINE. This file is a design artifact for Claude review.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class WeakestScene:
    id: str
    index: int
    start: float
    end: float
    failure_class: str
    visible_evidence: str
    root_cause: str
    repair_goal: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.id:
            errors.append("weakest_scene.id is required")
        if self.index < 0:
            errors.append("weakest_scene.index must be non-negative")
        if self.start < 0 or self.end <= self.start:
            errors.append("weakest_scene time range is invalid")
        for name in ("failure_class", "visible_evidence", "root_cause", "repair_goal"):
            if not getattr(self, name).strip():
                errors.append(f"weakest_scene.{name} is required")
        return errors


@dataclass(frozen=True)
class TemporalEvidence:
    effective_fps: float
    duplicate_ratio: float
    longest_duplicate_run: int = 0

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.effective_fps < 0:
            errors.append("effective_fps cannot be negative")
        if not 0 <= self.duplicate_ratio <= 1:
            errors.append("duplicate_ratio must be between 0 and 1")
        if self.longest_duplicate_run < 0:
            errors.append("longest_duplicate_run cannot be negative")
        return errors


@dataclass(frozen=True)
class ShowrunnerVerdict:
    verdict: str
    score: float | None
    dimensions: Mapping[str, float] = field(default_factory=dict)
    hard_failures: Sequence[str] = field(default_factory=tuple)
    weakest_scene: WeakestScene | None = None
    temporal: TemporalEvidence | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.verdict not in {"ship", "block", "unknown"}:
            errors.append("verdict must be ship, block, or unknown")
        if self.verdict != "unknown" and self.score is None:
            errors.append("known verdict requires score")
        if self.verdict == "block" and self.weakest_scene is None:
            errors.append("block verdict requires structured weakest_scene")
        if self.weakest_scene:
            errors.extend(self.weakest_scene.validate())
        if self.temporal:
            errors.extend(self.temporal.validate())
        return errors


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    objective_pass: bool
    objective_failures: Sequence[str]
    vision_score: float | None
    claim_clarity: float | None
    narration_fit: float | None
    cause_consequence: float | None
    composition: float | None
    novelty: float | None
    payoff: float | None
    rationale: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.candidate_id:
            errors.append("candidate_id is required")
        if not self.objective_pass and not self.objective_failures:
            errors.append("failed objective gate requires reasons")
        if self.objective_pass and self.vision_score is None:
            errors.append("objective survivor requires visual evaluation")
        if self.objective_pass and not self.rationale.strip():
            errors.append("visual evaluation requires rationale")
        return errors


@dataclass(frozen=True)
class BenchmarkSummary:
    run_id: str
    stories: int
    median_score: float
    lowest_score: float
    hard_failures: int
    effective_fps_min: float
    decorative_mascot_failures: int
    judge_version: str
    consecutive_qualifying_runs: int

    def qualifies(self, phase: int) -> bool:
        thresholds = {
            1: {"median": 70, "floor": 65},
            2: {"median": 80, "floor": 75},
            3: {"median": 90, "floor": 85},
        }
        if phase not in thresholds:
            raise ValueError(f"unsupported phase: {phase}")
        target = thresholds[phase]
        return all(
            [
                self.stories >= 6,
                self.median_score >= target["median"],
                self.lowest_score >= target["floor"],
                self.hard_failures == 0,
                self.effective_fps_min >= 24,
                self.decorative_mascot_failures == 0,
                self.consecutive_qualifying_runs >= 2,
                bool(self.judge_version),
            ]
        )


def parse_verdict(payload: Mapping[str, Any]) -> ShowrunnerVerdict:
    weakest_payload = payload.get("weakest_scene")
    weakest = WeakestScene(**weakest_payload) if isinstance(weakest_payload, Mapping) else None
    temporal_payload = payload.get("temporal")
    temporal = TemporalEvidence(**temporal_payload) if isinstance(temporal_payload, Mapping) else None
    verdict = ShowrunnerVerdict(
        verdict=str(payload.get("verdict", "unknown")),
        score=payload.get("score"),
        dimensions=payload.get("dimensions") or {},
        hard_failures=payload.get("hard_failures") or payload.get("auto_fails") or (),
        weakest_scene=weakest,
        temporal=temporal,
    )
    errors = verdict.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return verdict


def example() -> dict[str, Any]:
    verdict = ShowrunnerVerdict(
        verdict="block",
        score=62,
        dimensions={"clarity": 8, "mascot": 4, "payoff": 5},
        hard_failures=("decorative_mascot",),
        weakest_scene=WeakestScene(
            id="segment_1",
            index=1,
            start=7.2,
            end=12.8,
            failure_class="decorative_mascot",
            visible_evidence="Data follows the bar edge without a readable objective.",
            root_cause="Position is coupled, but performance is not.",
            repair_goal="Create goal, effort, reversal, and consequence.",
        ),
        temporal=TemporalEvidence(effective_fps=26.4, duplicate_ratio=0.08),
    )
    return asdict(verdict)


if __name__ == "__main__":
    print(json.dumps(example(), indent=2))
