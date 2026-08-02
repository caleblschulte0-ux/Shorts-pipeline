from __future__ import annotations

from .closure import CAPABILITIES, TestEvidence
from .evidence import GATES


def complete_test_evidence() -> tuple[TestEvidence, ...]:
    rows: list[TestEvidence] = []
    for capability in CAPABILITIES:
        rows.append(TestEvidence(f"design::{capability}", capability, ("designed",)))
        rows.append(TestEvidence(f"implementation::{capability}", capability, ("implemented",)))
        rows.append(TestEvidence(f"unit::{capability}", capability, ("unit_tested",)))
        rows.append(TestEvidence(f"integration::{capability}", capability, ("integration_tested",)))
        rows.append(TestEvidence(f"sandbox-wire::{capability}", capability, ("sandbox_wired",)))
        rows.append(TestEvidence(f"sandbox-proof::{capability}", capability, ("sandbox_proven",)))
    return tuple(rows)


def intentionally_incomplete_evidence() -> tuple[TestEvidence, ...]:
    rows = list(complete_test_evidence())
    rows = [row for row in rows if not (row.capability == CAPABILITIES[-1] and "sandbox_proven" in row.gates)]
    return tuple(rows)
