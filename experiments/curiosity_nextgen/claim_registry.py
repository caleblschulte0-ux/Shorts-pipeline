from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable, Mapping


class FactualMode(str, Enum):
    VERIFIED = "verified"
    ILLUSTRATIVE_MODEL = "illustrative_model"
    HISTORICAL_RECONSTRUCTION = "historical_reconstruction"
    FICTIONAL = "fictional"
    PURE_VISUALIZATION = "pure_visualization"


class ClaimType(str, Enum):
    NUMERIC = "numeric"
    COMPARATIVE = "comparative"
    SUPERLATIVE = "superlative"
    CAUSAL = "causal"
    HISTORICAL = "historical"
    GEOGRAPHIC = "geographic"
    SCIENTIFIC = "scientific"
    ATTRIBUTED = "attributed"
    GENERAL_FACT = "general_fact"


@dataclass(frozen=True)
class SourceRef:
    title: str
    publisher: str
    url: str
    publication_date: str | None = None
    accessed_date: str | None = None

    @property
    def complete(self) -> bool:
        return bool(self.title.strip() and self.publisher.strip() and self.url.strip())


@dataclass(frozen=True)
class Claim:
    claim_id: str
    beat_ids: tuple[str, ...]
    claim_text: str
    claim_type: ClaimType
    sources: tuple[SourceRef, ...] = ()
    assumptions: tuple[str, ...] = ()
    calculation: str | None = None
    uncertainty: str | None = None
    geography: str | None = None


@dataclass(frozen=True)
class DetectedSignal:
    beat_id: str
    claim_type: ClaimType
    excerpt: str


@dataclass(frozen=True)
class ClaimCoverageResult:
    valid: bool
    mode: FactualMode | None
    detected_signals: tuple[DetectedSignal, ...]
    uncovered_beats: tuple[str, ...]
    invalid_claims: tuple[str, ...]
    warnings: tuple[str, ...]
    coverage_ratio: float


_SIGNAL_PATTERNS: tuple[tuple[ClaimType, re.Pattern[str]], ...] = (
    (ClaimType.NUMERIC, re.compile(r"(?:\b\d+(?:[.,]\d+)?\b|\b(?:percent|percentage|million|billion|trillion|half|quarter|double|triple)\b)", re.I)),
    (ClaimType.HISTORICAL, re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2}|century|decade|historically|first recorded|invented|founded)\b", re.I)),
    (ClaimType.SUPERLATIVE, re.compile(r"\b(?:largest|smallest|fastest|slowest|highest|lowest|oldest|youngest|most|least|best|worst)\b", re.I)),
    (ClaimType.COMPARATIVE, re.compile(r"\b(?:more than|less than|fewer than|greater than|compared with|compared to|twice as|three times|more likely|less likely)\b", re.I)),
    (ClaimType.CAUSAL, re.compile(r"\b(?:causes?|caused by|because of|leads? to|results? in|drives?|therefore|which means)\b", re.I)),
    (ClaimType.SCIENTIFIC, re.compile(r"\b(?:scientists?|researchers?|study|studies|evidence|temperature|pressure|gravity|orbit|energy|chemical|biological|medical)\b", re.I)),
    (ClaimType.ATTRIBUTED, re.compile(r"\b(?:experts? say|according to|research shows|scientists? agree|studies show)\b", re.I)),
    (ClaimType.GEOGRAPHIC, re.compile(r"\b(?:United States|America|Europe|Asia|Africa|Japan|China|India|Earth|ocean|continent|country|state)\b", re.I)),
)


def detect_claim_signals(beat_texts: Mapping[str, str]) -> tuple[DetectedSignal, ...]:
    signals: list[DetectedSignal] = []
    for beat_id, text in beat_texts.items():
        normalized = " ".join(text.split())
        for claim_type, pattern in _SIGNAL_PATTERNS:
            match = pattern.search(normalized)
            if match:
                start = max(0, match.start() - 35)
                end = min(len(normalized), match.end() + 55)
                signals.append(DetectedSignal(beat_id, claim_type, normalized[start:end]))
    return tuple(signals)


def _claim_is_valid(claim: Claim, mode: FactualMode) -> bool:
    if not claim.claim_id.strip() or not claim.beat_ids or not claim.claim_text.strip():
        return False
    if mode in {FactualMode.VERIFIED, FactualMode.HISTORICAL_RECONSTRUCTION}:
        if not claim.sources or not all(source.complete for source in claim.sources):
            return False
    if mode is FactualMode.ILLUSTRATIVE_MODEL:
        if not claim.assumptions or not (claim.calculation and claim.calculation.strip()):
            return False
    return True


def evaluate_claim_coverage(
    beat_texts: Mapping[str, str],
    claims: Iterable[Claim],
    *,
    factual_mode: FactualMode | None,
) -> ClaimCoverageResult:
    signals = detect_claim_signals(beat_texts)
    claim_list = tuple(claims)
    warnings: list[str] = []

    if factual_mode is None:
        return ClaimCoverageResult(
            valid=False,
            mode=None,
            detected_signals=signals,
            uncovered_beats=tuple(sorted({signal.beat_id for signal in signals})),
            invalid_claims=(),
            warnings=("missing_factual_mode",),
            coverage_ratio=0.0 if signals else 1.0,
        )

    if factual_mode in {FactualMode.FICTIONAL, FactualMode.PURE_VISUALIZATION}:
        if signals:
            warnings.append("real_world_claim_signals_present_in_exempt_mode")
        return ClaimCoverageResult(
            valid=not signals,
            mode=factual_mode,
            detected_signals=signals,
            uncovered_beats=tuple(sorted({signal.beat_id for signal in signals})),
            invalid_claims=(),
            warnings=tuple(warnings),
            coverage_ratio=0.0 if signals else 1.0,
        )

    covered_beats = {beat_id for claim in claim_list for beat_id in claim.beat_ids}
    signal_beats = {signal.beat_id for signal in signals}
    uncovered = tuple(sorted(signal_beats - covered_beats))
    invalid = tuple(sorted(claim.claim_id for claim in claim_list if not _claim_is_valid(claim, factual_mode)))
    coverage_ratio = 1.0 if not signal_beats else len(signal_beats & covered_beats) / len(signal_beats)

    claim_types_by_beat: dict[str, set[ClaimType]] = {}
    for claim in claim_list:
        for beat_id in claim.beat_ids:
            claim_types_by_beat.setdefault(beat_id, set()).add(claim.claim_type)
    for signal in signals:
        types = claim_types_by_beat.get(signal.beat_id, set())
        if types and signal.claim_type not in types and ClaimType.GENERAL_FACT not in types:
            warnings.append(f"claim_type_mismatch:{signal.beat_id}:{signal.claim_type.value}")

    return ClaimCoverageResult(
        valid=not uncovered and not invalid,
        mode=factual_mode,
        detected_signals=signals,
        uncovered_beats=uncovered,
        invalid_claims=invalid,
        warnings=tuple(sorted(set(warnings))),
        coverage_ratio=round(coverage_ratio, 4),
    )
