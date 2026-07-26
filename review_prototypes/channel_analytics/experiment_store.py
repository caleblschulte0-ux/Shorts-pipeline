from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from enum import Enum
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .analytics_models import ExperimentDefinition, ExperimentStatus


class ExperimentStoreError(RuntimeError):
    pass


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


class ExperimentStore:
    """Atomic file store that enforces one active experiment at a time."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.experiments = self.root / "experiments"
        self.active_file = self.root / "active.json"

    def create(self, definition: ExperimentDefinition) -> Path:
        definition.validate()
        path = self.experiments / f"{definition.experiment_id}.json"
        if path.exists():
            raise ExperimentStoreError(f"experiment already exists: {definition.experiment_id}")
        self._write(path, _jsonable(asdict(definition)))
        return path

    def start(self, experiment_id: str) -> None:
        existing = self.active_id()
        if existing and existing != experiment_id:
            raise ExperimentStoreError(f"experiment {existing!r} is already active")
        payload = self._load(experiment_id)
        if payload.get("status") not in {ExperimentStatus.DRAFT.value, ExperimentStatus.ACTIVE.value}:
            raise ExperimentStoreError("only a draft experiment can be started")
        payload["status"] = ExperimentStatus.ACTIVE.value
        self._write(self.experiments / f"{experiment_id}.json", payload)
        self._write(self.active_file, {"experiment_id": experiment_id})

    def complete(self, experiment_id: str, *, decision: Mapping[str, Any]) -> None:
        if self.active_id() != experiment_id:
            raise ExperimentStoreError("cannot complete an experiment that is not active")
        payload = self._load(experiment_id)
        payload["status"] = ExperimentStatus.COMPLETED.value
        payload["decision"] = _jsonable(dict(decision))
        self._write(self.experiments / f"{experiment_id}.json", payload)
        self.active_file.unlink(missing_ok=True)

    def cancel(self, experiment_id: str, *, reason: str) -> None:
        payload = self._load(experiment_id)
        payload["status"] = ExperimentStatus.CANCELLED.value
        payload["cancel_reason"] = reason
        self._write(self.experiments / f"{experiment_id}.json", payload)
        if self.active_id() == experiment_id:
            self.active_file.unlink(missing_ok=True)

    def active_id(self) -> str | None:
        if not self.active_file.exists():
            return None
        try:
            return str(json.loads(self.active_file.read_text(encoding="utf-8"))["experiment_id"])
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            raise ExperimentStoreError("active experiment pointer is corrupt") from exc

    def _load(self, experiment_id: str) -> dict[str, Any]:
        path = self.experiments / f"{experiment_id}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ExperimentStoreError(f"unknown experiment: {experiment_id}") from exc
        except json.JSONDecodeError as exc:
            raise ExperimentStoreError(f"experiment file is corrupt: {experiment_id}") from exc

    @staticmethod
    def _write(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temp = Path(raw)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        except Exception:
            temp.unlink(missing_ok=True)
            raise
