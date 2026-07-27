from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .contracts import QueueItem, QueueStatus


class BufferState(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    EMERGENCY = "emergency"
    EMPTY = "empty"


@dataclass(frozen=True)
class BufferPolicy:
    target_ready: int = 30
    warning_ready: int = 14
    emergency_ready: int = 7

    def __post_init__(self) -> None:
        if not 0 < self.emergency_ready <= self.warning_ready <= self.target_ready:
            raise ValueError("thresholds must satisfy 0 < emergency <= warning <= target")


@dataclass(frozen=True)
class BufferReport:
    channel: str
    ready: int
    claimed: int
    posted: int
    rejected: int
    state: BufferState
    replenish_by: int
    estimated_posting_days: float


class BufferManager:
    def __init__(self, policy: BufferPolicy | None = None) -> None:
        self.policy = policy or BufferPolicy()

    def report(self, channel: str, items: Iterable[QueueItem], *, posts_per_day: float = 1.0) -> BufferReport:
        if posts_per_day <= 0:
            raise ValueError("posts_per_day must be positive")
        selected = [item for item in items if item.package.channel == channel]
        counts = {status: sum(item.status is status for item in selected) for status in QueueStatus}
        ready = counts[QueueStatus.READY]
        if ready == 0:
            state = BufferState.EMPTY
        elif ready <= self.policy.emergency_ready:
            state = BufferState.EMERGENCY
        elif ready <= self.policy.warning_ready:
            state = BufferState.WARNING
        else:
            state = BufferState.HEALTHY
        return BufferReport(
            channel=channel,
            ready=ready,
            claimed=counts[QueueStatus.CLAIMED],
            posted=counts[QueueStatus.POSTED],
            rejected=counts[QueueStatus.REJECTED],
            state=state,
            replenish_by=max(0, self.policy.target_ready - ready),
            estimated_posting_days=ready / posts_per_day,
        )
