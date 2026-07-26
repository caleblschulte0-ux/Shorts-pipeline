"""Integrated resilience preflight simulator for dormant next-generation controls."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from .checkpoint_store import CheckpointLedger, ResumeDecision
from .circuit_breaker import BreakerState, CircuitBreaker
from .lineage_graph import LineageGraph
from .resource_governor import ResourceDecision, ResourcePlan, ResourcePolicy, ResourceRequest, govern_resources
from .schema_registry import PayloadValidation, SchemaDefinition, validate_payload
from .security_scanner import SecurityReport, scan_payload


class ResilienceDecision(str, Enum):
    READY = "ready"
    HOLD = "hold"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class ResilienceInput:
    schema: SchemaDefinition
    payload: Mapping[str, object]
    lineage: LineageGraph
    checkpoint_ledger: CheckpointLedger
    required_stages: tuple[str, ...]
    manifest_sha256: str
    resource_request: ResourceRequest
    circuit_breaker: CircuitBreaker
    now: int
    expected_inputs: Mapping[str, str] | None = None
    allowed_hosts: frozenset[str] = frozenset()
    resource_policy: ResourcePolicy | None = None


@dataclass(frozen=True)
class ResilienceResult:
    decision: ResilienceDecision
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    schema_validation: PayloadValidation
    security_report: SecurityReport
    resource_plan: ResourcePlan
    resume_decision: ResumeDecision
    breaker_state: BreakerState


def simulate_resilience_preflight(inputs: ResilienceInput) -> ResilienceResult:
    blockers: list[str] = []
    warnings: list[str] = []

    schema_result = validate_payload(inputs.schema, inputs.payload)
    if not schema_result.valid:
        blockers.extend(f"schema:{item}" for item in schema_result.missing_fields)
        blockers.extend(f"schema:{item}" for item in schema_result.unknown_fields)
        blockers.extend(f"schema:{item}" for item in schema_result.type_errors)
    if schema_result.sensitive_fields_present:
        warnings.extend(f"sensitive_field_present:{item}" for item in schema_result.sensitive_fields_present)

    security_result = scan_payload(inputs.payload, allowed_hosts=inputs.allowed_hosts)
    if not security_result.valid:
        blockers.extend(f"security:{path}" for path in security_result.blocking_paths)
    elif security_result.findings:
        warnings.extend(f"security_warning:{item.path}:{item.kind.value}" for item in security_result.findings)

    lineage_result = inputs.lineage.validate()
    if not lineage_result.valid:
        blockers.extend(f"lineage:missing_parent:{item}" for item in lineage_result.missing_parents)
        blockers.extend(f"lineage:cycle:{'->'.join(item)}" for item in lineage_result.cycles)
        blockers.extend(f"lineage:manifest_mismatch:{item}" for item in lineage_result.manifest_mismatches)
    if lineage_result.duplicate_hashes:
        warnings.extend(f"lineage:duplicate_hash:{digest}" for digest, _ in lineage_result.duplicate_hashes)

    resume = inputs.checkpoint_ledger.plan_resume(
        inputs.required_stages,
        manifest_sha256=inputs.manifest_sha256,
        expected_inputs=dict(inputs.expected_inputs or {}),
    )
    if resume.decision is ResumeDecision.BLOCKED:
        blockers.extend(f"checkpoint:{item}" for item in resume.blockers)
    elif resume.decision is ResumeDecision.RETRY:
        warnings.append(f"checkpoint_retry:{resume.next_stage}:attempt_{resume.attempt}")

    admission = inputs.circuit_breaker.admit(now=inputs.now)
    unavailable = frozenset({inputs.resource_request.dependency}) if not admission.allowed else frozenset()
    if not admission.allowed:
        warnings.append(f"dependency:{admission.reason}")

    resource_plan = govern_resources(
        (inputs.resource_request,),
        policy=inputs.resource_policy,
        unavailable_dependencies=unavailable,
    )
    resource_decision = resource_plan.decisions[0]
    if resource_decision.decision is ResourceDecision.REJECT:
        blockers.extend(f"resource:{item}" for item in resource_decision.reasons)
    elif resource_decision.decision is ResourceDecision.DEFER:
        warnings.extend(f"resource:{item}" for item in resource_decision.reasons)

    if blockers:
        decision = ResilienceDecision.QUARANTINE
    elif not admission.allowed or resource_decision.decision is ResourceDecision.DEFER:
        decision = ResilienceDecision.HOLD
    else:
        decision = ResilienceDecision.READY

    return ResilienceResult(
        decision=decision,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
        schema_validation=schema_result,
        security_report=security_result,
        resource_plan=resource_plan,
        resume_decision=resume.decision,
        breaker_state=inputs.circuit_breaker.state,
    )
