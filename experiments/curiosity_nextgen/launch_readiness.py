"""Dormant strict launch-readiness assessment separated from reference completeness."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LaunchEvidence:
    reference_coverage_percent: float
    verified_test_percent: float
    integrated_adapter_percent: float
    fifty_story_simulation_passed: bool
    heterogeneous_shadow_batches_passed: int
    autonomous_canary_videos_passed: int
    artifact_hash_binding_active: bool
    factual_evidence_active: bool
    independent_judges_active: bool
    durable_execution_state_active: bool
    provider_fallbacks_active: bool
    bounded_recovery_active: bool
    budget_controls_active: bool
    monitoring_active: bool
    rollback_tested: bool
    kill_switch_tested: bool
    expected_channel_guard_active: bool
    publishing_disabled_by_default: bool
    hard_blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("reference_coverage_percent", "verified_test_percent", "integrated_adapter_percent"):
            value = getattr(self, name)
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
        if self.heterogeneous_shadow_batches_passed < 0 or self.autonomous_canary_videos_passed < 0:
            raise ValueError("batch and canary counts cannot be negative")


@dataclass(frozen=True)
class LaunchPolicy:
    minimum_reference_coverage_percent: float = 100.0
    minimum_verified_test_percent: float = 100.0
    minimum_integrated_adapter_percent: float = 100.0
    minimum_shadow_batches: int = 3
    minimum_canary_videos: int = 3

    def __post_init__(self) -> None:
        for name in (
            "minimum_reference_coverage_percent",
            "minimum_verified_test_percent",
            "minimum_integrated_adapter_percent",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
        if self.minimum_shadow_batches < 1 or self.minimum_canary_videos < 1:
            raise ValueError("launch evidence counts must be positive")


@dataclass(frozen=True)
class LaunchAssessment:
    phase: str
    score_percent: float
    blockers: tuple[str, ...]
    ready: bool


def assess_launch_readiness(evidence: LaunchEvidence, policy: LaunchPolicy = LaunchPolicy()) -> LaunchAssessment:
    blockers: list[str] = list(evidence.hard_blockers)
    checks = {
        "reference_coverage_incomplete": evidence.reference_coverage_percent >= policy.minimum_reference_coverage_percent,
        "tests_not_fully_verified": evidence.verified_test_percent >= policy.minimum_verified_test_percent,
        "adapters_not_fully_integrated": evidence.integrated_adapter_percent >= policy.minimum_integrated_adapter_percent,
        "fifty_story_simulation_missing": evidence.fifty_story_simulation_passed,
        "shadow_batches_incomplete": evidence.heterogeneous_shadow_batches_passed >= policy.minimum_shadow_batches,
        "canary_count_incomplete": evidence.autonomous_canary_videos_passed >= policy.minimum_canary_videos,
        "artifact_hash_binding_inactive": evidence.artifact_hash_binding_active,
        "factual_evidence_inactive": evidence.factual_evidence_active,
        "independent_judges_inactive": evidence.independent_judges_active,
        "durable_execution_state_inactive": evidence.durable_execution_state_active,
        "provider_fallbacks_inactive": evidence.provider_fallbacks_active,
        "bounded_recovery_inactive": evidence.bounded_recovery_active,
        "budget_controls_inactive": evidence.budget_controls_active,
        "monitoring_inactive": evidence.monitoring_active,
        "rollback_untested": evidence.rollback_tested,
        "kill_switch_untested": evidence.kill_switch_tested,
        "expected_channel_guard_inactive": evidence.expected_channel_guard_active,
        "publishing_not_disabled_by_default": evidence.publishing_disabled_by_default,
    }
    blockers.extend(name for name, passed in checks.items() if not passed)

    completed = sum(checks.values())
    score = round(completed / len(checks) * 100.0, 2)
    unique_blockers = tuple(sorted(set(blockers)))

    if evidence.reference_coverage_percent < policy.minimum_reference_coverage_percent:
        phase = "reference_incomplete"
    elif evidence.verified_test_percent < policy.minimum_verified_test_percent:
        phase = "reference_complete_execution_unverified"
    elif evidence.integrated_adapter_percent < policy.minimum_integrated_adapter_percent:
        phase = "execution_verified_integration_incomplete"
    elif not evidence.fifty_story_simulation_passed:
        phase = "integration_complete_simulation_incomplete"
    elif evidence.heterogeneous_shadow_batches_passed < policy.minimum_shadow_batches:
        phase = "simulation_complete_shadow_incomplete"
    elif evidence.autonomous_canary_videos_passed < policy.minimum_canary_videos:
        phase = "shadow_complete_canary_incomplete"
    elif unique_blockers:
        phase = "canary_complete_launch_blocked"
    else:
        phase = "launch_ready"

    return LaunchAssessment(phase=phase, score_percent=score, blockers=unique_blockers, ready=not unique_blockers)


def dormant_reference_assessment(reference_coverage_percent: float) -> LaunchAssessment:
    blockers = () if reference_coverage_percent == 100.0 else ("reference_coverage_incomplete",)
    return LaunchAssessment(
        phase="dormant_reference_complete" if not blockers else "reference_incomplete",
        score_percent=reference_coverage_percent,
        blockers=blockers,
        ready=not blockers,
    )
