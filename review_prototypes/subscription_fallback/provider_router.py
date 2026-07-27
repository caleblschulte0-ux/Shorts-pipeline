from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .contracts import GenerationRequest, ProviderKind
from .provider_health import ProviderHealth


@dataclass(frozen=True)
class ProviderRoute:
    order: tuple[ProviderKind, ...]
    skipped: Mapping[ProviderKind, str]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderPolicy:
    prefer_claude: bool = True
    allow_gemini: bool = True
    allow_template: bool = True
    allow_buffer: bool = True
    subscription_is_runtime_dependency: bool = False

    def default_order(self) -> tuple[ProviderKind, ...]:
        order: list[ProviderKind] = []
        if self.prefer_claude:
            order.append(ProviderKind.CLAUDE)
        if self.allow_gemini:
            order.append(ProviderKind.GEMINI)
        if self.allow_template:
            order.append(ProviderKind.TEMPLATE)
        if self.allow_buffer:
            order.append(ProviderKind.BUFFER)
        return tuple(order)


class ProviderRouter:
    """Routes by policy and health; never assumes a consumer subscription is available."""

    def __init__(self, policy: ProviderPolicy | None = None) -> None:
        self.policy = policy or ProviderPolicy()

    def route(
        self,
        request: GenerationRequest,
        health: Mapping[ProviderKind, ProviderHealth],
        configured: Mapping[ProviderKind, bool] | None = None,
    ) -> ProviderRoute:
        configured = configured or {}
        selected: list[ProviderKind] = []
        skipped: dict[ProviderKind, str] = {}
        for provider in self.policy.default_order():
            state = health.get(provider)
            if provider is ProviderKind.CLAUDE and not configured.get(provider, False):
                skipped[provider] = "claude_session_or_api_adapter_unavailable"
                continue
            if provider is ProviderKind.GEMINI and not configured.get(provider, False):
                skipped[provider] = "GEMINI_API_KEY_not_configured"
                continue
            if state and not state.available:
                skipped[provider] = f"circuit_open:{state.reason}"
                continue
            selected.append(provider)
        notes = (
            "Posting must consume an approved queue item; generation is never performed inside the posting transaction.",
            "Template and buffer fallbacks require no AI subscription.",
        )
        return ProviderRoute(tuple(selected), skipped, notes)
