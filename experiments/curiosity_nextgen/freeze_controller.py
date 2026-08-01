"""Fail-closed release state machine for the dormant next-generation lab.

The controller never uploads anything.  It models when publishing may be armed,
which signals immediately freeze it, and the mandatory return to frozen state
after one canary attempt.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .approval_token import ApprovalVerification


class ReleaseState(str, Enum):
    FROZEN = "frozen"
    HOLD = "hold"
    ARMED = "armed"
    UPLOADING = "uploading"


@dataclass(frozen=True)
class ReleaseSignals:
    package_ready: bool
    wrong_channel: bool = False
    artifact_mismatch: bool = False
    facts_failed: bool = False
    visual_failed: bool = False
    verdict_invalid: bool = False
    upload_verification_failed: bool = False
    provider_failure_ratio: float = 0.0
    consecutive_quarantines: int = 0
    render_over_budget: bool = False
    duplicate_upload_detected: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.provider_failure_ratio <= 1.0:
            raise ValueError("provider_failure_ratio must be between 0 and 1")
        if self.consecutive_quarantines < 0:
            raise ValueError("consecutive_quarantines cannot be negative")


@dataclass(frozen=True)
class FreezePolicy:
    maximum_provider_failure_ratio: float = 0.35
    maximum_consecutive_quarantines: int = 1
    freeze_on_render_budget_failure: bool = True


@dataclass(frozen=True)
class ReleaseTransition:
    previous_state: ReleaseState
    state: ReleaseState
    reasons: tuple[str, ...]
    automatic: bool


class ReleaseController:
    def __init__(self, state: ReleaseState = ReleaseState.FROZEN) -> None:
        self._state = state
        self._upload_attempts = 0

    @property
    def state(self) -> ReleaseState:
        return self._state

    @property
    def upload_attempts(self) -> int:
        return self._upload_attempts

    @staticmethod
    def freeze_reasons(signals: ReleaseSignals, policy: FreezePolicy) -> tuple[str, ...]:
        reasons: list[str] = []
        if signals.wrong_channel:
            reasons.append("wrong_channel")
        if signals.artifact_mismatch:
            reasons.append("artifact_mismatch")
        if signals.facts_failed:
            reasons.append("facts_failed")
        if signals.visual_failed:
            reasons.append("visual_failed")
        if signals.verdict_invalid:
            reasons.append("verdict_invalid")
        if signals.upload_verification_failed:
            reasons.append("upload_verification_failed")
        if signals.provider_failure_ratio > policy.maximum_provider_failure_ratio:
            reasons.append("provider_failure_ratio_exceeded")
        if signals.consecutive_quarantines > policy.maximum_consecutive_quarantines:
            reasons.append("consecutive_quarantines_exceeded")
        if policy.freeze_on_render_budget_failure and signals.render_over_budget:
            reasons.append("render_budget_failed")
        if signals.duplicate_upload_detected:
            reasons.append("duplicate_upload_detected")
        return tuple(sorted(reasons))

    def evaluate(
        self,
        signals: ReleaseSignals,
        *,
        policy: FreezePolicy | None = None,
    ) -> ReleaseTransition:
        policy = policy or FreezePolicy()
        previous = self._state
        reasons = self.freeze_reasons(signals, policy)
        if reasons:
            self._state = ReleaseState.FROZEN
            return ReleaseTransition(previous, self._state, reasons, True)
        if not signals.package_ready:
            self._state = ReleaseState.HOLD
            return ReleaseTransition(previous, self._state, ("package_not_ready",), True)
        if self._state is ReleaseState.FROZEN:
            return ReleaseTransition(previous, self._state, ("manual_approval_required",), False)
        self._state = ReleaseState.HOLD
        return ReleaseTransition(previous, self._state, ("package_ready_waiting_for_approval",), True)

    def arm(
        self,
        approval: ApprovalVerification,
        signals: ReleaseSignals,
        *,
        policy: FreezePolicy | None = None,
    ) -> ReleaseTransition:
        policy = policy or FreezePolicy()
        previous = self._state
        reasons = list(self.freeze_reasons(signals, policy))
        if not signals.package_ready:
            reasons.append("package_not_ready")
        if not approval.valid:
            reasons.extend(f"approval:{reason}" for reason in approval.reasons)
        if approval.claims is None:
            reasons.append("approval_missing_claims")
        if self._upload_attempts >= 1:
            reasons.append("canary_upload_limit_consumed")
        if reasons:
            self._state = ReleaseState.FROZEN
            return ReleaseTransition(previous, self._state, tuple(sorted(set(reasons))), True)
        self._state = ReleaseState.ARMED
        return ReleaseTransition(previous, self._state, ("exact_artifact_approved",), False)

    def begin_upload(self) -> ReleaseTransition:
        previous = self._state
        if self._state is not ReleaseState.ARMED:
            self._state = ReleaseState.FROZEN
            return ReleaseTransition(previous, self._state, ("upload_attempt_while_not_armed",), True)
        if self._upload_attempts >= 1:
            self._state = ReleaseState.FROZEN
            return ReleaseTransition(previous, self._state, ("canary_upload_limit_consumed",), True)
        self._upload_attempts += 1
        self._state = ReleaseState.UPLOADING
        return ReleaseTransition(previous, self._state, ("single_canary_upload_started",), False)

    def finish_upload(self, *, verified: bool) -> ReleaseTransition:
        previous = self._state
        self._state = ReleaseState.FROZEN
        reason = "upload_verified_and_refrozen" if verified else "upload_failed_or_unverified"
        return ReleaseTransition(previous, self._state, (reason,), True)

    def reset_canary_budget(self) -> None:
        if self._state is not ReleaseState.FROZEN:
            raise ValueError("canary budget may be reset only while frozen")
        self._upload_attempts = 0
