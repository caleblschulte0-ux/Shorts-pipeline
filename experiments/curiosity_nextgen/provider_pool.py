"""Dormant capability, cost, health, and independence-aware provider routing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ProviderRecord:
    provider_id: str
    provider_family: str
    model_family: str
    capabilities: frozenset[str]
    healthy: bool
    deterministic: bool
    unit_cost: float
    estimated_latency_seconds: float
    recent_error_rate: float
    quota_remaining: int

    def __post_init__(self) -> None:
        if not self.provider_id or not self.provider_family or not self.model_family:
            raise ValueError("provider identity fields are required")
        if not self.capabilities:
            raise ValueError("at least one capability is required")
        if self.unit_cost < 0 or self.estimated_latency_seconds < 0:
            raise ValueError("cost and latency cannot be negative")
        if not 0.0 <= self.recent_error_rate <= 1.0:
            raise ValueError("recent_error_rate must be between 0 and 1")
        if self.quota_remaining < 0:
            raise ValueError("quota_remaining cannot be negative")


@dataclass(frozen=True)
class RoutingRequest:
    stage: str
    required_capabilities: frozenset[str]
    maximum_unit_cost: float
    maximum_latency_seconds: float
    deterministic_required: bool = False
    excluded_provider_ids: frozenset[str] = frozenset()
    excluded_provider_families: frozenset[str] = frozenset()
    excluded_model_families: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.stage or not self.required_capabilities:
            raise ValueError("stage and capabilities are required")
        if self.maximum_unit_cost < 0 or self.maximum_latency_seconds < 0:
            raise ValueError("routing limits cannot be negative")


@dataclass(frozen=True)
class RoutingDecision:
    selected_provider_id: str | None
    fallback_provider_ids: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    valid: bool
    blockers: tuple[str, ...]


def _fitness(provider: ProviderRecord) -> float:
    reliability = 1.0 - provider.recent_error_rate
    cost_score = 1.0 / (1.0 + provider.unit_cost)
    latency_score = 1.0 / (1.0 + provider.estimated_latency_seconds / 30.0)
    quota_score = min(1.0, provider.quota_remaining / 100.0)
    return reliability * 0.45 + cost_score * 0.25 + latency_score * 0.20 + quota_score * 0.10


def route_provider(providers: Iterable[ProviderRecord], request: RoutingRequest, *, fallback_count: int = 2) -> RoutingDecision:
    if fallback_count < 0:
        raise ValueError("fallback_count cannot be negative")
    rejected: list[tuple[str, str]] = []
    eligible: list[ProviderRecord] = []

    for provider in providers:
        reason: str | None = None
        if provider.provider_id in request.excluded_provider_ids:
            reason = "provider_excluded"
        elif provider.provider_family in request.excluded_provider_families:
            reason = "provider_family_excluded"
        elif provider.model_family in request.excluded_model_families:
            reason = "model_family_excluded"
        elif not provider.healthy:
            reason = "unhealthy"
        elif provider.quota_remaining < 1:
            reason = "quota_exhausted"
        elif not request.required_capabilities.issubset(provider.capabilities):
            reason = "capability_mismatch"
        elif request.deterministic_required and not provider.deterministic:
            reason = "determinism_required"
        elif provider.unit_cost > request.maximum_unit_cost:
            reason = "cost_limit"
        elif provider.estimated_latency_seconds > request.maximum_latency_seconds:
            reason = "latency_limit"
        if reason:
            rejected.append((provider.provider_id, reason))
        else:
            eligible.append(provider)

    ranked = sorted(eligible, key=lambda item: (-_fitness(item), item.provider_id))
    selected = ranked[0] if ranked else None
    fallbacks: list[str] = []
    if selected is not None:
        used_families = {selected.provider_family}
        for provider in ranked[1:]:
            if provider.provider_family in used_families:
                continue
            fallbacks.append(provider.provider_id)
            used_families.add(provider.provider_family)
            if len(fallbacks) >= fallback_count:
                break

    blockers: list[str] = []
    if selected is None:
        blockers.append("no_eligible_provider")
    elif fallback_count and len(fallbacks) < fallback_count:
        blockers.append("insufficient_independent_fallbacks")

    return RoutingDecision(
        selected_provider_id=selected.provider_id if selected else None,
        fallback_provider_ids=tuple(fallbacks),
        rejected=tuple(sorted(rejected)),
        valid=not blockers,
        blockers=tuple(blockers),
    )


def independent_judge_routes(
    providers: Iterable[ProviderRecord],
    technical_request: RoutingRequest,
    editorial_request: RoutingRequest,
) -> tuple[RoutingDecision, RoutingDecision]:
    technical = route_provider(providers, technical_request)
    if not technical.selected_provider_id:
        return technical, route_provider((), editorial_request)
    provider_by_id = {provider.provider_id: provider for provider in providers}
    selected = provider_by_id[technical.selected_provider_id]
    editorial = route_provider(
        providers,
        RoutingRequest(
            stage=editorial_request.stage,
            required_capabilities=editorial_request.required_capabilities,
            maximum_unit_cost=editorial_request.maximum_unit_cost,
            maximum_latency_seconds=editorial_request.maximum_latency_seconds,
            deterministic_required=editorial_request.deterministic_required,
            excluded_provider_ids=editorial_request.excluded_provider_ids | frozenset({selected.provider_id}),
            excluded_provider_families=editorial_request.excluded_provider_families | frozenset({selected.provider_family}),
            excluded_model_families=editorial_request.excluded_model_families | frozenset({selected.model_family}),
        ),
    )
    return technical, editorial
