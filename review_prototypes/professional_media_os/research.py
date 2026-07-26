"""Evidence-first research packet compiler for the isolated prototype.

No retrieval is performed here. The compiler accepts already-normalized sources and claims,
then produces a fail-closed packet suitable for a future channel brain or candidate factory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import ContractError, EvidenceRef, Maturity, stable_hash, utc_now_iso


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    publisher: str
    source_type: str
    canonical_locator: str
    published_at: Optional[str]
    retrieved_at: str
    primary: bool
    authority_score: float
    rights_status: str
    content_hash: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all((self.source_id, self.publisher, self.source_type, self.canonical_locator)):
            raise ContractError("source records require stable identity and locator fields")
        if not 0.0 <= self.authority_score <= 1.0:
            raise ContractError("authority_score must be between 0 and 1")
        if len(self.content_hash) != 64:
            raise ContractError("content_hash must be a SHA-256 digest")


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    claim_type: str
    importance: str
    time_sensitive: bool
    required_for_promise: bool

    def __post_init__(self) -> None:
        if not all((self.claim_id, self.text.strip(), self.claim_type, self.importance)):
            raise ContractError("claims require id, text, type, and importance")


@dataclass(frozen=True)
class ClaimSupport:
    claim_id: str
    source_id: str
    support_type: str
    locator: str
    excerpt_hash: str
    confidence: float
    observed_at: str

    def __post_init__(self) -> None:
        if not all((self.claim_id, self.source_id, self.support_type, self.locator)):
            raise ContractError("claim support requires claim, source, type, and locator")
        if not 0.0 <= self.confidence <= 1.0:
            raise ContractError("claim support confidence must be between 0 and 1")
        if len(self.excerpt_hash) != 64:
            raise ContractError("excerpt_hash must be a SHA-256 digest")


@dataclass(frozen=True)
class ClaimConflict:
    conflict_id: str
    claim_id: str
    source_ids: Tuple[str, ...]
    description: str
    blocks_promise: bool


@dataclass(frozen=True)
class ResearchPolicy:
    allowed_rights_statuses: Tuple[str, ...]
    minimum_authority_score: float
    minimum_support_confidence: float
    minimum_independent_publishers_for_core_claim: int
    maximum_age_hours_for_time_sensitive_claim: int
    require_primary_source_for_core_claim: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_authority_score <= 1.0:
            raise ContractError("minimum_authority_score must be between 0 and 1")
        if not 0.0 <= self.minimum_support_confidence <= 1.0:
            raise ContractError("minimum_support_confidence must be between 0 and 1")
        if self.minimum_independent_publishers_for_core_claim < 1:
            raise ContractError("minimum publisher count must be at least one")
        if self.maximum_age_hours_for_time_sensitive_claim < 1:
            raise ContractError("maximum source age must be positive")


@dataclass(frozen=True)
class ClaimStatus:
    claim_id: str
    supported: bool
    blocking_reasons: Tuple[str, ...]
    warning_reasons: Tuple[str, ...]
    accepted_source_ids: Tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class ResearchPacket:
    packet_id: str
    claims: Tuple[Claim, ...]
    sources: Tuple[SourceRecord, ...]
    support: Tuple[ClaimSupport, ...]
    conflicts: Tuple[ClaimConflict, ...]
    statuses: Tuple[ClaimStatus, ...]
    publishable: bool
    blocking_reasons: Tuple[str, ...]
    evidence_refs: Tuple[EvidenceRef, ...]
    created_at: str = field(default_factory=utc_now_iso)


class ResearchCompiler:
    def compile(
        self,
        *,
        claims: Sequence[Claim],
        sources: Sequence[SourceRecord],
        support: Sequence[ClaimSupport],
        conflicts: Sequence[ClaimConflict],
        policy: ResearchPolicy,
        now: Optional[datetime] = None,
    ) -> ResearchPacket:
        if not claims:
            raise ContractError("research packet requires at least one claim")
        claim_map = self._unique_map(claims, "claim_id")
        source_map = self._unique_map(sources, "source_id")
        self._validate_support_references(support, claim_map, source_map)
        self._validate_conflicts(conflicts, claim_map, source_map)

        current_time = now or datetime.now(timezone.utc)
        statuses: List[ClaimStatus] = []
        packet_blocks: List[str] = []

        for claim in claims:
            claim_support = [item for item in support if item.claim_id == claim.claim_id]
            blocking: List[str] = []
            warnings: List[str] = []
            accepted: List[Tuple[ClaimSupport, SourceRecord]] = []

            for item in claim_support:
                source = source_map[item.source_id]
                if source.rights_status not in policy.allowed_rights_statuses:
                    warnings.append(f"source {source.source_id} has disallowed rights status")
                    continue
                if source.authority_score < policy.minimum_authority_score:
                    warnings.append(f"source {source.source_id} is below the authority floor")
                    continue
                if item.confidence < policy.minimum_support_confidence:
                    warnings.append(f"support from {source.source_id} is below the confidence floor")
                    continue
                if claim.time_sensitive and self._is_stale(
                    source,
                    current_time,
                    policy.maximum_age_hours_for_time_sensitive_claim,
                ):
                    warnings.append(f"source {source.source_id} is stale for a time-sensitive claim")
                    continue
                accepted.append((item, source))

            publishers = {source.publisher.lower() for _, source in accepted}
            has_primary = any(source.primary for _, source in accepted)
            related_conflicts = [item for item in conflicts if item.claim_id == claim.claim_id]

            if not accepted:
                blocking.append("no acceptable support remains after policy filters")
            if claim.required_for_promise:
                if len(publishers) < policy.minimum_independent_publishers_for_core_claim:
                    blocking.append(
                        "core claim lacks the required number of independent publishers"
                    )
                if policy.require_primary_source_for_core_claim and not has_primary:
                    blocking.append("core claim lacks a primary source")
                if any(item.blocks_promise for item in related_conflicts):
                    blocking.append("unresolved source conflict blocks the viewer promise")
            elif related_conflicts:
                warnings.append("claim has unresolved conflicting support")

            confidence = 0.0
            if accepted:
                confidence = sum(
                    item.confidence * source.authority_score for item, source in accepted
                ) / len(accepted)
                confidence = max(0.0, min(1.0, confidence))

            status = ClaimStatus(
                claim_id=claim.claim_id,
                supported=not blocking,
                blocking_reasons=tuple(sorted(set(blocking))),
                warning_reasons=tuple(sorted(set(warnings))),
                accepted_source_ids=tuple(sorted({source.source_id for _, source in accepted})),
                confidence=round(confidence, 6),
            )
            statuses.append(status)
            if claim.required_for_promise and blocking:
                packet_blocks.extend(
                    f"{claim.claim_id}: {reason}" for reason in status.blocking_reasons
                )

        evidence_refs = self._to_evidence_refs(sources, support, statuses)
        packet_seed = {
            "claims": [item.claim_id for item in claims],
            "sources": [item.source_id for item in sources],
            "support": [
                (item.claim_id, item.source_id, item.excerpt_hash) for item in support
            ],
            "policy": policy,
        }
        return ResearchPacket(
            packet_id=f"research-{stable_hash(packet_seed)[:20]}",
            claims=tuple(claims),
            sources=tuple(sources),
            support=tuple(support),
            conflicts=tuple(conflicts),
            statuses=tuple(statuses),
            publishable=not packet_blocks,
            blocking_reasons=tuple(sorted(set(packet_blocks))),
            evidence_refs=evidence_refs,
        )

    @staticmethod
    def _unique_map(records: Sequence[object], attribute: str) -> Mapping[str, object]:
        result: Dict[str, object] = {}
        for record in records:
            key = str(getattr(record, attribute))
            if key in result:
                raise ContractError(f"duplicate {attribute}: {key}")
            result[key] = record
        return result

    @staticmethod
    def _validate_support_references(
        support: Sequence[ClaimSupport],
        claims: Mapping[str, Claim],
        sources: Mapping[str, SourceRecord],
    ) -> None:
        seen = set()
        for item in support:
            if item.claim_id not in claims:
                raise ContractError(f"support references unknown claim: {item.claim_id}")
            if item.source_id not in sources:
                raise ContractError(f"support references unknown source: {item.source_id}")
            key = (item.claim_id, item.source_id, item.excerpt_hash)
            if key in seen:
                raise ContractError(f"duplicate support record: {key}")
            seen.add(key)

    @staticmethod
    def _validate_conflicts(
        conflicts: Sequence[ClaimConflict],
        claims: Mapping[str, Claim],
        sources: Mapping[str, SourceRecord],
    ) -> None:
        for conflict in conflicts:
            if conflict.claim_id not in claims:
                raise ContractError(f"conflict references unknown claim: {conflict.claim_id}")
            if len(conflict.source_ids) < 2:
                raise ContractError("claim conflicts require at least two sources")
            missing = [item for item in conflict.source_ids if item not in sources]
            if missing:
                raise ContractError(f"conflict references unknown sources: {missing}")

    @staticmethod
    def _is_stale(source: SourceRecord, now: datetime, maximum_age_hours: int) -> bool:
        timestamp = source.published_at or source.retrieved_at
        normalized = timestamp.replace("Z", "+00:00")
        try:
            source_time = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ContractError(f"invalid source timestamp: {timestamp}") from exc
        if source_time.tzinfo is None:
            source_time = source_time.replace(tzinfo=timezone.utc)
        age_hours = (now - source_time.astimezone(timezone.utc)).total_seconds() / 3600.0
        return age_hours > maximum_age_hours

    @staticmethod
    def _to_evidence_refs(
        sources: Sequence[SourceRecord],
        support: Sequence[ClaimSupport],
        statuses: Sequence[ClaimStatus],
    ) -> Tuple[EvidenceRef, ...]:
        source_map = {item.source_id: item for item in sources}
        status_map = {item.claim_id: item for item in statuses}
        evidence = []
        for item in support:
            source = source_map[item.source_id]
            status = status_map[item.claim_id]
            evidence.append(
                EvidenceRef(
                    evidence_id=f"evidence-{stable_hash((item.claim_id, item.source_id, item.excerpt_hash))[:20]}",
                    source_type=source.source_type,
                    locator=f"{source.canonical_locator}#{item.locator}",
                    observed_at=item.observed_at,
                    confidence=min(item.confidence, status.confidence),
                    rights_status=source.rights_status,
                    excerpt_hash=item.excerpt_hash,
                    maturity=Maturity.ANECDOTE,
                    metadata={
                        "claim_id": item.claim_id,
                        "source_id": item.source_id,
                        "publisher": source.publisher,
                        "primary": source.primary,
                    },
                )
            )
        return tuple(evidence)
