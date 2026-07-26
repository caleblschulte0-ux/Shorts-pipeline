from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping


GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditRecord:
    sequence: int
    timestamp: int
    actor: str
    action: str
    subject: str
    details: Mapping[str, Any]
    previous_hash: str
    record_hash: str


@dataclass(frozen=True)
class ChainVerification:
    valid: bool
    verified_records: int
    blockers: tuple[str, ...]
    head_hash: str


def _payload(
    sequence: int,
    timestamp: int,
    actor: str,
    action: str,
    subject: str,
    details: Mapping[str, Any],
    previous_hash: str,
) -> bytes:
    value = {
        "sequence": sequence,
        "timestamp": timestamp,
        "actor": actor,
        "action": action,
        "subject": subject,
        "details": dict(sorted(details.items())),
        "previous_hash": previous_hash,
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def append_record(
    records: Iterable[AuditRecord],
    *,
    timestamp: int,
    actor: str,
    action: str,
    subject: str,
    details: Mapping[str, Any] | None = None,
) -> tuple[AuditRecord, ...]:
    items = tuple(records)
    previous_hash = items[-1].record_hash if items else GENESIS_HASH
    sequence = len(items) + 1
    digest = hashlib.sha256(
        _payload(sequence, timestamp, actor, action, subject, details or {}, previous_hash)
    ).hexdigest()
    return items + (
        AuditRecord(
            sequence,
            timestamp,
            actor,
            action,
            subject,
            details or {},
            previous_hash,
            digest,
        ),
    )


def verify_chain(records: Iterable[AuditRecord]) -> ChainVerification:
    items = tuple(records)
    blockers: list[str] = []
    expected_previous = GENESIS_HASH
    last_timestamp = -1
    for index, record in enumerate(items, start=1):
        if record.sequence != index:
            blockers.append(f"sequence_mismatch:{index}")
        if record.previous_hash != expected_previous:
            blockers.append(f"previous_hash_mismatch:{index}")
        expected_hash = hashlib.sha256(
            _payload(
                record.sequence,
                record.timestamp,
                record.actor,
                record.action,
                record.subject,
                record.details,
                record.previous_hash,
            )
        ).hexdigest()
        if record.record_hash != expected_hash:
            blockers.append(f"record_hash_mismatch:{index}")
        if record.timestamp < last_timestamp:
            blockers.append(f"timestamp_regression:{index}")
        if not record.actor.strip() or not record.action.strip() or not record.subject.strip():
            blockers.append(f"blank_identity_field:{index}")
        expected_previous = record.record_hash
        last_timestamp = record.timestamp
    return ChainVerification(
        valid=not blockers,
        verified_records=len(items),
        blockers=tuple(blockers),
        head_hash=items[-1].record_hash if items else GENESIS_HASH,
    )


def locate_first_break(records: Iterable[AuditRecord]) -> int | None:
    verification = verify_chain(records)
    if verification.valid:
        return None
    for blocker in verification.blockers:
        try:
            return int(blocker.rsplit(":", 1)[1])
        except (IndexError, ValueError):
            continue
    return 1
