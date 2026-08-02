from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from .models import ReleaseCandidate, ReleaseManifest, ReleaseState


class ReleaseRepositoryError(RuntimeError):
    pass


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ReleaseRepository:
    """Review-only release state with immutable records and atomic canonical pointers."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.records = self.root / "records"
        self.quarantine_dir = self.root / "quarantine"
        self.state_path = self.root / "state.json"
        self.records.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._write_state(ReleaseState(None, (), ()))

    def _read_state(self) -> ReleaseState:
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        return ReleaseState(
            canonical_release_id=payload.get("canonical_release_id"),
            quarantined_release_ids=tuple(payload.get("quarantined_release_ids") or ()),
            history=tuple(payload.get("history") or ()),
        )

    def _write_state(self, state: ReleaseState) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".release-state-", dir=self.root)
        os.close(fd)
        staging = Path(name)
        try:
            staging.write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n")
            os.replace(staging, self.state_path)
        finally:
            staging.unlink(missing_ok=True)

    def record(self, candidate: ReleaseCandidate) -> ReleaseManifest:
        candidate.validate()
        destination = self.records / candidate.release_id
        if destination.exists():
            raise ReleaseRepositoryError(f"release already exists: {candidate.release_id}")
        previous = self._read_state().canonical_release_id
        body = {
            "release_id": candidate.release_id,
            "slug": candidate.slug,
            "attempt_id": candidate.attempt_id,
            "video_sha256": candidate.video_sha256,
            "verdict_sha256": candidate.verdict_sha256,
            "proof_run_id": candidate.proof_run_id,
            "score": candidate.score,
            "previous_release_id": previous,
        }
        manifest = ReleaseManifest(
            **body,
            manifest_sha256=_digest(body),
        )
        destination.mkdir()
        (destination / "manifest.json").write_text(
            json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return manifest

    def verify(self, release_id: str) -> bool:
        path = self.records / release_id / "manifest.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected = payload.pop("manifest_sha256")
        return _digest(payload) == expected

    def promote(self, release_id: str) -> ReleaseState:
        if not self.verify(release_id):
            raise ReleaseRepositoryError(f"release manifest failed verification: {release_id}")
        state = self._read_state()
        if release_id in state.quarantined_release_ids:
            raise ReleaseRepositoryError(f"release is quarantined: {release_id}")
        history = state.history if state.canonical_release_id == release_id else (*state.history, release_id)
        updated = ReleaseState(release_id, state.quarantined_release_ids, history)
        self._write_state(updated)
        return updated

    def quarantine(self, release_id: str, reason: str) -> ReleaseState:
        if not (self.records / release_id).exists():
            raise ReleaseRepositoryError(f"unknown release: {release_id}")
        marker = self.quarantine_dir / f"{release_id}.json"
        marker.write_text(json.dumps({"release_id": release_id, "reason": reason}, indent=2) + "\n")
        state = self._read_state()
        quarantined = tuple(dict.fromkeys((*state.quarantined_release_ids, release_id)))
        canonical = None if state.canonical_release_id == release_id else state.canonical_release_id
        updated = ReleaseState(canonical, quarantined, state.history)
        self._write_state(updated)
        return updated

    def rollback(self) -> ReleaseState:
        state = self._read_state()
        eligible = [release_id for release_id in state.history if release_id not in state.quarantined_release_ids]
        if state.canonical_release_id in eligible:
            eligible = eligible[: eligible.index(state.canonical_release_id)]
        if not eligible:
            raise ReleaseRepositoryError("no verified prior release available for rollback")
        target = eligible[-1]
        if not self.verify(target):
            raise ReleaseRepositoryError(f"rollback target failed verification: {target}")
        updated = ReleaseState(target, state.quarantined_release_ids, state.history)
        self._write_state(updated)
        return updated

    def state(self) -> ReleaseState:
        return self._read_state()
