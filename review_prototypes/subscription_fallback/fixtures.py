from __future__ import annotations

from dataclasses import replace

from .contracts import EvidenceFact, GeneratedPackage, GenerationRequest


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        channel="daily-data",
        topic="Sample employment change",
        evergreen=True,
        requested_at="2026-07-27T12:00:00+00:00",
        facts=(
            EvidenceFact(
                metric="employment",
                current_value="100.5 million",
                previous_value="99.8 million",
                source_name="Example public dataset",
                source_url="https://example.test/data",
                accessed_at="2026-07-27T12:00:00+00:00",
                verified_cause="the measured category expanded in the latest release",
                comparison="that is 0.7 million higher than the previous observation",
                next_metric="the next scheduled release",
            ),
        ),
    )


def approve(package: GeneratedPackage) -> GeneratedPackage:
    return replace(
        package,
        qa_passed=True,
        approved=True,
        artifact_paths={"video": f"artifacts/{package.package_id}.mp4", "manifest": f"artifacts/{package.package_id}.json"},
    )
