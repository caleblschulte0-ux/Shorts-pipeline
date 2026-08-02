from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from .evidence import CapabilityEvidence, ClosureReport, ClosureScorecard, GATES


CAPABILITIES = (
    "source_and_premise",
    "story_and_retention",
    "rendering",
    "visual_judging",
    "transactional_repair",
    "full_video_proof",
    "observability",
    "release_safety",
    "analytics_learning",
    "portfolio_operations",
    "fault_recovery",
    "contract_compatibility",
)


@dataclass(frozen=True)
class TestEvidence:
    test_id: str
    capability: str
    gates: tuple[str, ...]

    def validate(self) -> None:
        if self.capability not in CAPABILITIES:
            raise ValueError(f"unknown capability: {self.capability}")
        if not self.test_id:
            raise ValueError("test evidence ID is required")
        if not self.gates or any(gate not in GATES for gate in self.gates):
            raise ValueError("test evidence gates are invalid")


def build_closure_report(evidence: Iterable[TestEvidence]) -> ClosureReport:
    rows = tuple(evidence)
    for row in rows:
        row.validate()
    capabilities: list[CapabilityEvidence] = []
    for capability in CAPABILITIES:
        matching = tuple(row for row in rows if row.capability == capability)
        gates = {gate: any(gate in row.gates for row in matching) for gate in GATES}
        capabilities.append(CapabilityEvidence(capability, gates, tuple(row.test_id for row in matching)))
    return ClosureScorecard().evaluate(capabilities)


def write_closure_artifact(path: Path, report: ClosureReport) -> None:
    if not report.complete:
        raise ValueError("cannot write a completion artifact for an incomplete report")
    payload = {
        "scope": "isolated_review_test_area",
        "overall_percent": report.overall_percent,
        "gate_percentages": dict(report.gate_percentages),
        "capability_percentages": dict(report.capability_percentages),
        "missing": list(report.missing),
        "production_pipeline_modified": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
