"""Sentence-level factual-claim discovery and registry coverage auditing.

This module is deliberately isolated from the active pipeline.  It extends the
coarser beat-level detector in ``claim_registry`` with sentence-level evidence,
confidence scores, claim-type compatibility, and duplicate/overbroad registry
checks.  It uses deterministic heuristics only; a production integration could
replace the detector while retaining the audit contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .claim_registry import Claim, ClaimType


@dataclass(frozen=True)
class SemanticSignal:
    beat_id: str
    sentence_index: int
    sentence: str
    claim_types: tuple[ClaimType, ...]
    confidence: float
    triggers: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.beat_id}:{self.sentence_index}"


@dataclass(frozen=True)
class SemanticCoverageAudit:
    valid: bool
    coverage_ratio: float
    detected_count: int
    covered_count: int
    uncovered_signals: tuple[str, ...]
    type_mismatches: tuple[str, ...]
    overbroad_claims: tuple[str, ...]
    duplicate_claim_ids: tuple[str, ...]
    warnings: tuple[str, ...]


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")

_PATTERN_GROUPS: tuple[tuple[ClaimType, tuple[re.Pattern[str], ...], float], ...] = (
    (
        ClaimType.NUMERIC,
        (
            re.compile(r"\b\d+(?:[.,]\d+)?(?:\s?(?:%|percent|million|billion|trillion|km|miles?|years?|seconds?))?\b", re.I),
            re.compile(r"\b(?:half|quarter|double|triple|twice|three times|one in \d+)\b", re.I),
        ),
        0.72,
    ),
    (
        ClaimType.HISTORICAL,
        (
            re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2}|century|decade|era|historically)\b", re.I),
            re.compile(r"\b(?:invented|founded|discovered|first recorded|began|ended|ancient|medieval)\b", re.I),
        ),
        0.70,
    ),
    (
        ClaimType.SUPERLATIVE,
        (re.compile(r"\b(?:largest|smallest|fastest|slowest|highest|lowest|oldest|youngest|most|least|best|worst|only)\b", re.I),),
        0.76,
    ),
    (
        ClaimType.COMPARATIVE,
        (
            re.compile(r"\b(?:more|less|fewer|greater|higher|lower|faster|slower)\s+than\b", re.I),
            re.compile(r"\b(?:compared (?:with|to)|more likely|less likely|twice as|three times as)\b", re.I),
        ),
        0.74,
    ),
    (
        ClaimType.CAUSAL,
        (
            re.compile(r"\b(?:causes?|caused by|because|therefore|leads? to|results? in|drives?|prevents?|allows?)\b", re.I),
            re.compile(r"\b(?:which means|so that|due to|as a result)\b", re.I),
        ),
        0.68,
    ),
    (
        ClaimType.SCIENTIFIC,
        (
            re.compile(r"\b(?:gravity|pressure|temperature|energy|orbit|chemical|biological|medical|radiation|velocity|mass|density)\b", re.I),
            re.compile(r"\b(?:scientists?|researchers?|experiment|study|studies|evidence|measured|observed)\b", re.I),
        ),
        0.66,
    ),
    (
        ClaimType.ATTRIBUTED,
        (
            re.compile(r"\b(?:according to|experts? say|research shows|studies show|scientists? agree|reported by)\b", re.I),
            re.compile(r"\b(?:the [A-Z][A-Za-z.& ]+ (?:says|reports|estimates|found))\b"),
        ),
        0.82,
    ),
    (
        ClaimType.GEOGRAPHIC,
        (
            re.compile(r"\b(?:United States|America|Europe|Asia|Africa|Japan|China|India|Earth|Atlantic|Pacific|Arctic|country|continent|state)\b", re.I),
            re.compile(r"\b(?:global|worldwide|national|regional|local)\b", re.I),
        ),
        0.58,
    ),
)

_ASSERTIVE_VERBS = re.compile(
    r"\b(?:is|are|was|were|has|have|contains?|produces?|uses?|moves?|travels?|costs?|requires?|creates?)\b",
    re.I,
)
_HEDGE_WORDS = re.compile(r"\b(?:might|may|could|roughly|about|approximately|possibly|likely|estimated)\b", re.I)
_QUESTION_PREFIX = re.compile(r"^\s*(?:why|how|what|when|where|who|could|would|does|do|is|are)\b", re.I)


def split_sentences(text: str) -> tuple[str, ...]:
    normalized = " ".join(text.split()).strip()
    if not normalized:
        return ()
    pieces = _SENTENCE_BOUNDARY.split(normalized)
    return tuple(piece.strip() for piece in pieces if piece.strip())


def _classify_sentence(sentence: str) -> tuple[tuple[ClaimType, ...], tuple[str, ...], float]:
    matched_types: list[ClaimType] = []
    triggers: list[str] = []
    confidence_parts: list[float] = []

    for claim_type, patterns, base_confidence in _PATTERN_GROUPS:
        type_matches: list[str] = []
        for pattern in patterns:
            match = pattern.search(sentence)
            if match:
                type_matches.append(match.group(0))
        if type_matches:
            matched_types.append(claim_type)
            triggers.extend(type_matches)
            confidence_parts.append(base_confidence + min(0.12, 0.03 * (len(type_matches) - 1)))

    if not matched_types and _ASSERTIVE_VERBS.search(sentence) and not _QUESTION_PREFIX.search(sentence):
        matched_types.append(ClaimType.GENERAL_FACT)
        triggers.append("assertive_statement")
        confidence_parts.append(0.54)

    if not matched_types:
        return (), (), 0.0

    confidence = max(confidence_parts)
    if len(matched_types) > 1:
        confidence = min(0.97, confidence + min(0.15, 0.035 * (len(matched_types) - 1)))
    if _HEDGE_WORDS.search(sentence):
        confidence = max(0.35, confidence - 0.08)
    if sentence.rstrip().endswith("?"):
        confidence = max(0.0, confidence - 0.35)

    return tuple(dict.fromkeys(matched_types)), tuple(dict.fromkeys(triggers)), round(confidence, 3)


def extract_semantic_signals(
    beat_texts: Mapping[str, str],
    *,
    minimum_confidence: float = 0.5,
) -> tuple[SemanticSignal, ...]:
    signals: list[SemanticSignal] = []
    for beat_id, text in beat_texts.items():
        for sentence_index, sentence in enumerate(split_sentences(text)):
            claim_types, triggers, confidence = _classify_sentence(sentence)
            if claim_types and confidence >= minimum_confidence:
                signals.append(
                    SemanticSignal(
                        beat_id=str(beat_id),
                        sentence_index=sentence_index,
                        sentence=sentence,
                        claim_types=claim_types,
                        confidence=confidence,
                        triggers=triggers,
                    )
                )
    return tuple(signals)


def _compatible(signal_types: Iterable[ClaimType], claim_type: ClaimType) -> bool:
    signal_set = set(signal_types)
    return claim_type is ClaimType.GENERAL_FACT or claim_type in signal_set


def audit_semantic_coverage(
    signals: Iterable[SemanticSignal],
    claims: Iterable[Claim],
    *,
    maximum_beats_per_claim: int = 4,
) -> SemanticCoverageAudit:
    signal_list = tuple(signals)
    claim_list = tuple(claims)
    claims_by_beat: dict[str, list[Claim]] = {}
    claim_id_counts: dict[str, int] = {}

    for claim in claim_list:
        claim_id_counts[claim.claim_id] = claim_id_counts.get(claim.claim_id, 0) + 1
        for beat_id in claim.beat_ids:
            claims_by_beat.setdefault(beat_id, []).append(claim)

    uncovered: list[str] = []
    mismatches: list[str] = []
    covered = 0

    for signal in signal_list:
        candidates = claims_by_beat.get(signal.beat_id, [])
        if not candidates:
            uncovered.append(signal.key)
            continue
        compatible = [claim for claim in candidates if _compatible(signal.claim_types, claim.claim_type)]
        if compatible:
            covered += 1
        else:
            mismatches.append(
                f"{signal.key}:expected={','.join(item.value for item in signal.claim_types)}:"
                f"registered={','.join(sorted({claim.claim_type.value for claim in candidates}))}"
            )

    overbroad = tuple(sorted(
        claim.claim_id
        for claim in claim_list
        if len(set(claim.beat_ids)) > maximum_beats_per_claim
    ))
    duplicate_ids = tuple(sorted(claim_id for claim_id, count in claim_id_counts.items() if count > 1))
    warnings: list[str] = []
    if not signal_list:
        warnings.append("no_semantic_claim_signals_detected")
    if overbroad:
        warnings.append("overbroad_claim_mappings_present")
    if duplicate_ids:
        warnings.append("duplicate_claim_ids_present")

    coverage_ratio = 1.0 if not signal_list else covered / len(signal_list)
    valid = (
        not uncovered
        and not mismatches
        and not duplicate_ids
        and coverage_ratio == 1.0
    )
    return SemanticCoverageAudit(
        valid=valid,
        coverage_ratio=round(coverage_ratio, 4),
        detected_count=len(signal_list),
        covered_count=covered,
        uncovered_signals=tuple(sorted(uncovered)),
        type_mismatches=tuple(sorted(mismatches)),
        overbroad_claims=overbroad,
        duplicate_claim_ids=duplicate_ids,
        warnings=tuple(sorted(set(warnings))),
    )
