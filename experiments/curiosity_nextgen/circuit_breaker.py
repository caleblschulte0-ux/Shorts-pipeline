"""Dependency circuit-breaker and recovery-probe prototype."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True)
class BreakerPolicy:
    failure_threshold: int = 3
    recovery_timeout_seconds: int = 300
    half_open_max_probes: int = 1
    success_threshold_to_close: int = 1

    def __post_init__(self) -> None:
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if self.recovery_timeout_seconds < 1:
            raise ValueError("recovery_timeout_seconds must be >= 1")
        if self.half_open_max_probes < 1 or self.success_threshold_to_close < 1:
            raise ValueError("probe and success thresholds must be >= 1")


@dataclass(frozen=True)
class BreakerSnapshot:
    dependency: str
    state: BreakerState
    consecutive_failures: int
    consecutive_successes: int
    opened_at: int | None
    probes_in_flight: int
    total_failures: int
    total_successes: int


@dataclass(frozen=True)
class Admission:
    allowed: bool
    state: BreakerState
    reason: str


class CircuitBreaker:
    def __init__(self, dependency: str, *, policy: BreakerPolicy | None = None) -> None:
        if not dependency.strip():
            raise ValueError("dependency must be nonempty")
        self.dependency = dependency
        self.policy = policy or BreakerPolicy()
        self.state = BreakerState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.opened_at: int | None = None
        self.probes_in_flight = 0
        self.total_failures = 0
        self.total_successes = 0

    def snapshot(self) -> BreakerSnapshot:
        return BreakerSnapshot(
            self.dependency,
            self.state,
            self.consecutive_failures,
            self.consecutive_successes,
            self.opened_at,
            self.probes_in_flight,
            self.total_failures,
            self.total_successes,
        )

    def _refresh_state(self, now: int) -> None:
        if self.state is BreakerState.OPEN and self.opened_at is not None:
            if now - self.opened_at >= self.policy.recovery_timeout_seconds:
                self.state = BreakerState.HALF_OPEN
                self.consecutive_successes = 0
                self.probes_in_flight = 0

    def admit(self, *, now: int) -> Admission:
        self._refresh_state(now)
        if self.state is BreakerState.OPEN:
            return Admission(False, self.state, "dependency_circuit_open")
        if self.state is BreakerState.HALF_OPEN:
            if self.probes_in_flight >= self.policy.half_open_max_probes:
                return Admission(False, self.state, "half_open_probe_budget_exhausted")
            self.probes_in_flight += 1
            return Admission(True, self.state, "half_open_probe")
        return Admission(True, self.state, "circuit_closed")

    def record_success(self, *, now: int) -> BreakerSnapshot:
        self._refresh_state(now)
        self.total_successes += 1
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        if self.state is BreakerState.HALF_OPEN:
            self.probes_in_flight = max(0, self.probes_in_flight - 1)
            if self.consecutive_successes >= self.policy.success_threshold_to_close:
                self.state = BreakerState.CLOSED
                self.opened_at = None
                self.probes_in_flight = 0
        return self.snapshot()

    def record_failure(self, *, now: int) -> BreakerSnapshot:
        self._refresh_state(now)
        self.total_failures += 1
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        if self.state is BreakerState.HALF_OPEN:
            self.probes_in_flight = max(0, self.probes_in_flight - 1)
            self.state = BreakerState.OPEN
            self.opened_at = now
        elif self.consecutive_failures >= self.policy.failure_threshold:
            self.state = BreakerState.OPEN
            self.opened_at = now
        return self.snapshot()

    def force_open(self, *, now: int) -> BreakerSnapshot:
        self.state = BreakerState.OPEN
        self.opened_at = now
        self.probes_in_flight = 0
        self.consecutive_successes = 0
        return self.snapshot()

    def force_close(self) -> BreakerSnapshot:
        self.state = BreakerState.CLOSED
        self.opened_at = None
        self.probes_in_flight = 0
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        return self.snapshot()
