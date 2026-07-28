from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from .catalog import COMPONENTS, PHASES, build_master_handoff
from .models import AdoptionPhase, Component, HandoffValidationError
from .validator import (
    manifest_as_dict,
    validate_commands,
    validate_master_handoff,
    validate_production_boundaries,
    validate_repo_paths,
)


class MasterHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.handoff = build_master_handoff()

    def test_master_handoff_validates(self):
        self.handoff.validate()

    def test_status_is_review_only(self):
        self.assertEqual(self.handoff.status, "review_only_unwired")

    def test_pr_and_branch_are_pinned(self):
        self.assertEqual(self.handoff.pull_request, 174)
        self.assertEqual(self.handoff.branch, "agent/claude-roadmap-review")

    def test_component_catalog_is_large_enough(self):
        self.assertGreaterEqual(len(self.handoff.components), 20)

    def test_every_component_is_review_only(self):
        for component in self.handoff.components:
            self.assertTrue(component.root.startswith(("review_prototypes/", "docs/")))

    def test_component_ids_are_unique(self):
        ids = [component.component_id for component in self.handoff.components]
        self.assertEqual(len(ids), len(set(ids)))

    def test_phase_ids_are_unique(self):
        ids = [phase.phase_id for phase in self.handoff.phases]
        self.assertEqual(len(ids), len(set(ids)))

    def test_component_dependencies_exist(self):
        ids = {component.component_id for component in self.handoff.components}
        for component in self.handoff.components:
            self.assertFalse(set(component.depends_on) - ids)

    def test_phase_dependencies_exist(self):
        ids = {phase.phase_id for phase in self.handoff.phases}
        for phase in self.handoff.phases:
            self.assertFalse(set(phase.depends_on) - ids)

    def test_each_phase_has_acceptance_and_rollback(self):
        for phase in self.handoff.phases:
            self.assertTrue(phase.acceptance)
            self.assertTrue(phase.rollback)
            self.assertTrue(phase.stop_conditions)

    def test_first_phase_is_read_only(self):
        first = self.handoff.phases[0]
        self.assertEqual(first.authority_ceiling, "none")
        self.assertFalse(first.production_files)

    def test_no_unsafe_commands(self):
        self.assertEqual(validate_commands(self.handoff), [])

    def test_no_production_boundary_errors(self):
        self.assertEqual(validate_production_boundaries(self.handoff), [])

    def test_showrunner_guard_exists(self):
        guards = " ".join(self.handoff.sacred_guards).lower()
        self.assertIn("showrunner", guards)
        self.assertIn("block", guards)

    def test_publishing_guard_exists(self):
        guards = " ".join(self.handoff.sacred_guards).lower()
        self.assertIn("publishing", guards)
        self.assertIn("frozen", guards)

    def test_decision_routes_cover_current_quality(self):
        self.assertIn("improve_current_video_quality", self.handoff.decision_routes)

    def test_decision_routes_cover_subscription_independence(self):
        self.assertIn("make_posting_independent_of_live_ai", self.handoff.decision_routes)

    def test_decision_routes_cover_institutional_learning(self):
        self.assertIn("build_institutional_learning", self.handoff.decision_routes)

    def test_professional_media_os_has_no_production_authority(self):
        component = next(c for c in self.handoff.components if c.component_id == "professional_media_os")
        self.assertEqual(component.authority, "reference_only")
        self.assertIn("uncalibrated", component.maturity)

    def test_launch_closure_is_preview_only(self):
        component = next(c for c in self.handoff.components if c.component_id == "launch_closure")
        self.assertEqual(component.authority, "preview_only")

    def test_verified_and_unverified_evidence_are_distinct(self):
        statuses = {claim.status for claim in self.handoff.evidence}
        self.assertEqual(statuses, {"verified", "declared_unverified", "not_claimed"})

    def test_production_and_real_channel_are_not_claimed(self):
        claims = {claim.claim_id: claim for claim in self.handoff.evidence}
        self.assertEqual(claims["production_wiring"].status, "not_claimed")
        self.assertEqual(claims["real_channel_performance"].status, "not_claimed")

    def test_manifest_is_json_serializable(self):
        encoded = json.dumps(manifest_as_dict(), sort_keys=True)
        self.assertIn("claude-master-handoff/v1", encoded)

    def test_cycle_is_rejected(self):
        a = Component("a", "A", "review_prototypes/a", "a", "x", "none", depends_on=("b",))
        b = Component("b", "B", "review_prototypes/b", "b", "x", "none", depends_on=("a",))
        bad = replace(self.handoff, components=(a, b))
        with self.assertRaises(HandoffValidationError):
            bad.validate()

    def test_missing_phase_rollback_is_rejected(self):
        bad_phase = AdoptionPhase(
            "bad",
            "Bad",
            "bad",
            ("echo bad",),
            ("pass",),
            (),
            ("stop",),
        )
        bad = replace(self.handoff, phases=(bad_phase,))
        with self.assertRaises(HandoffValidationError):
            bad.validate()

    def test_repo_path_validation_passes_for_fixture_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            required = {component.root for component in self.handoff.components}
            required.update(claim.source_path for claim in self.handoff.evidence)
            required.update(
                {
                    "review_prototypes/launch_closure/fixtures/CLAUDE_LAUNCH.md",
                    "review_prototypes/launch_closure/fixtures/claude_launch_manifest.json",
                    "review_prototypes/professional_media_os/ADOPTION_MANIFEST.json",
                    "docs/future/CLAUDE_PROFESSIONAL_MEDIA_OS_ADOPTION.md",
                }
            )
            for relative in required:
                path = root / relative
                if Path(relative).suffix:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("fixture", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)
            self.assertEqual(validate_repo_paths(self.handoff, root), [])

    def test_repo_path_validation_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            errors = validate_repo_paths(self.handoff, Path(td))
            self.assertTrue(errors)
            self.assertTrue(all(error.startswith("missing referenced path") for error in errors))

    def test_validation_report_is_green_without_repo(self):
        report = validate_master_handoff()
        self.assertTrue(report.ok, report["errors"])
        self.assertEqual(report["components"], len(COMPONENTS))
        self.assertEqual(report["phases"], len(PHASES))


if __name__ == "__main__":
    unittest.main()
