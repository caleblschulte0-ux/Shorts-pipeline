from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    kind: str
    payload: Mapping[str, Any]
    previous_hash: str
    event_hash: str


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, kind: str, payload: Mapping[str, Any]) -> AuditEvent:
        events = self.read()
        previous = events[-1].event_hash if events else "GENESIS"
        sequence = len(events) + 1
        body = {
            "sequence": sequence,
            "kind": kind,
            "payload": payload,
            "previous_hash": previous,
        }
        event_hash = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        event = AuditEvent(sequence, kind, dict(payload), previous, event_hash)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**body, "event_hash": event_hash}, sort_keys=True) + "\n")
        return event

    def read(self) -> tuple[AuditEvent, ...]:
        if not self.path.exists():
            return ()
        events: list[AuditEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            data = json.loads(line)
            events.append(AuditEvent(data["sequence"], data["kind"], data["payload"], data["previous_hash"], data["event_hash"]))
        return tuple(events)

    def verify(self) -> None:
        previous = "GENESIS"
        for expected_sequence, event in enumerate(self.read(), start=1):
            if event.sequence != expected_sequence:
                raise ValueError("audit sequence mismatch")
            if event.previous_hash != previous:
                raise ValueError("audit chain link mismatch")
            body = {
                "sequence": event.sequence,
                "kind": event.kind,
                "payload": event.payload,
                "previous_hash": event.previous_hash,
            }
            expected_hash = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            if event.event_hash != expected_hash:
                raise ValueError("audit event hash mismatch")
            previous = event.event_hash
