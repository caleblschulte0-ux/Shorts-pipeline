from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class Decision(str, Enum):
    REJECT = "reject"
    HOLD = "hold"
    SHIP = "ship"


@dataclass(frozen=True)
class SceneDiagnosis:
    scene_id: str
    scene_index: int
    start_seconds: float
    end_seconds: float
    failure_class: str
    visible_evidence: str
    root_cause: str
    repair_goal: str

    def validate(self) -> None:
        if not self.scene_id:
            raise ValueError("scene_id is required")
        if self.scene_index < 0:
            raise ValueError("scene_index must be non-negative")
        if self.start_seconds < 0 or self.end_seconds <= self.start_seconds:
            raise ValueError("diagnosis time range must be positive")
        for name in ("failure_class", "visible_evidence", "root_cause", "repair_goal"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} is required")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SceneDiagnosis":
        obj = cls(
            scene_id=str(value["scene_id"]),
            scene_index=int(value["scene_index"]),
            start_seconds=float(value["start_seconds"]),
            end_seconds=float(value["end_seconds"]),
            failure_class=str(value["failure_class"]),
            visible_evidence=str(value["visible_evidence"]),
            root_cause=str(value["root_cause"]),
            repair_goal=str(value["repair_goal"]),
        )
        obj.validate()
        return obj


@dataclass(frozen=True)
class TemporalMetrics:
    effective_fps: float
    duplicate_ratio: float
    longest_duplicate_run: int = 0
    longest_unmarked_static_seconds: float = 0.0

    def validate(self) -> None:
        if self.effective_fps < 0:
            raise ValueError("effective_fps cannot be negative")
        if not 0 <= self.duplicate_ratio <= 1:
            raise ValueError("duplicate_ratio must be between 0 and 1")
        if self.longest_duplicate_run < 0:
            raise ValueError("longest_duplicate_run cannot be negative")
        if self.longest_unmarked_static_seconds < 0:
            raise ValueError("longest_unmarked_static_seconds cannot be negative")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "TemporalMetrics":
        value = value or {}
        obj = cls(
            effective_fps=float(value.get("effective_fps", 0.0)),
            duplicate_ratio=float(value.get("duplicate_ratio", 1.0)),
            longest_duplicate_run=int(value.get("longest_duplicate_run", 0)),
            longest_unmarked_static_seconds=float(
                value.get("longest_unmarked_static_seconds", 0.0)
            ),
        )
        obj.validate()
        return obj


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    score: float
    dimensions: Mapping[str, float]
    hard_failures: tuple[str, ...] = ()
    temporal: TemporalMetrics = field(
        default_factory=lambda: TemporalMetrics(0.0, 1.0)
    )
    weakest_scene: SceneDiagnosis | None = None
    watched_video: bool = False
    judge_version: str = "unknown"
    adversarial_objections: tuple[str, ...] = ()

    def validate(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")
        if not self.dimensions:
            raise ValueError("dimensions are required")
        for name, score in self.dimensions.items():
            if not name or not 0 <= float(score) <= 10:
                raise ValueError(f"invalid dimension {name!r}: {score!r}")
        self.temporal.validate()
        if self.weakest_scene is not None:
            self.weakest_scene.validate()
        if self.decision is Decision.SHIP:
            if not self.watched_video:
                raise ValueError("ship verdict requires watched_video=true")
            if self.hard_failures:
                raise ValueError("ship verdict cannot contain hard failures")
            if self.adversarial_objections:
                raise ValueError("ship verdict cannot contain adversarial objections")
        if self.decision is not Decision.SHIP and self.weakest_scene is None:
            raise ValueError("non-ship verdict requires a structured weakest_scene")

    @property
    def lowest_dimension(self) -> float:
        return min(float(v) for v in self.dimensions.values())

    @property
    def promotable(self) -> bool:
        return (
            self.watched_video
            and not self.hard_failures
            and not self.adversarial_objections
            and self.decision in {Decision.HOLD, Decision.SHIP}
        )

    def rank(self) -> tuple[int, int, int, float, float, float, float]:
        decision_rank = {
            Decision.REJECT: 0,
            Decision.HOLD: 1,
            Decision.SHIP: 2,
        }[self.decision]
        return (
            int(self.watched_video),
            int(not self.hard_failures),
            decision_rank,
            self.score,
            self.lowest_dimension,
            self.temporal.effective_fps,
            -self.temporal.duplicate_ratio,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision"] = self.decision.value
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Verdict":
        diagnosis_value = value.get("weakest_scene")
        obj = cls(
            decision=Decision(str(value["decision"]).lower()),
            score=float(value["score"]),
            dimensions={str(k): float(v) for k, v in dict(value["dimensions"]).items()},
            hard_failures=tuple(str(x) for x in value.get("hard_failures", ())),
            temporal=TemporalMetrics.from_dict(value.get("temporal")),
            weakest_scene=(
                SceneDiagnosis.from_dict(diagnosis_value)
                if diagnosis_value is not None
                else None
            ),
            watched_video=bool(value.get("watched_video", False)),
            judge_version=str(value.get("judge_version", "unknown")),
            adversarial_objections=tuple(
                str(x) for x in value.get("adversarial_objections", ())
            ),
        )
        obj.validate()
        return obj


@dataclass(frozen=True)
class SceneCandidate:
    candidate_id: str
    scene_id: str
    visualization: str
    performance_family: str
    repair_goal: str
    rationale: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        for name in (
            "candidate_id",
            "scene_id",
            "visualization",
            "performance_family",
            "repair_goal",
            "rationale",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttemptIdentity:
    slug: str
    run_id: str
    attempt_id: str

    def validate(self) -> None:
        for name in ("slug", "run_id", "attempt_id"):
            value = getattr(self, name)
            if not value or any(part in value for part in ("/", "\\", "..")):
                raise ValueError(f"unsafe {name}: {value!r}")
