from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable


class ManifestError(RuntimeError):
    pass


@dataclass(frozen=True)
class FileRecord:
    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class ArtifactManifest:
    version: int
    files: tuple[FileRecord, ...]
    total_bytes: int
    tree_sha256: str

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "files": [asdict(item) for item in self.files],
            "total_bytes": self.total_bytes,
            "tree_sha256": self.tree_sha256,
        }

    @classmethod
    def from_dict(cls, value: dict) -> "ArtifactManifest":
        return cls(
            version=int(value["version"]),
            files=tuple(FileRecord(**item) for item in value["files"]),
            total_bytes=int(value["total_bytes"]),
            tree_sha256=str(value["tree_sha256"]),
        )


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    root: Path,
    *,
    excluded: Iterable[str] = ("manifest.json",),
) -> ArtifactManifest:
    root = Path(root)
    if not root.is_dir():
        raise ManifestError(f"artifact root is missing: {root}")
    excluded_set = set(excluded)
    records: list[FileRecord] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded_set:
            continue
        records.append(
            FileRecord(
                relative_path=relative,
                size=path.stat().st_size,
                sha256=sha256_file(path),
            )
        )
    if not records:
        raise ManifestError("artifact root contains no files")
    canonical = json.dumps(
        [asdict(record) for record in records],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return ArtifactManifest(
        version=1,
        files=tuple(records),
        total_bytes=sum(record.size for record in records),
        tree_sha256=hashlib.sha256(canonical).hexdigest(),
    )


def write_manifest(root: Path) -> ArtifactManifest:
    manifest = build_manifest(root)
    target = Path(root) / "manifest.json"
    target.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_manifest(
    root: Path,
    manifest: ArtifactManifest | None = None,
) -> None:
    root = Path(root)
    if manifest is None:
        path = root / "manifest.json"
        try:
            manifest = ArtifactManifest.from_dict(
                json.loads(path.read_text(encoding="utf-8"))
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ManifestError(f"invalid manifest: {exc}") from exc
    actual = build_manifest(root)
    if actual != manifest:
        expected = {item.relative_path: item for item in manifest.files}
        observed = {item.relative_path: item for item in actual.files}
        missing = sorted(set(expected) - set(observed))
        unexpected = sorted(set(observed) - set(expected))
        changed = sorted(
            path
            for path in set(expected) & set(observed)
            if expected[path] != observed[path]
        )
        raise ManifestError(
            "artifact manifest mismatch; "
            f"missing={missing}, unexpected={unexpected}, changed={changed}"
        )
