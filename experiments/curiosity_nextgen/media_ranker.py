"""Metadata-first media candidate ranking prototype.

This code is dormant and intentionally disconnected from the live media gateway.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class MediaRequirements:
    query: str
    required_subjects: frozenset[str] = frozenset()
    geography: str | None = None
    era_start: int | None = None
    era_end: int | None = None
    min_width: int = 1280
    min_height: int = 720
    allowed_licenses: frozenset[str] = frozenset({
        "public_domain", "cc_by", "licensed", "provider_api"
    })
    allow_visible_text: bool = False
    allow_brand_dominance: bool = False
    recent_asset_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MediaCandidate:
    asset_id: str
    source: str
    width: int
    height: int
    semantic_score: float
    composition_score: float
    continuity_score: float
    uniqueness_score: float
    license: str
    subjects: frozenset[str] = frozenset()
    geography: str | None = None
    year: int | None = None
    detected_text: tuple[str, ...] = ()
    dominant_brand: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("semantic_score", "composition_score", "continuity_score", "uniqueness_score"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class RankedCandidate:
    candidate: MediaCandidate
    score: float
    rejected: bool
    rejection_reasons: tuple[str, ...]
    score_breakdown: dict[str, float]


def _normal(value: str | None) -> str | None:
    return value.casefold().strip() if value else None


def evaluate_candidate(candidate: MediaCandidate,
                       requirements: MediaRequirements) -> RankedCandidate:
    reasons: list[str] = []
    if candidate.width < requirements.min_width or candidate.height < requirements.min_height:
        reasons.append("resolution below requirement")
    if candidate.license not in requirements.allowed_licenses:
        reasons.append(f"license {candidate.license!r} not allowed")
    missing_subjects = requirements.required_subjects - candidate.subjects
    if missing_subjects:
        reasons.append("missing subjects: " + ", ".join(sorted(missing_subjects)))
    if requirements.geography and candidate.geography and _normal(requirements.geography) != _normal(candidate.geography):
        reasons.append(f"geography mismatch: {candidate.geography!r}")
    if candidate.year is not None:
        if requirements.era_start is not None and candidate.year < requirements.era_start:
            reasons.append("asset predates required era")
        if requirements.era_end is not None and candidate.year > requirements.era_end:
            reasons.append("asset postdates required era")
    if candidate.detected_text and not requirements.allow_visible_text:
        reasons.append("visible text/signage not allowed")
    if candidate.dominant_brand and not requirements.allow_brand_dominance:
        reasons.append("dominant brand not allowed")
    if candidate.asset_id in requirements.recent_asset_ids:
        reasons.append("asset used recently")

    breakdown = {
        "semantic": candidate.semantic_score * 0.40,
        "composition": candidate.composition_score * 0.22,
        "continuity": candidate.continuity_score * 0.18,
        "uniqueness": candidate.uniqueness_score * 0.15,
        "resolution_bonus": min(candidate.width / 3840, 1.0) * 0.05,
    }
    score = sum(breakdown.values()) - min(0.75, len(reasons) * 0.15)
    return RankedCandidate(candidate, round(score, 4), bool(reasons), tuple(reasons),
                           {key: round(value, 4) for key, value in breakdown.items()})


def rank_candidates(candidates: Iterable[MediaCandidate],
                    requirements: MediaRequirements,
                    *, include_rejected: bool = True) -> list[RankedCandidate]:
    ranked = [evaluate_candidate(item, requirements) for item in candidates]
    if not include_rejected:
        ranked = [item for item in ranked if not item.rejected]
    return sorted(ranked, key=lambda item: (item.rejected, -item.score, item.candidate.asset_id))


def select_best(candidates: Iterable[MediaCandidate],
                requirements: MediaRequirements) -> RankedCandidate | None:
    ranked = rank_candidates(candidates, requirements, include_rejected=False)
    return ranked[0] if ranked else None
