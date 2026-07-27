from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class Maturity(str, Enum):
    PROTOTYPE = "prototype"
    SHADOW = "shadow"
    CANARY = "canary"
    PRODUCTION = "production"


class Verdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    UNKNOWN = "unknown"


class CapabilityKind(str, Enum):
    RESEARCH = "research"
    CREATIVE = "creative"
    MEDIA = "media"
    AUDIO = "audio"
    VIDEO = "video"
    QA = "qa"
    LEARNING = "learning"
    STORAGE = "storage"


class CostClass(str, Enum):
    FREE_LOCAL = "free_local"
    FREE_API = "free_api"
    METERED = "metered"
    EXPENSIVE = "expensive"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_id(prefix: str, value: Any) -> str:
    digest = sha256(canonical_json(value).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


@dataclass(frozen=True)
class SecretRequirement:
    name: str
    provider: str
    required: bool = False
    purpose: str = ""


@dataclass(frozen=True)
class ToolRequirement:
    executable: str
    purpose: str
    optional: bool = True
    install_hint: str = ""


@dataclass(frozen=True)
class RequestPlan:
    provider: str
    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    query: Mapping[str, str] = field(default_factory=dict)
    json_body: Mapping[str, Any] = field(default_factory=dict)
    output_kind: str = "json"
    secret_names: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def request_id(self) -> str:
        return stable_id("req", asdict(self))


@dataclass(frozen=True)
class CommandPlan:
    tool: str
    argv: tuple[str, ...]
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    env_names: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def command_id(self) -> str:
        return stable_id("cmd", asdict(self))


@dataclass(frozen=True)
class EvidenceClaim:
    claim: str
    source_url: str
    publisher: str
    accessed_at: str
    source_type: str
    supports: str
    confidence: float
    published_at: str | None = None
    rights_note: str = ""

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.claim.strip():
            failures.append("claim_missing")
        if not self.source_url.startswith(("https://", "http://")):
            failures.append("source_url_invalid")
        if not self.publisher.strip():
            failures.append("publisher_missing")
        if not 0.0 <= self.confidence <= 1.0:
            failures.append("confidence_out_of_range")
        if not self.supports.strip():
            failures.append("support_target_missing")
        return tuple(failures)


@dataclass(frozen=True)
class MediaAsset:
    provider: str
    asset_id: str
    source_url: str
    download_url: str
    media_type: str
    width: int = 0
    height: int = 0
    duration_seconds: float = 0.0
    license_code: str = "unknown"
    attribution: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    content_hash: str = ""

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0


@dataclass(frozen=True)
class AudienceSignal:
    source_video_id: str
    comment_id: str
    text: str
    likes: int = 0
    reply_count: int = 0
    categories: tuple[str, ...] = ()
    extracted_phrases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompetitorObservation:
    video_id: str
    title: str
    duration_seconds: float
    age_hours: float
    views: int
    hook_text: str = ""
    first_frame_text: str = ""
    first_five_second_cuts: int = 0
    payoff_second: float | None = None
    caption_position: str = "unknown"
    visual_change_seconds: tuple[float, ...] = ()

    @property
    def views_per_hour(self) -> float:
        return self.views / max(self.age_hours, 1.0)


@dataclass(frozen=True)
class CreativeVariant:
    variant_id: str
    kind: str
    text: str
    visual_brief: str = ""
    structure: str = ""
    estimated_cost: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreCard:
    candidate_id: str
    scores: Mapping[str, float]
    hard_failures: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def weighted_total(self, weights: Mapping[str, float]) -> float:
        if self.hard_failures:
            return float("-inf")
        return sum(float(self.scores.get(name, 0.0)) * weight for name, weight in weights.items())


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    title: str
    kind: CapabilityKind
    summary: str
    maturity: Maturity = Maturity.PROTOTYPE
    cost_class: CostClass = CostClass.FREE_LOCAL
    secret_requirements: tuple[SecretRequirement, ...] = ()
    tool_requirements: tuple[ToolRequirement, ...] = ()
    production_imports: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChannelProfile:
    channel: str
    accepted_topics: tuple[str, ...]
    preferred_formats: tuple[str, ...]
    forbidden_topics: tuple[str, ...] = ()
    voice_style: str = "neutral"


@dataclass(frozen=True)
class CapabilityTruthRecord:
    capability_id: str
    channel: str
    code_exists: bool
    secret_configured: bool | None
    workflow_passes_secret: bool | None
    imported_by_runtime: bool
    last_invoked_at: str | None = None
    last_success_at: str | None = None
    fallback_available: bool = False
    status_note: str = ""


@dataclass(frozen=True)
class ReplayArtifact:
    role: str
    path: str
    sha256: str
    bytes: int


@dataclass(frozen=True)
class ReplayBundle:
    run_id: str
    channel: str
    created_at: str
    artifacts: tuple[ReplayArtifact, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def tupled(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(values or ())
