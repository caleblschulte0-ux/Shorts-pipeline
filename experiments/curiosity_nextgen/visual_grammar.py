from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class SceneIntent(str, Enum):
    QUESTION = "question"
    EVIDENCE = "evidence"
    MECHANISM = "mechanism"
    CONSEQUENCE = "consequence"
    CHARACTER = "character"
    SCALE = "scale"
    COMPARISON = "comparison"
    PAYOFF = "payoff"


class VisualFamily(str, Enum):
    CHARACTER = "character"
    REAL_MEDIA = "real_media"
    MECHANISM = "mechanism"
    DIAGRAM = "diagram"
    DATA = "data"
    MAP = "map"
    OBJECT_DEMO = "object_demo"
    TIMELINE = "timeline"
    TEXT_CARD = "text_card"


@dataclass(frozen=True)
class BeatVisualNeed:
    beat_id: str
    intent: SceneIntent
    topic: str
    tone: str
    requires_character: bool = False
    requires_real_evidence: bool = False
    allows_text_card: bool = True


@dataclass(frozen=True)
class VisualFamilySpec:
    family: VisualFamily
    supported_intents: frozenset[SceneIntent]
    topics: frozenset[str] = frozenset()
    tones: frozenset[str] = frozenset()
    supports_character: bool = False
    supports_real_evidence: bool = False
    text_heavy: bool = False
    max_consecutive: int = 2

    def __post_init__(self) -> None:
        if self.max_consecutive < 1:
            raise ValueError("max_consecutive must be positive")


@dataclass(frozen=True)
class VisualAssignment:
    beat_id: str
    family: VisualFamily
    score: float
    rationale: tuple[str, ...]


@dataclass(frozen=True)
class VisualGrammarPlan:
    assignments: tuple[VisualAssignment, ...]
    family_counts: dict[str, int]
    dominant_share: float
    text_card_share: float
    defects: tuple[str, ...]


def _eligible(need: BeatVisualNeed, spec: VisualFamilySpec) -> bool:
    if need.intent not in spec.supported_intents:
        return False
    if need.requires_character and not spec.supports_character:
        return False
    if need.requires_real_evidence and not spec.supports_real_evidence:
        return False
    if not need.allows_text_card and spec.family is VisualFamily.TEXT_CARD:
        return False
    return True


def _candidate_score(need: BeatVisualNeed, spec: VisualFamilySpec, counts: Counter[VisualFamily], recent: tuple[VisualFamily, ...]) -> tuple[float, tuple[str, ...]]:
    score = 6.0
    rationale = ["intent_match"]
    if need.topic in spec.topics:
        score += 1.5
        rationale.append("topic_match")
    if need.tone in spec.tones:
        score += 1.0
        rationale.append("tone_match")
    if need.requires_character and spec.supports_character:
        score += 1.0
        rationale.append("character_requirement")
    if need.requires_real_evidence and spec.supports_real_evidence:
        score += 1.0
        rationale.append("evidence_requirement")
    score -= counts[spec.family] * 0.55
    if recent and recent[-1] is spec.family:
        score -= 1.4
        rationale.append("repeat_penalty")
    if len(recent) >= spec.max_consecutive and all(item is spec.family for item in recent[-spec.max_consecutive:]):
        score -= 5.0
        rationale.append("consecutive_limit")
    if spec.text_heavy:
        score -= 0.8
        rationale.append("text_burden")
    return score, tuple(rationale)


def plan_visual_grammar(needs: Iterable[BeatVisualNeed], specs: Iterable[VisualFamilySpec]) -> VisualGrammarPlan:
    need_items = tuple(needs)
    spec_items = tuple(specs)
    if len({item.beat_id for item in need_items}) != len(need_items):
        raise ValueError("duplicate beat_id")
    if len({item.family for item in spec_items}) != len(spec_items):
        raise ValueError("duplicate visual family")

    assignments: list[VisualAssignment] = []
    counts: Counter[VisualFamily] = Counter()
    recent: list[VisualFamily] = []
    for need in need_items:
        candidates = []
        for spec in spec_items:
            if not _eligible(need, spec):
                continue
            score, rationale = _candidate_score(need, spec, counts, tuple(recent))
            candidates.append((score, spec.family.value, spec, rationale))
        if not candidates:
            raise ValueError(f"no eligible visual family for {need.beat_id}")
        score, _, selected, rationale = max(candidates, key=lambda item: (item[0], item[1]))
        assignments.append(VisualAssignment(need.beat_id, selected.family, round(score, 3), rationale))
        counts[selected.family] += 1
        recent.append(selected.family)

    total = len(assignments)
    dominant = max(counts.values(), default=0) / total if total else 0.0
    text_count = counts[VisualFamily.TEXT_CARD]
    text_share = text_count / total if total else 0.0
    defects: list[str] = []
    if total >= 5 and len(counts) < 3:
        defects.append("insufficient_visual_families")
    if dominant > 0.4:
        defects.append("dominant_visual_family")
    if text_share > 0.2:
        defects.append("text_card_overuse")
    for index in range(len(assignments) - 2):
        if len({assignments[index + offset].family for offset in range(3)}) == 1:
            defects.append(f"three_family_run:{assignments[index].beat_id}")

    return VisualGrammarPlan(
        tuple(assignments),
        {family.value: count for family, count in sorted(counts.items(), key=lambda item: item[0].value)},
        round(dominant, 3),
        round(text_share, 3),
        tuple(sorted(set(defects))),
    )
