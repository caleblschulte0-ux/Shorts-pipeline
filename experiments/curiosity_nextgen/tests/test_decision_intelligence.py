from __future__ import annotations

import unittest

from experiments.curiosity_nextgen.claim_registry import (
    Claim,
    ClaimType,
    FactualMode,
    SourceRef,
    evaluate_claim_coverage,
)
from experiments.curiosity_nextgen.experiment_attribution import (
    ExperimentDecision,
    RateMetric,
    evaluate_experiment,
)
from experiments.curiosity_nextgen.package_readiness import (
    GateResult,
    GateState,
    PackageDecision,
    evaluate_package,
)
from experiments.curiosity_nextgen.pipeline_status import (
    CapabilityStatus,
    EvidenceLevel,
    summarize_pipeline,
)
from experiments.curiosity_nextgen.render_budget import (
    BudgetDecision,
    RenderProfile,
    ShotCost,
    estimate_render,
)
from experiments.curiosity_nextgen.repair_planner import (
    DefectEvidence,
    DefectType,
    RepairAction,
    Severity,
    plan_repairs,
)
from experiments.curiosity_nextgen.repetition_ledger import (
    CreativeSignature,
    evaluate_repetition,
)


class ClaimRegistryTests(unittest.TestCase):
    def test_missing_mode_fails_closed(self) -> None:
        result = evaluate_claim_coverage(
            {"b1": "In 2024 this was the largest system in America."},
            [],
            factual_mode=None,
        )
        self.assertFalse(result.valid)
        self.assertIn("missing_factual_mode", result.warnings)

    def test_verified_claim_covers_detected_beat(self) -> None:
        source = SourceRef("Report", "Agency", "https://example.test/report")
        claim = Claim(
            "c1",
            ("b1",),
            "The value was 42 percent.",
            ClaimType.NUMERIC,
            sources=(source,),
        )
        result = evaluate_claim_coverage(
            {"b1": "The value was 42 percent."},
            [claim],
            factual_mode=FactualMode.VERIFIED,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.coverage_ratio, 1.0)

    def test_model_requires_assumptions_and_calculation(self) -> None:
        claim = Claim("c1", ("b1",), "It costs 50 dollars.", ClaimType.NUMERIC)
        result = evaluate_claim_coverage(
            {"b1": "It costs 50 dollars."},
            [claim],
            factual_mode=FactualMode.ILLUSTRATIVE_MODEL,
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.invalid_claims, ("c1",))


class RepairPlannerTests(unittest.TestCase):
    def test_exhausted_repairs_require_reauthoring(self) -> None:
        defect = DefectEvidence(
            "d1",
            "hook",
            DefectType.HOOK,
            Severity.HIGH,
            "opening still feels generic",
            location_seconds=2,
            previous_actions=(RepairAction.REWRITE_HOOK, RepairAction.REBUILD_SCENE),
            repair_round=2,
        )
        plan = plan_repairs([defect])
        self.assertTrue(plan.requires_human_reauthor)
        self.assertTrue(plan.quarantine)
        self.assertEqual(plan.steps[0].action, RepairAction.HUMAN_REAUTHOR)

    def test_blocking_factual_defect_is_first(self) -> None:
        defects = [
            DefectEvidence("d1", "b8", DefectType.REPETITION, Severity.MEDIUM, "same card"),
            DefectEvidence("d2", "b2", DefectType.FACTUAL, Severity.BLOCKING, "source conflicts"),
        ]
        plan = plan_repairs(defects)
        self.assertEqual(plan.steps[0].defect_id, "d2")
        self.assertTrue(plan.quarantine)


class RepetitionTests(unittest.TestCase):
    def test_asset_reuse_blocks(self) -> None:
        history = [CreativeSignature("old", "question", "callback", asset_ids=("asset-1",))]
        candidate = CreativeSignature("new", "question", "callback", asset_ids=("asset-1",))
        result = evaluate_repetition(candidate, history)
        self.assertFalse(result.valid)
        self.assertTrue(result.hard_blocks)

    def test_dominant_visual_family_warns(self) -> None:
        candidate = CreativeSignature(
            "new",
            "contradiction",
            "reveal",
            visual_families=("card", "card", "card", "card", "media"),
        )
        result = evaluate_repetition(candidate, [])
        self.assertTrue(any(item.startswith("dominant_visual_family") for item in result.warnings))


class RenderBudgetTests(unittest.TestCase):
    def test_cache_hits_reduce_estimate(self) -> None:
        uncached = [ShotCost("s1", "chart", 20, 3.0), ShotCost("s2", "chart", 20, 3.0)]
        cached = [ShotCost("s1", "chart", 20, 3.0, True), ShotCost("s2", "chart", 20, 3.0, True)]
        first = estimate_render(uncached, profile=RenderProfile.DRAFT)
        second = estimate_render(cached, profile=RenderProfile.DRAFT)
        self.assertLess(second.estimated_seconds, first.estimated_seconds)
        self.assertEqual(second.cache_hit_rate, 1.0)

    def test_hard_budget_rejects(self) -> None:
        shots = [ShotCost("s1", "character", 200, 4.0)]
        result = estimate_render(shots, profile=RenderProfile.DRAFT)
        self.assertEqual(result.decision, BudgetDecision.REJECT)


class PackageReadinessTests(unittest.TestCase):
    @staticmethod
    def gates(state: GateState = GateState.PASS, manifest: str = "m") -> list[GateResult]:
        names = [
            "manifest",
            "facts",
            "visual_judge",
            "fallbacks",
            "performance",
            "technical",
            "catalog",
            "channel_guard",
        ]
        return [GateResult(name, state, manifest_sha256=manifest) for name in names]

    def test_green_package_holds_when_publish_disabled(self) -> None:
        result = evaluate_package(self.gates(), expected_manifest_sha256="m", publishing_enabled=False)
        self.assertEqual(result.decision, PackageDecision.HOLD)
        self.assertEqual(result.readiness_score, 100.0)

    def test_hash_mismatch_quarantines(self) -> None:
        gates = self.gates()
        gates[0] = GateResult("manifest", GateState.PASS, manifest_sha256="wrong")
        result = evaluate_package(gates, expected_manifest_sha256="m", publishing_enabled=True)
        self.assertEqual(result.decision, PackageDecision.QUARANTINE)
        self.assertIn("artifact_mismatch:manifest", result.blockers)


class ExperimentTests(unittest.TestCase):
    def test_clear_lift_promotes(self) -> None:
        result = evaluate_experiment(
            RateMetric("retained", 400, 2000),
            RateMetric("retained", 500, 2000),
            min_trials_per_arm=1000,
            minimum_absolute_lift=0.02,
        )
        self.assertEqual(result.decision, ExperimentDecision.PROMOTE)

    def test_guardrail_harm_rejects(self) -> None:
        result = evaluate_experiment(
            RateMetric("retained", 400, 2000),
            RateMetric("retained", 500, 2000),
            guardrail_pairs=[
                (RateMetric("satisfaction", 600, 2000), RateMetric("satisfaction", 520, 2000))
            ],
        )
        self.assertEqual(result.decision, ExperimentDecision.REJECT)


class PipelineStatusTests(unittest.TestCase):
    def test_status_prioritizes_low_evidence_work(self) -> None:
        result = summarize_pipeline([
            CapabilityStatus("routing", 20, 100, EvidenceLevel.PRODUCTION_PROVEN),
            CapabilityStatus("facts", 20, 70, EvidenceLevel.TESTED, blocking=True),
            CapabilityStatus("visual_quality", 30, 60, EvidenceLevel.TESTED, blocking=True),
            CapabilityStatus("learning", 10, 20, EvidenceLevel.PROTOTYPED),
        ])
        self.assertLess(result.weighted_readiness, result.implementation_score)
        self.assertIn("visual_quality", result.blocking_gaps)
        self.assertIn("learning", result.next_priorities)


if __name__ == "__main__":
    unittest.main()
