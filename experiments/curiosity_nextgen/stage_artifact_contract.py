"""Dormant stage-level artifact interfaces and hash-bound handoff validation."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable


@dataclass(frozen=True)
class StageArtifactSpec:
    stage: str
    required_inputs: frozenset[str]
    required_outputs: frozenset[str]
    schema_version: int = 1
    maximum_output_bytes: int = 50_000_000

    def __post_init__(self) -> None:
        if not self.stage:
            raise ValueError("stage is required")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if self.maximum_output_bytes < 1:
            raise ValueError("maximum_output_bytes must be positive")


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    story_id: str
    stage: str
    kind: str
    schema_version: int
    content_sha256: str
    producer_id: str
    input_hashes: tuple[str, ...] = ()
    size_bytes: int = 0

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.story_id or not self.stage or not self.kind or not self.producer_id:
            raise ValueError("artifact identity fields are required")
        if self.schema_version < 1:
            raise ValueError("schema_version must be positive")
        if len(self.content_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.content_sha256):
            raise ValueError("content_sha256 must be lowercase SHA-256")
        if self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")

    def binding_digest(self) -> str:
        payload = {
            "artifact_id": self.artifact_id,
            "story_id": self.story_id,
            "stage": self.stage,
            "kind": self.kind,
            "schema_version": self.schema_version,
            "content_sha256": self.content_sha256,
            "producer_id": self.producer_id,
            "input_hashes": sorted(self.input_hashes),
            "size_bytes": self.size_bytes,
        }
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class ArtifactValidation:
    valid: bool
    blockers: tuple[str, ...]
    input_hashes: tuple[str, ...]
    output_hashes: tuple[str, ...]
    bundle_digest: str | None


def validate_stage_artifacts(
    spec: StageArtifactSpec,
    story_id: str,
    inputs: Iterable[ArtifactRecord],
    outputs: Iterable[ArtifactRecord],
) -> ArtifactValidation:
    input_items = tuple(inputs)
    output_items = tuple(outputs)
    blockers: list[str] = []

    all_items = input_items + output_items
    if any(item.story_id != story_id for item in all_items):
        blockers.append("cross_story_artifact")
    if any(item.stage != spec.stage for item in output_items):
        blockers.append("output_stage_mismatch")
    if any(item.schema_version != spec.schema_version for item in output_items):
        blockers.append("output_schema_mismatch")
    if len({item.artifact_id for item in all_items}) != len(all_items):
        blockers.append("duplicate_artifact_id")
    if len({item.content_sha256 for item in output_items}) != len(output_items):
        blockers.append("duplicate_output_content")

    input_kinds = {item.kind for item in input_items}
    output_kinds = {item.kind for item in output_items}
    missing_inputs = spec.required_inputs - input_kinds
    missing_outputs = spec.required_outputs - output_kinds
    if missing_inputs:
        blockers.extend(f"missing_input:{kind}" for kind in sorted(missing_inputs))
    if missing_outputs:
        blockers.extend(f"missing_output:{kind}" for kind in sorted(missing_outputs))
    if sum(item.size_bytes for item in output_items) > spec.maximum_output_bytes:
        blockers.append("output_size_limit")

    expected_input_hashes = tuple(sorted(item.content_sha256 for item in input_items))
    for output in output_items:
        if tuple(sorted(output.input_hashes)) != expected_input_hashes:
            blockers.append(f"stale_or_unbound_output:{output.artifact_id}")

    output_hashes = tuple(sorted(item.content_sha256 for item in output_items))
    bundle_digest: str | None = None
    if not blockers:
        payload = {
            "stage": spec.stage,
            "story_id": story_id,
            "schema_version": spec.schema_version,
            "inputs": expected_input_hashes,
            "outputs": output_hashes,
            "bindings": sorted(item.binding_digest() for item in output_items),
        }
        bundle_digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    return ArtifactValidation(
        valid=not blockers,
        blockers=tuple(sorted(set(blockers))),
        input_hashes=expected_input_hashes,
        output_hashes=output_hashes,
        bundle_digest=bundle_digest,
    )
