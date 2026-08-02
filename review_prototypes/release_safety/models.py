from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ReleaseCandidate:
    release_id: str
    slug: str
    attempt_id: str
    video_sha256: str
    verdict_sha256: str
    proof_run_id: str
    score: float
    hard_failures: tuple[str, ...]
    readiness: Mapping[str, bool]

    def validate(self) -> None:
        if not all((self.release_id, self.slug, self.attempt_id, self.video_sha256, self.verdict_sha256, self.proof_run_id)):
            raise ValueError("release candidate missing identity or hashes")
        if self.hard_failures:
            raise ValueError("release candidate has hard failures")
        failed = [name for name, passed in self.readiness.items() if not passed]
        if failed:
            raise ValueError(f"release candidate failed readiness: {failed}")
        if self.score < 0 or self.score > 100:
            raise ValueError("release score must be within [0, 100]")


@dataclass(frozen=True)
class ReleaseManifest:
    release_id: str
    slug: str
    attempt_id: str
    video_sha256: str
    verdict_sha256: str
    proof_run_id: str
    score: float
    previous_release_id: str | None
    manifest_sha256: str


@dataclass(frozen=True)
class ReleaseState:
    canonical_release_id: str | None
    quarantined_release_ids: tuple[str, ...]
    history: tuple[str, ...]
