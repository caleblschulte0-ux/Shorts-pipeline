"""Append-only institutional memory for the isolated prototype.

The file-backed ledger rewrites a complete validated snapshot through an atomic replace.
That is intentionally conservative for a reference implementation: a partial append can
never leave a valid-looking truncated event. It is single-writer by contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import tempfile
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

from .contracts import ContractError, canonical_json, stable_hash, utc_now_iso


GENESIS_HASH = "0" * 64
LEDGER_VERSION = "professional-media-os-ledger/v1"


class LedgerIntegrityError(RuntimeError):
    """Raised when event sequence or hash-chain integrity fails."""


@dataclass(frozen=True)
class LedgerEvent:
    sequence: int
    event_id: str
    event_type: str
    occurred_at: str
    payload: Mapping[str, Any]
    previous_hash: str
    event_hash: str
    ledger_version: str = LEDGER_VERSION

    def unsigned(self) -> Mapping[str, Any]:
        return {
            "sequence": self.sequence,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "payload": self.payload,
            "previous_hash": self.previous_hash,
            "ledger_version": self.ledger_version,
        }

    def as_dict(self) -> Mapping[str, Any]:
        value = dict(self.unsigned())
        value["event_hash"] = self.event_hash
        return value

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        event_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        previous_hash: str,
        occurred_at: Optional[str] = None,
    ) -> "LedgerEvent":
        if sequence < 1:
            raise ContractError("ledger sequence must begin at 1")
        if len(previous_hash) != 64:
            raise ContractError("previous_hash must be a SHA-256 hex digest")
        unsigned = {
            "sequence": sequence,
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": occurred_at or utc_now_iso(),
            "payload": dict(payload),
            "previous_hash": previous_hash,
            "ledger_version": LEDGER_VERSION,
        }
        return cls(event_hash=stable_hash(unsigned), **unsigned)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LedgerEvent":
        try:
            return cls(
                sequence=int(value["sequence"]),
                event_id=str(value["event_id"]),
                event_type=str(value["event_type"]),
                occurred_at=str(value["occurred_at"]),
                payload=dict(value["payload"]),
                previous_hash=str(value["previous_hash"]),
                event_hash=str(value["event_hash"]),
                ledger_version=str(value["ledger_version"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise LedgerIntegrityError(f"invalid ledger event shape: {exc}") from exc


class MemoryLedger:
    """In-memory ledger used by tests, demos, and shadow evaluation."""

    def __init__(self, events: Optional[Sequence[LedgerEvent]] = None) -> None:
        self._events: List[LedgerEvent] = list(events or ())
        verify_events(self._events)

    def append(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        event_id: Optional[str] = None,
        occurred_at: Optional[str] = None,
    ) -> LedgerEvent:
        previous_hash = self._events[-1].event_hash if self._events else GENESIS_HASH
        sequence = len(self._events) + 1
        deterministic_id = event_id or f"evt-{sequence:08d}-{stable_hash(payload)[:12]}"
        event = LedgerEvent.create(
            sequence=sequence,
            event_id=deterministic_id,
            event_type=event_type,
            payload=payload,
            previous_hash=previous_hash,
            occurred_at=occurred_at,
        )
        self._events.append(event)
        return event

    def events(self, event_type: Optional[str] = None) -> Tuple[LedgerEvent, ...]:
        if event_type is None:
            return tuple(self._events)
        return tuple(event for event in self._events if event.event_type == event_type)

    def verify(self) -> None:
        verify_events(self._events)

    @property
    def head_hash(self) -> str:
        return self._events[-1].event_hash if self._events else GENESIS_HASH


class FileLedger:
    """Single-writer, atomic-snapshot JSONL ledger.

    The caller must provide an explicit prototype path. No default production-looking path
    exists. The file is validated before and after every append.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.name.endswith(".jsonl"):
            raise ContractError("file ledger path must end with .jsonl")

    def load(self) -> MemoryLedger:
        if not self.path.exists():
            return MemoryLedger()
        events: List[LedgerEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise LedgerIntegrityError(
                        f"invalid JSON at {self.path}:{line_number}: {exc}"
                    ) from exc
                events.append(LedgerEvent.from_dict(value))
        return MemoryLedger(events)

    def append(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        event_id: Optional[str] = None,
        occurred_at: Optional[str] = None,
    ) -> LedgerEvent:
        ledger = self.load()
        event = ledger.append(
            event_type,
            payload,
            event_id=event_id,
            occurred_at=occurred_at,
        )
        self._atomic_write(ledger.events())
        self.load().verify()
        return event

    def verify(self) -> Tuple[int, str]:
        ledger = self.load()
        ledger.verify()
        return len(ledger.events()), ledger.head_hash

    def _atomic_write(self, events: Sequence[LedgerEvent]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(self.path.parent),
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_name = handle.name
                for event in events:
                    handle.write(canonical_json(event.as_dict()))
                    handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            temporary_name = None
        finally:
            if temporary_name is not None:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass


def verify_events(events: Sequence[LedgerEvent]) -> None:
    previous_hash = GENESIS_HASH
    seen_ids = set()
    for expected_sequence, event in enumerate(events, start=1):
        if event.sequence != expected_sequence:
            raise LedgerIntegrityError(
                f"expected sequence {expected_sequence}, found {event.sequence}"
            )
        if event.event_id in seen_ids:
            raise LedgerIntegrityError(f"duplicate event_id: {event.event_id}")
        if event.ledger_version != LEDGER_VERSION:
            raise LedgerIntegrityError(
                f"unsupported ledger version: {event.ledger_version}"
            )
        if event.previous_hash != previous_hash:
            raise LedgerIntegrityError(
                f"broken chain at sequence {event.sequence}: previous hash mismatch"
            )
        expected_hash = stable_hash(event.unsigned())
        if event.event_hash != expected_hash:
            raise LedgerIntegrityError(
                f"tampered event at sequence {event.sequence}: hash mismatch"
            )
        seen_ids.add(event.event_id)
        previous_hash = event.event_hash


def replay_latest(
    events: Iterable[LedgerEvent],
    *,
    event_type: str,
    key_field: str,
) -> Mapping[str, Mapping[str, Any]]:
    """Return the latest payload per key without deleting historical records."""

    latest: Dict[str, Mapping[str, Any]] = {}
    for event in events:
        if event.event_type != event_type:
            continue
        if key_field not in event.payload:
            raise LedgerIntegrityError(
                f"event {event.event_id} lacks replay key field {key_field}"
            )
        latest[str(event.payload[key_field])] = event.payload
    return latest
