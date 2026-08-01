"""Blind visual-judge evidence package contracts.

The active renderer is intentionally unaware of this module.  It models the
minimum evidence a visual judge should receive and rejects incomplete, stale,
or internally revealing packages before a verdict can be trusted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class EvidenceKind(str, Enum):
    CONTACT_SHEET = "contact_sheet"
    OPENING_CLIP = "opening_clip"
    PAYOFF_CLIP = "payoff_clip"
    CHAPTER_TRANSITIONS = "chapter_transitions"
    MOTION_SAMPLE = "motion_sample"
    THUMBNAIL = "thumbnail"
    TRANSCRIPT = "transcript"
    BEAT_MAP = "beat_map"
    CAPTIONS = "captions"
    AUDIO_SAMPLE = "audio_sample"


@dataclass(frozen=True)
class EvidenceArtifact:
    kind: EvidenceKind
    artifact_id: str
    sha256: str
    manifest_sha256: str
    media_type: str
    duration_seconds: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.artifact_id.strip():
            raise ValueError("artifact_id must be nonempty")
        if len(self.sha256) < 16:
            raise ValueError("sha256 must look like a content hash")
        if len(self.manifest_sha256) < 16:
            raise ValueError("manifest_sha256 must look like a content hash")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative")


@dataclass(frozen=True)
class JudgeEvidencePolicy:
    required_singletons: frozenset[EvidenceKind] = frozenset({
        EvidenceKind.CONTACT_SHEET,
        EvidenceKind.OPENING_CLIP,
        EvidenceKind.PAYOFF_CLIP,
        EvidenceKind.CHAPTER_TRANSITIONS,
        EvidenceKind.THUMBNAIL,
        EvidenceKind.TRANSCRIPT,
        EvidenceKind.BEAT_MAP,
    })
    minimum_motion_samples: int = 3
    opening_min_seconds: float = 6.0
    opening_max_seconds: float = 15.0
    payoff_min_seconds: float = 3.0
    payoff_max_seconds: float = 25.0
    maximum_total_video_seconds: float = 120.0
    forbidden_metadata_keys: frozenset[str] = frozenset({
        "source_code",
        "planner_reasoning",
        "repair_history",
        "previous_verdict",
        "developer_notes",
        "intended_score",
    })


@dataclass(frozen=True)
class JudgeEvidencePackage:
    slug: str
    manifest_sha256: str
    video_sha256: str
    artifacts: tuple[EvidenceArtifact, ...]
    package_version: str = "1"
    public_context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.slug.strip():
            raise ValueError("slug must be nonempty")
        if len(self.manifest_sha256) < 16 or len(self.video_sha256) < 16:
            raise ValueError("package hashes must look like content hashes")


@dataclass(frozen=True)
class EvidenceValidation:
    valid: bool
    completeness_score: float
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    artifact_counts: Mapping[str, int]
    total_video_seconds: float


_ALLOWED_MEDIA_TYPES: dict[EvidenceKind, frozenset[str]] = {
    EvidenceKind.CONTACT_SHEET: frozenset({"image/png", "image/jpeg"}),
    EvidenceKind.OPENING_CLIP: frozenset({"video/mp4", "video/webm"}),
    EvidenceKind.PAYOFF_CLIP: frozenset({"video/mp4", "video/webm"}),
    EvidenceKind.CHAPTER_TRANSITIONS: frozenset({"video/mp4", "video/webm"}),
    EvidenceKind.MOTION_SAMPLE: frozenset({"video/mp4", "video/webm"}),
    EvidenceKind.THUMBNAIL: frozenset({"image/png", "image/jpeg"}),
    EvidenceKind.TRANSCRIPT: frozenset({"application/json", "text/plain"}),
    EvidenceKind.BEAT_MAP: frozenset({"application/json"}),
    EvidenceKind.CAPTIONS: frozenset({"text/vtt", "application/x-subrip", "text/plain"}),
    EvidenceKind.AUDIO_SAMPLE: frozenset({"audio/mpeg", "audio/wav", "audio/mp4"}),
}


def _duration_between(
    artifact: EvidenceArtifact,
    minimum: float,
    maximum: float,
    label: str,
    blockers: list[str],
) -> None:
    if artifact.duration_seconds is None:
        blockers.append(f"missing_duration:{label}")
    elif not minimum <= artifact.duration_seconds <= maximum:
        blockers.append(f"invalid_duration:{label}:{artifact.duration_seconds}")


def validate_evidence_package(
    package: JudgeEvidencePackage,
    *,
    expected_manifest_sha256: str,
    expected_video_sha256: str | None = None,
    policy: JudgeEvidencePolicy | None = None,
) -> EvidenceValidation:
    policy = policy or JudgeEvidencePolicy()
    blockers: list[str] = []
    warnings: list[str] = []
    counts: dict[EvidenceKind, int] = {}
    seen_ids: set[str] = set()

    if package.manifest_sha256 != expected_manifest_sha256:
        blockers.append("package_manifest_mismatch")
    if expected_video_sha256 is not None and package.video_sha256 != expected_video_sha256:
        blockers.append("package_video_mismatch")

    for key in package.public_context:
        if key in policy.forbidden_metadata_keys:
            blockers.append(f"blindness_violation:package:{key}")

    for artifact in package.artifacts:
        counts[artifact.kind] = counts.get(artifact.kind, 0) + 1
        if artifact.artifact_id in seen_ids:
            blockers.append(f"duplicate_artifact_id:{artifact.artifact_id}")
        seen_ids.add(artifact.artifact_id)

        if artifact.manifest_sha256 != expected_manifest_sha256:
            blockers.append(f"artifact_manifest_mismatch:{artifact.artifact_id}")
        if artifact.media_type not in _ALLOWED_MEDIA_TYPES[artifact.kind]:
            blockers.append(f"invalid_media_type:{artifact.artifact_id}:{artifact.media_type}")
        for key in artifact.metadata:
            if key in policy.forbidden_metadata_keys:
                blockers.append(f"blindness_violation:{artifact.artifact_id}:{key}")

    for kind in sorted(policy.required_singletons, key=lambda item: item.value):
        count = counts.get(kind, 0)
        if count == 0:
            blockers.append(f"missing_evidence:{kind.value}")
        elif count > 1:
            blockers.append(f"duplicate_singleton:{kind.value}:{count}")

    motion_count = counts.get(EvidenceKind.MOTION_SAMPLE, 0)
    if motion_count < policy.minimum_motion_samples:
        blockers.append(f"insufficient_motion_samples:{motion_count}")

    opening = next((item for item in package.artifacts if item.kind is EvidenceKind.OPENING_CLIP), None)
    payoff = next((item for item in package.artifacts if item.kind is EvidenceKind.PAYOFF_CLIP), None)
    if opening is not None:
        _duration_between(opening, policy.opening_min_seconds, policy.opening_max_seconds, "opening", blockers)
    if payoff is not None:
        _duration_between(payoff, policy.payoff_min_seconds, policy.payoff_max_seconds, "payoff", blockers)

    video_seconds = sum(
        artifact.duration_seconds or 0.0
        for artifact in package.artifacts
        if artifact.media_type.startswith("video/")
    )
    if video_seconds > policy.maximum_total_video_seconds:
        warnings.append(f"oversized_judge_package:{round(video_seconds, 2)}")

    expected_units = len(policy.required_singletons) + policy.minimum_motion_samples
    present_units = sum(1 for kind in policy.required_singletons if counts.get(kind, 0) == 1)
    present_units += min(policy.minimum_motion_samples, motion_count)
    completeness = 100.0 if expected_units == 0 else present_units / expected_units * 100

    return EvidenceValidation(
        valid=not blockers,
        completeness_score=round(completeness, 1),
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
        artifact_counts={kind.value: count for kind, count in sorted(counts.items(), key=lambda item: item[0].value)},
        total_video_seconds=round(video_seconds, 2),
    )


def build_blind_payload(package: JudgeEvidencePackage) -> dict[str, object]:
    """Return the only payload shape a blind judge should receive."""
    return {
        "schema_version": package.package_version,
        "slug": package.slug,
        "manifest_sha256": package.manifest_sha256,
        "video_sha256": package.video_sha256,
        "context": dict(package.public_context),
        "artifacts": [
            {
                "kind": artifact.kind.value,
                "artifact_id": artifact.artifact_id,
                "sha256": artifact.sha256,
                "media_type": artifact.media_type,
                "duration_seconds": artifact.duration_seconds,
                "metadata": dict(artifact.metadata),
            }
            for artifact in package.artifacts
        ],
    }
