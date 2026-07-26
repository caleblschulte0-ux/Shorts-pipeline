from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateState(str, Enum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    label: str
    state: GateState
    evidence: dict[str, Any] = field(default_factory=dict)
    blocking: bool = True

    def __post_init__(self) -> None:
        if not self.gate_id or not self.gate_id.replace("_", "").isalnum():
            raise ValueError("gate_id must be a safe non-empty identifier")
        if not self.label.strip():
            raise ValueError("gate label is required")
        if not isinstance(self.evidence, dict):
            raise TypeError("gate evidence must be a dict")

    @property
    def passed(self) -> bool:
        return self.state is GateState.PASS


@dataclass(frozen=True)
class LaunchReport:
    scope: str
    gates: tuple[GateResult, ...]
    dimensions: dict[str, float]
    weights: dict[str, float]
    production_pipeline_modified: bool = False
    publishing_enabled: bool = False
    showrunner_authority_changed: bool = False

    def __post_init__(self) -> None:
        if not self.scope:
            raise ValueError("scope is required")
        if not self.gates:
            raise ValueError("at least one gate is required")
        ids = [g.gate_id for g in self.gates]
        if len(ids) != len(set(ids)):
            raise ValueError("gate ids must be unique")
        if set(self.dimensions) != set(self.weights):
            raise ValueError("dimensions and weights must name the same keys")
        if abs(sum(self.weights.values()) - 100.0) > 1e-6:
            raise ValueError("weights must sum to 100")
        for value in self.dimensions.values():
            if value < 0 or value > 100:
                raise ValueError("dimension values must be between 0 and 100")

    @property
    def blockers(self) -> tuple[GateResult, ...]:
        return tuple(g for g in self.gates if g.blocking and not g.passed)

    @property
    def launch_scope_percent(self) -> float:
        blocking = [g for g in self.gates if g.blocking]
        return round(100.0 * sum(g.passed for g in blocking) / len(blocking), 1)

    @property
    def overall_percent(self) -> float:
        return round(
            sum(self.dimensions[k] * self.weights[k] for k in self.dimensions) / 100.0,
            1,
        )

    @property
    def closed(self) -> bool:
        return not self.blockers

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "closed": self.closed,
            "launch_scope_percent": self.launch_scope_percent,
            "overall_percent": self.overall_percent,
            "gates": [
                {
                    "gate_id": g.gate_id,
                    "label": g.label,
                    "state": g.state.value,
                    "blocking": g.blocking,
                    "evidence": g.evidence,
                }
                for g in self.gates
            ],
            "dimensions": self.dimensions,
            "weights": self.weights,
            "production_pipeline_modified": self.production_pipeline_modified,
            "publishing_enabled": self.publishing_enabled,
            "showrunner_authority_changed": self.showrunner_authority_changed,
        }
