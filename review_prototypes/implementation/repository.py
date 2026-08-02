from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from .manifest import ArtifactManifest, ManifestError, verify_manifest, write_manifest
from .models import AttemptIdentity, SceneCandidate, Verdict


class RepositoryError(RuntimeError):
    pass


@dataclass(frozen=True)
class AttemptRecord:
    identity: AttemptIdentity
    path: Path
    verdict: Verdict
    manifest: ArtifactManifest
    parent_attempt_id: str | None
    candidate: SceneCandidate | None


class FileLock:
    def __init__(self, path: Path, *, timeout_seconds: float = 10.0) -> None:
        self.path = Path(path)
        self.timeout_seconds = timeout_seconds
        self._fd: int | None = None

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self._fd = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(self._fd, f"pid={os.getpid()}\n".encode())
                os.fsync(self._fd)
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise RepositoryError(
                        f"timed out acquiring lock: {self.path}"
                    )
                time.sleep(0.05)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self.path.unlink(missing_ok=True)


class AttemptRepository:
    REQUIRED_FILES = (
        "video.mp4",
        "scene_plan.json",
        "verdict.json",
        "attempt.json",
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.attempts_root = self.root / "attempts"
        self.canonical_root = self.root / "canonical"
        self.locks_root = self.root / "locks"

    def record(
        self,
        *,
        identity: AttemptIdentity,
        rendered_dir: Path,
        verdict: Verdict,
        parent_attempt_id: str | None,
        candidate: SceneCandidate | None,
    ) -> AttemptRecord:
        identity.validate()
        verdict.validate()
        rendered_dir = Path(rendered_dir)
        destination = (
            self.attempts_root
            / identity.slug
            / identity.run_id
            / identity.attempt_id
        )
        with FileLock(self.locks_root / f"{identity.slug}.lock"):
            if destination.exists():
                raise RepositoryError(f"attempt already exists: {destination}")
            self._validate_rendered_dir(rendered_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(
                tempfile.mkdtemp(
                    prefix=f".{identity.attempt_id}-",
                    dir=destination.parent,
                )
            )
            try:
                shutil.copytree(rendered_dir, staging, dirs_exist_ok=True)
                (staging / "verdict.json").write_text(
                    json.dumps(verdict.to_dict(), indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
                (staging / "attempt.json").write_text(
                    json.dumps(
                        {
                            "identity": {
                                "slug": identity.slug,
                                "run_id": identity.run_id,
                                "attempt_id": identity.attempt_id,
                            },
                            "parent_attempt_id": parent_attempt_id,
                            "candidate": (
                                candidate.to_dict() if candidate else None
                            ),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                manifest = write_manifest(staging)
                self._fsync_tree(staging)
                os.replace(staging, destination)
            except Exception:
                shutil.rmtree(staging, ignore_errors=True)
                raise
        return self.load(identity)

    def load(self, identity: AttemptIdentity) -> AttemptRecord:
        identity.validate()
        path = (
            self.attempts_root
            / identity.slug
            / identity.run_id
            / identity.attempt_id
        )
        self._assert_complete(path)
        try:
            metadata = json.loads(
                (path / "attempt.json").read_text(encoding="utf-8")
            )
            verdict = Verdict.from_dict(
                json.loads(
                    (path / "verdict.json").read_text(encoding="utf-8")
                )
            )
            manifest = ArtifactManifest.from_dict(
                json.loads(
                    (path / "manifest.json").read_text(encoding="utf-8")
                )
            )
            verify_manifest(path, manifest)
            candidate_data = metadata.get("candidate")
            candidate = (
                SceneCandidate(**candidate_data) if candidate_data else None
            )
            if candidate:
                candidate.validate()
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ManifestError,
        ) as exc:
            raise RepositoryError(f"invalid attempt at {path}: {exc}") from exc
        return AttemptRecord(
            identity=identity,
            path=path,
            verdict=verdict,
            manifest=manifest,
            parent_attempt_id=metadata.get("parent_attempt_id"),
            candidate=candidate,
        )

    def promote(self, record: AttemptRecord) -> Path:
        if not record.verdict.promotable:
            raise RepositoryError(
                f"attempt {record.identity.attempt_id} is not promotable"
            )
        verify_manifest(record.path, record.manifest)
        canonical = self.canonical_root / record.identity.slug
        canonical.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(self.locks_root / f"{record.identity.slug}.lock"):
            staging = Path(
                tempfile.mkdtemp(
                    prefix=f".{record.identity.slug}-",
                    dir=canonical.parent,
                )
            )
            backup = canonical.with_name(f".{canonical.name}.previous")
            try:
                shutil.rmtree(staging)
                shutil.copytree(record.path, staging)
                self._fsync_tree(staging)
                if backup.exists():
                    shutil.rmtree(backup)
                if canonical.exists():
                    os.replace(canonical, backup)
                os.replace(staging, canonical)
                verify_manifest(canonical)
                shutil.rmtree(backup, ignore_errors=True)
            except Exception:
                if not canonical.exists() and backup.exists():
                    os.replace(backup, canonical)
                shutil.rmtree(staging, ignore_errors=True)
                raise
        return canonical

    def canonical(self, slug: str) -> AttemptRecord | None:
        canonical = self.canonical_root / slug
        if not canonical.exists():
            return None
        try:
            metadata = json.loads(
                (canonical / "attempt.json").read_text(encoding="utf-8")
            )
            identity = AttemptIdentity(**metadata["identity"])
            verdict = Verdict.from_dict(
                json.loads(
                    (canonical / "verdict.json").read_text(
                        encoding="utf-8"
                    )
                )
            )
            manifest = ArtifactManifest.from_dict(
                json.loads(
                    (canonical / "manifest.json").read_text(
                        encoding="utf-8"
                    )
                )
            )
            verify_manifest(canonical, manifest)
            candidate_data = metadata.get("candidate")
            candidate = (
                SceneCandidate(**candidate_data) if candidate_data else None
            )
        except Exception as exc:
            raise RepositoryError(
                f"invalid canonical state for {slug}: {exc}"
            ) from exc
        return AttemptRecord(
            identity=identity,
            path=canonical,
            verdict=verdict,
            manifest=manifest,
            parent_attempt_id=metadata.get("parent_attempt_id"),
            candidate=candidate,
        )

    @classmethod
    def _validate_rendered_dir(cls, path: Path) -> None:
        if not path.is_dir():
            raise RepositoryError(
                f"rendered directory is missing: {path}"
            )
        missing = [
            name
            for name in ("video.mp4", "scene_plan.json")
            if not (path / name).is_file()
        ]
        if missing:
            raise RepositoryError(
                f"rendered directory is incomplete: {missing}"
            )

    @classmethod
    def _assert_complete(cls, path: Path) -> None:
        missing = [
            name
            for name in (*cls.REQUIRED_FILES, "manifest.json")
            if not (path / name).is_file()
        ]
        if missing:
            raise RepositoryError(
                f"attempt is incomplete at {path}; missing={missing}"
            )

    @staticmethod
    def _fsync_tree(path: Path) -> None:
        for item in path.rglob("*"):
            if item.is_file():
                with item.open("rb") as handle:
                    os.fsync(handle.fileno())
