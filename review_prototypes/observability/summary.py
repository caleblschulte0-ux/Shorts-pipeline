from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    event_count: int
    completed_stages: tuple[str, ...]
    failed_stages: tuple[str, ...]
    attempt_ids: tuple[str, ...]
    artifact_refs: tuple[str, ...]


class RunSummaryBuilder:
    def from_jsonl(self, path: Path, run_id: str) -> RunSummary:
        completed: list[str] = []
        failed: list[str] = []
        attempts: list[str] = []
        artifacts: list[str] = []
        count = 0
        if not Path(path).exists():
            return RunSummary(run_id, 0, (), (), (), ())
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("run_id") != run_id:
                continue
            count += 1
            stage = str(item.get("stage") or "unknown")
            kind = str(item.get("kind") or "")
            payload = item.get("payload") or {}
            if kind.endswith("completed") and stage not in completed:
                completed.append(stage)
            if kind.endswith("failed") and stage not in failed:
                failed.append(stage)
            if isinstance(payload, Mapping):
                attempt = payload.get("attempt_id")
                artifact = payload.get("artifact_ref")
                if attempt and str(attempt) not in attempts:
                    attempts.append(str(attempt))
                if artifact and str(artifact) not in artifacts:
                    artifacts.append(str(artifact))
        return RunSummary(run_id, count, tuple(completed), tuple(failed), tuple(attempts), tuple(artifacts))
