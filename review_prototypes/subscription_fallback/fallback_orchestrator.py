from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import os
import time
from pathlib import Path
from typing import Callable, Mapping

from .approved_queue import ApprovedQueue
from .contracts import (
    DegradationLevel,
    GeneratedPackage,
    GenerationRequest,
    GenerationResult,
    PostingClaim,
    ProviderAttempt,
    ProviderKind,
)
from .deterministic_writer import DeterministicWriter
from .provider_health import ProviderHealthEvent, ProviderHealthStore
from .provider_router import ProviderRouter


ProviderCallable = Callable[[GenerationRequest], GeneratedPackage]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FallbackOrchestrator:
    """Generation fills a buffer; posting only consumes previously approved packages."""

    def __init__(
        self,
        workspace: Path,
        *,
        providers: Mapping[ProviderKind, ProviderCallable] | None = None,
        router: ProviderRouter | None = None,
    ) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.queue = ApprovedQueue(self.workspace / "queue")
        self.health = ProviderHealthStore(self.workspace / "provider_health.jsonl")
        self.router = router or ProviderRouter()
        self.providers = dict(providers or {})
        self.template_writer = DeterministicWriter()

    def configured(self) -> dict[ProviderKind, bool]:
        return {
            ProviderKind.CLAUDE: ProviderKind.CLAUDE in self.providers,
            ProviderKind.GEMINI: ProviderKind.GEMINI in self.providers or bool(os.environ.get("GEMINI_API_KEY")),
            ProviderKind.TEMPLATE: True,
            ProviderKind.BUFFER: True,
        }

    def build_into_buffer(
        self,
        request: GenerationRequest,
        *,
        approval: Callable[[GeneratedPackage], GeneratedPackage] | None = None,
    ) -> GenerationResult:
        route = self.router.route(
            request,
            self.health.snapshot(ProviderKind),
            self.configured(),
        )
        attempts: list[ProviderAttempt] = []
        for provider in route.order:
            if provider is ProviderKind.BUFFER:
                break
            started = now_iso()
            monotonic = time.monotonic()
            try:
                if provider is ProviderKind.TEMPLATE:
                    package = self.template_writer.write(request, created_at=started)
                else:
                    callable_ = self.providers.get(provider)
                    if callable_ is None:
                        raise RuntimeError("provider adapter not configured")
                    package = callable_(request)
                expected = {
                    ProviderKind.CLAUDE: DegradationLevel.FULL,
                    ProviderKind.GEMINI: DegradationLevel.ACCEPTABLE,
                    ProviderKind.TEMPLATE: DegradationLevel.DEGRADED,
                }[provider]
                package = replace(package, provider=provider, degradation=expected)
                if approval is not None:
                    package = approval(package)
                if not package.postable():
                    raise RuntimeError("package_not_approved_or_QA_passed")
                self.queue.enqueue(package)
                ended = now_iso()
                attempts.append(ProviderAttempt(provider, True, "enqueued", started, ended, package.package_id))
                self.health.record(ProviderHealthEvent(provider, True, ended, latency_ms=int((time.monotonic() - monotonic) * 1000)))
                return GenerationResult(request.request_id, package, tuple(attempts), True, "generated_and_buffered")
            except Exception as exc:  # noqa: BLE001 - fallback boundary records and continues
                ended = now_iso()
                reason = f"{type(exc).__name__}:{exc}"
                attempts.append(ProviderAttempt(provider, False, reason, started, ended))
                self.health.record(ProviderHealthEvent(provider, False, ended, reason, int((time.monotonic() - monotonic) * 1000)))
        return GenerationResult(request.request_id, None, tuple(attempts), False, "all_generation_providers_failed")

    def claim_next_upload(self, channel: str, *, at: str | None = None) -> PostingClaim:
        """No generation occurs here. Empty queue is explicit and never triggers an AI call."""
        return self.queue.claim_next(channel, at=at)
