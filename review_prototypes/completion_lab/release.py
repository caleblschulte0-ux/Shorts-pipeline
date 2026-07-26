from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping


@dataclass(frozen=True)
class ReleaseManifest:
    release_id: str
    story_slug: str
    video_hash: str
    proof_hashes: tuple[str, ...]
    metadata: Mapping[str, Any]

    def canonical_payload(self) -> Mapping[str, Any]:
        return {
            "release_id": self.release_id,
            "story_slug": self.story_slug,
            "video_hash": self.video_hash,
            "proof_hashes": list(self.proof_hashes),
            "metadata": dict(self.metadata),
        }

    @property
    def digest(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ReleaseRepository:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.releases = self.root / "releases"
        self.canonical = self.root / "canonical"
        self.history = self.root / "history.jsonl"

    def record(self, manifest: ReleaseManifest, video_path: Path) -> Path:
        destination = self.releases / manifest.release_id
        if destination.exists():
            raise ValueError("release is immutable")
        destination.mkdir(parents=True, exist_ok=False)
        shutil.copy2(video_path, destination / "video.mp4")
        payload = {**manifest.canonical_payload(), "digest": manifest.digest}
        (destination / "manifest.json").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return destination

    def load(self, release_id: str) -> ReleaseManifest:
        path = self.releases / release_id / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        digest = data.pop("digest")
        manifest = ReleaseManifest(
            release_id=data["release_id"],
            story_slug=data["story_slug"],
            video_hash=data["video_hash"],
            proof_hashes=tuple(data["proof_hashes"]),
            metadata=data["metadata"],
        )
        if manifest.digest != digest:
            raise ValueError("release manifest digest mismatch")
        video = self.releases / release_id / "video.mp4"
        actual = hashlib.sha256(video.read_bytes()).hexdigest()
        if actual != manifest.video_hash:
            raise ValueError("release video hash mismatch")
        return manifest

    def promote(self, release_id: str) -> None:
        self.load(release_id)
        source = self.releases / release_id
        self.root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".canonical-", dir=self.root))
        try:
            shutil.rmtree(staging)
            shutil.copytree(source, staging)
            previous = self.current_release_id()
            backup = self.root / ".canonical.previous"
            shutil.rmtree(backup, ignore_errors=True)
            if self.canonical.exists():
                os.replace(self.canonical, backup)
            os.replace(staging, self.canonical)
            shutil.rmtree(backup, ignore_errors=True)
            with self.history.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"release_id": release_id, "previous": previous}) + "\n")
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def current_release_id(self) -> str | None:
        manifest_path = self.canonical / "manifest.json"
        if not manifest_path.exists():
            return None
        return json.loads(manifest_path.read_text(encoding="utf-8"))["release_id"]

    def rollback(self) -> str:
        if not self.history.exists():
            raise ValueError("no rollback history")
        history = [json.loads(line) for line in self.history.read_text(encoding="utf-8").splitlines()]
        if len(history) < 2:
            raise ValueError("no verified rollback target")
        target = history[-2]["release_id"]
        self.promote(target)
        return target
