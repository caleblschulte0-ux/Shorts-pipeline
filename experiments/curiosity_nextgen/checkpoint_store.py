"""Idempotent checkpoint, retry, and resume-planning prototype."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class StageState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class ResumeDecision(str, Enum):
    COMPLETE = "complete"
    RESUME = "resume"
    RETRY = "retry"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Checkpoint:
    stage: str
    manifest_sha256: str
    input_digest: str
    state: StageState
    attempt: int
    idempotency_key: str
    output_digest: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.stage.strip() or not self.idempotency_key.strip():
            raise ValueError("stage and idempotency_key must be nonempty")
        if self.attempt < 1:
            raise ValueError("attempt must be >= 1")
        for name, digest in (("manifest_sha256", self.manifest_sha256), ("input_digest", self.input_digest)):
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
                raise ValueError(f"{name} must be a SHA-256 digest")
        if self.output_digest is not None and (
            len(self.output_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in self.output_digest.lower())
        ):
            raise ValueError("output_digest must be a SHA-256 digest")
        if self.state is StageState.PASSED and self.output_digest is None:
            raise ValueError("passed checkpoints require output_digest")
        if self.state in {StageState.FAILED, StageState.QUARANTINED} and not self.reason:
            raise ValueError("failed or quarantined checkpoints require a reason")


@dataclass(frozen=True)
class ResumePlan:
    decision: ResumeDecision
    next_stage: str | None
    completed_stages: tuple[str, ...]
    blockers: tuple[str, ...]
    stale_stages: tuple[str, ...]
    attempt: int | None = None


class CheckpointLedger:
    def __init__(self, checkpoints: Iterable[Checkpoint] = (), *, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts
        self._history: list[Checkpoint] = []
        for checkpoint in checkpoints:
            self.append(checkpoint)

    @property
    def history(self) -> tuple[Checkpoint, ...]:
        return tuple(self._history)

    def latest_by_stage(self) -> dict[str, Checkpoint]:
        latest: dict[str, Checkpoint] = {}
        for checkpoint in self._history:
            latest[checkpoint.stage] = checkpoint
        return latest

    def append(self, checkpoint: Checkpoint) -> None:
        if any(
            item.idempotency_key == checkpoint.idempotency_key
            and item.state is StageState.PASSED
            for item in self._history
        ):
            raise ValueError("idempotency key has already produced a passed checkpoint")

        previous = next(
            (item for item in reversed(self._history) if item.stage == checkpoint.stage),
            None,
        )
        if previous is not None:
            if previous.manifest_sha256 != checkpoint.manifest_sha256:
                raise ValueError("stage checkpoint manifest changed")
            if checkpoint.attempt < previous.attempt:
                raise ValueError("checkpoint attempt cannot decrease")
            if previous.state is StageState.PASSED:
                raise ValueError("passed stage may not be appended again")
            if previous.state is StageState.QUARANTINED:
                raise ValueError("quarantined stage may not resume")
            if previous.state is StageState.FAILED and checkpoint.attempt != previous.attempt + 1:
                raise ValueError("failed stage retry must increment attempt by one")
            if previous.state in {StageState.PENDING, StageState.RUNNING} and checkpoint.attempt != previous.attempt:
                raise ValueError("in-flight stage transition must keep attempt number")

        if checkpoint.attempt > self.max_attempts:
            raise ValueError("checkpoint exceeds maximum attempts")
        self._history.append(checkpoint)

    def plan_resume(
        self,
        required_stages: tuple[str, ...],
        *,
        manifest_sha256: str,
        expected_inputs: dict[str, str] | None = None,
    ) -> ResumePlan:
        if len(required_stages) != len(set(required_stages)):
            raise ValueError("required_stages must be unique")
        latest = self.latest_by_stage()
        completed: list[str] = []
        stale: list[str] = []
        expected_inputs = expected_inputs or {}

        for stage in required_stages:
            checkpoint = latest.get(stage)
            if checkpoint is None:
                return ResumePlan(ResumeDecision.RESUME, stage, tuple(completed), (), tuple(stale), 1)
            if checkpoint.manifest_sha256 != manifest_sha256:
                stale.append(stage)
                return ResumePlan(
                    ResumeDecision.BLOCKED,
                    None,
                    tuple(completed),
                    (f"manifest_mismatch:{stage}",),
                    tuple(stale),
                )
            expected = expected_inputs.get(stage)
            if expected is not None and checkpoint.input_digest != expected:
                stale.append(stage)
                return ResumePlan(
                    ResumeDecision.BLOCKED,
                    None,
                    tuple(completed),
                    (f"input_digest_changed:{stage}",),
                    tuple(stale),
                )
            if checkpoint.state is StageState.PASSED:
                completed.append(stage)
                continue
            if checkpoint.state is StageState.QUARANTINED:
                return ResumePlan(
                    ResumeDecision.BLOCKED,
                    None,
                    tuple(completed),
                    (f"stage_quarantined:{stage}",),
                    tuple(stale),
                )
            if checkpoint.state is StageState.FAILED:
                if checkpoint.attempt >= self.max_attempts:
                    return ResumePlan(
                        ResumeDecision.BLOCKED,
                        None,
                        tuple(completed),
                        (f"retry_budget_exhausted:{stage}",),
                        tuple(stale),
                    )
                return ResumePlan(
                    ResumeDecision.RETRY,
                    stage,
                    tuple(completed),
                    (),
                    tuple(stale),
                    checkpoint.attempt + 1,
                )
            return ResumePlan(
                ResumeDecision.RESUME,
                stage,
                tuple(completed),
                (),
                tuple(stale),
                checkpoint.attempt,
            )

        return ResumePlan(ResumeDecision.COMPLETE, None, tuple(completed), (), tuple(stale), None)
