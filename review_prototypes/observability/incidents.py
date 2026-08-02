from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import tempfile
import os


class IncidentSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Incident:
    incident_id: str
    run_id: str
    stage: str
    severity: IncidentSeverity
    failure_class: str
    message: str
    retryable: bool
    artifact_refs: tuple[str, ...] = ()


class IncidentClassifier:
    CRITICAL_MARKERS = ("corrupt", "tamper", "publish", "rollback failed")
    RETRYABLE_MARKERS = ("timeout", "temporarily", "rate limit", "unavailable")

    def classify(self, *, run_id: str, stage: str, error: BaseException) -> Incident:
        message = str(error)
        lowered = message.lower()
        severity = (
            IncidentSeverity.CRITICAL
            if any(marker in lowered for marker in self.CRITICAL_MARKERS)
            else IncidentSeverity.ERROR
        )
        retryable = any(marker in lowered for marker in self.RETRYABLE_MARKERS)
        failure_class = error.__class__.__name__
        digest = hashlib.sha256(
            f"{run_id}|{stage}|{failure_class}|{message}".encode("utf-8")
        ).hexdigest()[:16]
        return Incident(
            incident_id=digest,
            run_id=run_id,
            stage=stage,
            severity=severity,
            failure_class=failure_class,
            message=message,
            retryable=retryable,
        )


class DeadLetterQueue:
    """Stores failed work immutably for later inspection, never silent discard."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def enqueue(self, incident: Incident, work_payload: dict[str, object]) -> Path:
        destination = self.root / f"{incident.incident_id}.json"
        if destination.exists():
            return destination
        payload = {"incident": asdict(incident), "work_payload": work_payload}
        staging = Path(tempfile.mkstemp(prefix=".dead-letter-", dir=self.root)[1])
        try:
            staging.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
            os.replace(staging, destination)
        finally:
            staging.unlink(missing_ok=True)
        return destination
