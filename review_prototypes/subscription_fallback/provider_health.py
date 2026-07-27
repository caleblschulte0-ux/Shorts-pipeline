from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Iterable

from .contracts import ProviderKind


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utc_now()).isoformat()


@dataclass(frozen=True)
class ProviderHealthEvent:
    provider: ProviderKind
    ok: bool
    at: str
    reason: str = ""
    latency_ms: int = 0


@dataclass(frozen=True)
class ProviderHealth:
    provider: ProviderKind
    available: bool
    circuit_open: bool
    consecutive_failures: int
    last_success_at: str = ""
    last_failure_at: str = ""
    reason: str = ""


class ProviderHealthStore:
    """Append-only provider outcomes with a simple cooldown circuit breaker."""

    def __init__(self, path: Path, *, failure_threshold: int = 3, cooldown_minutes: int = 60) -> None:
        self.path = Path(path)
        self.failure_threshold = failure_threshold
        self.cooldown = timedelta(minutes=cooldown_minutes)

    def record(self, event: ProviderHealthEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")

    def events(self) -> tuple[ProviderHealthEvent, ...]:
        if not self.path.exists():
            return ()
        values: list[ProviderHealthEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            data["provider"] = ProviderKind(data["provider"])
            values.append(ProviderHealthEvent(**data))
        return tuple(values)

    def status(self, provider: ProviderKind, *, now: datetime | None = None) -> ProviderHealth:
        now = now or utc_now()
        events = [event for event in self.events() if event.provider is provider]
        failures = 0
        last_success = ""
        last_failure = ""
        reason = "no_history"
        for event in reversed(events):
            if event.ok:
                last_success = event.at
                break
        for event in reversed(events):
            if not event.ok:
                last_failure = event.at
                reason = event.reason or "provider_failure"
                break
        for event in reversed(events):
            if event.ok:
                break
            failures += 1
        circuit_open = False
        if failures >= self.failure_threshold and last_failure:
            try:
                circuit_open = datetime.fromisoformat(last_failure) + self.cooldown > now
            except ValueError:
                circuit_open = True
        return ProviderHealth(
            provider=provider,
            available=not circuit_open,
            circuit_open=circuit_open,
            consecutive_failures=failures,
            last_success_at=last_success,
            last_failure_at=last_failure,
            reason=reason if circuit_open else "available",
        )

    def snapshot(self, providers: Iterable[ProviderKind]) -> dict[ProviderKind, ProviderHealth]:
        return {provider: self.status(provider) for provider in providers}
