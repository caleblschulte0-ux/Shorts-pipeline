from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class StructuralDomain(str, Enum):
    ARTIFACT_IDENTITY = "artifact_identity"
    FACTS_PROVENANCE = "facts_provenance"
    JUDGE_WORKFLOW = "judge_workflow"
    MEDIA_SELECTION = "media_selection"
    QUALITY_REPAIR = "quality_repair"
    CACHE_PERFORMANCE = "cache_performance"
    CATALOG_SCHEDULING = "catalog_scheduling"
    PACKAGE_READINESS = "package_readiness"
    RELEASE_AUTHORIZATION = "release_authorization"
    OBSERVABILITY = "observability"
    EXPERIMENTATION = "experimentation"
    SCHEMA_EVOLUTION = "schema_evolution"
    LINEAGE = "lineage"
    REPLAY_RECOVERY = "replay_recovery"
    DEPENDENCY_RESILIENCE = "dependency_resilience"
    RESOURCE_GOVERNANCE = "resource_governance"
    SECURITY = "security"
    FAULT_INJECTION = "fault_injection"
    POLICY_MANAGEMENT = "policy_management"
    ADAPTER_CONTRACTS = "adapter_contracts"
    AUDIT_INTEGRITY = "audit_integrity"
    HUMAN_REVIEW = "human_review"
    LIFECYCLE_RECOVERY = "lifecycle_recovery"
    ENVIRONMENT_REPRODUCIBILITY = "environment_reproducibility"
    DRIFT_MONITORING = "drift_monitoring"
    PORTFOLIO_BALANCING = "portfolio_balancing"
    GENERALIZATION = "generalization"


REQUIRED_DOMAINS = frozenset(StructuralDomain)


@dataclass(frozen=True)
class DomainEvidence:
    domain: StructuralDomain
    module_paths: tuple[str, ...]
    test_ids: tuple[str, ...]
    isolated: bool
    documentation_reference: str | None = None
    execution_verified: bool = False


@dataclass(frozen=True)
class CompletenessReport:
    reference_coverage_percent: float
    verified_execution_percent: float
    reference_complete: bool
    execution_complete: bool
    missing_domains: tuple[StructuralDomain, ...]
    invalid_domains: tuple[StructuralDomain, ...]
    blockers: tuple[str, ...]


def _validate_evidence(item: DomainEvidence, *, minimum_tests: int) -> tuple[str, ...]:
    blockers: list[str] = []
    if not item.module_paths:
        blockers.append("missing_module_reference")
    if any(not path.startswith("experiments/curiosity_nextgen/") for path in item.module_paths):
        blockers.append("module_outside_isolation_boundary")
    if len(set(item.module_paths)) != len(item.module_paths):
        blockers.append("duplicate_module_reference")
    if len(item.test_ids) < minimum_tests:
        blockers.append("insufficient_contract_tests")
    if len(set(item.test_ids)) != len(item.test_ids):
        blockers.append("duplicate_test_reference")
    if not item.isolated:
        blockers.append("not_isolated")
    return tuple(blockers)


def assess_structural_completeness(
    evidence: Iterable[DomainEvidence],
    *,
    minimum_tests_per_domain: int = 2,
) -> CompletenessReport:
    items = tuple(evidence)
    blockers: list[str] = []
    by_domain: dict[StructuralDomain, DomainEvidence] = {}
    for item in items:
        if item.domain in by_domain:
            blockers.append(f"duplicate_domain:{item.domain.value}")
        else:
            by_domain[item.domain] = item

    missing = tuple(sorted(REQUIRED_DOMAINS - set(by_domain), key=lambda value: value.value))
    invalid: list[StructuralDomain] = []
    valid_domains = 0
    verified_domains = 0
    for domain in sorted(REQUIRED_DOMAINS, key=lambda value: value.value):
        item = by_domain.get(domain)
        if item is None:
            continue
        domain_blockers = _validate_evidence(item, minimum_tests=minimum_tests_per_domain)
        if domain_blockers:
            invalid.append(domain)
            blockers.extend(f"{domain.value}:{reason}" for reason in domain_blockers)
            continue
        valid_domains += 1
        if item.execution_verified:
            verified_domains += 1

    total = len(REQUIRED_DOMAINS)
    reference_score = round(valid_domains / total * 100, 1)
    verified_score = round(verified_domains / total * 100, 1)
    reference_complete = reference_score == 100.0 and not missing and not invalid and not blockers
    execution_complete = reference_complete and verified_score == 100.0
    return CompletenessReport(
        reference_coverage_percent=reference_score,
        verified_execution_percent=verified_score,
        reference_complete=reference_complete,
        execution_complete=execution_complete,
        missing_domains=missing,
        invalid_domains=tuple(invalid),
        blockers=tuple(sorted(set(blockers))),
    )


def complete_reference_evidence(*, execution_verified: bool = False) -> tuple[DomainEvidence, ...]:
    module_map = {
        StructuralDomain.ARTIFACT_IDENTITY: ("artifact_manifest.py", "package_readiness.py"),
        StructuralDomain.FACTS_PROVENANCE: ("claim_registry.py", "semantic_claims.py"),
        StructuralDomain.JUDGE_WORKFLOW: ("judge_contract.py", "judge_orchestrator.py"),
        StructuralDomain.MEDIA_SELECTION: ("media_ranker.py", "repetition_ledger.py"),
        StructuralDomain.QUALITY_REPAIR: ("quality.py", "repair_planner.py"),
        StructuralDomain.CACHE_PERFORMANCE: ("shot_cache.py", "render_budget.py"),
        StructuralDomain.CATALOG_SCHEDULING: ("story_catalog.py", "render_scheduler.py"),
        StructuralDomain.PACKAGE_READINESS: ("package_readiness.py", "integration_lab.py"),
        StructuralDomain.RELEASE_AUTHORIZATION: ("approval_token.py", "freeze_controller.py"),
        StructuralDomain.OBSERVABILITY: ("observability.py", "pipeline_status.py"),
        StructuralDomain.EXPERIMENTATION: ("experiment_attribution.py", "portfolio_optimizer.py"),
        StructuralDomain.SCHEMA_EVOLUTION: ("schema_registry.py", "migration_planner.py"),
        StructuralDomain.LINEAGE: ("lineage_graph.py", "artifact_manifest.py"),
        StructuralDomain.REPLAY_RECOVERY: ("replay_engine.py", "checkpoint_store.py"),
        StructuralDomain.DEPENDENCY_RESILIENCE: ("circuit_breaker.py", "adapter_contracts.py"),
        StructuralDomain.RESOURCE_GOVERNANCE: ("resource_governor.py", "render_scheduler.py"),
        StructuralDomain.SECURITY: ("security_scanner.py", "audit_chain.py"),
        StructuralDomain.FAULT_INJECTION: ("fault_injection.py", "resilience_lab.py"),
        StructuralDomain.POLICY_MANAGEMENT: ("policy_snapshot.py", "schema_registry.py"),
        StructuralDomain.ADAPTER_CONTRACTS: ("adapter_contracts.py", "environment_lock.py"),
        StructuralDomain.AUDIT_INTEGRITY: ("audit_chain.py", "observability.py"),
        StructuralDomain.HUMAN_REVIEW: ("review_queue.py", "judge_orchestrator.py"),
        StructuralDomain.LIFECYCLE_RECOVERY: ("lifecycle_controls.py", "checkpoint_store.py"),
        StructuralDomain.ENVIRONMENT_REPRODUCIBILITY: ("environment_lock.py", "replay_engine.py"),
        StructuralDomain.DRIFT_MONITORING: ("drift_monitor.py", "observability.py"),
        StructuralDomain.PORTFOLIO_BALANCING: ("portfolio_optimizer.py", "catalog_triage.py"),
        StructuralDomain.GENERALIZATION: ("generalization_suite.py", "integration_lab.py"),
    }
    evidence: list[DomainEvidence] = []
    for domain, filenames in module_map.items():
        paths = tuple(f"experiments/curiosity_nextgen/{name}" for name in filenames)
        evidence.append(
            DomainEvidence(
                domain=domain,
                module_paths=paths,
                test_ids=(f"{domain.value}:positive", f"{domain.value}:negative"),
                isolated=True,
                documentation_reference="experiments/curiosity_nextgen/README.md",
                execution_verified=execution_verified,
            )
        )
    return tuple(evidence)
