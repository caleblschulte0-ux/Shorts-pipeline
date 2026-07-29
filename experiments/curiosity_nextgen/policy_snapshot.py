from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Mapping


class PolicyError(ValueError):
    pass


@dataclass(frozen=True)
class PolicyRule:
    key: str
    value: Any
    mutable_at_runtime: bool = False
    description: str = ""


@dataclass(frozen=True)
class PolicySnapshot:
    policy_id: str
    version: int
    rules: tuple[PolicyRule, ...]
    parent_sha256: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def canonical_payload(self) -> bytes:
        payload = {
            "policy_id": self.policy_id,
            "version": self.version,
            "parent_sha256": self.parent_sha256,
            "rules": [
                {
                    "key": rule.key,
                    "value": rule.value,
                    "mutable_at_runtime": rule.mutable_at_runtime,
                    "description": rule.description,
                }
                for rule in sorted(self.rules, key=lambda item: item.key)
            ],
            "metadata": dict(sorted(self.metadata.items())),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_payload()).hexdigest()

    def as_mapping(self) -> dict[str, Any]:
        return {rule.key: rule.value for rule in self.rules}


@dataclass(frozen=True)
class PolicyEvaluation:
    valid: bool
    effective_values: Mapping[str, Any]
    blockers: tuple[str, ...]
    snapshot_sha256: str


def validate_snapshot(snapshot: PolicySnapshot) -> tuple[str, ...]:
    blockers: list[str] = []
    if not snapshot.policy_id.strip():
        blockers.append("missing_policy_id")
    if snapshot.version < 1:
        blockers.append("invalid_policy_version")
    keys = [rule.key for rule in snapshot.rules]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    blockers.extend(f"duplicate_rule:{key}" for key in duplicates)
    blockers.extend(f"blank_rule_key:{index}" for index, key in enumerate(keys) if not key.strip())
    if snapshot.parent_sha256 is not None and len(snapshot.parent_sha256) != 64:
        blockers.append("invalid_parent_hash")
    return tuple(blockers)


def evaluate_policy(
    snapshot: PolicySnapshot,
    *,
    runtime_overrides: Mapping[str, Any] | None = None,
    expected_sha256: str | None = None,
) -> PolicyEvaluation:
    blockers = list(validate_snapshot(snapshot))
    if expected_sha256 is not None and snapshot.sha256 != expected_sha256:
        blockers.append("policy_hash_mismatch")

    effective = snapshot.as_mapping()
    rules_by_key = {rule.key: rule for rule in snapshot.rules}
    for key, value in (runtime_overrides or {}).items():
        rule = rules_by_key.get(key)
        if rule is None:
            blockers.append(f"unknown_override:{key}")
            continue
        if not rule.mutable_at_runtime:
            blockers.append(f"immutable_override:{key}")
            continue
        effective[key] = value

    return PolicyEvaluation(
        valid=not blockers,
        effective_values=effective,
        blockers=tuple(sorted(set(blockers))),
        snapshot_sha256=snapshot.sha256,
    )


def derive_snapshot(
    parent: PolicySnapshot,
    *,
    version: int,
    replacements: Mapping[str, Any],
    metadata: Mapping[str, str] | None = None,
) -> PolicySnapshot:
    if version <= parent.version:
        raise PolicyError("derived policy version must increase")
    known = {rule.key for rule in parent.rules}
    unknown = sorted(set(replacements) - known)
    if unknown:
        raise PolicyError(f"unknown replacement keys: {','.join(unknown)}")
    rules = tuple(
        PolicyRule(
            rule.key,
            replacements.get(rule.key, rule.value),
            rule.mutable_at_runtime,
            rule.description,
        )
        for rule in parent.rules
    )
    return PolicySnapshot(
        policy_id=parent.policy_id,
        version=version,
        rules=rules,
        parent_sha256=parent.sha256,
        metadata=metadata or parent.metadata,
    )
