from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import math
import re
from typing import Any, Iterable, Mapping, Sequence


class ContentValidationError(ValueError):
    """Raised when content evidence or a compiled story is internally inconsistent."""


class Officiality(str, Enum):
    OFFICIAL = "official"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ILLUSTRATIVE = "illustrative"
    UNKNOWN = "unknown"


class ContentDomain(str, Enum):
    SCIENCE = "science"
    SPACE = "space"
    NATURE = "nature"
    HUMAN_BODY = "human_body"
    HISTORY = "history"
    GEOGRAPHY = "geography"
    TECHNOLOGY = "technology"
    ECONOMICS = "economics"
    GENERAL = "general"


class Relationship(str, Enum):
    TREND = "trend"
    RANKING = "ranking"
    COMPARISON = "comparison"
    PART_TO_WHOLE = "part_to_whole"
    SCALE = "scale"
    CHANGE = "change"
    DISTRIBUTION = "distribution"


_NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?")


def extract_numbers(text: str) -> tuple[float, ...]:
    values: list[float] = []
    for raw in _NUMBER_RE.findall(text or ""):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return tuple(values)


def _nonempty(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ContentValidationError(f"{field_name} is required")
    return clean


@dataclass(frozen=True)
class SourceRef:
    name: str
    publisher: str
    url: str
    officiality: Officiality
    access_date: date

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SourceRef":
        try:
            accessed = date.fromisoformat(str(payload.get("access_date", "")))
        except ValueError as exc:
            raise ContentValidationError("source.access_date must be ISO YYYY-MM-DD") from exc
        try:
            officiality = Officiality(str(payload.get("officiality", "unknown")).lower())
        except ValueError:
            officiality = Officiality.UNKNOWN
        return cls(
            name=_nonempty(payload.get("name", ""), "source.name"),
            publisher=_nonempty(payload.get("publisher", ""), "source.publisher"),
            url=_nonempty(payload.get("url", ""), "source.url"),
            officiality=officiality,
            access_date=accessed,
        )

    @property
    def publishable(self) -> bool:
        return self.officiality in {
            Officiality.OFFICIAL,
            Officiality.PRIMARY,
            Officiality.SECONDARY,
        }


@dataclass(frozen=True)
class DataPoint:
    label: str
    value: float
    context: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DataPoint":
        label = _nonempty(payload.get("label", ""), "point.label")
        raw = payload.get("value")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ContentValidationError(f"point {label!r} requires a numeric value")
        value = float(raw)
        if not math.isfinite(value):
            raise ContentValidationError(f"point {label!r} value must be finite")
        context = {k: v for k, v in payload.items() if k not in {"label", "value"}}
        return cls(label=label, value=value, context=context)


@dataclass(frozen=True)
class Dataset:
    key: str
    title: str
    unit: str
    geography: str
    time_coverage: str
    source: SourceRef
    points: tuple[DataPoint, ...]
    baseline: DataPoint | None = None
    notes: str = ""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Dataset":
        raw_points = payload.get("points")
        if not isinstance(raw_points, Sequence) or isinstance(raw_points, (str, bytes)):
            raise ContentValidationError("dataset.points must be a list")
        points = tuple(DataPoint.from_dict(item) for item in raw_points)
        if not points:
            raise ContentValidationError("dataset requires at least one point")
        labels = [point.label.casefold() for point in points]
        if len(labels) != len(set(labels)):
            raise ContentValidationError("dataset point labels must be unique")
        baseline_payload = payload.get("baseline")
        baseline = DataPoint.from_dict(baseline_payload) if isinstance(baseline_payload, Mapping) else None
        return cls(
            key=_nonempty(payload.get("key", ""), "dataset.key"),
            title=_nonempty(payload.get("title", ""), "dataset.title"),
            unit=_nonempty(payload.get("unit", ""), "dataset.unit"),
            geography=_nonempty(payload.get("geography", ""), "dataset.geography"),
            time_coverage=_nonempty(payload.get("time_coverage", ""), "dataset.time_coverage"),
            source=SourceRef.from_dict(payload.get("source") or {}),
            points=points,
            baseline=baseline,
            notes=str(payload.get("notes", "")).strip(),
        )

    def point(self, label: str) -> DataPoint:
        match = next((point for point in self.points if point.label.casefold() == label.casefold()), None)
        if match is None:
            raise ContentValidationError(f"dataset {self.key!r} has no point {label!r}")
        return match

    @property
    def value_range(self) -> float:
        values = [point.value for point in self.points]
        return max(values) - min(values)


@dataclass(frozen=True)
class PremiseCandidate:
    candidate_id: str
    title: str
    hook: str
    expectation: str
    reversal: str
    stakes: str
    hero_number: float
    hero_label: str
    unit: str
    domain: ContentDomain
    relationship: Relationship
    visual_form: str
    score: float = 0.0
    score_reasons: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        return not self.rejection_reasons and self.score >= 0


@dataclass(frozen=True)
class ClaimBinding:
    claim_id: str
    text: str
    dataset_key: str
    point_labels: tuple[str, ...]
    expected_numbers: tuple[float, ...]
    relationship: Relationship
    unit: str

    def validate_against(self, dataset: Dataset, *, tolerance: float = 0.011) -> None:
        if dataset.key != self.dataset_key:
            raise ContentValidationError(
                f"claim {self.claim_id} expected dataset {self.dataset_key!r}, got {dataset.key!r}"
            )
        if not self.point_labels:
            raise ContentValidationError(f"claim {self.claim_id} must bind at least one point")
        actual = tuple(dataset.point(label).value for label in self.point_labels)
        if len(actual) != len(self.expected_numbers):
            raise ContentValidationError(f"claim {self.claim_id} number count does not match bindings")
        for label, expected, observed in zip(self.point_labels, self.expected_numbers, actual):
            allowed = max(abs(observed) * tolerance, 0.05)
            if abs(expected - observed) > allowed:
                raise ContentValidationError(
                    f"claim {self.claim_id} value for {label!r} is {expected}, source says {observed}"
                )
        spoken = extract_numbers(self.text)
        for expected in self.expected_numbers:
            if not any(abs(value - expected) <= max(abs(expected) * tolerance, 0.05) for value in spoken):
                raise ContentValidationError(
                    f"claim {self.claim_id} does not state source value {expected:g} in its text"
                )


@dataclass(frozen=True)
class VisualIntent:
    relationship: Relationship
    primary_focus: str
    required_affordances: frozenset[str]
    forbidden_distortions: frozenset[str]
    mascot_objective: str
    payoff: str


@dataclass(frozen=True)
class StoryBeat:
    beat_id: str
    role: str
    narration: str
    claim_ids: tuple[str, ...]
    visual: VisualIntent
    estimated_seconds: float

    def validate(self) -> None:
        _nonempty(self.beat_id, "beat_id")
        _nonempty(self.role, "beat.role")
        _nonempty(self.narration, "beat.narration")
        if not self.claim_ids:
            raise ContentValidationError(f"beat {self.beat_id} must use at least one claim")
        if not 1.0 <= self.estimated_seconds <= 20.0:
            raise ContentValidationError(
                f"beat {self.beat_id} estimated_seconds must be between 1 and 20"
            )


@dataclass(frozen=True)
class StoryPackage:
    slug: str
    premise: PremiseCandidate
    datasets: tuple[Dataset, ...]
    claims: tuple[ClaimBinding, ...]
    beats: tuple[StoryBeat, ...]
    closing: str
    question: str
    hashtags: tuple[str, ...]

    def validate(self) -> None:
        _nonempty(self.slug, "story.slug")
        if not self.premise.eligible:
            raise ContentValidationError("story premise is not eligible")
        if not self.datasets:
            raise ContentValidationError("story requires datasets")
        dataset_map = {dataset.key: dataset for dataset in self.datasets}
        if len(dataset_map) != len(self.datasets):
            raise ContentValidationError("story datasets must have unique keys")
        claim_map = {claim.claim_id: claim for claim in self.claims}
        if len(claim_map) != len(self.claims):
            raise ContentValidationError("story claims must have unique IDs")
        for claim in self.claims:
            dataset = dataset_map.get(claim.dataset_key)
            if dataset is None:
                raise ContentValidationError(
                    f"claim {claim.claim_id} references missing dataset {claim.dataset_key!r}"
                )
            claim.validate_against(dataset)
        used_claims: set[str] = set()
        for beat in self.beats:
            beat.validate()
            for claim_id in beat.claim_ids:
                if claim_id not in claim_map:
                    raise ContentValidationError(
                        f"beat {beat.beat_id} references missing claim {claim_id!r}"
                    )
                used_claims.add(claim_id)
        unused = set(claim_map) - used_claims
        if unused:
            raise ContentValidationError(f"story has unused claims: {sorted(unused)}")
        if len(self.beats) < 2:
            raise ContentValidationError("story needs at least two beats")
        _nonempty(self.closing, "story.closing")
        _nonempty(self.question, "story.question")
        if not self.hashtags:
            raise ContentValidationError("story requires hashtags")

    @property
    def estimated_seconds(self) -> float:
        return sum(beat.estimated_seconds for beat in self.beats)


def numbers_supported(text: str, supported: Iterable[float], *, tolerance: float = 0.011) -> bool:
    supported_values = tuple(float(value) for value in supported)
    for value in extract_numbers(text):
        if not any(abs(value - allowed) <= max(abs(allowed) * tolerance, 0.05) for allowed in supported_values):
            return False
    return True
