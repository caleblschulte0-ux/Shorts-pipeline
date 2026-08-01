"""Dormant append-only execution ledger with leases and idempotent outcomes."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Iterable


@dataclass(frozen=True)
class LedgerEvent:
    sequence: int
    event_type: str
    story_id: str
    stage: str | None
    idempotency_key: str
    payload: dict[str, object]
    created_at: str
    previous_hash: str
    event_hash: str


@dataclass(frozen=True)
class Lease:
    story_id: str
    stage: str
    worker_id: str
    lease_token: str
    expires_at: str

    def expired(self, now: datetime) -> bool:
        return datetime.fromisoformat(self.expires_at) <= now


@dataclass(frozen=True)
class MaterializedStoryState:
    story_id: str
    current_stage: str | None
    status: str
    attempts: dict[str, int]
    spend: float
    artifact_hashes: tuple[str, ...]
    last_sequence: int


class ExecutionLedger:
    def __init__(self) -> None:
        self._events: list[LedgerEvent] = []
        self._idempotency_keys: set[str] = set()
        self._leases: dict[tuple[str, str], Lease] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @property
    def events(self) -> tuple[LedgerEvent, ...]:
        return tuple(self._events)

    @property
    def leases(self) -> tuple[Lease, ...]:
        return tuple(sorted(self._leases.values(), key=lambda item: (item.story_id, item.stage)))

    def append(
        self,
        event_type: str,
        story_id: str,
        *,
        stage: str | None,
        idempotency_key: str,
        payload: dict[str, object] | None = None,
        created_at: datetime | None = None,
    ) -> LedgerEvent:
        if not event_type or not story_id or not idempotency_key:
            raise ValueError("event_type, story_id, and idempotency_key are required")
        if idempotency_key in self._idempotency_keys:
            raise ValueError("duplicate idempotency key")
        timestamp = (created_at or self._now()).astimezone(timezone.utc).isoformat()
        sequence = len(self._events) + 1
        previous_hash = self._events[-1].event_hash if self._events else "0" * 64
        body = {
            "sequence": sequence,
            "event_type": event_type,
            "story_id": story_id,
            "stage": stage,
            "idempotency_key": idempotency_key,
            "payload": payload or {},
            "created_at": timestamp,
            "previous_hash": previous_hash,
        }
        event_hash = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        event = LedgerEvent(event_hash=event_hash, **body)
        self._events.append(event)
        self._idempotency_keys.add(idempotency_key)
        return event

    def claim(
        self,
        story_id: str,
        stage: str,
        worker_id: str,
        *,
        lease_seconds: int = 900,
        now: datetime | None = None,
    ) -> Lease:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        current = (now or self._now()).astimezone(timezone.utc)
        key = (story_id, stage)
        existing = self._leases.get(key)
        if existing and not existing.expired(current):
            raise ValueError("stage already leased")
        token_material = f"{story_id}|{stage}|{worker_id}|{current.isoformat()}|{len(self._events)}"
        lease = Lease(
            story_id=story_id,
            stage=stage,
            worker_id=worker_id,
            lease_token=sha256(token_material.encode()).hexdigest(),
            expires_at=(current + timedelta(seconds=lease_seconds)).isoformat(),
        )
        self._leases[key] = lease
        return lease

    def release(self, lease_token: str) -> None:
        for key, lease in tuple(self._leases.items()):
            if lease.lease_token == lease_token:
                del self._leases[key]
                return
        raise KeyError("unknown lease token")

    def expire_stale_leases(self, *, now: datetime | None = None) -> tuple[Lease, ...]:
        current = (now or self._now()).astimezone(timezone.utc)
        expired: list[Lease] = []
        for key, lease in tuple(self._leases.items()):
            if lease.expired(current):
                expired.append(lease)
                del self._leases[key]
        return tuple(sorted(expired, key=lambda item: (item.story_id, item.stage)))

    def validate_chain(self) -> tuple[str, ...]:
        blockers: list[str] = []
        previous_hash = "0" * 64
        seen_keys: set[str] = set()
        for expected_sequence, event in enumerate(self._events, start=1):
            if event.sequence != expected_sequence:
                blockers.append(f"sequence_gap:{expected_sequence}")
            if event.previous_hash != previous_hash:
                blockers.append(f"previous_hash_mismatch:{event.sequence}")
            if event.idempotency_key in seen_keys:
                blockers.append(f"duplicate_idempotency_key:{event.idempotency_key}")
            body = {
                "sequence": event.sequence,
                "event_type": event.event_type,
                "story_id": event.story_id,
                "stage": event.stage,
                "idempotency_key": event.idempotency_key,
                "payload": event.payload,
                "created_at": event.created_at,
                "previous_hash": event.previous_hash,
            }
            calculated = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if calculated != event.event_hash:
                blockers.append(f"event_hash_mismatch:{event.sequence}")
            seen_keys.add(event.idempotency_key)
            previous_hash = event.event_hash
        return tuple(blockers)

    def materialize(self, story_id: str) -> MaterializedStoryState:
        current_stage: str | None = None
        status = "unknown"
        attempts: dict[str, int] = {}
        spend = 0.0
        artifact_hashes: list[str] = []
        last_sequence = 0
        for event in self._events:
            if event.story_id != story_id:
                continue
            last_sequence = event.sequence
            if event.stage:
                current_stage = event.stage
            if event.event_type == "registered":
                status = "pending"
            elif event.event_type == "claimed":
                status = "running"
                if event.stage:
                    attempts[event.stage] = attempts.get(event.stage, 0) + 1
            elif event.event_type in {"advanced", "rewound", "held", "quarantined", "completed"}:
                status = event.event_type
            spend += float(event.payload.get("cost", 0.0))
            hashes = event.payload.get("artifact_hashes", ())
            if isinstance(hashes, (list, tuple)):
                artifact_hashes.extend(str(value) for value in hashes)
        return MaterializedStoryState(
            story_id=story_id,
            current_stage=current_stage,
            status=status,
            attempts=attempts,
            spend=round(spend, 4),
            artifact_hashes=tuple(sorted(set(artifact_hashes))),
            last_sequence=last_sequence,
        )


def replay_events(events: Iterable[LedgerEvent]) -> ExecutionLedger:
    ledger = ExecutionLedger()
    for event in events:
        ledger.append(
            event.event_type,
            event.story_id,
            stage=event.stage,
            idempotency_key=event.idempotency_key,
            payload=dict(event.payload),
            created_at=datetime.fromisoformat(event.created_at),
        )
    return ledger
