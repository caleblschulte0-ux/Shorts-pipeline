from __future__ import annotations

from .scorecard import CapabilityStatus, ScorecardReport, SystemScorecard


def isolated_review_snapshot() -> ScorecardReport:
    """Snapshot of the review branch, not a claim about production readiness."""

    capabilities = (
        CapabilityStatus(
            "source_and_premise_quality", 9, 1.0, 0.9, 0.9, 0.35, 0.0, 0.0,
            ("content_system package", "content tests"),
        ),
        CapabilityStatus(
            "retention_architecture", 10, 1.0, 0.85, 0.8, 0.35, 0.0, 0.0,
            ("retention_system package",),
        ),
        CapabilityStatus(
            "transactional_repair", 10, 1.0, 0.9, 0.9, 0.55, 0.0, 0.0,
            ("implementation engine", "rollback tests"),
        ),
        CapabilityStatus(
            "visual_judging", 10, 0.9, 0.65, 0.75, 0.25, 0.0, 0.0,
            ("judge ensemble", "adapter tests"),
        ),
        CapabilityStatus(
            "benchmarking", 9, 1.0, 0.75, 0.75, 0.3, 0.0, 0.0,
            ("benchmark lab", "quality state machine"),
        ),
        CapabilityStatus(
            "analytics_learning", 8, 1.0, 0.85, 0.85, 0.35, 0.0, 0.0,
            ("channel analytics package",),
        ),
        CapabilityStatus(
            "release_operations", 7, 1.0, 0.85, 0.8, 0.25, 0.0, 0.0,
            ("channel operations package",),
        ),
        CapabilityStatus(
            "production_integration", 10, 0.75, 0.05, 0.0, 0.0, 0.0, 0.0,
            ("integration intentionally prohibited on this branch",),
        ),
        CapabilityStatus(
            "full_video_proof", 10, 0.8, 0.1, 0.0, 0.0, 0.0, 0.0,
            ("acceptance criteria defined",),
        ),
    )
    return SystemScorecard().evaluate(capabilities)
