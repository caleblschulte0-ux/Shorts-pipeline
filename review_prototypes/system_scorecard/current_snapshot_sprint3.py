from __future__ import annotations

from .scorecard import CapabilityStatus, ScorecardReport, SystemScorecard


def isolated_review_snapshot_sprint3() -> ScorecardReport:
    """Evidence snapshot after sandbox adapters, proof, audit, and rollback code.

    This remains a review-branch measurement. Production wiring and production
    proof stay at zero because these modules are intentionally not connected.
    """

    capabilities = (
        CapabilityStatus("source_and_premise_quality", 9, 1.0, 0.90, 0.90, 0.35, 0.0, 0.0, ("content_system", "8 tests")),
        CapabilityStatus("retention_architecture", 10, 1.0, 0.85, 0.80, 0.35, 0.0, 0.0, ("retention_system", "retention tests")),
        CapabilityStatus("transactional_repair", 10, 1.0, 0.90, 0.90, 0.55, 0.0, 0.0, ("repair engine", "rollback tests")),
        CapabilityStatus("visual_judging", 10, 0.90, 0.65, 0.75, 0.25, 0.0, 0.0, ("judge ensemble", "adapter tests")),
        CapabilityStatus("full_video_proof", 10, 1.0, 0.90, 0.90, 0.70, 0.0, 0.0, ("full_video_proof", "two-run acceptance tests")),
        CapabilityStatus("analytics_learning", 8, 1.0, 0.85, 0.85, 0.35, 0.0, 0.0, ("channel_analytics", "experiment tests")),
        CapabilityStatus("release_operations", 8, 1.0, 0.90, 0.85, 0.55, 0.0, 0.0, ("channel_operations", "portfolio tests")),
        CapabilityStatus("sandbox_adapters", 9, 1.0, 0.90, 0.90, 0.70, 0.0, 0.0, ("sandbox_adapters", "4 tests")),
        CapabilityStatus("observability", 8, 1.0, 0.90, 0.90, 0.75, 0.0, 0.0, ("hash chain", "incident tests")),
        CapabilityStatus("release_rollback", 9, 1.0, 0.90, 0.90, 0.75, 0.0, 0.0, ("release_safety", "rollback tests")),
        CapabilityStatus("production_integration", 10, 0.90, 0.30, 0.20, 0.15, 0.0, 0.0, ("safe adapter boundary exists",)),
        CapabilityStatus("production_performance_proof", 10, 0.90, 0.25, 0.10, 0.10, 0.0, 0.0, ("proof harness exists; no real renders",)),
    )
    return SystemScorecard().evaluate(capabilities)
