from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class RetentionClass(str, Enum):
    TRANSIENT = "transient"
    WORKING = "working"
    RELEASE_EVIDENCE = "release_evidence"
    AUDIT = "audit"


_RETENTION_SECONDS = {
    RetentionClass.TRANSIENT: 86_400,
    RetentionClass.WORKING: 30 * 86_400,
    RetentionClass.RELEASE_EVIDENCE: 365 * 86_400,
    RetentionClass.AUDIT: 7 * 365 * 86_400,
}


@dataclass(frozen=True)
class StoredArtifact:
    artifact_id: str
    sha256: str
    created_at: int
    retention_class: RetentionClass
    legal_hold: bool = False
    referenced_by_open_run: bool = False


@dataclass(frozen=True)
class PurgePlan:
    purge_ids: tuple[str, ...]
    retained_ids: tuple[str, ...]
    blockers: tuple[str, ...]


def plan_purge(artifacts: Iterable[StoredArtifact], *, now: int) -> PurgePlan:
    purge: list[str] = []
    retained: list[str] = []
    blockers: list[str] = []
    seen: set[str] = set()
    for artifact in artifacts:
        if artifact.artifact_id in seen:
            blockers.append(f"duplicate_artifact:{artifact.artifact_id}")
        seen.add(artifact.artifact_id)
        if len(artifact.sha256) != 64:
            blockers.append(f"invalid_hash:{artifact.artifact_id}")
            retained.append(artifact.artifact_id)
            continue
        age = max(0, now - artifact.created_at)
        expired = age >= _RETENTION_SECONDS[artifact.retention_class]
        if expired and not artifact.legal_hold and not artifact.referenced_by_open_run:
            purge.append(artifact.artifact_id)
        else:
            retained.append(artifact.artifact_id)
    return PurgePlan(tuple(sorted(purge)), tuple(sorted(retained)), tuple(sorted(set(blockers))))


@dataclass(frozen=True)
class BackupSnapshot:
    snapshot_id: str
    created_at: int
    manifest_sha256: str
    artifact_count: int
    replicated_regions: tuple[str, ...]
    restore_tested_at: int | None = None
    restore_duration_seconds: int | None = None


@dataclass(frozen=True)
class RecoveryObjective:
    maximum_rpo_seconds: int
    maximum_rto_seconds: int
    minimum_regions: int = 2


@dataclass(frozen=True)
class RecoveryAssessment:
    recoverable: bool
    selected_snapshot_id: str | None
    blockers: tuple[str, ...]


def assess_recovery(
    snapshots: Iterable[BackupSnapshot],
    *,
    incident_at: int,
    objective: RecoveryObjective,
) -> RecoveryAssessment:
    candidates = sorted(
        (item for item in snapshots if item.created_at <= incident_at),
        key=lambda item: item.created_at,
        reverse=True,
    )
    blockers: list[str] = []
    for snapshot in candidates:
        local: list[str] = []
        if incident_at - snapshot.created_at > objective.maximum_rpo_seconds:
            local.append("rpo_exceeded")
        if len(set(snapshot.replicated_regions)) < objective.minimum_regions:
            local.append("insufficient_region_replicas")
        if snapshot.restore_tested_at is None or snapshot.restore_duration_seconds is None:
            local.append("restore_not_tested")
        elif snapshot.restore_duration_seconds > objective.maximum_rto_seconds:
            local.append("rto_exceeded")
        if len(snapshot.manifest_sha256) != 64 or snapshot.artifact_count < 1:
            local.append("invalid_snapshot")
        if not local:
            return RecoveryAssessment(True, snapshot.snapshot_id, ())
        blockers.extend(f"{snapshot.snapshot_id}:{reason}" for reason in local)
    return RecoveryAssessment(False, None, tuple(blockers or ["no_snapshot_before_incident"]))


@dataclass(frozen=True)
class ChangeStep:
    step_id: str
    dependencies: tuple[str, ...]
    reversible: bool
    rollback_action: str | None
    state_migration: bool = False
    data_backup_required: bool = False


@dataclass(frozen=True)
class RollbackPlan:
    safe: bool
    ordered_step_ids: tuple[str, ...]
    rollback_actions: tuple[str, ...]
    blockers: tuple[str, ...]


def build_rollback_plan(steps: Iterable[ChangeStep], *, backup_available: bool) -> RollbackPlan:
    items = tuple(steps)
    by_id = {step.step_id: step for step in items}
    blockers: list[str] = []
    if len(by_id) != len(items):
        blockers.append("duplicate_step_id")
    for step in items:
        for dependency in step.dependencies:
            if dependency not in by_id:
                blockers.append(f"missing_dependency:{step.step_id}:{dependency}")
        if not step.reversible or not step.rollback_action:
            blockers.append(f"irreversible_step:{step.step_id}")
        if (step.state_migration or step.data_backup_required) and not backup_available:
            blockers.append(f"backup_required:{step.step_id}")

    ordered: list[str] = []
    remaining = set(by_id)
    while remaining:
        ready = sorted(
            step_id
            for step_id in remaining
            if set(by_id[step_id].dependencies).issubset(set(ordered))
        )
        if not ready:
            blockers.append("dependency_cycle")
            break
        ordered.extend(ready)
        remaining.difference_update(ready)

    rollback_order = tuple(reversed(ordered))
    actions = tuple(by_id[step_id].rollback_action or "" for step_id in rollback_order)
    return RollbackPlan(not blockers, rollback_order, actions, tuple(sorted(set(blockers))))


class RolloutStage(str, Enum):
    SHADOW = "shadow"
    INTERNAL = "internal"
    CANARY = "canary"
    LIMITED = "limited"
    FULL = "full"
    FROZEN = "frozen"


_STAGE_ORDER = (
    RolloutStage.SHADOW,
    RolloutStage.INTERNAL,
    RolloutStage.CANARY,
    RolloutStage.LIMITED,
    RolloutStage.FULL,
)


@dataclass(frozen=True)
class RolloutSignals:
    error_rate: float
    quarantine_rate: float
    quality_score: float
    sample_size: int
    rollback_ready: bool
    audit_chain_valid: bool


@dataclass(frozen=True)
class RolloutDecision:
    current_stage: RolloutStage
    next_stage: RolloutStage
    promote: bool
    blockers: tuple[str, ...]


def evaluate_rollout(
    current_stage: RolloutStage,
    signals: RolloutSignals,
    *,
    minimum_sample_size: int = 10,
    maximum_error_rate: float = 0.02,
    maximum_quarantine_rate: float = 0.10,
    minimum_quality_score: float = 7.5,
) -> RolloutDecision:
    blockers: list[str] = []
    if not signals.rollback_ready:
        blockers.append("rollback_not_ready")
    if not signals.audit_chain_valid:
        blockers.append("audit_chain_invalid")
    if signals.sample_size < minimum_sample_size:
        blockers.append("insufficient_sample")
    if signals.error_rate > maximum_error_rate:
        blockers.append("error_rate_exceeded")
    if signals.quarantine_rate > maximum_quarantine_rate:
        blockers.append("quarantine_rate_exceeded")
    if signals.quality_score < minimum_quality_score:
        blockers.append("quality_below_floor")

    if blockers:
        return RolloutDecision(current_stage, RolloutStage.FROZEN, False, tuple(blockers))
    if current_stage is RolloutStage.FROZEN:
        return RolloutDecision(current_stage, RolloutStage.SHADOW, False, ("manual_unfreeze_required",))
    try:
        index = _STAGE_ORDER.index(current_stage)
    except ValueError:
        return RolloutDecision(current_stage, RolloutStage.FROZEN, False, ("unknown_stage",))
    next_stage = _STAGE_ORDER[min(index + 1, len(_STAGE_ORDER) - 1)]
    return RolloutDecision(current_stage, next_stage, next_stage is not current_stage, ())
