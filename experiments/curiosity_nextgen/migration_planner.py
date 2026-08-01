"""Safe schema-migration path planning prototype."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class MigrationDecision(str, Enum):
    READY = "ready"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class MigrationStep:
    schema_name: str
    from_version: int
    to_version: int
    migration_id: str
    reversible: bool = True
    lossy: bool = False
    requires_manual_review: bool = False

    def __post_init__(self) -> None:
        if not self.schema_name.strip() or not self.migration_id.strip():
            raise ValueError("schema_name and migration_id must be nonempty")
        if self.from_version < 1 or self.to_version < 1:
            raise ValueError("migration versions must be >= 1")
        if self.from_version == self.to_version:
            raise ValueError("migration step must change version")
        if self.lossy and self.reversible:
            raise ValueError("lossy migrations cannot be marked reversible")


@dataclass(frozen=True)
class MigrationPlan:
    decision: MigrationDecision
    schema_name: str
    source_version: int
    target_version: int
    steps: tuple[MigrationStep, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def reversible(self) -> bool:
        return bool(self.steps) and all(step.reversible for step in self.steps)


class MigrationCatalog:
    def __init__(self, steps: Iterable[MigrationStep] = ()) -> None:
        self._steps: dict[tuple[str, int, int], MigrationStep] = {}
        self._ids: set[str] = set()
        for step in steps:
            self.register(step)

    def register(self, step: MigrationStep) -> None:
        key = (step.schema_name, step.from_version, step.to_version)
        if key in self._steps:
            raise ValueError(f"duplicate migration edge {key}")
        if step.migration_id in self._ids:
            raise ValueError(f"duplicate migration id {step.migration_id!r}")
        self._steps[key] = step
        self._ids.add(step.migration_id)

    def for_schema(self, schema_name: str) -> tuple[MigrationStep, ...]:
        return tuple(
            sorted(
                (step for step in self._steps.values() if step.schema_name == schema_name),
                key=lambda item: (item.from_version, item.to_version, item.migration_id),
            )
        )


def plan_migration(
    catalog: MigrationCatalog,
    *,
    schema_name: str,
    source_version: int,
    target_version: int,
    allow_lossy: bool = False,
    manual_review_approved: bool = False,
) -> MigrationPlan:
    if source_version == target_version:
        return MigrationPlan(
            MigrationDecision.READY,
            schema_name,
            source_version,
            target_version,
            (),
            (),
            ("already_at_target_version",),
        )

    edges = catalog.for_schema(schema_name)
    adjacency: dict[int, list[MigrationStep]] = {}
    for step in edges:
        adjacency.setdefault(step.from_version, []).append(step)
    for values in adjacency.values():
        values.sort(key=lambda item: (item.to_version, item.migration_id))

    queue: deque[tuple[int, tuple[MigrationStep, ...]]] = deque([(source_version, ())])
    visited = {source_version}
    selected: tuple[MigrationStep, ...] | None = None

    while queue:
        version, path = queue.popleft()
        for step in adjacency.get(version, []):
            next_path = path + (step,)
            if step.to_version == target_version:
                selected = next_path
                queue.clear()
                break
            if step.to_version not in visited:
                visited.add(step.to_version)
                queue.append((step.to_version, next_path))

    if selected is None:
        return MigrationPlan(
            MigrationDecision.BLOCKED,
            schema_name,
            source_version,
            target_version,
            (),
            ("no_complete_migration_path",),
            (),
        )

    blockers: list[str] = []
    warnings: list[str] = []
    for step in selected:
        if step.lossy and not allow_lossy:
            blockers.append(f"lossy_step_not_allowed:{step.migration_id}")
        elif step.lossy:
            warnings.append(f"lossy_step:{step.migration_id}")
        if step.requires_manual_review and not manual_review_approved:
            warnings.append(f"manual_review_required:{step.migration_id}")
        if not step.reversible:
            warnings.append(f"irreversible_step:{step.migration_id}")

    if blockers:
        decision = MigrationDecision.BLOCKED
    elif any(item.startswith("manual_review_required:") for item in warnings):
        decision = MigrationDecision.REVIEW
    else:
        decision = MigrationDecision.READY

    return MigrationPlan(
        decision,
        schema_name,
        source_version,
        target_version,
        selected,
        tuple(sorted(set(blockers))),
        tuple(sorted(set(warnings))),
    )
