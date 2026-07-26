from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Sequence

from .models import ReleaseCandidate, ReleaseSlot, ScheduleResult


class ReleaseScheduler:
    """Space a selected batch instead of dumping every video at once."""

    def __init__(self, *, minimum_spacing_hours: float = 2.0) -> None:
        if minimum_spacing_hours <= 0:
            raise ValueError("minimum spacing must be positive")
        self.minimum_spacing = timedelta(hours=minimum_spacing_hours)

    def schedule(
        self,
        candidates: Sequence[ReleaseCandidate],
        *,
        publish_date: date,
        preferred_hours_utc: Sequence[int] = (13, 15, 17, 19, 21, 23),
    ) -> ScheduleResult:
        if len(set(preferred_hours_utc)) != len(preferred_hours_utc):
            raise ValueError("preferred hours must be unique")
        if any(hour < 0 or hour > 23 for hour in preferred_hours_utc):
            raise ValueError("publish hour must be in [0, 23]")
        if len(candidates) > len(preferred_hours_utc):
            raise ValueError("not enough preferred slots for selected batch")
        slots: list[ReleaseSlot] = []
        warnings: list[str] = []
        previous: datetime | None = None
        for index, (candidate, hour) in enumerate(zip(candidates, preferred_hours_utc)):
            publish_at = datetime.combine(
                publish_date,
                time(hour=hour, tzinfo=timezone.utc),
            )
            if previous and publish_at - previous < self.minimum_spacing:
                raise ValueError("preferred slots violate minimum spacing")
            slots.append(
                ReleaseSlot(
                    slug=candidate.slug,
                    publish_at=publish_at,
                    experiment_id=candidate.experiment_id,
                    sequence_index=index,
                )
            )
            previous = publish_at
        if len(candidates) >= 5:
            warnings.append("large daily batch may reduce learning clarity")
        experiment_ids = {item.experiment_id for item in candidates if item.experiment_id}
        if len(experiment_ids) > 1:
            raise ValueError("schedule contains multiple active experiments")
        return ScheduleResult(tuple(slots), tuple(warnings))
