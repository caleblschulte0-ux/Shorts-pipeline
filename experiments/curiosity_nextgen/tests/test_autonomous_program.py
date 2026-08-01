from __future__ import annotations

import unittest

from experiments.curiosity_nextgen.autonomous_batch_controller import AutonomousBatchController, BatchPolicy, RunState
from experiments.curiosity_nextgen.autonomous_decision_engine import NextAction, StageOutcome, StageVerdict
from experiments.curiosity_nextgen.autonomous_program import compile_autonomous_program
from experiments.curiosity_nextgen.batch_acceptance import (
    BatchAcceptancePolicy,
    BatchDecision,
    StoryAcceptance,
    evaluate_batch_acceptance,
)
from experiments.curiosity_nextgen.production_stage_graph import StageName, build_default_graph
from experiments.curiosity_nextgen.story_intake_contract import AudienceLevel, FactualRisk, MediaMode, StoryBrief


def brief(story_id: str = "story-001", **overrides) -> StoryBrief:
    values = dict(
        story_id=story_id,
        topic_family="science",
        format_family="explainer",
        core_question="Why does this process work this way?",
        target_seconds=120,
        audience=AudienceLevel.GENERAL,
        factual_risk=FactualRisk.LOW,
        media_mode=MediaMode.MIXED,
        priority=50,
    )
    values.update(overrides)
    return StoryBrief(**values)


def pass_outcome(story_id: str, stage: StageName, **overrides) -> StageOutcome:
    values = dict(
        story_id=story_id,
        stage=stage,
        verdict=StageVerdict.PASS,
        severity=0.0,
        confidence=9.0,
    )
    values.update(overrides)
    return StageOutcome(**values)


def acceptance(story_id: str, index: int = 0, **overrides) -> StoryAcceptance:
    values = dict(
        story_id=story_id,
        topic_family=f"topic-{index % 4}",
        format_family=f"format-{index % 4}",
        completed=True,
        quarantined=False,
        quality_score=8.2,
        artifact_hash_bound=True,
        factual_evidence_complete=True,
        technical_pass=True,
        editorial_pass=True,
        hook_family=f"hook-{index}",
        visual_family=f"visual-{index}",
    )
    values.update(overrides)
    return StoryAcceptance(**values)


class AutonomousBatchControllerTests(unittest.TestCase):
    def controller(self, policy: BatchPolicy | None = None) -> AutonomousBatchController:
        return AutonomousBatchController(build_default_graph(), batch_policy=policy or BatchPolicy())

    def test_register_and_admit_respects_active_capacity(self):
        controller = self.controller(BatchPolicy(maximum_active_stories=2))
        controller.register((brief("a"), brief("b", topic_family="history"), brief("c", topic_family="nature")))
        self.assertEqual(len(controller.admit_pending()), 2)

    def test_duplicate_registration_raises(self):
        controller = self.controller()
        controller.register((brief("a"),))
        with self.assertRaises(ValueError):
            controller.register((brief("a"),))

    def test_exactly_fifty_stories_can_register(self):
        controller = self.controller(BatchPolicy(maximum_stories=50))
        controller.register(tuple(brief(f"story-{index:03d}") for index in range(50)))
        self.assertEqual(controller.snapshot().total, 50)

    def test_fifty_one_stories_cannot_register(self):
        controller = self.controller(BatchPolicy(maximum_stories=50))
        with self.assertRaises(ValueError):
            controller.register(tuple(brief(f"story-{index:03d}") for index in range(51)))

    def test_topic_concurrency_cap_is_enforced(self):
        policy = BatchPolicy(maximum_active_stories=3, maximum_concurrent_per_topic=1)
        controller = self.controller(policy)
        controller.register((brief("a"), brief("b"), brief("c")))
        self.assertEqual(controller.admit_pending(), ("a",))

    def test_format_concurrency_cap_is_enforced(self):
        policy = BatchPolicy(maximum_active_stories=3, maximum_concurrent_per_format=1)
        controller = self.controller(policy)
        controller.register((brief("a", topic_family="a"), brief("b", topic_family="b"), brief("c", topic_family="c")))
        self.assertEqual(controller.admit_pending(), ("a",))

    def test_claim_work_respects_stage_capacity(self):
        controller = self.controller(BatchPolicy(maximum_active_stories=3))
        controller.register((brief("a"), brief("b", topic_family="history"), brief("c", topic_family="nature")))
        controller.admit_pending()
        assignments = controller.claim_work({StageName.INTAKE: 2})
        self.assertEqual(len(assignments), 2)

    def test_negative_stage_capacity_raises(self):
        controller = self.controller()
        with self.assertRaises(ValueError):
            controller.claim_work({StageName.INTAKE: -1})

    def test_passed_stage_is_recorded_complete(self):
        controller = self.controller()
        controller.register((brief("a"),))
        controller.admit_pending()
        controller.claim_work({StageName.INTAKE: 1})
        decision = controller.record_outcome(pass_outcome("a", StageName.INTAKE))
        self.assertEqual(decision.action, NextAction.ADVANCE)
        self.assertIn(StageName.INTAKE, controller.get("a").completed)

    def test_unclaimed_outcome_is_rejected(self):
        controller = self.controller()
        controller.register((brief("a"),))
        controller.admit_pending()
        with self.assertRaises(ValueError):
            controller.record_outcome(pass_outcome("a", StageName.INTAKE))

    def test_held_story_can_resume(self):
        controller = self.controller()
        controller.register((brief("a"),))
        controller.admit_pending()
        controller.claim_work({StageName.INTAKE: 1})
        controller.record_outcome(pass_outcome("a", StageName.INTAKE, verdict=StageVerdict.HOLD))
        self.assertEqual(controller.get("a").state, RunState.HELD)
        controller.resume_held("a")
        self.assertEqual(controller.get("a").state, RunState.ACTIVE)

    def test_per_story_cost_budget_quarantines(self):
        controller = self.controller(BatchPolicy(maximum_cost_per_story=1.0))
        controller.register((brief("a"),))
        controller.admit_pending()
        controller.claim_work({StageName.INTAKE: 1})
        decision = controller.record_outcome(pass_outcome("a", StageName.INTAKE, cost_delta=2.0))
        self.assertEqual(decision.action, NextAction.QUARANTINE)
        self.assertEqual(controller.get("a").state, RunState.QUARANTINED)

    def test_repairable_failure_creates_forced_repair_work(self):
        controller = self.controller()
        controller.register((brief("a"),))
        controller.admit_pending()
        controller.claim_work({StageName.INTAKE: 1})
        controller.record_outcome(
            StageOutcome("a", StageName.INTAKE, StageVerdict.FAIL, 6.0, 8.0, repairable=True)
        )
        assignments = controller.claim_work({StageName.REPAIR: 1})
        self.assertEqual(assignments[0].stage, StageName.REPAIR)

    def test_factual_gap_rewinds_completed_descendants(self):
        controller = self.controller()
        controller.register((brief("a"),))
        run = controller.get("a")
        run.state = RunState.ACTIVE
        run.completed.update({
            StageName.INTAKE,
            StageName.RESEARCH,
            StageName.CLAIMS,
            StageName.SCRIPT,
            StageName.STORYBOARD,
            StageName.MEDIA,
            StageName.DRAFT_RENDER,
        })
        controller.claim_work({StageName.FACT_REVIEW: 1})
        controller.record_outcome(
            StageOutcome("a", StageName.FACT_REVIEW, StageVerdict.FAIL, 7.0, 8.0, factual_gap=True)
        )
        self.assertNotIn(StageName.RESEARCH, run.completed)
        self.assertNotIn(StageName.SCRIPT, run.completed)
        self.assertIn(StageName.INTAKE, run.completed)

    def test_quarantine_share_can_make_snapshot_unhealthy(self):
        controller = self.controller(BatchPolicy(maximum_quarantine_share=0.2))
        controller.register(tuple(brief(f"s{index}", topic_family=f"t{index}") for index in range(4)))
        controller.get("s0").state = RunState.QUARANTINED
        snapshot = controller.snapshot()
        self.assertFalse(snapshot.healthy)
        self.assertIn("quarantine_share_exceeds_policy", snapshot.warnings)

    def test_invariant_audit_detects_stage_overlap(self):
        controller = self.controller()
        controller.register((brief("a"),))
        run = controller.get("a")
        run.completed.add(StageName.INTAKE)
        run.in_progress.add(StageName.INTAKE)
        self.assertTrue(controller.audit_invariants())

    def test_publish_pass_marks_story_complete(self):
        controller = self.controller()
        controller.register((brief("a"),))
        run = controller.get("a")
        run.state = RunState.ACTIVE
        run.in_progress.add(StageName.PUBLISH)
        controller.record_outcome(pass_outcome("a", StageName.PUBLISH))
        self.assertEqual(run.state, RunState.COMPLETE)


class BatchAcceptanceTests(unittest.TestCase):
    def test_strong_diverse_batch_passes(self):
        report = evaluate_batch_acceptance(tuple(acceptance(f"s{index}", index) for index in range(4)))
        self.assertEqual(report.decision, BatchDecision.PASS)

    def test_low_completion_rate_rejects(self):
        stories = (acceptance("a", 0), acceptance("b", 1, completed=False), acceptance("c", 2, completed=False), acceptance("d", 3, completed=False))
        self.assertIn("completion_rate_below_floor", evaluate_batch_acceptance(stories).blockers)

    def test_excessive_quarantine_rate_rejects(self):
        stories = (acceptance("a", 0),) + tuple(acceptance(f"q{index}", index + 1, completed=False, quarantined=True, quality_score=None) for index in range(3))
        self.assertIn("quarantine_rate_above_ceiling", evaluate_batch_acceptance(stories).blockers)

    def test_low_quality_completed_story_rejects(self):
        stories = tuple(acceptance(f"s{index}", index, quality_score=6.0 if index == 0 else 8.0) for index in range(4))
        self.assertIn("completed_story_below_quality_floor", evaluate_batch_acceptance(stories).blockers)

    def test_missing_hash_binding_rejects(self):
        stories = tuple(acceptance(f"s{index}", index, artifact_hash_bound=index != 0) for index in range(4))
        self.assertIn("completed_story_not_hash_bound", evaluate_batch_acceptance(stories).blockers)

    def test_missing_factual_evidence_rejects(self):
        stories = tuple(acceptance(f"s{index}", index, factual_evidence_complete=index != 0) for index in range(4))
        self.assertIn("completed_story_missing_factual_evidence", evaluate_batch_acceptance(stories).blockers)

    def test_missing_judge_pass_rejects(self):
        stories = tuple(acceptance(f"s{index}", index, editorial_pass=index != 0) for index in range(4))
        self.assertIn("completed_story_missing_required_judge_pass", evaluate_batch_acceptance(stories).blockers)

    def test_hard_blocker_on_completed_story_rejects(self):
        stories = tuple(acceptance(f"s{index}", index, hard_blockers=("unsafe",) if index == 0 else ()) for index in range(4))
        self.assertIn("completed_story_has_hard_blocker", evaluate_batch_acceptance(stories).blockers)

    def test_hook_family_concentration_requires_revision(self):
        stories = tuple(acceptance(f"s{index}", index, hook_family="same-hook") for index in range(4))
        report = evaluate_batch_acceptance(stories)
        self.assertEqual(report.decision, BatchDecision.REVISE)
        self.assertIn("hook_family_overconcentrated", report.warnings)

    def test_visual_family_concentration_requires_revision(self):
        stories = tuple(acceptance(f"s{index}", index, visual_family="same-visual") for index in range(4))
        self.assertIn("visual_family_overconcentrated", evaluate_batch_acceptance(stories).warnings)

    def test_duplicate_acceptance_record_raises(self):
        with self.assertRaises(ValueError):
            evaluate_batch_acceptance((acceptance("same"), acceptance("same", 1)))

    def test_story_cannot_be_complete_and_quarantined(self):
        with self.assertRaises(ValueError):
            acceptance("bad", completed=True, quarantined=True)


class AutonomousProgramTests(unittest.TestCase):
    def test_compile_registers_admits_and_assigns(self):
        _, plan = compile_autonomous_program((brief("a"), brief("b", topic_family="history")))
        self.assertTrue(plan.ready)
        self.assertEqual(len(plan.registered_story_ids), 2)
        self.assertEqual(len(plan.initial_assignments), 2)

    def test_invalid_intake_does_not_report_ready(self):
        _, plan = compile_autonomous_program((brief("bad", core_question="Why now?"),))
        self.assertFalse(plan.ready)
        self.assertIn("no_accepted_stories", plan.blockers)

    def test_cycle_advances_from_intake_to_research(self):
        program, plan = compile_autonomous_program((brief("a"),))
        self.assertEqual(plan.initial_assignments, (("a", "intake"),))
        assignments = program.cycle(
            stage_capacities={StageName.RESEARCH: 1},
            outcomes=(pass_outcome("a", StageName.INTAKE),),
        )
        self.assertEqual(assignments, (("a", "research"),))

    def test_fifty_story_program_only_activates_configured_wave(self):
        stories = tuple(
            brief(f"story-{index:03d}", topic_family=f"topic-{index % 10}", format_family=f"format-{index % 5}")
            for index in range(50)
        )
        _, plan = compile_autonomous_program(stories, batch_policy=BatchPolicy(maximum_active_stories=8, maximum_concurrent_per_topic=2))
        self.assertEqual(len(plan.registered_story_ids), 50)
        self.assertEqual(len(plan.initial_admitted_story_ids), 8)

    def test_program_graph_digest_is_sha256_length(self):
        _, plan = compile_autonomous_program((brief("a"),))
        self.assertEqual(len(plan.graph_digest), 64)


if __name__ == "__main__":
    unittest.main()
