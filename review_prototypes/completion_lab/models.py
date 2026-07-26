from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


class PipelineStatus(str, Enum):
    SHIPPED = "shipped"
    HELD = "held"
    FAILED = "failed"


class Fault(str, Enum):
    NONE = "none"
    MISSING_SOURCE = "missing_source"
    STALE_SOURCE = "stale_source"
    RENDER_CRASH = "render_crash"
    MISSING_VIDEO = "missing_video"
    MALFORMED_VERDICT = "malformed_verdict"
    JUDGE_UNWATCHED = "judge_unwatched"
    LOW_SCORE = "low_score"
    VERSION_DRIFT = "version_drift"
    PROOF_TAMPER = "proof_tamper"
    RELEASE_TAMPER = "release_tamper"
    AUDIT_TAMPER = "audit_tamper"
    ROLLBACK_WITHOUT_TARGET = "rollback_without_target"


@dataclass(frozen=True)
class SourceFact:
    publisher: str
    url: str
    accessed: date
    claim: str
    value: float
    unit: str

    def validate(self, *, today: date) -> None:
        if not self.publisher.strip():
            raise ValueError("source publisher is required")
        if not self.url.startswith("https://"):
            raise ValueError("source URL must use https")
        if self.accessed > today:
            raise ValueError("source access date cannot be in the future")
        if (today - self.accessed).days > 365:
            raise ValueError("source is stale")
        if not self.claim.strip() or not self.unit.strip():
            raise ValueError("source claim and unit are required")


@dataclass(frozen=True)
class StoryBeat:
    beat_id: str
    narration: str
    duration_seconds: float
    visual_family: str
    mascot_action: str
    tension: float

    def validate(self) -> None:
        if not self.beat_id or not self.narration.strip():
            raise ValueError("beat identity and narration are required")
        if not 0.35 <= self.duration_seconds <= 8.0:
            raise ValueError("beat duration is outside the supported range")
        if not self.visual_family or not self.mascot_action:
            raise ValueError("visual family and mascot action are required")
        if not 0.0 <= self.tension <= 1.0:
            raise ValueError("tension must be in [0, 1]")


@dataclass(frozen=True)
class StorySpec:
    slug: str
    title: str
    hook: str
    closing: str
    source: SourceFact
    beats: tuple[StoryBeat, ...]
    renderer_version: str = "synthetic-renderer-v1"
    judge_version: str = "synthetic-judge-v1"
    suite_version: str = "completion-suite-v1"

    def validate(self, *, today: date) -> None:
        if not self.slug or not self.title.strip() or not self.hook.strip():
            raise ValueError("story identity, title, and hook are required")
        if not any(char.isdigit() for char in self.hook + self.title):
            raise ValueError("story premise requires a consequential number")
        self.source.validate(today=today)
        if len(self.beats) < 3:
            raise ValueError("story requires at least three beats")
        for beat in self.beats:
            beat.validate()
        if self.beats[0].duration_seconds > 1.5:
            raise ValueError("hook reveal is too slow")
        if len({beat.mascot_action for beat in self.beats}) < 3:
            raise ValueError("mascot performance is too repetitive")
        if self.beats[-1].tension >= max(beat.tension for beat in self.beats[:-1]):
            raise ValueError("ending does not resolve tension")

    def canonical_payload(self) -> Mapping[str, Any]:
        return {
            "slug": self.slug,
            "title": self.title,
            "hook": self.hook,
            "closing": self.closing,
            "source": {
                "publisher": self.source.publisher,
                "url": self.source.url,
                "accessed": self.source.accessed.isoformat(),
                "claim": self.source.claim,
                "value": self.source.value,
                "unit": self.source.unit,
            },
            "beats": [
                {
                    "beat_id": beat.beat_id,
                    "narration": beat.narration,
                    "duration_seconds": beat.duration_seconds,
                    "visual_family": beat.visual_family,
                    "mascot_action": beat.mascot_action,
                    "tension": beat.tension,
                }
                for beat in self.beats
            ],
            "renderer_version": self.renderer_version,
            "judge_version": self.judge_version,
            "suite_version": self.suite_version,
        }

    @property
    def digest(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RenderBundle:
    story_slug: str
    attempt_id: str
    directory: Path
    video_path: Path
    plan_path: Path
    video_hash: str
    plan_hash: str
    renderer_version: str

    def validate(self) -> None:
        if not self.video_path.is_file() or not self.plan_path.is_file():
            raise ValueError("render bundle is incomplete")
        if sha256_file(self.video_path) != self.video_hash:
            raise ValueError("video hash mismatch")
        if sha256_file(self.plan_path) != self.plan_hash:
            raise ValueError("plan hash mismatch")


@dataclass(frozen=True)
class Verdict:
    score: float
    lowest_dimension: float
    effective_fps: float
    duplicate_ratio: float
    watched_video: bool
    hard_failures: tuple[str, ...]
    judge_version: str

    def validate(self) -> None:
        for value, name in (
            (self.score, "score"),
            (self.lowest_dimension, "lowest_dimension"),
            (self.effective_fps, "effective_fps"),
            (self.duplicate_ratio, "duplicate_ratio"),
        ):
            if not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
        if not 0 <= self.score <= 100 or not 0 <= self.lowest_dimension <= 10:
            raise ValueError("verdict score is outside bounds")
        if self.effective_fps <= 0 or not 0 <= self.duplicate_ratio <= 1:
            raise ValueError("temporal evidence is invalid")
        if not self.watched_video:
            raise ValueError("judge did not watch the video")
        if not self.judge_version:
            raise ValueError("judge version is required")

    @property
    def shippable(self) -> bool:
        self.validate()
        return (
            not self.hard_failures
            and self.score >= 90
            and self.lowest_dimension >= 8.5
            and self.effective_fps >= 24
            and self.duplicate_ratio <= 0.10
        )


@dataclass(frozen=True)
class ProofRun:
    run_id: str
    suite_version: str
    renderer_version: str
    judge_version: str
    video_hash: str
    verdict_hash: str
    score: float
    lowest_dimension: float
    effective_fps: float
    duplicate_ratio: float
    watched_video: bool
    hard_failures: tuple[str, ...] = ()

    def canonical_payload(self) -> Mapping[str, Any]:
        return {
            "run_id": self.run_id,
            "suite_version": self.suite_version,
            "renderer_version": self.renderer_version,
            "judge_version": self.judge_version,
            "video_hash": self.video_hash,
            "verdict_hash": self.verdict_hash,
            "score": self.score,
            "lowest_dimension": self.lowest_dimension,
            "effective_fps": self.effective_fps,
            "duplicate_ratio": self.duplicate_ratio,
            "watched_video": self.watched_video,
            "hard_failures": list(self.hard_failures),
        }

    @property
    def digest(self) -> str:
        raw = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PipelineResult:
    status: PipelineStatus
    story_slug: str
    canonical_release_id: str | None
    score: float | None
    reasons: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
