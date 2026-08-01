"""Deterministic run-envelope and replay-comparison prototype."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RunEnvelope:
    run_id: str
    story_slug: str
    manifest_sha256: str
    input_digest: str
    policy_digest: str
    dependency_versions: Mapping[str, str]
    random_seed: int
    planned_stages: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.run_id.strip() or not self.story_slug.strip():
            raise ValueError("run_id and story_slug must be nonempty")
        for name, digest in (
            ("manifest_sha256", self.manifest_sha256),
            ("input_digest", self.input_digest),
            ("policy_digest", self.policy_digest),
        ):
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
                raise ValueError(f"{name} must be a SHA-256 digest")
        if len(self.planned_stages) != len(set(self.planned_stages)):
            raise ValueError("planned_stages must be unique")


@dataclass(frozen=True)
class StageRecord:
    stage: str
    input_digest: str
    output_digest: str
    decision: str
    attempt: int = 1
    duration_ms: int = 0

    def __post_init__(self) -> None:
        if not self.stage.strip() or not self.decision.strip():
            raise ValueError("stage and decision must be nonempty")
        if self.attempt < 1 or self.duration_ms < 0:
            raise ValueError("attempt must be >= 1 and duration_ms >= 0")
        for name, digest in (("input_digest", self.input_digest), ("output_digest", self.output_digest)):
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
                raise ValueError(f"{name} must be a SHA-256 digest")


@dataclass(frozen=True)
class RunRecord:
    envelope: RunEnvelope
    stages: tuple[StageRecord, ...]

    def __post_init__(self) -> None:
        names = [stage.stage for stage in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("run stages must be unique")


@dataclass(frozen=True)
class ReplayComparison:
    deterministic: bool
    envelope_mismatches: tuple[str, ...]
    missing_stages: tuple[str, ...]
    extra_stages: tuple[str, ...]
    order_mismatch: bool
    input_mismatches: tuple[str, ...]
    output_mismatches: tuple[str, ...]
    decision_mismatches: tuple[str, ...]
    duration_regressions: tuple[str, ...]


def compare_replay(
    baseline: RunRecord,
    candidate: RunRecord,
    *,
    duration_regression_ratio: float = 1.5,
    duration_regression_floor_ms: int = 1000,
) -> ReplayComparison:
    if duration_regression_ratio < 1.0:
        raise ValueError("duration_regression_ratio must be >= 1")

    envelope_mismatches: list[str] = []
    base_env = baseline.envelope
    cand_env = candidate.envelope
    for name in ("story_slug", "manifest_sha256", "input_digest", "policy_digest", "random_seed"):
        if getattr(base_env, name) != getattr(cand_env, name):
            envelope_mismatches.append(name)
    if dict(base_env.dependency_versions) != dict(cand_env.dependency_versions):
        envelope_mismatches.append("dependency_versions")
    if base_env.planned_stages != cand_env.planned_stages:
        envelope_mismatches.append("planned_stages")

    base_map = {stage.stage: stage for stage in baseline.stages}
    cand_map = {stage.stage: stage for stage in candidate.stages}
    missing = tuple(sorted(set(base_map) - set(cand_map)))
    extra = tuple(sorted(set(cand_map) - set(base_map)))
    shared = sorted(set(base_map) & set(cand_map))
    input_mismatches = tuple(stage for stage in shared if base_map[stage].input_digest != cand_map[stage].input_digest)
    output_mismatches = tuple(stage for stage in shared if base_map[stage].output_digest != cand_map[stage].output_digest)
    decision_mismatches = tuple(stage for stage in shared if base_map[stage].decision != cand_map[stage].decision)

    baseline_order = tuple(stage.stage for stage in baseline.stages if stage.stage in cand_map)
    candidate_order = tuple(stage.stage for stage in candidate.stages if stage.stage in base_map)
    order_mismatch = baseline_order != candidate_order

    duration_regressions: list[str] = []
    for stage in shared:
        old = base_map[stage].duration_ms
        new = cand_map[stage].duration_ms
        threshold = max(duration_regression_floor_ms, int(old * duration_regression_ratio))
        if new > threshold:
            duration_regressions.append(stage)

    deterministic = not (
        envelope_mismatches
        or missing
        or extra
        or order_mismatch
        or input_mismatches
        or output_mismatches
        or decision_mismatches
    )
    return ReplayComparison(
        deterministic=deterministic,
        envelope_mismatches=tuple(sorted(envelope_mismatches)),
        missing_stages=missing,
        extra_stages=extra,
        order_mismatch=order_mismatch,
        input_mismatches=input_mismatches,
        output_mismatches=output_mismatches,
        decision_mismatches=decision_mismatches,
        duration_regressions=tuple(sorted(duration_regressions)),
    )


def build_run_record(
    envelope: RunEnvelope,
    stage_payloads: Iterable[tuple[str, object, object, str, int]],
) -> RunRecord:
    stages = tuple(
        StageRecord(
            stage=stage,
            input_digest=canonical_digest(input_payload),
            output_digest=canonical_digest(output_payload),
            decision=decision,
            duration_ms=duration_ms,
        )
        for stage, input_payload, output_payload, decision, duration_ms in stage_payloads
    )
    return RunRecord(envelope, stages)
