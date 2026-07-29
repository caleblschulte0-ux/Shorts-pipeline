"""Dormant finite autonomy reference-completeness rubric.

This module deliberately separates authored reference closure from executed,
integrated, or live launch readiness.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


AUTONOMY_DOMAINS: tuple[str, ...] = (
    "idea_funnel",
    "story_intake",
    "portfolio_selection",
    "production_stage_graph",
    "stage_artifact_contracts",
    "provider_routing",
    "durable_execution_ledger",
    "idempotency_and_leases",
    "resource_scheduling",
    "budget_governance",
    "generic_decisioning",
    "bounded_retry_repair_reauthor",
    "factual_rewind",
    "quarantine_and_deferral",
    "independent_judging",
    "artifact_hash_binding",
    "batch_acceptance",
    "deterministic_simulation",
    "observability_and_audit",
    "security_and_resilience",
    "controlled_learning",
    "rollback_and_kill_switch",
    "launch_readiness",
    "claude_execution_handoff",
)


@dataclass(frozen=True)
class DomainEvidence:
    domain: str
    implementation_paths: tuple[str, ...]
    positive_test_references: tuple[str, ...]
    negative_test_references: tuple[str, ...]
    isolated: bool
    verified_executed: bool = False
    integrated: bool = False
    live_evidence: bool = False

    def __post_init__(self) -> None:
        if self.domain not in AUTONOMY_DOMAINS:
            raise ValueError(f"unknown autonomy domain {self.domain!r}")


@dataclass(frozen=True)
class AutonomyCompletenessReport:
    reference_coverage_percent: float
    verified_execution_percent: float
    integration_percent: float
    live_evidence_percent: float
    missing_domains: tuple[str, ...]
    invalid_domains: tuple[str, ...]
    non_isolated_domains: tuple[str, ...]
    verified_domains: tuple[str, ...]
    complete_reference_surface: bool


def assess_autonomy_completeness(evidence: Iterable[DomainEvidence]) -> AutonomyCompletenessReport:
    items = tuple(evidence)
    grouped: dict[str, list[DomainEvidence]] = {}
    invalid: list[str] = []
    non_isolated: list[str] = []

    for item in items:
        grouped.setdefault(item.domain, []).append(item)
        if not item.implementation_paths or not item.positive_test_references or not item.negative_test_references:
            invalid.append(item.domain)
        if any(not path.startswith(("experiments/", "docs/")) for path in item.implementation_paths):
            non_isolated.append(item.domain)
        if not item.isolated:
            non_isolated.append(item.domain)

    duplicate_domains = {domain for domain, records in grouped.items() if len(records) != 1}
    invalid.extend(duplicate_domains)
    missing = tuple(domain for domain in AUTONOMY_DOMAINS if domain not in grouped)
    valid_domains = {
        domain
        for domain, records in grouped.items()
        if len(records) == 1
        and domain not in invalid
        and domain not in non_isolated
        and records[0].implementation_paths
        and records[0].positive_test_references
        and records[0].negative_test_references
    }

    denominator = len(AUTONOMY_DOMAINS)
    reference_percent = round(len(valid_domains) / denominator * 100.0, 2)
    verified_domains = tuple(
        sorted(domain for domain in valid_domains if grouped[domain][0].verified_executed)
    )
    integrated_domains = tuple(
        domain for domain in valid_domains if grouped[domain][0].integrated
    )
    live_domains = tuple(
        domain for domain in valid_domains if grouped[domain][0].live_evidence
    )

    return AutonomyCompletenessReport(
        reference_coverage_percent=reference_percent,
        verified_execution_percent=round(len(verified_domains) / denominator * 100.0, 2),
        integration_percent=round(len(integrated_domains) / denominator * 100.0, 2),
        live_evidence_percent=round(len(live_domains) / denominator * 100.0, 2),
        missing_domains=missing,
        invalid_domains=tuple(sorted(set(invalid))),
        non_isolated_domains=tuple(sorted(set(non_isolated))),
        verified_domains=verified_domains,
        complete_reference_surface=(
            reference_percent == 100.0
            and not missing
            and not invalid
            and not non_isolated
        ),
    )


def complete_autonomy_reference_evidence() -> tuple[DomainEvidence, ...]:
    mapping: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
        "idea_funnel": (("experiments/curiosity_nextgen/idea_funnel.py",), ("test_autonomy_closure.py",)),
        "story_intake": (("experiments/curiosity_nextgen/story_intake_contract.py",), ("test_autonomous_core.py",)),
        "portfolio_selection": (("experiments/curiosity_nextgen/portfolio_optimizer.py", "experiments/curiosity_nextgen/edit_blueprint.py"), ("test_completeness_closure.py", "test_retention_quality.py")),
        "production_stage_graph": (("experiments/curiosity_nextgen/production_stage_graph.py",), ("test_autonomous_core.py",)),
        "stage_artifact_contracts": (("experiments/curiosity_nextgen/stage_artifact_contract.py",), ("test_autonomy_closure.py",)),
        "provider_routing": (("experiments/curiosity_nextgen/provider_pool.py", "experiments/curiosity_nextgen/adapter_contracts.py"), ("test_autonomy_closure.py", "test_completeness_closure.py")),
        "durable_execution_ledger": (("experiments/curiosity_nextgen/execution_ledger.py",), ("test_autonomy_closure.py",)),
        "idempotency_and_leases": (("experiments/curiosity_nextgen/execution_ledger.py", "experiments/curiosity_nextgen/checkpoint_store.py"), ("test_autonomy_closure.py", "test_resilience_controls.py")),
        "resource_scheduling": (("experiments/curiosity_nextgen/autonomous_batch_controller.py", "experiments/curiosity_nextgen/render_scheduler.py"), ("test_autonomous_program.py", "test_structural_hardening.py")),
        "budget_governance": (("experiments/curiosity_nextgen/resource_governor.py", "experiments/curiosity_nextgen/render_budget.py"), ("test_resilience_controls.py", "test_structural_hardening.py")),
        "generic_decisioning": (("experiments/curiosity_nextgen/autonomous_decision_engine.py",), ("test_autonomous_core.py",)),
        "bounded_retry_repair_reauthor": (("experiments/curiosity_nextgen/autonomous_decision_engine.py", "experiments/curiosity_nextgen/repair_planner.py"), ("test_autonomous_core.py", "test_decision_intelligence.py")),
        "factual_rewind": (("experiments/curiosity_nextgen/autonomous_batch_controller.py", "experiments/curiosity_nextgen/claim_registry.py"), ("test_autonomous_program.py", "test_structural_hardening.py")),
        "quarantine_and_deferral": (("experiments/curiosity_nextgen/autonomous_batch_controller.py", "experiments/curiosity_nextgen/story_catalog.py"), ("test_autonomous_program.py", "test_structural_hardening.py")),
        "independent_judging": (("experiments/curiosity_nextgen/judge_orchestrator.py", "experiments/curiosity_nextgen/provider_pool.py"), ("test_structural_hardening.py", "test_autonomy_closure.py")),
        "artifact_hash_binding": (("experiments/curiosity_nextgen/artifact_manifest.py", "experiments/curiosity_nextgen/stage_artifact_contract.py"), ("test_prototypes.py", "test_autonomy_closure.py")),
        "batch_acceptance": (("experiments/curiosity_nextgen/batch_acceptance.py",), ("test_autonomous_program.py",)),
        "deterministic_simulation": (("experiments/curiosity_nextgen/autonomous_simulator.py", "experiments/curiosity_nextgen/replay_engine.py"), ("test_autonomy_closure.py", "test_resilience_controls.py")),
        "observability_and_audit": (("experiments/curiosity_nextgen/observability.py", "experiments/curiosity_nextgen/audit_chain.py", "experiments/curiosity_nextgen/execution_ledger.py"), ("test_structural_hardening.py", "test_completeness_closure.py", "test_autonomy_closure.py")),
        "security_and_resilience": (("experiments/curiosity_nextgen/security_scanner.py", "experiments/curiosity_nextgen/resilience_lab.py"), ("test_resilience_controls.py",)),
        "controlled_learning": (("experiments/curiosity_nextgen/controlled_learning_loop.py", "experiments/curiosity_nextgen/experiment_attribution.py"), ("test_autonomy_launch.py", "test_decision_intelligence.py")),
        "rollback_and_kill_switch": (("experiments/curiosity_nextgen/lifecycle_controls.py", "experiments/curiosity_nextgen/freeze_controller.py"), ("test_completeness_closure.py", "test_structural_hardening.py")),
        "launch_readiness": (("experiments/curiosity_nextgen/launch_readiness.py",), ("test_autonomy_launch.py",)),
        "claude_execution_handoff": (("docs/CLAUDE_AUTONOMY_LAUNCHOFF.md", "docs/CLAUDE_EXECUTION_CHECKLIST.md"), ("test_autonomy_launch.py",)),
    }
    return tuple(
        DomainEvidence(
            domain=domain,
            implementation_paths=paths,
            positive_test_references=tests,
            negative_test_references=tests,
            isolated=True,
        )
        for domain, (paths, tests) in mapping.items()
    )
