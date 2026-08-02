from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


class HandoffValidationError(ValueError):
    """Raised when the master handoff becomes internally inconsistent."""


@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: str
    status: str
    value: str
    source_path: str
    notes: str = ""

    def validate(self) -> None:
        if not self.claim_id.strip():
            raise HandoffValidationError("evidence claim_id is required")
        if self.status not in {"verified", "declared_unverified", "not_claimed"}:
            raise HandoffValidationError(f"invalid evidence status: {self.status}")
        if not self.source_path.startswith(("review_prototypes/", "docs/")):
            raise HandoffValidationError("evidence source must remain review-only")


@dataclass(frozen=True)
class Component:
    component_id: str
    title: str
    root: str
    purpose: str
    maturity: str
    authority: str
    test_commands: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    adoption_lane: str = ""
    notes: str = ""

    def validate(self) -> None:
        if not self.component_id.strip() or not self.title.strip():
            raise HandoffValidationError("component id and title are required")
        if not self.root.startswith(("review_prototypes/", "docs/")):
            raise HandoffValidationError(
                f"component {self.component_id} leaves review-only roots: {self.root}"
            )
        if self.authority not in {
            "none",
            "record_only",
            "shadow_only",
            "preview_only",
            "reference_only",
        }:
            raise HandoffValidationError(
                f"component {self.component_id} has invalid authority {self.authority}"
            )


@dataclass(frozen=True)
class AdoptionPhase:
    phase_id: str
    title: str
    purpose: str
    commands: tuple[str, ...]
    acceptance: tuple[str, ...]
    rollback: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    production_files: tuple[str, ...] = ()
    authority_ceiling: str = "none"

    def validate(self) -> None:
        if not all((self.phase_id, self.title, self.purpose)):
            raise HandoffValidationError("phase id, title, and purpose are required")
        if not self.commands or not self.acceptance or not self.rollback or not self.stop_conditions:
            raise HandoffValidationError(
                f"phase {self.phase_id} must define commands, acceptance, rollback, and stop conditions"
            )
        if self.authority_ceiling not in {
            "none",
            "record_only",
            "shadow_only",
            "preview_only",
            "rough_cut_only",
            "bounded_canary",
        }:
            raise HandoffValidationError(
                f"phase {self.phase_id} has invalid authority ceiling {self.authority_ceiling}"
            )


@dataclass(frozen=True)
class Risk:
    risk_id: str
    title: str
    trigger: str
    mitigation: tuple[str, ...]
    rollback: tuple[str, ...]
    severity: str

    def validate(self) -> None:
        if self.severity not in {"critical", "high", "medium", "low"}:
            raise HandoffValidationError(f"invalid risk severity: {self.severity}")
        if not isinstance(self.mitigation, tuple) or not isinstance(self.rollback, tuple):
            raise HandoffValidationError(f"risk {self.risk_id} mitigation and rollback must be tuples")
        if not self.mitigation or not self.rollback:
            raise HandoffValidationError(f"risk {self.risk_id} lacks mitigation/rollback")


@dataclass(frozen=True)
class MasterHandoff:
    schema_version: str
    branch: str
    pull_request: int
    status: str
    components: tuple[Component, ...]
    phases: tuple[AdoptionPhase, ...]
    risks: tuple[Risk, ...]
    evidence: tuple[EvidenceClaim, ...]
    sacred_guards: tuple[str, ...]
    first_session_commands: tuple[str, ...]
    decision_routes: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.status != "review_only_unwired":
            raise HandoffValidationError("master handoff must remain review_only_unwired")
        if self.pull_request <= 0:
            raise HandoffValidationError("pull_request must be positive")

        component_ids = [c.component_id for c in self.components]
        phase_ids = [p.phase_id for p in self.phases]
        if len(component_ids) != len(set(component_ids)):
            raise HandoffValidationError("duplicate component ids")
        if len(phase_ids) != len(set(phase_ids)):
            raise HandoffValidationError("duplicate phase ids")

        for component in self.components:
            component.validate()
            missing = set(component.depends_on) - set(component_ids)
            if missing:
                raise HandoffValidationError(
                    f"component {component.component_id} has missing dependencies: {sorted(missing)}"
                )
        for phase in self.phases:
            phase.validate()
            missing = set(phase.depends_on) - set(phase_ids)
            if missing:
                raise HandoffValidationError(
                    f"phase {phase.phase_id} has missing dependencies: {sorted(missing)}"
                )
        for risk in self.risks:
            risk.validate()
        for claim in self.evidence:
            claim.validate()

        _assert_acyclic(component_ids, {c.component_id: c.depends_on for c in self.components}, "component")
        _assert_acyclic(phase_ids, {p.phase_id: p.depends_on for p in self.phases}, "phase")

        if not any("showrunner" in guard.lower() for guard in self.sacred_guards):
            raise HandoffValidationError("showrunner sovereignty guard is missing")
        if not any("publishing" in guard.lower() for guard in self.sacred_guards):
            raise HandoffValidationError("publishing freeze guard is missing")
        if not self.first_session_commands:
            raise HandoffValidationError("first session commands are required")


def _assert_acyclic(nodes: Iterable[str], deps: dict[str, tuple[str, ...]], label: str) -> None:
    state: dict[str, int] = {n: 0 for n in nodes}

    def visit(node: str) -> None:
        if state[node] == 1:
            raise HandoffValidationError(f"{label} dependency cycle at {node}")
        if state[node] == 2:
            return
        state[node] = 1
        for dep in deps.get(node, ()):
            visit(dep)
        state[node] = 2

    for node in nodes:
        visit(node)
