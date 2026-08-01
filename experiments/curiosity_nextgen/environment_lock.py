from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping


@dataclass(frozen=True)
class DependencyPin:
    name: str
    version: str
    sha256: str | None = None
    source: str = "registry"


@dataclass(frozen=True)
class EnvironmentManifest:
    python_version: str
    os_name: str
    architecture: str
    dependencies: tuple[DependencyPin, ...]
    tool_versions: Mapping[str, str]
    environment_variables: tuple[str, ...] = ()

    def canonical_bytes(self) -> bytes:
        payload = {
            "python_version": self.python_version,
            "os_name": self.os_name,
            "architecture": self.architecture,
            "dependencies": [
                {
                    "name": item.name,
                    "version": item.version,
                    "sha256": item.sha256,
                    "source": item.source,
                }
                for item in sorted(self.dependencies, key=lambda value: value.name)
            ],
            "tool_versions": dict(sorted(self.tool_versions.items())),
            "environment_variables": sorted(self.environment_variables),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class EnvironmentComparison:
    compatible: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    expected_sha256: str
    observed_sha256: str


def validate_manifest(manifest: EnvironmentManifest) -> tuple[str, ...]:
    blockers: list[str] = []
    if not manifest.python_version.strip() or not manifest.os_name.strip() or not manifest.architecture.strip():
        blockers.append("missing_platform_identity")
    names = [item.name for item in manifest.dependencies]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    blockers.extend(f"duplicate_dependency:{name}" for name in duplicates)
    for item in manifest.dependencies:
        if not item.name.strip() or not item.version.strip():
            blockers.append(f"invalid_dependency:{item.name or 'blank'}")
        if item.sha256 is not None and len(item.sha256) != 64:
            blockers.append(f"invalid_dependency_hash:{item.name}")
    return tuple(sorted(set(blockers)))


def compare_environments(
    expected: EnvironmentManifest,
    observed: EnvironmentManifest,
    *,
    allowed_tool_drift: Iterable[str] = (),
) -> EnvironmentComparison:
    blockers = list(validate_manifest(expected)) + list(validate_manifest(observed))
    warnings: list[str] = []
    allowed = set(allowed_tool_drift)
    if expected.python_version != observed.python_version:
        blockers.append("python_version_mismatch")
    if expected.os_name != observed.os_name:
        blockers.append("os_mismatch")
    if expected.architecture != observed.architecture:
        blockers.append("architecture_mismatch")

    expected_dependencies = {item.name: item for item in expected.dependencies}
    observed_dependencies = {item.name: item for item in observed.dependencies}
    for name in sorted(set(expected_dependencies) | set(observed_dependencies)):
        wanted = expected_dependencies.get(name)
        actual = observed_dependencies.get(name)
        if wanted is None:
            blockers.append(f"unexpected_dependency:{name}")
        elif actual is None:
            blockers.append(f"missing_dependency:{name}")
        elif wanted.version != actual.version or wanted.sha256 != actual.sha256 or wanted.source != actual.source:
            blockers.append(f"dependency_mismatch:{name}")

    for name in sorted(set(expected.tool_versions) | set(observed.tool_versions)):
        wanted = expected.tool_versions.get(name)
        actual = observed.tool_versions.get(name)
        if wanted != actual:
            if name in allowed:
                warnings.append(f"allowed_tool_drift:{name}")
            else:
                blockers.append(f"tool_mismatch:{name}")

    if set(expected.environment_variables) != set(observed.environment_variables):
        blockers.append("environment_variable_contract_mismatch")

    return EnvironmentComparison(
        compatible=not blockers,
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(warnings),
        expected_sha256=expected.sha256,
        observed_sha256=observed.sha256,
    )
