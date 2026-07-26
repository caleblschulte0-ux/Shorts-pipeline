"""Isolated lineage tests for the Professional Media OS prototype."""

from __future__ import annotations

import unittest

from .contracts import ContractError, stable_hash
from .lineage import (
    ArtifactRef,
    DecisionLineage,
    LineageGraph,
    MetricLineage,
    Transformation,
    build_decision_snapshot_hash,
)


class LineageTests(unittest.TestCase):
    def _artifact(self, artifact_id: str, kind: str) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=artifact_id,
            kind=kind,
            sha256=stable_hash({"artifact": artifact_id}),
            producer_id="fixture-producer",
            producer_version="1.0.0",
            created_at="2026-07-26T12:00:00Z",
        )

    def test_metric_and_decision_lineage_are_explainable(self) -> None:
        graph = LineageGraph()
        raw = self._artifact("artifact-raw-001", "youtube-analytics-raw")
        normalized = self._artifact("artifact-normalized-001", "normalized-stage-metrics")
        graph.add_artifact(raw)
        graph.add_artifact(normalized)
        transform = Transformation(
            transformation_id="transform-metric-001",
            transformation_type="normalize-stage-metric",
            implementation_version="1.0.0",
            input_artifact_ids=(raw.artifact_id,),
            output_artifact_ids=(normalized.artifact_id,),
            config_hash=stable_hash({"definition": "youtube-shorts/v2"}),
            deterministic=True,
        )
        graph.add_transformation(transform)
        metric = MetricLineage(
            metric_record_id="metric-hook-001",
            metric_name="derived_hook_score",
            metric_definition_version="youtube-shorts/v2",
            raw_artifact_ids=(raw.artifact_id,),
            transformation_ids=(transform.transformation_id,),
            eligibility_filters=("views>=100",),
            sample_size=1000,
            observed_at="2026-07-27T12:00:00Z",
        )
        graph.add_metric(metric)
        snapshot_hash = build_decision_snapshot_hash(
            candidate_ids=("candidate-one", "candidate-two"),
            selected_candidate_id="candidate-two",
            evidence_ids=("evidence-one",),
            metric_record_ids=(metric.metric_record_id,),
            evaluator_ids=("hard-constraints", "first-seconds"),
            policy_version="policy/v1",
        )
        decision = DecisionLineage(
            decision_id="decision-select-001",
            candidate_ids=("candidate-one", "candidate-two"),
            selected_candidate_id="candidate-two",
            evidence_ids=("evidence-one",),
            metric_record_ids=(metric.metric_record_id,),
            evaluator_ids=("hard-constraints", "first-seconds"),
            policy_version="policy/v1",
            snapshot_hash=snapshot_hash,
        )
        graph.add_decision(decision)

        self.assertEqual(graph.ancestors(normalized.artifact_id), (raw,))
        self.assertEqual(graph.explain_metric(metric.metric_record_id)["metric"], metric)
        self.assertEqual(graph.explain_decision(decision.decision_id)["decision"], decision)

    def test_decision_rejects_selected_candidate_outside_candidate_set(self) -> None:
        with self.assertRaises(ContractError):
            DecisionLineage(
                decision_id="decision-invalid-001",
                candidate_ids=("candidate-one",),
                selected_candidate_id="candidate-two",
                evidence_ids=(),
                metric_record_ids=(),
                evaluator_ids=(),
                policy_version="policy/v1",
                snapshot_hash=stable_hash("invalid"),
            )


if __name__ == "__main__":
    unittest.main()
