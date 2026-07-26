from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .closure import DIMENSIONS, WEIGHTS, run_launch_rehearsal
from .contracts import CONTRACTS, canonical_snapshot, validate_snapshot
from .launch_plan import PATCH_TARGETS, PHASES, validate_launch_plan
from .media import ARCHETYPES
from .models import GateResult, GateState, LaunchReport
from .rehearsal import run_archetype_rehearsal
from .reviewer import preserve_sovereign_block, review_metrics, structural_repair_candidates, two_pass_review
from .state_restore import apply_shadow_plan, canonical_hash, restore_original


class ModelsTests(unittest.TestCase):
    def test_gate_pass_property(self):
        self.assertTrue(GateResult("gate_one", "Gate one", GateState.PASS).passed)

    def test_gate_rejects_unsafe_id(self):
        with self.assertRaises(ValueError):
            GateResult("../bad", "Bad", GateState.FAIL)

    def test_gate_requires_label(self):
        with self.assertRaises(ValueError):
            GateResult("good", " ", GateState.FAIL)

    def test_report_requires_unique_gate_ids(self):
        gate = GateResult("same", "Same", GateState.PASS)
        with self.assertRaises(ValueError):
            LaunchReport("x", (gate, gate), {"x": 100}, {"x": 100})

    def test_report_weights_must_sum_to_100(self):
        gate = GateResult("a", "A", GateState.PASS)
        with self.assertRaises(ValueError):
            LaunchReport("x", (gate,), {"x": 100}, {"x": 99})

    def test_closed_report_has_no_blockers(self):
        gate = GateResult("a", "A", GateState.PASS)
        self.assertTrue(LaunchReport("x", (gate,), {"x": 100}, {"x": 100}).closed)

    def test_failed_blocking_gate_opens_report(self):
        gate = GateResult("a", "A", GateState.FAIL)
        self.assertFalse(LaunchReport("x", (gate,), {"x": 100}, {"x": 100}).closed)

    def test_weighted_overall_calculation(self):
        gate = GateResult("a", "A", GateState.PASS)
        report = LaunchReport("x", (gate,), {"a": 80, "b": 20}, {"a": 75, "b": 25})
        self.assertEqual(report.overall_percent, 65.0)


class ContractTests(unittest.TestCase):
    def test_eight_contracts_exist(self):
        self.assertEqual(len(CONTRACTS), 8)

    def test_contract_paths_are_unique(self):
        self.assertEqual(len({contract.path for contract in CONTRACTS}), 8)

    def test_canonical_snapshot_passes(self):
        self.assertTrue(validate_snapshot(canonical_snapshot())["ok"])

    def test_missing_contract_fails(self):
        self.assertFalse(validate_snapshot(canonical_snapshot()[:-1])["ok"])

    def test_sha_drift_fails(self):
        rows = canonical_snapshot()
        rows[0]["sha"] = "0" * 40
        self.assertFalse(validate_snapshot(rows)["ok"])

    def test_symbol_drift_fails(self):
        rows = canonical_snapshot()
        rows[0]["symbols"] = []
        self.assertFalse(validate_snapshot(rows)["ok"])


class LaunchPlanTests(unittest.TestCase):
    def test_seven_patch_targets(self):
        self.assertEqual(len(PATCH_TARGETS), 7)

    def test_five_phases(self):
        self.assertEqual(len(PHASES), 5)

    def test_patch_order_is_contiguous(self):
        self.assertEqual([item["order"] for item in PATCH_TARGETS], list(range(1, 8)))

    def test_phase_order_is_contiguous(self):
        self.assertEqual([item["phase"] for item in PHASES], list(range(5)))

    def test_every_patch_has_rollback(self):
        self.assertTrue(all(item["rollback"] for item in PATCH_TARGETS))

    def test_every_phase_has_gate(self):
        self.assertTrue(all(item["gate"] for item in PHASES))

    def test_launch_plan_validates(self):
        self.assertTrue(validate_launch_plan()["ok"])


class ReviewerTests(unittest.TestCase):
    def setUp(self):
        self.good = {"width": 1080, "height": 1920, "fps": 30, "has_audio": True, "motion_ratio": 1.0}

    def test_good_metrics_ship(self):
        self.assertEqual(review_metrics(self.good)["verdict"], "ship")

    def test_static_metrics_block(self):
        self.assertEqual(review_metrics({**self.good, "motion_ratio": 0.0})["verdict"], "block")

    def test_wrong_geometry_blocks(self):
        self.assertIn("wrong_geometry", review_metrics({**self.good, "width": 720})["auto_fails"])

    def test_missing_audio_blocks(self):
        self.assertIn("missing_audio", review_metrics({**self.good, "has_audio": False})["auto_fails"])

    def test_two_pass_review_is_stable(self):
        result = two_pass_review(self.good)
        self.assertTrue(result["both_ship"])
        self.assertTrue(result["scores_equal"])

    def test_all_archetypes_have_three_candidates(self):
        self.assertTrue(all(len(structural_repair_candidates(archetype)) == 3 for archetype in ARCHETYPES))

    def test_unknown_archetype_rejected(self):
        with self.assertRaises(ValueError):
            structural_repair_candidates("unknown")

    def test_sovereign_block_is_preserved(self):
        verdict = review_metrics({**self.good, "motion_ratio": 0.0})
        routed = preserve_sovereign_block(verdict, structural_repair_candidates("money"))
        self.assertFalse(routed["ship_override"])

    def test_ship_cannot_enter_block_router(self):
        with self.assertRaises(ValueError):
            preserve_sovereign_block(review_metrics(self.good), [{"viz": "trend"}])


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.story = {"slug": "x", "segments": [{"kind": "bubbles", "plan_locked": False}]}
        self.plan = {"segments": [{"index": 0, "kind": "trend", "perf_override": "drag_line"}]}

    def test_apply_changes_a_copy(self):
        changed, _ = apply_shadow_plan(self.story, self.plan)
        self.assertEqual(self.story["segments"][0]["kind"], "bubbles")
        self.assertEqual(changed["segments"][0]["kind"], "trend")

    def test_apply_locks_plan(self):
        changed, _ = apply_shadow_plan(self.story, self.plan)
        self.assertTrue(changed["segments"][0]["plan_locked"])

    def test_restore_returns_original_hash(self):
        changed, receipt = apply_shadow_plan(self.story, self.plan)
        restored = restore_original(changed, receipt)
        self.assertEqual(canonical_hash(restored), canonical_hash(self.story))

    def test_tampered_state_refuses_restore(self):
        changed, receipt = apply_shadow_plan(self.story, self.plan)
        changed["segments"][0]["kind"] = "share"
        with self.assertRaises(ValueError):
            restore_original(changed, receipt)

    def test_noop_plan_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_shadow_plan(self.story, {"segments": []})


class MediaAndClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.money = run_archetype_rehearsal(cls.root, "money")
        cls.payload = run_launch_rehearsal(cls.root / "all", cls.root / "evidence")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_rendered_video_has_production_geometry(self):
        self.assertEqual(self.money["shadow"]["probe"]["width"], 1080)
        self.assertEqual(self.money["shadow"]["probe"]["height"], 1920)

    def test_rendered_video_has_audio(self):
        self.assertTrue(self.money["shadow"]["probe"]["has_audio"])

    def test_shadow_motion_exceeds_baseline(self):
        self.assertGreater(self.money["improvement"]["motion_delta"], 0.5)

    def test_shadow_score_exceeds_baseline(self):
        self.assertGreater(self.money["improvement"]["score_delta"], 40)

    def test_shadow_rerun_is_deterministic(self):
        self.assertEqual(self.money["shadow"]["fingerprint"], self.money["shadow"]["rerun_fingerprint"])

    def test_baseline_is_blocked(self):
        self.assertEqual(self.money["baseline"]["verdict"]["verdict"], "block")

    def test_shadow_gets_two_ship_verdicts(self):
        self.assertTrue(self.money["shadow"]["review"]["both_ship"])

    def test_restore_drill_verified(self):
        self.assertTrue(self.money["rollback"]["verified"])

    def test_full_rehearsal_has_five_archetypes(self):
        self.assertEqual(len(self.payload["rehearsals"]), 5)

    def test_all_fourteen_gates_pass(self):
        self.assertEqual(self.payload["summary"]["launch_gates_passed"], 14)
        self.assertEqual(self.payload["summary"]["launch_gates_total"], 14)

    def test_launch_scope_is_100(self):
        self.assertEqual(self.payload["report"]["launch_scope_percent"], 100.0)

    def test_review_scope_is_100(self):
        self.assertEqual(self.payload["summary"]["review_scope_percent"], 100.0)

    def test_overall_is_honest_and_below_100(self):
        self.assertEqual(self.payload["summary"]["overall_percent"], 79.5)

    def test_production_stays_unmodified(self):
        self.assertFalse(self.payload["report"]["production_pipeline_modified"])

    def test_publishing_stays_disabled(self):
        self.assertFalse(self.payload["report"]["publishing_enabled"])

    def test_showrunner_authority_stays_unchanged(self):
        self.assertFalse(self.payload["report"]["showrunner_authority_changed"])

    def test_evidence_files_written(self):
        self.assertTrue((self.root / "evidence" / "sprint10_launch_report.json").exists())
        self.assertTrue((self.root / "evidence" / "sprint10_scorecard.json").exists())

    def test_dimensions_and_weights_match(self):
        self.assertEqual(set(DIMENSIONS), set(WEIGHTS))

    def test_weights_sum_to_100(self):
        self.assertAlmostEqual(sum(WEIGHTS.values()), 100.0)


if __name__ == "__main__":
    unittest.main()
