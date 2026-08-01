"""Dormant story catalog and state-transition prototype."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Iterable


class StoryStatus(str, Enum):
    IDEA = "idea"
    RESEARCHING = "researching"
    AUTHORING = "authoring"
    RENDERABLE = "renderable"
    NEEDS_REWRITE = "needs_rewrite"
    QUARANTINED = "quarantined"
    PRODUCTION_CANDIDATE = "production_candidate"
    PUBLISHED = "published"
    RETIRED = "retired"


_ALLOWED: dict[StoryStatus, frozenset[StoryStatus]] = {
    StoryStatus.IDEA: frozenset({StoryStatus.RESEARCHING, StoryStatus.RETIRED}),
    StoryStatus.RESEARCHING: frozenset({StoryStatus.AUTHORING, StoryStatus.NEEDS_REWRITE, StoryStatus.RETIRED}),
    StoryStatus.AUTHORING: frozenset({StoryStatus.RENDERABLE, StoryStatus.NEEDS_REWRITE, StoryStatus.RETIRED}),
    StoryStatus.RENDERABLE: frozenset({StoryStatus.PRODUCTION_CANDIDATE, StoryStatus.NEEDS_REWRITE, StoryStatus.QUARANTINED}),
    StoryStatus.NEEDS_REWRITE: frozenset({StoryStatus.RESEARCHING, StoryStatus.AUTHORING, StoryStatus.RETIRED}),
    StoryStatus.QUARANTINED: frozenset({StoryStatus.AUTHORING, StoryStatus.NEEDS_REWRITE, StoryStatus.RETIRED}),
    StoryStatus.PRODUCTION_CANDIDATE: frozenset({StoryStatus.PUBLISHED, StoryStatus.QUARANTINED, StoryStatus.NEEDS_REWRITE}),
    StoryStatus.PUBLISHED: frozenset({StoryStatus.RETIRED, StoryStatus.NEEDS_REWRITE}),
    StoryStatus.RETIRED: frozenset(),
}


@dataclass
class StoryRecord:
    slug: str
    status: StoryStatus
    priority: int = 50
    quality_score: float | None = None
    factual_mode: str | None = None
    last_pass_sha: str | None = None
    blocking_reasons: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.slug or "/" in self.slug:
            raise ValueError("slug must be nonempty and may not contain '/'")
        if not 0 <= self.priority <= 100:
            raise ValueError("priority must be between 0 and 100")
        if self.quality_score is not None and not 0 <= self.quality_score <= 10:
            raise ValueError("quality_score must be between 0 and 10")

    def transition(self, new_status: StoryStatus, *, reason: str | None = None,
                   quality_score: float | None = None, pass_sha: str | None = None) -> None:
        if new_status not in _ALLOWED[self.status]:
            raise ValueError(f"illegal transition {self.status.value} -> {new_status.value}")
        if new_status is StoryStatus.PRODUCTION_CANDIDATE:
            if quality_score is None or quality_score < 7.5:
                raise ValueError("production candidates require quality_score >= 7.5")
            if not pass_sha:
                raise ValueError("production candidates require a passing artifact SHA")
            if self.blocking_reasons:
                raise ValueError("clear blocking reasons before promotion")
        if new_status in {StoryStatus.QUARANTINED, StoryStatus.NEEDS_REWRITE} and not reason:
            raise ValueError(f"{new_status.value} transition requires a reason")

        self.status = new_status
        if quality_score is not None:
            self.quality_score = quality_score
        if pass_sha is not None:
            self.last_pass_sha = pass_sha
        if reason:
            self.blocking_reasons = [reason]
        elif new_status is StoryStatus.PRODUCTION_CANDIDATE:
            self.blocking_reasons.clear()
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, object]:
        raw = asdict(self)
        raw["status"] = self.status.value
        return raw


class StoryCatalog:
    def __init__(self, records: Iterable[StoryRecord] = ()) -> None:
        self._records: dict[str, StoryRecord] = {}
        for record in records:
            self.add(record)

    def add(self, record: StoryRecord) -> None:
        if record.slug in self._records:
            raise ValueError(f"duplicate story slug {record.slug!r}")
        self._records[record.slug] = record

    def get(self, slug: str) -> StoryRecord:
        return self._records[slug]

    def production_candidates(self) -> list[StoryRecord]:
        candidates = [
            record for record in self._records.values()
            if record.status is StoryStatus.PRODUCTION_CANDIDATE
            and not record.blocking_reasons
            and record.quality_score is not None
            and record.quality_score >= 7.5
            and record.last_pass_sha
        ]
        return sorted(candidates, key=lambda record: (-record.priority, -(record.quality_score or 0), record.updated_at, record.slug))

    def to_dict(self) -> dict[str, object]:
        return {"schema_version": 1, "stories": {slug: record.to_dict() for slug, record in sorted(self._records.items())}}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")
