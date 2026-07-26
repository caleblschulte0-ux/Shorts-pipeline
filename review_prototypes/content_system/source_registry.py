from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .content_models import (
    ClaimBinding,
    ContentValidationError,
    Dataset,
    Officiality,
    StoryPackage,
)


@dataclass(frozen=True)
class SourcePolicy:
    allowed_officiality: frozenset[Officiality] = frozenset(
        {Officiality.OFFICIAL, Officiality.PRIMARY, Officiality.SECONDARY}
    )
    maximum_age_days: int = 550
    require_https: bool = True
    allowed_publishers: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    message: str
    dataset_key: str | None = None
    claim_id: str | None = None


@dataclass(frozen=True)
class SourceAudit:
    passed: bool
    issues: tuple[AuditIssue, ...]
    datasets_checked: int
    claims_checked: int

    @property
    def blockers(self) -> tuple[AuditIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == "block")


class DatasetRegistry:
    """Strict local registry for source-backed data files.

    Missing or invalid data is never fabricated and never silently downgraded.
    """

    def __init__(self, root: Path, *, policy: SourcePolicy | None = None) -> None:
        self.root = Path(root)
        self.policy = policy or SourcePolicy()
        self._datasets: dict[str, Dataset] = {}

    def load_file(self, path: Path) -> Dataset:
        file_path = Path(path)
        if not file_path.is_absolute():
            file_path = self.root / file_path
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ContentValidationError(f"unable to read dataset: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise ContentValidationError(f"invalid dataset JSON: {file_path}: {exc}") from exc
        dataset = Dataset.from_dict(payload)
        self.register(dataset)
        return dataset

    def register(self, dataset: Dataset) -> None:
        existing = self._datasets.get(dataset.key)
        if existing is not None and existing != dataset:
            raise ContentValidationError(f"dataset key collision: {dataset.key!r}")
        self._datasets[dataset.key] = dataset

    def get(self, key: str) -> Dataset:
        try:
            return self._datasets[key]
        except KeyError as exc:
            raise ContentValidationError(f"unknown dataset: {key!r}") from exc

    def values_for_claim(self, claim: ClaimBinding) -> tuple[float, ...]:
        dataset = self.get(claim.dataset_key)
        return tuple(dataset.point(label).value for label in claim.point_labels)

    def audit_dataset(self, dataset: Dataset, *, as_of: date | None = None) -> tuple[AuditIssue, ...]:
        as_of = as_of or date.today()
        source = dataset.source
        issues: list[AuditIssue] = []
        if source.officiality not in self.policy.allowed_officiality:
            issues.append(
                AuditIssue(
                    "block",
                    "unpublishable_officiality",
                    f"officiality {source.officiality.value!r} is not allowed",
                    dataset_key=dataset.key,
                )
            )
        age = (as_of - source.access_date).days
        if age < 0:
            issues.append(
                AuditIssue(
                    "block",
                    "future_access_date",
                    "source access date is in the future",
                    dataset_key=dataset.key,
                )
            )
        elif age > self.policy.maximum_age_days:
            issues.append(
                AuditIssue(
                    "block",
                    "stale_source",
                    f"source was accessed {age} days ago; maximum is {self.policy.maximum_age_days}",
                    dataset_key=dataset.key,
                )
            )
        if self.policy.require_https and not source.url.lower().startswith("https://"):
            issues.append(
                AuditIssue(
                    "block",
                    "insecure_source_url",
                    "source URL must use HTTPS",
                    dataset_key=dataset.key,
                )
            )
        if self.policy.allowed_publishers:
            normalized = source.publisher.casefold()
            if normalized not in {publisher.casefold() for publisher in self.policy.allowed_publishers}:
                issues.append(
                    AuditIssue(
                        "block",
                        "publisher_not_allowed",
                        f"publisher {source.publisher!r} is not allowlisted",
                        dataset_key=dataset.key,
                    )
                )
        if dataset.value_range == 0 and len(dataset.points) > 1:
            issues.append(
                AuditIssue(
                    "warn",
                    "flat_dataset",
                    "all values are identical, so the story may lack a visual relationship",
                    dataset_key=dataset.key,
                )
            )
        return tuple(issues)

    def audit_story(self, story: StoryPackage, *, as_of: date | None = None) -> SourceAudit:
        issues: list[AuditIssue] = []
        for dataset in story.datasets:
            issues.extend(self.audit_dataset(dataset, as_of=as_of))
        datasets = {dataset.key: dataset for dataset in story.datasets}
        for claim in story.claims:
            dataset = datasets.get(claim.dataset_key)
            if dataset is None:
                issues.append(
                    AuditIssue(
                        "block",
                        "missing_claim_dataset",
                        f"claim references missing dataset {claim.dataset_key!r}",
                        claim_id=claim.claim_id,
                    )
                )
                continue
            try:
                claim.validate_against(dataset)
            except ContentValidationError as exc:
                issues.append(
                    AuditIssue(
                        "block",
                        "claim_mismatch",
                        str(exc),
                        dataset_key=dataset.key,
                        claim_id=claim.claim_id,
                    )
                )
        return SourceAudit(
            passed=not any(issue.severity == "block" for issue in issues),
            issues=tuple(issues),
            datasets_checked=len(story.datasets),
            claims_checked=len(story.claims),
        )

    def load_story_datasets(self, story_config: Mapping[str, Any]) -> tuple[Dataset, ...]:
        loaded: list[Dataset] = []
        for index, segment in enumerate(story_config.get("segments") or []):
            params = segment.get("params") or {}
            filename = params.get("file") or f"{segment.get('key', '')}.json"
            if not filename or filename == ".json":
                raise ContentValidationError(f"segment {index} has no dataset file")
            loaded.append(self.load_file(Path(filename)))
        if not loaded:
            raise ContentValidationError("story config has no data segments")
        return tuple(loaded)


def audit_raw_datasets(
    payloads: Iterable[Mapping[str, Any]],
    *,
    policy: SourcePolicy | None = None,
    as_of: date | None = None,
) -> SourceAudit:
    registry = DatasetRegistry(Path("."), policy=policy)
    issues: list[AuditIssue] = []
    count = 0
    for payload in payloads:
        count += 1
        try:
            dataset = Dataset.from_dict(payload)
            registry.register(dataset)
            issues.extend(registry.audit_dataset(dataset, as_of=as_of))
        except ContentValidationError as exc:
            issues.append(AuditIssue("block", "invalid_dataset", str(exc)))
    return SourceAudit(
        passed=not any(issue.severity == "block" for issue in issues),
        issues=tuple(issues),
        datasets_checked=count,
        claims_checked=0,
    )
