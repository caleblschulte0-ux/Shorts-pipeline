from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

from .config import secret_status
from .contracts import CapabilityTruthRecord
from .registry import CapabilityRegistry


class CapabilityTruthReport:
    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def prototype_records(self, *, channel: str = "review-only", env: Mapping[str, str] | None = None) -> tuple[CapabilityTruthRecord, ...]:
        status = secret_status(env)
        records: list[CapabilityTruthRecord] = []
        for spec in self.registry.list():
            names = tuple(secret.name for secret in spec.secret_requirements)
            configured = all(status.get(name, False) for name in names) if names else None
            records.append(CapabilityTruthRecord(capability_id=spec.capability_id, channel=channel, code_exists=True, secret_configured=configured, workflow_passes_secret=False if names else None, imported_by_runtime=False, fallback_available=bool(spec.tool_requirements), status_note="isolated prototype only; no production wiring"))
        return tuple(records)

    def write(self, path: Path, *, channel: str = "review-only", env: Mapping[str, str] | None = None) -> None:
        payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "channel": channel, "records": [asdict(record) for record in self.prototype_records(channel=channel, env=env)]}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
