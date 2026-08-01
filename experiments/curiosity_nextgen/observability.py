"""Append-only pipeline event ledger and health summaries.

This prototype gives every hold, quarantine, repair, and release transition a
machine-readable explanation.  It is not connected to production logging.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Iterable, Mapping


class EventSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RunOutcome(str, Enum):
    PASS = "pass"
    HOLD = "hold"
    QUARANTINE = "quarantine"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PipelineEvent:
    event_id: str
    run_id: str
    slug: str
    stage: str
    event_type: str
    severity: EventSeverity
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float | None = None
    reason: str | None = None
    manifest_sha256: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.run_id.strip() or not self.stage.strip() or not self.event_type.strip():
            raise ValueError("event_id, run_id, stage, and event_type must be nonempty")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative")
        datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


@dataclass(frozen=True)
class RunHealth:
    run_id: str
    slug: str
    outcome: RunOutcome
    total_duration_seconds: float
    maximum_severity: EventSeverity
    reasons: tuple[str, ...]
    stages_seen: tuple[str, ...]
    event_count: int


@dataclass(frozen=True)
class HealthSnapshot:
    run_count: int
    pass_rate: float
    hold_rate: float
    quarantine_rate: float
    failure_rate: float
    average_run_seconds: float
    p95_run_seconds: float
    top_reasons: tuple[tuple[str, int], ...]
    stage_average_seconds: tuple[tuple[str, float], ...]
    critical_event_count: int
    duplicate_event_count: int


_SEVERITY_ORDER = {
    EventSeverity.DEBUG: 0,
    EventSeverity.INFO: 1,
    EventSeverity.WARNING: 2,
    EventSeverity.ERROR: 3,
    EventSeverity.CRITICAL: 4,
}


class EventLedger:
    def __init__(self, events: Iterable[PipelineEvent] = ()) -> None:
        self._events: list[PipelineEvent] = []
        self._ids: set[str] = set()
        self._duplicate_attempts = 0
        for event in events:
            self.append(event)

    def append(self, event: PipelineEvent) -> None:
        if event.event_id in self._ids:
            self._duplicate_attempts += 1
            raise ValueError(f"duplicate event_id {event.event_id!r}")
        self._events.append(event)
        self._ids.add(event.event_id)

    @property
    def events(self) -> tuple[PipelineEvent, ...]:
        return tuple(self._events)

    @property
    def duplicate_attempts(self) -> int:
        return self._duplicate_attempts

    def by_run(self, run_id: str) -> tuple[PipelineEvent, ...]:
        return tuple(sorted(
            (event for event in self._events if event.run_id == run_id),
            key=lambda event: (event.timestamp, event.event_id),
        ))

    def to_json_lines(self) -> str:
        rows: list[str] = []
        for event in self._events:
            raw = asdict(event)
            raw["severity"] = event.severity.value
            rows.append(json.dumps(raw, sort_keys=True, separators=(",", ":")))
        return "\n".join(rows) + ("\n" if rows else "")


def _infer_outcome(events: Iterable[PipelineEvent]) -> RunOutcome:
    event_types = {event.event_type for event in events}
    if "run_failed" in event_types or "upload_failed" in event_types:
        return RunOutcome.FAILURE
    if "package_quarantined" in event_types or "run_quarantined" in event_types:
        return RunOutcome.QUARANTINE
    if "package_held" in event_types or "run_held" in event_types:
        return RunOutcome.HOLD
    if "run_passed" in event_types or "upload_verified" in event_types:
        return RunOutcome.PASS
    return RunOutcome.UNKNOWN


def summarize_run(events: Iterable[PipelineEvent]) -> RunHealth:
    items = tuple(events)
    if not items:
        raise ValueError("cannot summarize an empty run")
    run_ids = {event.run_id for event in items}
    if len(run_ids) != 1:
        raise ValueError("run summary requires exactly one run_id")
    slugs = {event.slug for event in items}
    slug = sorted(slugs)[0] if slugs else ""
    duration = sum(event.duration_seconds or 0.0 for event in items)
    maximum = max((event.severity for event in items), key=lambda value: _SEVERITY_ORDER[value])
    reasons = tuple(sorted({event.reason for event in items if event.reason}))
    stages = tuple(sorted({event.stage for event in items}))
    return RunHealth(
        run_id=next(iter(run_ids)),
        slug=slug,
        outcome=_infer_outcome(items),
        total_duration_seconds=round(duration, 2),
        maximum_severity=maximum,
        reasons=reasons,
        stages_seen=stages,
        event_count=len(items),
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def build_health_snapshot(ledger: EventLedger) -> HealthSnapshot:
    run_ids = sorted({event.run_id for event in ledger.events})
    runs = [summarize_run(ledger.by_run(run_id)) for run_id in run_ids]
    total = len(runs)
    outcome_counts = {outcome: sum(run.outcome is outcome for run in runs) for outcome in RunOutcome}
    durations = [run.total_duration_seconds for run in runs]

    reason_counts: dict[str, int] = {}
    stage_totals: dict[str, list[float]] = {}
    for event in ledger.events:
        if event.reason:
            reason_counts[event.reason] = reason_counts.get(event.reason, 0) + 1
        if event.duration_seconds is not None:
            stage_totals.setdefault(event.stage, []).append(event.duration_seconds)

    rate = lambda outcome: 0.0 if total == 0 else outcome_counts[outcome] / total * 100
    stage_averages = tuple(sorted(
        (stage, round(sum(values) / len(values), 2))
        for stage, values in stage_totals.items()
        if values
    ))
    top_reasons = tuple(sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:10])
    critical_count = sum(event.severity is EventSeverity.CRITICAL for event in ledger.events)

    return HealthSnapshot(
        run_count=total,
        pass_rate=round(rate(RunOutcome.PASS), 1),
        hold_rate=round(rate(RunOutcome.HOLD), 1),
        quarantine_rate=round(rate(RunOutcome.QUARANTINE), 1),
        failure_rate=round(rate(RunOutcome.FAILURE), 1),
        average_run_seconds=round(sum(durations) / total, 2) if total else 0.0,
        p95_run_seconds=round(_percentile(durations, 0.95), 2),
        top_reasons=top_reasons,
        stage_average_seconds=stage_averages,
        critical_event_count=critical_count,
        duplicate_event_count=ledger.duplicate_attempts,
    )
