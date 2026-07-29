from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class StoryArchetype(str, Enum):
    MECHANISM = "mechanism"
    HISTORICAL = "historical"
    SCALE_COMPARISON = "scale_comparison"
    COUNTERINTUITIVE = "counterintuitive"
    PROCESS = "process"
    BIOGRAPHICAL = "biographical"


@dataclass(frozen=True)
class StoryFixture:
    slug: str
    archetype: StoryArchetype
    topic_family: str
    factual_mode: str
    beat_count: int
    expected_duration_seconds: float
    has_real_media: bool
    has_generated_media: bool
    claim_count: int
    evidence_package_complete: bool
    expected_failure: str | None = None


@dataclass(frozen=True)
class GeneralizationPolicy:
    minimum_fixtures: int = 5
    minimum_archetypes: int = 4
    minimum_topic_families: int = 4
    require_mixed_media_fixture: bool = True
    require_negative_control: bool = True
    maximum_duration_ratio: float = 4.0


@dataclass(frozen=True)
class GeneralizationReport:
    valid: bool
    fixture_count: int
    archetype_count: int
    topic_family_count: int
    blockers: tuple[str, ...]
    covered_archetypes: tuple[StoryArchetype, ...]


def validate_fixture(fixture: StoryFixture) -> tuple[str, ...]:
    blockers: list[str] = []
    if not fixture.slug.strip():
        blockers.append("missing_slug")
    if fixture.beat_count < 2:
        blockers.append(f"insufficient_beats:{fixture.slug}")
    if fixture.expected_duration_seconds <= 0:
        blockers.append(f"invalid_duration:{fixture.slug}")
    if fixture.claim_count < 0:
        blockers.append(f"invalid_claim_count:{fixture.slug}")
    if fixture.factual_mode == "required" and fixture.claim_count == 0:
        blockers.append(f"required_mode_without_claims:{fixture.slug}")
    if fixture.expected_failure is None and not fixture.evidence_package_complete:
        blockers.append(f"positive_fixture_missing_evidence:{fixture.slug}")
    return tuple(blockers)


def assess_generalization(
    fixtures: Iterable[StoryFixture],
    policy: GeneralizationPolicy = GeneralizationPolicy(),
) -> GeneralizationReport:
    items = tuple(fixtures)
    blockers: list[str] = []
    if len({item.slug for item in items}) != len(items):
        blockers.append("duplicate_fixture_slug")
    for fixture in items:
        blockers.extend(validate_fixture(fixture))

    archetypes = tuple(sorted({item.archetype for item in items}, key=lambda value: value.value))
    topic_families = {item.topic_family for item in items}
    if len(items) < policy.minimum_fixtures:
        blockers.append("fixture_count_below_minimum")
    if len(archetypes) < policy.minimum_archetypes:
        blockers.append("archetype_diversity_below_minimum")
    if len(topic_families) < policy.minimum_topic_families:
        blockers.append("topic_diversity_below_minimum")
    if policy.require_mixed_media_fixture and not any(item.has_real_media and item.has_generated_media for item in items):
        blockers.append("missing_mixed_media_fixture")
    if policy.require_negative_control and not any(item.expected_failure for item in items):
        blockers.append("missing_negative_control")

    durations = [item.expected_duration_seconds for item in items if item.expected_failure is None]
    if durations and min(durations) > 0 and max(durations) / min(durations) > policy.maximum_duration_ratio:
        blockers.append("duration_range_too_wide")

    return GeneralizationReport(
        valid=not blockers,
        fixture_count=len(items),
        archetype_count=len(archetypes),
        topic_family_count=len(topic_families),
        blockers=tuple(sorted(set(blockers))),
        covered_archetypes=archetypes,
    )


def fixture_matrix(fixtures: Iterable[StoryFixture]) -> dict[str, tuple[str, ...]]:
    items = tuple(fixtures)
    return {
        "archetypes": tuple(sorted({item.archetype.value for item in items})),
        "topic_families": tuple(sorted({item.topic_family for item in items})),
        "factual_modes": tuple(sorted({item.factual_mode for item in items})),
        "media_modes": tuple(sorted({
            "mixed" if item.has_real_media and item.has_generated_media
            else "real" if item.has_real_media
            else "generated" if item.has_generated_media
            else "none"
            for item in items
        })),
    }
