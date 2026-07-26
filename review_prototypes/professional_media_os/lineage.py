"""Artifact, metric, and decision lineage for the isolated prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .contracts import ContractError, stable_hash, utc_now_iso


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    kind: str
    sha256: str
    producer_id: str
    producer_version: str
    created_at: str
    location: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all((self.artifact_id, self.kind, self.producer_id, self.producer_version)):
            raise ContractError("artifact lineage requires identity, kind, and producer")
        if len(self.sha256) != 64:
            raise ContractError("artifact sha256 must be a 64-character digest")


@dataclass(frozen=True)
class Transformation:
    transformation_id: str
    transformation_type: str
    implementation_version: str
    input_artifact_ids: Tuple[str, ...]
    output_artifact_ids: Tuple[str, ...]
    config_hash: str
    deterministic: bool
    occurred_at: str = field(default_factory=utc_now_iso)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(
            (
                self.transformation_id,
                self.transformation_type,
                self.implementation_version,
            )
        ):
            raise ContractError("transformations require identity, type, and version")
        if not self.input_artifact_ids:
            raise ContractError("transformations require at least one input artifact")
        if not self.output_artifact_ids:
            raise ContractError("transformations require at least one output artifact")
        if set(self.input_artifact_ids).intersection(self.output_artifact_ids):
            raise ContractError("a transformation cannot use the same artifact as input and output")
        if len(self.config_hash) != 64:
            raise ContractError("config_hash must be a 64-character digest")


@dataclass(frozen=True)
class MetricLineage:
    metric_record_id: str
    metric_name: str
    metric_definition_version: str
    raw_artifact_ids: Tuple[str, ...]
    transformation_ids: Tuple[str, ...]
    eligibility_filters: Tuple[str, ...]
    sample_size: int
    observed_at: str

    def __post_init__(self) -> None:
        if not all((self.metric_record_id, self.metric_name, self.metric_definition_version)):
            raise ContractError("metric lineage requires id, name, and definition version")
        if self.sample_size < 0:
            raise ContractError("metric lineage sample size must be non-negative")
        if not self.raw_artifact_ids:
            raise ContractError("metric lineage requires at least one raw artifact")


@dataclass(frozen=True)
class DecisionLineage:
    decision_id: str
    candidate_ids: Tuple[str, ...]
    selected_candidate_id: Optional[str]
    evidence_ids: Tuple[str, ...]
    metric_record_ids: Tuple[str, ...]
    evaluator_ids: Tuple[str, ...]
    policy_version: str
    snapshot_hash: str

    def __post_init__(self) -> None:
        if not self.decision_id or not self.policy_version:
            raise ContractError("decision lineage requires identity and policy version")
        if self.selected_candidate_id is not None and self.selected_candidate_id not in self.candidate_ids:
            raise ContractError("selected candidate must be present in the candidate set")
        if len(self.snapshot_hash) != 64:
            raise ContractError("decision snapshot_hash must be a 64-character digest")


class LineageGraph:
    """A small acyclic artifact graph with exact producer and transform versions."""

    def __init__(self) -> None:
        self._artifacts: Dict[str, ArtifactRef] = {}
        self._transforms: Dict[str, Transformation] = {}
        self._producer_for_artifact: Dict[str, str] = {}
        self._metrics: Dict[str, MetricLineage] = {}
        self._decisions: Dict[str, DecisionLineage] = {}

    def add_artifact(self, artifact: ArtifactRef) -> None:
        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None and existing != artifact:
            raise ContractError(f"artifact id collision: {artifact.artifact_id}")
        self._artifacts[artifact.artifact_id] = artifact

    def add_transformation(self, transformation: Transformation) -> None:
        existing = self._transforms.get(transformation.transformation_id)
        if existing is not None and existing != transformation:
            raise ContractError(
                f"transformation id collision: {transformation.transformation_id}"
            )
        missing_inputs = [
            item for item in transformation.input_artifact_ids if item not in self._artifacts
        ]
        missing_outputs = [
            item for item in transformation.output_artifact_ids if item not in self._artifacts
        ]
        if missing_inputs or missing_outputs:
            raise ContractError(
                f"transformation references unknown artifacts; inputs={missing_inputs}, outputs={missing_outputs}"
            )
        for output_id in transformation.output_artifact_ids:
            existing_producer = self._producer_for_artifact.get(output_id)
            if existing_producer is not None and existing_producer != transformation.transformation_id:
                raise ContractError(
                    f"artifact {output_id} already has producer transformation {existing_producer}"
                )
        self._transforms[transformation.transformation_id] = transformation
        for output_id in transformation.output_artifact_ids:
            self._producer_for_artifact[output_id] = transformation.transformation_id
        self._assert_acyclic()

    def add_metric(self, metric: MetricLineage) -> None:
        missing_artifacts = [
            item for item in metric.raw_artifact_ids if item not in self._artifacts
        ]
        missing_transforms = [
            item for item in metric.transformation_ids if item not in self._transforms
        ]
        if missing_artifacts or missing_transforms:
            raise ContractError(
                f"metric lineage is incomplete; artifacts={missing_artifacts}, transforms={missing_transforms}"
            )
        existing = self._metrics.get(metric.metric_record_id)
        if existing is not None and existing != metric:
            raise ContractError(f"metric record collision: {metric.metric_record_id}")
        self._metrics[metric.metric_record_id] = metric

    def add_decision(self, decision: DecisionLineage) -> None:
        missing_metrics = [
            item for item in decision.metric_record_ids if item not in self._metrics
        ]
        if missing_metrics:
            raise ContractError(f"decision references unknown metric records: {missing_metrics}")
        existing = self._decisions.get(decision.decision_id)
        if existing is not None and existing != decision:
            raise ContractError(f"decision lineage collision: {decision.decision_id}")
        self._decisions[decision.decision_id] = decision

    def ancestors(self, artifact_id: str) -> Tuple[ArtifactRef, ...]:
        if artifact_id not in self._artifacts:
            raise ContractError(f"unknown artifact: {artifact_id}")
        visited: Set[str] = set()

        def visit(current_id: str) -> None:
            transform_id = self._producer_for_artifact.get(current_id)
            if transform_id is None:
                return
            transform = self._transforms[transform_id]
            for input_id in transform.input_artifact_ids:
                if input_id not in visited:
                    visited.add(input_id)
                    visit(input_id)

        visit(artifact_id)
        return tuple(sorted((self._artifacts[item] for item in visited), key=lambda item: item.artifact_id))

    def explain_metric(self, metric_record_id: str) -> Mapping[str, Any]:
        metric = self._metrics.get(metric_record_id)
        if metric is None:
            raise ContractError(f"unknown metric record: {metric_record_id}")
        raw = [self._artifacts[item] for item in metric.raw_artifact_ids]
        transforms = [self._transforms[item] for item in metric.transformation_ids]
        return {
            "metric": metric,
            "raw_artifacts": tuple(raw),
            "transformations": tuple(transforms),
        }

    def explain_decision(self, decision_id: str) -> Mapping[str, Any]:
        decision = self._decisions.get(decision_id)
        if decision is None:
            raise ContractError(f"unknown decision: {decision_id}")
        return {
            "decision": decision,
            "metrics": tuple(self._metrics[item] for item in decision.metric_record_ids),
        }

    def _assert_acyclic(self) -> None:
        adjacency: Dict[str, Set[str]] = {artifact_id: set() for artifact_id in self._artifacts}
        for transform in self._transforms.values():
            for input_id in transform.input_artifact_ids:
                adjacency.setdefault(input_id, set()).update(transform.output_artifact_ids)

        visiting: Set[str] = set()
        visited: Set[str] = set()

        def walk(node: str) -> None:
            if node in visiting:
                raise ContractError(f"artifact lineage cycle detected at {node}")
            if node in visited:
                return
            visiting.add(node)
            for child in adjacency.get(node, ()):  # pragma: no branch - tiny graph
                walk(child)
            visiting.remove(node)
            visited.add(node)

        for node in adjacency:
            walk(node)


def build_decision_snapshot_hash(
    *,
    candidate_ids: Sequence[str],
    selected_candidate_id: Optional[str],
    evidence_ids: Sequence[str],
    metric_record_ids: Sequence[str],
    evaluator_ids: Sequence[str],
    policy_version: str,
) -> str:
    return stable_hash(
        {
            "candidate_ids": tuple(candidate_ids),
            "selected_candidate_id": selected_candidate_id,
            "evidence_ids": tuple(evidence_ids),
            "metric_record_ids": tuple(metric_record_ids),
            "evaluator_ids": tuple(evaluator_ids),
            "policy_version": policy_version,
        }
    )
