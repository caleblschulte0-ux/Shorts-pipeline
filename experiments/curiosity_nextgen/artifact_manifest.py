"""Content-addressed artifact manifests for dormant render-package experiments."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ArtifactRecord:
    path: str
    sha256: str
    size_bytes: int
    media_type: str | None = None


@dataclass(frozen=True)
class ArtifactManifest:
    slug: str
    renderer_commit: str
    render_profile: str
    artifacts: tuple[ArtifactRecord, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = 1

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "slug": self.slug,
            "renderer_commit": self.renderer_commit,
            "render_profile": self.render_profile,
            "artifacts": [asdict(item) for item in self.artifacts],
            "metadata": dict(self.metadata),
        }

    @property
    def manifest_sha256(self) -> str:
        return sha256(canonical_json_bytes(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        result = self.payload()
        result["manifest_sha256"] = self.manifest_sha256
        return result


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    missing: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    size_mismatch: tuple[str, ...] = ()

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(
            [*(f"missing artifact: {p}" for p in self.missing),
             *(f"hash mismatch: {p}" for p in self.changed),
             *(f"size mismatch: {p}" for p in self.size_mismatch)]
        )


def build_manifest(*, root: Path, slug: str, renderer_commit: str,
                   render_profile: str, files: Iterable[Path],
                   metadata: Mapping[str, Any] | None = None) -> ArtifactManifest:
    root = root.resolve()
    records: list[ArtifactRecord] = []
    for item in sorted((Path(p) for p in files), key=lambda p: p.as_posix()):
        path = item if item.is_absolute() else root / item
        path = path.resolve()
        relative = path.relative_to(root).as_posix()
        if not path.is_file():
            raise FileNotFoundError(path)
        records.append(ArtifactRecord(relative, sha256_file(path), path.stat().st_size))
    return ArtifactManifest(slug, renderer_commit, render_profile,
                            tuple(records), dict(metadata or {}))


def validate_manifest(root: Path, manifest: ArtifactManifest) -> ValidationResult:
    root = root.resolve()
    missing: list[str] = []
    changed: list[str] = []
    size_mismatch: list[str] = []
    for record in manifest.artifacts:
        path = root / record.path
        if not path.is_file():
            missing.append(record.path)
            continue
        if path.stat().st_size != record.size_bytes:
            size_mismatch.append(record.path)
        if sha256_file(path) != record.sha256:
            changed.append(record.path)
    return ValidationResult(not (missing or changed or size_mismatch),
                            tuple(missing), tuple(changed), tuple(size_mismatch))


def bind_report(report: Mapping[str, Any], manifest: ArtifactManifest,
                *, report_type: str, producer: str) -> dict[str, Any]:
    return {
        **dict(report),
        "binding": {
            "schema_version": 1,
            "report_type": report_type,
            "producer": producer,
            "manifest_sha256": manifest.manifest_sha256,
            "slug": manifest.slug,
            "renderer_commit": manifest.renderer_commit,
        },
    }


def validate_report_binding(report: Mapping[str, Any], manifest: ArtifactManifest) -> tuple[bool, tuple[str, ...]]:
    binding = report.get("binding")
    if not isinstance(binding, Mapping):
        return False, ("missing report binding",)
    reasons: list[str] = []
    if binding.get("manifest_sha256") != manifest.manifest_sha256:
        reasons.append("report is bound to a different manifest")
    if binding.get("slug") != manifest.slug:
        reasons.append("report slug does not match")
    if binding.get("renderer_commit") != manifest.renderer_commit:
        reasons.append("report renderer commit does not match")
    return not reasons, tuple(reasons)
