from __future__ import annotations

from .models import ReleaseCandidate, ReleaseDecision


class ReadinessGate:
    """Fail closed when any proof required for publication is missing."""

    def __init__(
        self,
        *,
        minimum_quality: float = 80.0,
        minimum_dimension: float = 7.0,
    ) -> None:
        self.minimum_quality = minimum_quality
        self.minimum_dimension = minimum_dimension

    def evaluate(self, candidate: ReleaseCandidate) -> ReleaseDecision:
        candidate.validate()
        reasons: list[str] = []
        if not candidate.source_verified:
            reasons.append("source evidence is not verified")
        if not candidate.retention_passed:
            reasons.append("retention package did not pass")
        if candidate.showrunner_decision != "ship":
            reasons.append(f"showrunner decision is {candidate.showrunner_decision}")
        if candidate.hard_failures:
            reasons.extend(f"hard failure: {item}" for item in candidate.hard_failures)
        if candidate.quality_score < self.minimum_quality:
            reasons.append(
                f"quality score {candidate.quality_score:.1f} below {self.minimum_quality:.1f}"
            )
        if candidate.lowest_dimension < self.minimum_dimension:
            reasons.append(
                f"lowest dimension {candidate.lowest_dimension:.1f} below {self.minimum_dimension:.1f}"
            )
        if not candidate.artifact_manifest_hash:
            reasons.append("artifact manifest hash missing")
        readiness = (
            candidate.quality_score * 0.55
            + candidate.lowest_dimension * 10.0 * 0.25
            + candidate.freshness_score * 100.0 * 0.10
            + max(0.0, min(1.0, candidate.reaction_prediction)) * 100.0 * 0.10
        )
        if reasons:
            readiness -= min(60.0, len(reasons) * 15.0)
        return ReleaseDecision(
            slug=candidate.slug,
            eligible=not reasons,
            reasons=tuple(reasons),
            readiness_score=round(max(0.0, min(100.0, readiness)), 2),
        )
