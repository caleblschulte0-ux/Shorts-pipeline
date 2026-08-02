"""Immutable reference contracts for the isolated Professional Media OS prototype.

These types deliberately avoid production imports and third-party dependencies. They are
intended to make future migrations explicit, versioned, and reviewable rather than to be
used as a drop-in production package.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:/-]{2,127}$")


class ContractError(ValueError):
    """Raised when a prototype record violates an explicit contract."""


class Maturity(str, Enum):
    ANECDOTE = "anecdote"
    DIRECTIONAL = "directional"
    EXPERIMENTAL = "experimental"
    ESTABLISHED = "established"
    DEPRECATED = "deprecated"


class KnowledgeKind(str, Enum):
    OBSERVATION = "observation"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"
    DECISION = "decision"


class EvaluationVerdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


class ExperimentState(str, Enum):
    DRAFT = "draft"
    SHADOW = "shadow"
    CANARY = "canary"
    COMPLETE = "complete"
    STOPPED = "stopped"
    ADOPTED = "adopted"
    REJECTED = "rejected"


class FunnelStage(str, Enum):
    EXPOSURE = "exposure"
    HOOK = "hook"
    BODY = "body"
    ENDING = "ending"
    SATISFACTION = "satisfaction"
    EXPANSION = "expansion"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_id(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ContractError(
            f"{field_name} must be 3-128 characters and contain only stable id characters"
        )


def _require_unit_interval(value: float, field_name: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ContractError(f"{field_name} must be a finite number")
    if not 0.0 <= float(value) <= 1.0:
        raise ContractError(f"{field_name} must be between 0 and 1")


def _require_non_negative(value: float, field_name: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ContractError(f"{field_name} must be a finite number")
    if float(value) < 0:
        raise ContractError(f"{field_name} must be non-negative")


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field_name} must be non-empty")


def to_primitive(value: Any) -> Any:
    """Convert a contract or nested value to a stable JSON-compatible structure."""

    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [to_primitive(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_primitive(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source_type: str
    locator: str
    observed_at: str
    confidence: float
    rights_status: str = "unknown"
    excerpt_hash: Optional[str] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    review_after: Optional[str] = None
    maturity: Maturity = Maturity.ANECDOTE
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_id(self.evidence_id, "evidence_id")
        _require_nonempty(self.source_type, "source_type")
        _require_nonempty(self.locator, "locator")
        _require_nonempty(self.observed_at, "observed_at")
        _require_unit_interval(self.confidence, "confidence")
        _require_nonempty(self.rights_status, "rights_status")


@dataclass(frozen=True)
class ContentGenome:
    genome_id: str
    schema_version: str
    channel_id: str
    subject_entities: Tuple[str, ...]
    event_type: str
    viewer_question: str
    emotional_driver: str
    payoff_type: str
    hook_structure: str
    first_visual_type: str
    first_subject_ms: int
    first_proof_ms: Optional[int]
    narrative_structure: str
    beat_count: int
    reveal_position: float
    open_loop_count: int
    presentation_format: str
    caption_style: str
    average_shot_seconds: float
    visual_sources: Tuple[str, ...]
    title_pattern: str
    duration_seconds: float
    evidence_completeness: float
    media_feasibility: float
    rights_risk: str
    estimated_cost: float
    estimated_runtime_seconds: float
    novelty_score: float
    tags: Tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_id(self.genome_id, "genome_id")
        _require_nonempty(self.schema_version, "schema_version")
        _require_id(self.channel_id, "channel_id")
        if not self.subject_entities:
            raise ContractError("subject_entities must contain at least one entity")
        for field_name in (
            "event_type",
            "viewer_question",
            "emotional_driver",
            "payoff_type",
            "hook_structure",
            "first_visual_type",
            "narrative_structure",
            "presentation_format",
            "caption_style",
            "title_pattern",
            "rights_risk",
        ):
            _require_nonempty(getattr(self, field_name), field_name)
        if self.first_subject_ms < 0:
            raise ContractError("first_subject_ms must be non-negative")
        if self.first_proof_ms is not None and self.first_proof_ms < 0:
            raise ContractError("first_proof_ms must be non-negative when supplied")
        if self.beat_count < 2:
            raise ContractError("beat_count must be at least 2")
        if self.open_loop_count < 0:
            raise ContractError("open_loop_count must be non-negative")
        _require_unit_interval(self.reveal_position, "reveal_position")
        _require_unit_interval(self.evidence_completeness, "evidence_completeness")
        _require_unit_interval(self.media_feasibility, "media_feasibility")
        _require_unit_interval(self.novelty_score, "novelty_score")
        _require_non_negative(self.average_shot_seconds, "average_shot_seconds")
        _require_non_negative(self.duration_seconds, "duration_seconds")
        _require_non_negative(self.estimated_cost, "estimated_cost")
        _require_non_negative(self.estimated_runtime_seconds, "estimated_runtime_seconds")
        if self.duration_seconds <= 0:
            raise ContractError("duration_seconds must be greater than zero")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    hypothesis_id: str
    genome: ContentGenome
    promise: str
    opening_line: str
    payoff_line: str
    evidence_ids: Tuple[str, ...]
    estimated_value: float
    exploration: bool = False
    parent_candidate_id: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_id(self.candidate_id, "candidate_id")
        _require_id(self.hypothesis_id, "hypothesis_id")
        _require_nonempty(self.promise, "promise")
        _require_nonempty(self.opening_line, "opening_line")
        _require_nonempty(self.payoff_line, "payoff_line")
        _require_non_negative(self.estimated_value, "estimated_value")
        if self.parent_candidate_id is not None:
            _require_id(self.parent_candidate_id, "parent_candidate_id")


@dataclass(frozen=True)
class EvaluationFinding:
    code: str
    message: str
    verdict: EvaluationVerdict
    confidence: float
    evidence_ids: Tuple[str, ...] = ()
    repair_hint: Optional[str] = None

    def __post_init__(self) -> None:
        _require_id(self.code, "code")
        _require_nonempty(self.message, "message")
        _require_unit_interval(self.confidence, "confidence")


@dataclass(frozen=True)
class CandidateEvaluation:
    evaluation_id: str
    candidate_id: str
    evaluator_id: str
    evaluator_version: str
    findings: Tuple[EvaluationFinding, ...]
    utility: Optional[float]
    evaluated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_id(self.evaluation_id, "evaluation_id")
        _require_id(self.candidate_id, "candidate_id")
        _require_id(self.evaluator_id, "evaluator_id")
        _require_nonempty(self.evaluator_version, "evaluator_version")
        if self.utility is not None:
            _require_unit_interval(self.utility, "utility")

    @property
    def blocked(self) -> bool:
        return any(item.verdict is EvaluationVerdict.BLOCK for item in self.findings)


@dataclass(frozen=True)
class TournamentResult:
    tournament_id: str
    ranked_candidate_ids: Tuple[str, ...]
    blocked_candidate_ids: Tuple[str, ...]
    utilities: Mapping[str, float]
    reasons: Mapping[str, Tuple[str, ...]]
    evaluator_versions: Mapping[str, str]
    selected_candidate_id: Optional[str]
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_id(self.tournament_id, "tournament_id")
        if self.selected_candidate_id is not None:
            _require_id(self.selected_candidate_id, "selected_candidate_id")
        overlap = set(self.ranked_candidate_ids).intersection(self.blocked_candidate_ids)
        if overlap:
            raise ContractError(f"candidates cannot be both ranked and blocked: {sorted(overlap)}")


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    hypothesis: str
    channel_ids: Tuple[str, ...]
    treatment: str
    control: str
    primary_metric: str
    guardrail_metrics: Tuple[str, ...]
    minimum_eligible_videos: int
    minimum_views_per_video: int
    maximum_allocation: float
    stop_conditions: Tuple[str, ...]
    state: ExperimentState = ExperimentState.DRAFT
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_id(self.experiment_id, "experiment_id")
        _require_nonempty(self.hypothesis, "hypothesis")
        _require_nonempty(self.treatment, "treatment")
        _require_nonempty(self.control, "control")
        _require_nonempty(self.primary_metric, "primary_metric")
        if self.minimum_eligible_videos < 1:
            raise ContractError("minimum_eligible_videos must be at least 1")
        if self.minimum_views_per_video < 1:
            raise ContractError("minimum_views_per_video must be at least 1")
        _require_unit_interval(self.maximum_allocation, "maximum_allocation")
        if self.maximum_allocation <= 0:
            raise ContractError("maximum_allocation must be greater than zero")


@dataclass(frozen=True)
class PatternRecord:
    pattern_id: str
    name: str
    applies_to: Tuple[str, ...]
    excludes: Tuple[str, ...]
    structure: Tuple[str, ...]
    strengths: Mapping[str, str]
    failure_modes: Tuple[str, ...]
    evidence_ids: Tuple[str, ...]
    maturity: Maturity
    confidence: float
    version: str
    review_after: Optional[str]

    def __post_init__(self) -> None:
        _require_id(self.pattern_id, "pattern_id")
        _require_nonempty(self.name, "name")
        _require_nonempty(self.version, "version")
        _require_unit_interval(self.confidence, "confidence")
        if not self.structure:
            raise ContractError("structure must contain at least one step")


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    title: str
    rationale: str
    applies_to: Tuple[str, ...]
    excludes: Tuple[str, ...]
    evidence_ids: Tuple[str, ...]
    approved_by: str
    rollback: str
    maturity: Maturity
    confidence: float
    policy_version: str
    supersedes: Optional[str] = None
    review_after: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_id(self.decision_id, "decision_id")
        _require_nonempty(self.title, "title")
        _require_nonempty(self.rationale, "rationale")
        _require_nonempty(self.approved_by, "approved_by")
        _require_nonempty(self.rollback, "rollback")
        _require_nonempty(self.policy_version, "policy_version")
        _require_unit_interval(self.confidence, "confidence")
        if self.supersedes is not None:
            _require_id(self.supersedes, "supersedes")


@dataclass(frozen=True)
class PortfolioConstraints:
    target_count: int
    maximum_total_cost: float
    maximum_total_runtime_seconds: float
    maximum_per_topic: int
    maximum_per_channel: Mapping[str, int]
    minimum_exploration: int
    allowed_rights_risks: Tuple[str, ...]
    minimum_evidence_completeness: float
    minimum_media_feasibility: float

    def __post_init__(self) -> None:
        if self.target_count < 1:
            raise ContractError("target_count must be at least 1")
        _require_non_negative(self.maximum_total_cost, "maximum_total_cost")
        _require_non_negative(
            self.maximum_total_runtime_seconds, "maximum_total_runtime_seconds"
        )
        if self.maximum_per_topic < 1:
            raise ContractError("maximum_per_topic must be at least 1")
        if self.minimum_exploration < 0:
            raise ContractError("minimum_exploration must be non-negative")
        if self.minimum_exploration > self.target_count:
            raise ContractError("minimum_exploration cannot exceed target_count")
        _require_unit_interval(
            self.minimum_evidence_completeness, "minimum_evidence_completeness"
        )
        _require_unit_interval(self.minimum_media_feasibility, "minimum_media_feasibility")


@dataclass(frozen=True)
class PortfolioPlan:
    plan_id: str
    selected_candidate_ids: Tuple[str, ...]
    rejected_reasons: Mapping[str, Tuple[str, ...]]
    total_cost: float
    total_runtime_seconds: float
    exploration_count: int
    constraint_hash: str
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require_id(self.plan_id, "plan_id")
        _require_non_negative(self.total_cost, "total_cost")
        _require_non_negative(self.total_runtime_seconds, "total_runtime_seconds")
        if self.exploration_count < 0:
            raise ContractError("exploration_count must be non-negative")


@dataclass(frozen=True)
class StageMetrics:
    stage: FunnelStage
    eligible: bool
    sample_size: int
    value: Optional[float]
    metric_name: str
    metric_definition_version: str
    observed_at: str

    def __post_init__(self) -> None:
        if self.sample_size < 0:
            raise ContractError("sample_size must be non-negative")
        _require_nonempty(self.metric_name, "metric_name")
        _require_nonempty(self.metric_definition_version, "metric_definition_version")
        _require_nonempty(self.observed_at, "observed_at")
        if self.value is not None and not math.isfinite(float(self.value)):
            raise ContractError("value must be finite when supplied")
        if not self.eligible and self.value is not None:
            raise ContractError("ineligible stage metrics must keep value unknown")


@dataclass(frozen=True)
class VideoOutcome:
    video_id: str
    candidate_id: str
    channel_id: str
    genome_id: str
    stages: Tuple[StageMetrics, ...]
    timeline_events_ms: Mapping[str, int]
    production_cost: float
    production_runtime_seconds: float
    observed_at: str

    def __post_init__(self) -> None:
        _require_id(self.video_id, "video_id")
        _require_id(self.candidate_id, "candidate_id")
        _require_id(self.channel_id, "channel_id")
        _require_id(self.genome_id, "genome_id")
        _require_non_negative(self.production_cost, "production_cost")
        _require_non_negative(self.production_runtime_seconds, "production_runtime_seconds")
        if len({metric.stage for metric in self.stages}) != len(self.stages):
            raise ContractError("stages must contain at most one metric per funnel stage")
        for name, timestamp in self.timeline_events_ms.items():
            _require_nonempty(name, "timeline event name")
            if timestamp < 0:
                raise ContractError("timeline event timestamps must be non-negative")


def ensure_unique_ids(records: Iterable[Any], attribute: str) -> None:
    seen = set()
    for record in records:
        value = getattr(record, attribute)
        if value in seen:
            raise ContractError(f"duplicate {attribute}: {value}")
        seen.add(value)
