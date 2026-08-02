from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Mapping


GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class EventRecord:
    sequence: int
    timestamp: str
    run_id: str
    stage: str
    kind: str
    payload: Mapping[str, object]
    previous_hash: str
    event_hash: str


class EventLogError(RuntimeError):
    pass


def _hash_event(body: Mapping[str, object]) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class HashChainedEventLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _records(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EventLogError(f"invalid JSON on line {number}") from exc
            if not isinstance(item, dict):
                raise EventLogError(f"event line {number} is not an object")
            records.append(item)
        return records

    def append(
        self,
        *,
        run_id: str,
        stage: str,
        kind: str,
        payload: Mapping[str, object] | None = None,
        timestamp: str | None = None,
    ) -> EventRecord:
        records = self._records()
        previous_hash = str(records[-1]["event_hash"]) if records else GENESIS_HASH
        body = {
            "sequence": len(records),
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "stage": stage,
            "kind": kind,
            "payload": dict(payload or {}),
            "previous_hash": previous_hash,
        }
        event_hash = _hash_event(body)
        record = EventRecord(**body, event_hash=event_hash)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
            handle.flush()
        return record

    def verify(self) -> tuple[bool, str | None]:
        previous = GENESIS_HASH
        for expected_sequence, item in enumerate(self._records()):
            if item.get("sequence") != expected_sequence:
                return False, f"sequence mismatch at {expected_sequence}"
            if item.get("previous_hash") != previous:
                return False, f"chain mismatch at {expected_sequence}"
            body = {key: value for key, value in item.items() if key != "event_hash"}
            actual = _hash_event(body)
            if item.get("event_hash") != actual:
                return False, f"hash mismatch at {expected_sequence}"
            previous = actual
        return True, None
