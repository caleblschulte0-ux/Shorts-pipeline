"""Versioned creative-pattern library with explicit applicability and exclusions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import ContractError, ContentGenome, Maturity, PatternRecord


_MATURITY_RANK = {
    Maturity.DEPRECATED: -1,
    Maturity.ANECDOTE: 0,
    Maturity.DIRECTIONAL: 1,
    Maturity.EXPERIMENTAL: 2,
    Maturity.ESTABLISHED: 3,
}


@dataclass(frozen=True)
class PatternMatch:
    pattern_id: str
    version: str
    score: float
    matched_context: Tuple[str, ...]
    excluded_context: Tuple[str, ...]
    safe_for_automatic_ranking: bool
    reasons: Tuple[str, ...]


class PatternLibrary:
    """Store patterns without erasing superseded or contradictory knowledge."""

    def __init__(self, records: Sequence[PatternRecord] = ()) -> None:
        self._records: Dict[Tuple[str, str], PatternRecord] = {}
        for record in records:
            self.add(record)

    def add(self, record: PatternRecord) -> None:
        key = (record.pattern_id, record.version)
        existing = self._records.get(key)
        if existing is not None and existing != record:
            raise ContractError(f"pattern version collision: {key}")
        self._records[key] = record

    def versions(self, pattern_id: str) -> Tuple[PatternRecord, ...]:
        values = [
            record
            for (current_id, _), record in self._records.items()
            if current_id == pattern_id
        ]
        return tuple(sorted(values, key=lambda item: item.version))

    def latest(self, pattern_id: str) -> PatternRecord:
        values = self.versions(pattern_id)
        if not values:
            raise ContractError(f"unknown pattern: {pattern_id}")
        return values[-1]

    def match(
        self,
        genome: ContentGenome,
        *,
        context_labels: Sequence[str],
        minimum_maturity: Maturity = Maturity.DIRECTIONAL,
        minimum_confidence: float = 0.60,
    ) -> Tuple[PatternMatch, ...]:
        labels = set(context_labels)
        labels.update(
            {
                genome.channel_id,
                genome.event_type,
                genome.emotional_driver,
                genome.hook_structure,
                genome.narrative_structure,
                genome.presentation_format,
            }
        )
        matches: List[PatternMatch] = []

        latest_by_id: Dict[str, PatternRecord] = {}
        for record in self._records.values():
            previous = latest_by_id.get(record.pattern_id)
            if previous is None or record.version > previous.version:
                latest_by_id[record.pattern_id] = record

        for record in latest_by_id.values():
            applicable = set(record.applies_to)
            exclusions = set(record.excludes)
            matched = tuple(sorted(labels.intersection(applicable)))
            excluded = tuple(sorted(labels.intersection(exclusions)))
            reasons: List[str] = []

            if not matched:
                continue
            if excluded:
                reasons.append("explicit exclusion matched")
            if _MATURITY_RANK[record.maturity] < _MATURITY_RANK[minimum_maturity]:
                reasons.append(
                    f"maturity {record.maturity.value} is below {minimum_maturity.value}"
                )
            if record.confidence < minimum_confidence:
                reasons.append(
                    f"confidence {record.confidence:.2f} is below {minimum_confidence:.2f}"
                )
            if record.maturity is Maturity.DEPRECATED:
                reasons.append("pattern is deprecated")

            applicability = len(matched) / max(1, len(applicable))
            exclusion_penalty = 1.0 if excluded else 0.0
            score = max(
                0.0,
                min(
                    1.0,
                    record.confidence * 0.7 + applicability * 0.3 - exclusion_penalty,
                ),
            )
            safe = not reasons and record.maturity in (
                Maturity.EXPERIMENTAL,
                Maturity.ESTABLISHED,
            )
            matches.append(
                PatternMatch(
                    pattern_id=record.pattern_id,
                    version=record.version,
                    score=round(score, 6),
                    matched_context=matched,
                    excluded_context=excluded,
                    safe_for_automatic_ranking=safe,
                    reasons=tuple(reasons),
                )
            )

        return tuple(
            sorted(matches, key=lambda item: (-item.score, item.pattern_id, item.version))
        )

    def all_records(self) -> Tuple[PatternRecord, ...]:
        return tuple(
            sorted(self._records.values(), key=lambda item: (item.pattern_id, item.version))
        )
