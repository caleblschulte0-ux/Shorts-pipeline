from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .contracts import UploadReservation, stable_id


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UploadLedger:
    """Prevents retry timeouts from creating duplicate uploads."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, UploadReservation]:
        if not self.path.exists():
            return {}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return {key: UploadReservation(**value) for key, value in data.get("reservations", {}).items()}

    def _save(self, values: dict[str, UploadReservation]) -> None:
        payload = {"schema_version": 1, "reservations": {key: asdict(value) for key, value in values.items()}}
        fd, temp_name = tempfile.mkstemp(prefix="upload-ledger-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.path)
        finally:
            Path(temp_name).unlink(missing_ok=True)

    def reserve(self, channel: str, content_fingerprint: str, scheduled_slot: str) -> UploadReservation:
        key = stable_id("upload", {"channel": channel, "fingerprint": content_fingerprint, "slot": scheduled_slot})
        values = self._load()
        existing = values.get(key)
        if existing:
            return existing
        if any(value.content_fingerprint == content_fingerprint and value.state == "completed" for value in values.values()):
            raise ValueError("content_already_uploaded")
        reservation = UploadReservation(key, content_fingerprint, "reserved", now_iso())
        values[key] = reservation
        self._save(values)
        return reservation

    def complete(self, idempotency_key: str, external_upload_id: str) -> UploadReservation:
        values = self._load()
        current = values[idempotency_key]
        if current.state == "completed":
            return current
        completed = UploadReservation(
            idempotency_key=current.idempotency_key,
            content_fingerprint=current.content_fingerprint,
            state="completed",
            reserved_at=current.reserved_at,
            completed_at=now_iso(),
            external_upload_id=external_upload_id,
        )
        values[idempotency_key] = completed
        self._save(values)
        return completed

    def fail(self, idempotency_key: str, reason: str) -> UploadReservation:
        values = self._load()
        current = values[idempotency_key]
        failed = UploadReservation(
            idempotency_key=current.idempotency_key,
            content_fingerprint=current.content_fingerprint,
            state="failed",
            reserved_at=current.reserved_at,
            failure_reason=reason,
        )
        values[idempotency_key] = failed
        self._save(values)
        return failed
