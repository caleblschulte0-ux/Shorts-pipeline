from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class GateState(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    MISSING = "missing"


class PackageDecision(str, Enum):
    PASS = "pass"
    HOLD = "hold"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class GateResult:
    gate: str
    state: GateState
    manifest_sha256: str | None = None
    score: float | None = None
    reasons: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True)
class PackageReadiness:
    decision: PackageDecision
    readiness_score: float
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    passed_gates: int
    required_gates: int


DEFAULT_REQUIRED_GATES = frozenset({
    "manifest",
    "facts",
    "visual_judge",
    "fallbacks",
    "performance",
    "technical",
    "catalog",
    "channel_guard",
})


def evaluate_package(
    gates: Iterable[GateResult],
    *,
    expected_manifest_sha256: str,
    publishing_enabled: bool,
    required_gates: frozenset[str] = DEFAULT_REQUIRED_GATES,
) -> PackageReadiness:
    gate_map = {gate.gate: gate for gate in gates}
    blockers: list[str] = []
    warnings: list[str] = []
    passed = 0

    for gate_name in sorted(required_gates):
        gate = gate_map.get(gate_name)
        if gate is None:
            blockers.append(f"missing_gate:{gate_name}")
            continue
        if gate.manifest_sha256 and gate.manifest_sha256 != expected_manifest_sha256:
            blockers.append(f"artifact_mismatch:{gate_name}")
            continue
        if gate.state in {GateState.FAIL, GateState.MISSING}:
            blockers.append(f"gate_failed:{gate_name}")
        elif gate.state is GateState.WARN:
            warnings.append(f"gate_warning:{gate_name}")
        else:
            passed += 1

    for gate in gate_map.values():
        if not gate.required and gate.state is GateState.WARN:
            warnings.append(f"optional_warning:{gate.gate}")

    required_count = len(required_gates)
    readiness = 0.0 if required_count == 0 else passed / required_count * 100
    if blockers:
        decision = PackageDecision.QUARANTINE
    elif not publishing_enabled:
        decision = PackageDecision.HOLD
    else:
        decision = PackageDecision.PASS

    return PackageReadiness(
        decision=decision,
        readiness_score=round(readiness, 1),
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
        passed_gates=passed,
        required_gates=required_count,
    )
