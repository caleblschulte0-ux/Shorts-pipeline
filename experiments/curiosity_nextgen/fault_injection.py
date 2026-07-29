"""Fail-safe fault-injection campaign and control-coverage prototype."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class FaultKind(str, Enum):
    STALE_HASH = "stale_hash"
    DEPENDENCY_TIMEOUT = "dependency_timeout"
    PARTIAL_ARTIFACT = "partial_artifact"
    JUDGE_DISAGREEMENT = "judge_disagreement"
    DUPLICATE_PUBLISH = "duplicate_publish"
    BUDGET_EXHAUSTION = "budget_exhaustion"
    CORRUPTED_CHECKPOINT = "corrupted_checkpoint"
    SECRET_LEAK = "secret_leak"
    SCHEMA_BREAK = "schema_break"
    NONDETERMINISTIC_REPLAY = "nondeterministic_replay"


class ExpectedDecision(str, Enum):
    HOLD = "hold"
    QUARANTINE = "quarantine"
    REJECT = "reject"
    DEFER = "defer"
    FREEZE = "freeze"


@dataclass(frozen=True)
class FaultScenario:
    scenario_id: str
    fault: FaultKind
    target_control: str
    expected_decision: ExpectedDecision
    required_reason: str
    critical: bool = True

    def __post_init__(self) -> None:
        if not self.scenario_id.strip() or not self.target_control.strip() or not self.required_reason.strip():
            raise ValueError("scenario fields must be nonempty")


@dataclass(frozen=True)
class FaultObservation:
    scenario_id: str
    observed_decision: str
    observed_reasons: tuple[str, ...]
    publishing_frozen: bool


@dataclass(frozen=True)
class FaultEvaluation:
    scenario_id: str
    passed: bool
    failures: tuple[str, ...]


@dataclass(frozen=True)
class CampaignReport:
    valid: bool
    scenario_count: int
    critical_count: int
    covered_faults: tuple[FaultKind, ...]
    missing_critical_faults: tuple[FaultKind, ...]
    duplicate_scenario_ids: tuple[str, ...]
    unsafe_expectations: tuple[str, ...]


CRITICAL_FAULTS = frozenset({
    FaultKind.STALE_HASH,
    FaultKind.DEPENDENCY_TIMEOUT,
    FaultKind.PARTIAL_ARTIFACT,
    FaultKind.DUPLICATE_PUBLISH,
    FaultKind.SECRET_LEAK,
    FaultKind.SCHEMA_BREAK,
})


def default_fault_campaign() -> tuple[FaultScenario, ...]:
    return (
        FaultScenario("stale-hash", FaultKind.STALE_HASH, "lineage", ExpectedDecision.QUARANTINE, "artifact_mismatch"),
        FaultScenario("dependency-timeout", FaultKind.DEPENDENCY_TIMEOUT, "circuit_breaker", ExpectedDecision.DEFER, "dependency_circuit_open"),
        FaultScenario("partial-artifact", FaultKind.PARTIAL_ARTIFACT, "package_readiness", ExpectedDecision.QUARANTINE, "missing_gate"),
        FaultScenario("judge-split", FaultKind.JUDGE_DISAGREEMENT, "judge_contract", ExpectedDecision.QUARANTINE, "judge disagreement"),
        FaultScenario("duplicate-publish", FaultKind.DUPLICATE_PUBLISH, "approval_token", ExpectedDecision.FREEZE, "approval_already_consumed"),
        FaultScenario("budget-exhaustion", FaultKind.BUDGET_EXHAUSTION, "resource_governor", ExpectedDecision.DEFER, "time_budget", critical=False),
        FaultScenario("corrupt-checkpoint", FaultKind.CORRUPTED_CHECKPOINT, "checkpoint_store", ExpectedDecision.HOLD, "input_digest_changed", critical=False),
        FaultScenario("secret-leak", FaultKind.SECRET_LEAK, "security_scanner", ExpectedDecision.REJECT, "credential", critical=True),
        FaultScenario("schema-break", FaultKind.SCHEMA_BREAK, "schema_registry", ExpectedDecision.HOLD, "new_required_field_without_default"),
        FaultScenario("replay-drift", FaultKind.NONDETERMINISTIC_REPLAY, "replay_engine", ExpectedDecision.HOLD, "output_mismatch", critical=False),
    )


def validate_campaign(scenarios: Iterable[FaultScenario]) -> CampaignReport:
    items = tuple(scenarios)
    counts: dict[str, int] = {}
    unsafe: list[str] = []
    for scenario in items:
        counts[scenario.scenario_id] = counts.get(scenario.scenario_id, 0) + 1
        # Safe expectations for a CRITICAL fault are the non-advancing
        # decisions. DEFER belongs here: it retries later without publishing
        # or advancing anything — the fail-closed sibling of HOLD (a
        # dependency timeout that must NOT quarantine, or transient outages
        # would kill stories the breaker exists to let recover).
        if scenario.critical and scenario.expected_decision not in {
            ExpectedDecision.HOLD,
            ExpectedDecision.DEFER,
            ExpectedDecision.QUARANTINE,
            ExpectedDecision.REJECT,
            ExpectedDecision.FREEZE,
        }:
            unsafe.append(scenario.scenario_id)
    duplicates = tuple(sorted(key for key, count in counts.items() if count > 1))
    covered = frozenset(scenario.fault for scenario in items)
    missing = tuple(sorted(CRITICAL_FAULTS - covered, key=lambda item: item.value))
    return CampaignReport(
        valid=not duplicates and not missing and not unsafe,
        scenario_count=len(items),
        critical_count=sum(scenario.critical for scenario in items),
        covered_faults=tuple(sorted(covered, key=lambda item: item.value)),
        missing_critical_faults=missing,
        duplicate_scenario_ids=duplicates,
        unsafe_expectations=tuple(sorted(unsafe)),
    )


def evaluate_observation(scenario: FaultScenario, observation: FaultObservation) -> FaultEvaluation:
    failures: list[str] = []
    if observation.scenario_id != scenario.scenario_id:
        failures.append("scenario_id_mismatch")
    if observation.observed_decision != scenario.expected_decision.value:
        failures.append(
            f"decision_mismatch:{observation.observed_decision}!={scenario.expected_decision.value}"
        )
    joined = " ".join(observation.observed_reasons).lower()
    if scenario.required_reason.lower() not in joined:
        failures.append("required_reason_missing")
    if scenario.expected_decision is ExpectedDecision.FREEZE and not observation.publishing_frozen:
        failures.append("publishing_not_frozen")
    return FaultEvaluation(scenario.scenario_id, not failures, tuple(failures))


def summarize_fault_results(
    scenarios: Iterable[FaultScenario],
    observations: Iterable[FaultObservation],
) -> Mapping[str, FaultEvaluation]:
    scenario_map = {scenario.scenario_id: scenario for scenario in scenarios}
    results: dict[str, FaultEvaluation] = {}
    for observation in observations:
        scenario = scenario_map.get(observation.scenario_id)
        if scenario is None:
            results[observation.scenario_id] = FaultEvaluation(
                observation.scenario_id,
                False,
                ("unknown_scenario",),
            )
        else:
            results[observation.scenario_id] = evaluate_observation(scenario, observation)
    for scenario_id in scenario_map:
        if scenario_id not in results:
            results[scenario_id] = FaultEvaluation(scenario_id, False, ("missing_observation",))
    return dict(sorted(results.items()))
