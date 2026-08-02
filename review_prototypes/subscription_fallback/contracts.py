from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256(canonical_json(value).encode('utf-8')).hexdigest()[:20]}"


class ProviderKind(str, Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    TEMPLATE = "template"
    BUFFER = "buffer"


class DegradationLevel(str, Enum):
    FULL = "full"
    ACCEPTABLE = "acceptable"
    DEGRADED = "degraded"
    BUFFERED = "buffered"
    BLOCKED = "blocked"


class QueueStatus(str, Enum):
    READY = "ready"
    CLAIMED = "claimed"
    POSTED = "posted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class EvidenceFact:
    metric: str
    current_value: str
    source_name: str
    source_url: str
    accessed_at: str
    previous_value: str = ""
    comparison: str = ""
    verified_cause: str = ""
    next_metric: str = ""
    units: str = ""
    published_at: str = ""
    raw_response_sha256: str = ""

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.metric.strip():
            failures.append("metric_missing")
        if not self.current_value.strip():
            failures.append("current_value_missing")
        if not self.source_name.strip():
            failures.append("source_name_missing")
        if not self.source_url.startswith(("https://", "http://")):
            failures.append("source_url_invalid")
        if not self.accessed_at.strip():
            failures.append("accessed_at_missing")
        return tuple(failures)


@dataclass(frozen=True)
class GenerationRequest:
    channel: str
    topic: str
    facts: tuple[EvidenceFact, ...]
    duration_seconds: int = 45
    format: str = "narrated_explainer"
    evergreen: bool = False
    requested_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.channel.strip() or not self.topic.strip():
            raise ValueError("channel and topic are required")
        if not 10 <= self.duration_seconds <= 180:
            raise ValueError("duration_seconds must be between 10 and 180")

    @property
    def request_id(self) -> str:
        return stable_id("gen", asdict(self))


@dataclass(frozen=True)
class GeneratedPackage:
    package_id: str
    channel: str
    topic: str
    provider: ProviderKind
    degradation: DegradationLevel
    script: str
    title: str
    description: str
    source_urls: tuple[str, ...]
    artifact_paths: Mapping[str, str] = field(default_factory=dict)
    qa_passed: bool = False
    approved: bool = False
    evergreen: bool = False
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def content_fingerprint(self) -> str:
        payload = {
            "channel": self.channel,
            "topic": self.topic,
            "script": self.script,
            "source_urls": self.source_urls,
            "artifact_paths": dict(self.artifact_paths),
        }
        return sha256(canonical_json(payload).encode("utf-8")).hexdigest()

    def postable(self) -> bool:
        return self.qa_passed and self.approved and self.degradation is not DegradationLevel.BLOCKED


@dataclass(frozen=True)
class QueueItem:
    package: GeneratedPackage
    status: QueueStatus = QueueStatus.READY
    priority: int = 100
    available_at: str = ""
    claim_token: str = ""
    claimed_at: str = ""
    posted_at: str = ""
    upload_id: str = ""
    rejection_reason: str = ""

    @property
    def queue_id(self) -> str:
        return stable_id("queue", {"package_id": self.package.package_id, "channel": self.package.channel})


@dataclass(frozen=True)
class ProviderAttempt:
    provider: ProviderKind
    ok: bool
    reason: str
    started_at: str
    ended_at: str
    package_id: str = ""


@dataclass(frozen=True)
class GenerationResult:
    request_id: str
    package: GeneratedPackage | None
    attempts: tuple[ProviderAttempt, ...]
    enqueued: bool
    reason: str


@dataclass(frozen=True)
class PostingClaim:
    item: QueueItem | None
    claim_token: str
    reason: str


@dataclass(frozen=True)
class UploadReservation:
    idempotency_key: str
    content_fingerprint: str
    state: str
    reserved_at: str
    completed_at: str = ""
    external_upload_id: str = ""
    failure_reason: str = ""
