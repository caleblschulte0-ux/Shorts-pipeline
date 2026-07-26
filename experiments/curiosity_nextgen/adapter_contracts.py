from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Capability(str, Enum):
    FETCH_MEDIA = "fetch_media"
    GENERATE_IMAGE = "generate_image"
    SYNTHESIZE_AUDIO = "synthesize_audio"
    RENDER_VIDEO = "render_video"
    STORE_ARTIFACT = "store_artifact"
    JUDGE_TECHNICAL = "judge_technical"
    JUDGE_EDITORIAL = "judge_editorial"
    PUBLISH_CANARY = "publish_canary"
    DELETE_REMOTE = "delete_remote"


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_id: str
    version: str
    capabilities: frozenset[Capability]
    input_schema_versions: tuple[int, ...]
    output_schema_versions: tuple[int, ...]
    deterministic: bool
    supports_idempotency: bool
    provider_family: str


@dataclass(frozen=True)
class AdapterRequirement:
    capability: Capability
    minimum_input_schema: int
    minimum_output_schema: int
    deterministic_required: bool = False
    idempotency_required: bool = True
    prohibited_provider_families: frozenset[str] = frozenset()


@dataclass(frozen=True)
class NegotiationResult:
    accepted: bool
    selected_adapter_id: str | None
    selected_version: str | None
    blockers: tuple[str, ...]
    eligible_adapter_ids: tuple[str, ...]


def _adapter_blockers(adapter: AdapterDescriptor, requirement: AdapterRequirement) -> tuple[str, ...]:
    blockers: list[str] = []
    if requirement.capability not in adapter.capabilities:
        blockers.append("missing_capability")
    if not any(version >= requirement.minimum_input_schema for version in adapter.input_schema_versions):
        blockers.append("input_schema_unsupported")
    if not any(version >= requirement.minimum_output_schema for version in adapter.output_schema_versions):
        blockers.append("output_schema_unsupported")
    if requirement.deterministic_required and not adapter.deterministic:
        blockers.append("nondeterministic_adapter")
    if requirement.idempotency_required and not adapter.supports_idempotency:
        blockers.append("missing_idempotency")
    if adapter.provider_family in requirement.prohibited_provider_families:
        blockers.append("prohibited_provider_family")
    if not adapter.adapter_id.strip() or not adapter.version.strip():
        blockers.append("invalid_adapter_identity")
    return tuple(blockers)


def negotiate_adapter(
    adapters: Iterable[AdapterDescriptor],
    requirement: AdapterRequirement,
    *,
    preferred_adapter_ids: tuple[str, ...] = (),
) -> NegotiationResult:
    items = tuple(adapters)
    eligible = tuple(adapter for adapter in items if not _adapter_blockers(adapter, requirement))
    if not eligible:
        all_reasons = sorted({
            reason
            for adapter in items
            for reason in _adapter_blockers(adapter, requirement)
        })
        return NegotiationResult(False, None, None, tuple(all_reasons or ["no_adapters"]), ())

    preference_rank = {adapter_id: index for index, adapter_id in enumerate(preferred_adapter_ids)}
    selected = sorted(
        eligible,
        key=lambda adapter: (
            preference_rank.get(adapter.adapter_id, len(preference_rank)),
            not adapter.deterministic,
            not adapter.supports_idempotency,
            adapter.provider_family,
            adapter.adapter_id,
            adapter.version,
        ),
    )[0]
    return NegotiationResult(
        True,
        selected.adapter_id,
        selected.version,
        (),
        tuple(sorted(adapter.adapter_id for adapter in eligible)),
    )


def validate_separation_of_duties(
    technical: AdapterDescriptor,
    editorial: AdapterDescriptor,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if technical.adapter_id == editorial.adapter_id:
        blockers.append("same_adapter")
    if technical.provider_family == editorial.provider_family:
        blockers.append("same_provider_family")
    if Capability.JUDGE_TECHNICAL not in technical.capabilities:
        blockers.append("technical_capability_missing")
    if Capability.JUDGE_EDITORIAL not in editorial.capabilities:
        blockers.append("editorial_capability_missing")
    return tuple(blockers)
