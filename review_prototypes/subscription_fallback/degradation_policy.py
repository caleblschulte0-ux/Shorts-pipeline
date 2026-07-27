from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .contracts import DegradationLevel, GeneratedPackage, ProviderKind


@dataclass(frozen=True)
class DegradationDecision:
    level: DegradationLevel
    postable: bool
    failures: tuple[str, ...]
    notes: tuple[str, ...]


class DegradationPolicy:
    """Keeps quality reductions explicit while allowing safe local fallbacks to post."""

    PROVIDER_LEVEL = {
        ProviderKind.CLAUDE: DegradationLevel.FULL,
        ProviderKind.GEMINI: DegradationLevel.ACCEPTABLE,
        ProviderKind.TEMPLATE: DegradationLevel.DEGRADED,
        ProviderKind.BUFFER: DegradationLevel.BUFFERED,
    }

    REQUIRED_CHECKS = (
        "valid_mp4",
        "portrait_1080x1920",
        "duration_valid",
        "audio_valid",
        "captions_safe",
        "claims_supported",
        "rights_recorded",
        "not_duplicate",
    )

    def evaluate(self, package: GeneratedPackage, checks: Mapping[str, bool]) -> DegradationDecision:
        failures = tuple(check for check in self.REQUIRED_CHECKS if not checks.get(check, False))
        level = self.PROVIDER_LEVEL[package.provider]
        postable = not failures and package.approved and package.qa_passed
        if failures:
            level = DegradationLevel.BLOCKED
        return DegradationDecision(
            level=level,
            postable=postable,
            failures=failures,
            notes=(f"provider={package.provider.value}", "degradation must be persisted in the upload manifest"),
        )
