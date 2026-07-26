from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


GATES = (
    "designed",
    "implemented",
    "unit_tested",
    "integration_tested",
    "sandbox_wired",
    "sandbox_proven",
)


@dataclass(frozen=True)
class CapabilityEvidence:
    name: str
    gates: Mapping[str, bool]
    evidence_ids: tuple[str, ...]

    def validate(self) -> None:
        if not self.name:
            raise ValueError("capability name is required")
        if set(self.gates) != set(GATES):
            raise ValueError("capability gate set is incomplete")
        if not self.evidence_ids:
            raise ValueError("capability evidence is required")


@dataclass(frozen=True)
class ClosureReport:
    overall_percent: float
    gate_percentages: Mapping[str, float]
    capability_percentages: Mapping[str, float]
    missing: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return self.overall_percent == 100.0 and not self.missing


class ClosureScorecard:
    def evaluate(self, capabilities: Iterable[CapabilityEvidence]) -> ClosureReport:
        items = tuple(capabilities)
        if not items:
            raise ValueError("closure scorecard requires capabilities")
        missing: list[str] = []
        for item in items:
            item.validate()
            for gate, passed in item.gates.items():
                if not passed:
                    missing.append(f"{item.name}.{gate}")
        gate_percentages = {
            gate: round(sum(1 for item in items if item.gates[gate]) / len(items) * 100, 1)
            for gate in GATES
        }
        capability_percentages = {
            item.name: round(sum(1 for gate in GATES if item.gates[gate]) / len(GATES) * 100, 1)
            for item in items
        }
        overall = round(sum(capability_percentages.values()) / len(capability_percentages), 1)
        return ClosureReport(overall, gate_percentages, capability_percentages, tuple(missing))
