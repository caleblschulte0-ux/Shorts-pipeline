from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


class SandboxViolation(RuntimeError):
    """Raised when an adapter attempts to escape its isolated workspace."""


@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: Path
    timeout_seconds: float = 300.0
    env: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.argv or not self.argv[0]:
            raise ValueError("command requires an executable")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout must be positive")


@dataclass(frozen=True)
class ExecutionResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class RenderRequest:
    slug: str
    attempt_id: str
    output_dir: Path
    mode: str
    candidate_payload: Mapping[str, object] | None = None

    def validate(self) -> None:
        if not self.slug or not self.attempt_id:
            raise ValueError("render request requires slug and attempt_id")
        if self.mode not in {"baseline", "candidate"}:
            raise ValueError(f"unsupported render mode: {self.mode}")
        if self.mode == "candidate" and not self.candidate_payload:
            raise ValueError("candidate render requires candidate_payload")


@dataclass(frozen=True)
class JudgeRequest:
    slug: str
    attempt_id: str
    video_path: Path
    output_dir: Path

    def validate(self) -> None:
        if not self.slug or not self.attempt_id:
            raise ValueError("judge request requires slug and attempt_id")
        if not self.video_path.is_file():
            raise FileNotFoundError(self.video_path)


@dataclass(frozen=True)
class AdapterVerdict:
    decision: str
    score: float
    dimensions: Mapping[str, float]
    hard_failures: tuple[str, ...]
    watched_video: bool
    judge_version: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "AdapterVerdict":
        decision = str(payload.get("decision") or payload.get("verdict") or "").lower()
        if decision == "block":
            decision = "hold"
        if decision not in {"ship", "hold", "reject"}:
            raise ValueError(f"unsupported decision: {decision!r}")
        score = payload.get("score")
        if not isinstance(score, (int, float)):
            raise ValueError("verdict requires numeric score")
        dimensions_raw = payload.get("dimensions") or {}
        if not isinstance(dimensions_raw, Mapping):
            raise ValueError("dimensions must be a mapping")
        dimensions = {str(k): float(v) for k, v in dimensions_raw.items()}
        hard_raw = payload.get("hard_failures") or payload.get("auto_fails") or ()
        if not isinstance(hard_raw, Sequence) or isinstance(hard_raw, (str, bytes)):
            raise ValueError("hard_failures must be a sequence")
        watched = bool(payload.get("watched_video"))
        if decision == "ship" and not watched:
            raise ValueError("ship verdict requires watched_video=true")
        version = str(payload.get("judge_version") or "").strip()
        if not version:
            raise ValueError("judge_version is required")
        return cls(
            decision=decision,
            score=float(score),
            dimensions=dimensions,
            hard_failures=tuple(str(item) for item in hard_raw),
            watched_video=watched,
            judge_version=version,
        )
