from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ChapterNeed:
    chapter_id: str
    topic_family: str
    emotional_tone: str
    requires_text: bool = True
    requires_character: bool = False
    requires_real_media: bool = False


@dataclass(frozen=True)
class TransitionFamily:
    family_id: str
    compatible_topics: frozenset[str] = frozenset()
    compatible_tones: frozenset[str] = frozenset()
    supports_text: bool = True
    supports_character: bool = False
    supports_real_media: bool = False
    recent_use_count: int = 0


@dataclass(frozen=True)
class ChapterAssignment:
    chapter_id: str
    family_id: str
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ChapterStylePlan:
    assignments: tuple[ChapterAssignment, ...]
    family_counts: dict[str, int]
    dominant_share: float
    violations: tuple[str, ...]


def _compatibility(need: ChapterNeed, family: TransitionFamily) -> tuple[float, list[str]]:
    score = 5.0
    reasons: list[str] = []
    if family.compatible_topics:
        if need.topic_family in family.compatible_topics:
            score += 1.5
            reasons.append("topic_match")
        else:
            score -= 1.0
    if family.compatible_tones:
        if need.emotional_tone in family.compatible_tones:
            score += 1.25
            reasons.append("tone_match")
        else:
            score -= 0.75
    if need.requires_text and not family.supports_text:
        return -100.0, ["missing_text_support"]
    if need.requires_character and not family.supports_character:
        return -100.0, ["missing_character_support"]
    if need.requires_real_media and not family.supports_real_media:
        return -100.0, ["missing_real_media_support"]
    score -= min(2.0, family.recent_use_count * 0.35)
    if family.recent_use_count:
        reasons.append("recent_use_penalty")
    return score, reasons


def plan_chapter_styles(
    chapters: Iterable[ChapterNeed],
    families: Iterable[TransitionFamily],
    *,
    max_family_share: float = 0.4,
    max_consecutive_same: int = 1,
) -> ChapterStylePlan:
    ordered_chapters = tuple(chapters)
    available = tuple(families)
    if not ordered_chapters:
        return ChapterStylePlan((), {}, 0.0, ())
    if not available:
        raise ValueError("at least one transition family is required")
    if len({chapter.chapter_id for chapter in ordered_chapters}) != len(ordered_chapters):
        raise ValueError("duplicate chapter_id")
    if len({family.family_id for family in available}) != len(available):
        raise ValueError("duplicate family_id")

    counts: Counter[str] = Counter()
    assignments: list[ChapterAssignment] = []
    previous_family: str | None = None
    consecutive = 0

    for index, chapter in enumerate(ordered_chapters):
        candidates: list[tuple[float, TransitionFamily, list[str]]] = []
        for family in available:
            score, reasons = _compatibility(chapter, family)
            projected_share = (counts[family.family_id] + 1) / (index + 1)
            if projected_share > max_family_share and len(available) > 1:
                score -= 2.5
                reasons.append("dominance_penalty")
            if previous_family == family.family_id:
                projected_consecutive = consecutive + 1
                if projected_consecutive > max_consecutive_same:
                    score -= 3.0
                    reasons.append("consecutive_penalty")
            score -= counts[family.family_id] * 0.6
            candidates.append((score, family, reasons))

        score, chosen, reasons = max(candidates, key=lambda item: (item[0], -counts[item[1].family_id], item[1].family_id))
        if score < -50:
            raise ValueError(f"no compatible transition family for {chapter.chapter_id}")
        counts[chosen.family_id] += 1
        if previous_family == chosen.family_id:
            consecutive += 1
        else:
            previous_family = chosen.family_id
            consecutive = 1
        assignments.append(ChapterAssignment(chapter.chapter_id, chosen.family_id, round(score, 3), tuple(reasons)))

    dominant_share = max(counts.values()) / len(ordered_chapters)
    violations: list[str] = []
    if dominant_share > max_family_share and len(available) > 1:
        violations.append("family_dominance")
    run_family: str | None = None
    run_length = 0
    for assignment in assignments:
        if assignment.family_id == run_family:
            run_length += 1
        else:
            run_family = assignment.family_id
            run_length = 1
        if run_length > max_consecutive_same:
            violations.append(f"consecutive_family:{assignment.family_id}")

    return ChapterStylePlan(
        assignments=tuple(assignments),
        family_counts=dict(sorted(counts.items())),
        dominant_share=round(dominant_share, 3),
        violations=tuple(sorted(set(violations))),
    )
