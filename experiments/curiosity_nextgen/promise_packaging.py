from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TitleCandidate:
    title_id: str
    text: str
    specificity: float
    curiosity: float
    credibility: float
    payoff_alignment: float

    def __post_init__(self) -> None:
        if not self.title_id.strip() or not self.text.strip():
            raise ValueError("title_id and text are required")
        for value, name in ((self.specificity, "specificity"), (self.curiosity, "curiosity"), (self.credibility, "credibility"), (self.payoff_alignment, "payoff_alignment")):
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")


@dataclass(frozen=True)
class ThumbnailConcept:
    concept_id: str
    subject_count: int
    text: str
    focal_clarity: float
    contrast: float
    curiosity: float
    payoff_alignment: float
    duplicates_title: bool = False

    def __post_init__(self) -> None:
        if not self.concept_id.strip():
            raise ValueError("concept_id is required")
        if self.subject_count < 1:
            raise ValueError("subject_count must be positive")
        for value, name in ((self.focal_clarity, "focal_clarity"), (self.contrast, "contrast"), (self.curiosity, "curiosity"), (self.payoff_alignment, "payoff_alignment")):
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")


@dataclass(frozen=True)
class PackagingResult:
    title_id: str
    concept_id: str
    score: float
    defects: tuple[str, ...]


def evaluate_packaging(title: TitleCandidate, thumbnail: ThumbnailConcept) -> PackagingResult:
    defects: list[str] = []
    score = (
        title.specificity * 1.1
        + title.curiosity * 1.2
        + title.credibility * 1.0
        + title.payoff_alignment * 1.4
        + thumbnail.focal_clarity * 1.3
        + thumbnail.contrast * 0.8
        + thumbnail.curiosity * 1.1
        + thumbnail.payoff_alignment * 1.4
    ) / 9.3

    title_length = len(title.text.strip())
    if title_length < 28:
        defects.append("title_too_vague_or_short")
        score -= 0.6
    if title_length > 72:
        defects.append("title_too_long")
        score -= 0.6
    if any(token in title.text.lower() for token in ("you won't believe", "insane", "shocking truth")):
        defects.append("unearned_hype")
        score -= 1.0
    if len(thumbnail.text.split()) > 5:
        defects.append("thumbnail_text_overload")
        score -= 0.7
    if thumbnail.subject_count > 3:
        defects.append("too_many_thumbnail_subjects")
        score -= 0.7
    if thumbnail.duplicates_title:
        defects.append("title_thumbnail_redundancy")
        score -= 0.6
    if min(title.payoff_alignment, thumbnail.payoff_alignment) < 6:
        defects.append("packaging_promise_mismatch")
        score -= 1.0
    if thumbnail.focal_clarity < 6:
        defects.append("weak_thumbnail_focal_point")
        score -= 0.8
    if title.credibility < 6:
        defects.append("credibility_risk")
        score -= 0.8

    return PackagingResult(title.title_id, thumbnail.concept_id, round(max(0.0, min(10.0, score)), 3), tuple(sorted(defects)))


def rank_packaging(titles: Iterable[TitleCandidate], thumbnails: Iterable[ThumbnailConcept]) -> tuple[PackagingResult, ...]:
    title_items = tuple(titles)
    thumbnail_items = tuple(thumbnails)
    if len({item.title_id for item in title_items}) != len(title_items):
        raise ValueError("duplicate title_id")
    if len({item.concept_id for item in thumbnail_items}) != len(thumbnail_items):
        raise ValueError("duplicate concept_id")
    results = [evaluate_packaging(title, thumbnail) for title in title_items for thumbnail in thumbnail_items]
    return tuple(sorted(results, key=lambda item: (-item.score, len(item.defects), item.title_id, item.concept_id)))
