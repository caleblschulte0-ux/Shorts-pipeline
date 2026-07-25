"""Review-only structural pattern catalog.

NOT WIRED INTO THE PIPELINE.

Stores successful scene structures and known weak structures in memory. Retrieval
rewards semantic relevance while penalizing near-duplicates of recent scenes.
Persistence and renderer integration are intentionally absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class SceneSignature:
    data_shape: str
    relationship: str
    visualization: str
    performance_family: str
    hook_mechanism: str
    payoff_mechanism: str
    camera_purpose: str

    def fields(self) -> tuple[str, ...]:
        return (
            self.data_shape,
            self.relationship,
            self.visualization,
            self.performance_family,
            self.hook_mechanism,
            self.payoff_mechanism,
            self.camera_purpose,
        )


@dataclass(frozen=True)
class SuccessPattern:
    pattern_id: str
    signature: SceneSignature
    score: float
    lowest_dimension: float
    why_it_worked: tuple[str, ...]
    artifact_manifest_hash: str


@dataclass(frozen=True)
class AvoidancePattern:
    pattern_id: str
    signature: SceneSignature
    failure_labels: tuple[str, ...]
    visible_evidence: str
    repair_principle: str


@dataclass(frozen=True)
class PatternQuery:
    data_shape: str
    relationship: str
    recent_signatures: tuple[SceneSignature, ...] = ()
    disallowed_families: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PatternMatch:
    pattern: SuccessPattern
    relevance: float
    repetition_penalty: float
    weak_pattern_penalty: float
    final_score: float
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def signature_similarity(left: SceneSignature, right: SceneSignature) -> float:
    left_fields = left.fields()
    right_fields = right.fields()
    exact = sum(a == b for a, b in zip(left_fields, right_fields))
    return exact / len(left_fields)


class PatternCatalog:
    def __init__(self) -> None:
        self.successes: dict[str, SuccessPattern] = {}
        self.avoidances: dict[str, AvoidancePattern] = {}

    def add_success(self, pattern: SuccessPattern) -> None:
        if pattern.score < 90.0:
            raise ValueError("success patterns require a score of at least 90")
        if pattern.lowest_dimension < 8.0:
            raise ValueError("success patterns require lowest dimension at least 8")
        if not pattern.artifact_manifest_hash:
            raise ValueError("success pattern requires an artifact manifest hash")
        self.successes[pattern.pattern_id] = pattern

    def add_avoidance(self, pattern: AvoidancePattern) -> None:
        if not pattern.failure_labels:
            raise ValueError("avoidance pattern requires failure labels")
        self.avoidances[pattern.pattern_id] = pattern

    def retrieve(self, query: PatternQuery, *, limit: int = 5) -> list[PatternMatch]:
        matches: list[PatternMatch] = []
        for pattern in self.successes.values():
            if pattern.signature.performance_family in query.disallowed_families:
                continue

            reasons: list[str] = []
            warnings: list[str] = []
            relevance = 0.0
            if pattern.signature.data_shape == query.data_shape:
                relevance += 0.45
                reasons.append("same data shape")
            if pattern.signature.relationship == query.relationship:
                relevance += 0.45
                reasons.append("same semantic relationship")
            relevance += min(0.10, max(0.0, (pattern.score - 90.0) / 100.0))

            repetition_penalty = 0.0
            for recent in query.recent_signatures:
                similarity = signature_similarity(pattern.signature, recent)
                if similarity >= 0.85:
                    repetition_penalty = max(repetition_penalty, 0.65)
                    warnings.append("near-duplicate of recent scene structure")
                elif similarity >= 0.70:
                    repetition_penalty = max(repetition_penalty, 0.25)
                    warnings.append("substantially similar to recent structure")

            weak_penalty = 0.0
            for weak in self.avoidances.values():
                similarity = signature_similarity(pattern.signature, weak.signature)
                if similarity >= 0.85:
                    weak_penalty = max(weak_penalty, 0.55)
                    warnings.append(
                        "matches known weak structure: "
                        + ", ".join(weak.failure_labels)
                    )
                elif similarity >= 0.70:
                    weak_penalty = max(weak_penalty, 0.20)
                    warnings.append(
                        "resembles known weak structure: "
                        + ", ".join(weak.failure_labels)
                    )

            final = max(0.0, relevance - repetition_penalty - weak_penalty)
            matches.append(
                PatternMatch(
                    pattern=pattern,
                    relevance=round(relevance, 4),
                    repetition_penalty=round(repetition_penalty, 4),
                    weak_pattern_penalty=round(weak_penalty, 4),
                    final_score=round(final, 4),
                    reasons=tuple(reasons),
                    warnings=tuple(warnings),
                )
            )

        return sorted(
            matches,
            key=lambda match: (
                match.final_score,
                match.pattern.score,
                -len(match.warnings),
            ),
            reverse=True,
        )[:limit]

    def family_distribution(self) -> Mapping[str, int]:
        counts: dict[str, int] = {}
        for pattern in self.successes.values():
            family = pattern.signature.performance_family
            counts[family] = counts.get(family, 0) + 1
        return counts

    def saturated_families(self, *, maximum_share: float = 0.25) -> frozenset[str]:
        counts = self.family_distribution()
        total = sum(counts.values())
        if total <= 0:
            return frozenset()
        return frozenset(
            family
            for family, count in counts.items()
            if count / total > maximum_share
        )


def build_catalog(
    successes: Iterable[SuccessPattern],
    avoidances: Iterable[AvoidancePattern],
) -> PatternCatalog:
    catalog = PatternCatalog()
    for pattern in successes:
        catalog.add_success(pattern)
    for pattern in avoidances:
        catalog.add_avoidance(pattern)
    return catalog


def recommend_new_candidate_constraints(
    catalog: PatternCatalog,
    recent: Sequence[SceneSignature],
) -> Mapping[str, object]:
    """Return constraints for a generator without selecting a scene itself."""

    return {
        "avoid_performance_families": sorted(catalog.saturated_families()),
        "recent_signatures": [signature.fields() for signature in recent],
        "must_preserve_semantics": True,
        "must_not_clone_exact_layout": True,
    }
