from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import ReplayArtifact, ReplayBundle, hash_file, stable_id


class ReplayBundleWriter:
    def build(self, *, channel: str, artifacts: Mapping[str, Path], metadata: Mapping[str, Any] | None = None) -> ReplayBundle:
        rows: list[ReplayArtifact] = []
        for role, path in sorted(artifacts.items()):
            if not path.is_file(): raise FileNotFoundError(path)
            rows.append(ReplayArtifact(role, str(path), hash_file(path), path.stat().st_size))
        created_at = datetime.now(timezone.utc).isoformat()
        run_id = stable_id("run", {"channel": channel, "created_at": created_at, "artifacts": [asdict(row) for row in rows]})
        return ReplayBundle(run_id, channel, created_at, tuple(rows), dict(metadata or {}))

    def write(self, bundle: ReplayBundle, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        output = directory / "replay_bundle.json"
        output.write_text(bundle.to_json(), encoding="utf-8")
        return output


class AssetLineageIndex:
    def __init__(self) -> None:
        self._by_hash: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._by_source: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def add_bundle(self, bundle: ReplayBundle) -> None:
        for artifact in bundle.artifacts:
            self._by_hash[artifact.sha256].append((bundle.run_id, artifact.role))
        sources = bundle.metadata.get("source_urls", ())
        for source in sources if isinstance(sources, (list, tuple)) else ():
            self._by_source[str(source)].append((bundle.run_id, "source"))

    def recall_hash(self, digest: str) -> tuple[tuple[str, str], ...]:
        return tuple(self._by_hash.get(digest, ()))

    def recall_source(self, source_url: str) -> tuple[tuple[str, str], ...]:
        return tuple(self._by_source.get(source_url, ()))


class TechnicalLearningStore:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def record(self, *, subsystem: str, failure: str, resolution: str, version: str, channel: str = "shared") -> None:
        self._events.append({"event_id": stable_id("learn", {"subsystem": subsystem, "failure": failure, "resolution": resolution, "version": version, "channel": channel}), "subsystem": subsystem, "failure": failure, "resolution": resolution, "version": version, "channel": channel})

    def query(self, *, subsystem: str | None = None) -> tuple[Mapping[str, Any], ...]:
        return tuple(event for event in self._events if subsystem is None or event["subsystem"] == subsystem)
