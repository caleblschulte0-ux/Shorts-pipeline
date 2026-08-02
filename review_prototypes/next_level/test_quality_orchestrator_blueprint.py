"""Standalone review examples for quality_orchestrator_blueprint.py.

Run manually from the repository root if desired:
    python review_prototypes/next_level/test_quality_orchestrator_blueprint.py

No workflow invokes this file. All collaborators are in-memory fakes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "quality_orchestrator_blueprint",
    HERE / "quality_orchestrator_blueprint.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def target():
    return MODULE.RepairTarget(
        scene_id="segment_1",
        scene_index=1,
        start_seconds=6.0,
        end_seconds=10.0,
        failure_class="decorative_mascot",
        visible_evidence="The mascot follows the chart without a readable goal.",
        root_cause="Position following was treated as performance.",
        repair_goal="Add effort, reversal, and consequence.",
    )


def verdict(kind, score, *, weakest=None):
    return MODULE.FullVerdict(
        verdict=kind,
        score=float(score),
        lowest_dimension=7.0 if score >= 70 else 5.5,
        hard_failures=(),
        weakest_scene=weakest,
        watched_video=True,
        primary_judge_version="taste-v4",
        adversarial_judge_version="adversarial-v2",
    )


def bundle(attempt_id):
    return MODULE.ArtifactBundle(
        attempt_id=attempt_id,
        story_slug="world-power-mix",
        plan_hash=f"plan:{attempt_id}",
        video_hash=f"video:{attempt_id}",
        manifest_hash=f"manifest:{attempt_id}",
        video_location=f"isolated/{attempt_id}/video.mp4",
        plan_location=f"isolated/{attempt_id}/plan.json",
    )


class FakeCandidates:
    def propose(self, story_slug, repair_target, *, incumbent, count):
        self.last_target = repair_target
        plans = (
            MODULE.ScenePlan(
                candidate_id="candidate-balance",
                scene_id=repair_target.scene_id,
                visualization="weighted_balance",
                performance_family="overwhelmed_balance",
                camera_purpose="reveal the dominant side dropping",
                payoff="mascot loses footing when the beam tips",
                semantic_rationale="balance directly communicates dominance",
            ),
            MODULE.ScenePlan(
                candidate_id="candidate-stack",
                scene_id=repair_target.scene_id,
                visualization="stack",
                performance_family="overload_carry",
                camera_purpose="reveal accumulated scale",
                payoff="the stack overwhelms the mascot",
                semantic_rationale="stack preserves part-to-whole dominance",
            ),
        )
        return plans[:count]


class FakeRenderer:
    def __init__(self, *, preview_pass=True):
        self.preview_pass = preview_pass
        self.full_count = 0

    def render_baseline(self, story_slug):
        return bundle("attempt-0")

    def render_scene_preview(self, story_slug, candidate):
        return MODULE.ScenePreview(
            candidate=candidate,
            preview_hash=f"preview:{candidate.candidate_id}",
            preview_location=f"previews/{candidate.candidate_id}.mp4",
            objective_passed=self.preview_pass,
            objective_failures=() if self.preview_pass else ("text_overflow",),
        )

    def render_full_attempt(self, story_slug, *, incumbent, candidate, iteration):
        self.full_count += 1
        return bundle(f"attempt-{iteration}")


class FakeJudge:
    def __init__(self, verdicts):
        self.verdicts = verdicts

    def judge_full(self, artifacts):
        return self.verdicts[artifacts.attempt_id]

    def rank_previews(self, repair_target, previews):
        ordered = tuple(preview.candidate.candidate_id for preview in previews)
        return MODULE.CandidateRanking(
            ordered_candidate_ids=ordered,
            reasons={ordered[0]: "best semantic and visual fit"},
            watched_previews=True,
            judge_version="preview-v2",
        )


class FakeStore:
    def __init__(self):
        self.attempts = {}
        self.canonical = {}

    def save_attempt(self, attempt):
        self.attempts[attempt.artifacts.attempt_id] = attempt

    def promote(self, attempt_id):
        attempt = self.attempts[attempt_id]
        self.canonical[attempt.artifacts.story_slug] = attempt_id

    def canonical_attempt_id(self, story_slug):
        return self.canonical.get(story_slug)


class QualityOrchestratorBlueprintTests(unittest.TestCase):
    def test_worse_challenger_never_replaces_incumbent_state(self) -> None:
        store = FakeStore()
        orchestrator = MODULE.QualityOrchestrator(
            renderer=FakeRenderer(),
            judge=FakeJudge(
                {
                    "attempt-0": verdict(
                        MODULE.VerdictClass.HOLD,
                        68,
                        weakest=target(),
                    ),
                    "attempt-1": verdict(
                        MODULE.VerdictClass.HOLD,
                        54,
                        weakest=target(),
                    ),
                }
            ),
            candidates=FakeCandidates(),
            store=store,
            maximum_repairs=1,
        )
        report = orchestrator.run("world-power-mix")
        self.assertEqual(report.canonical_attempt_id, "attempt-0")
        self.assertEqual(store.canonical_attempt_id("world-power-mix"), "attempt-0")
        self.assertTrue(
            any(event.kind == "challenger_rejected" for event in report.events)
        )

    def test_better_complete_challenger_is_promoted(self) -> None:
        store = FakeStore()
        orchestrator = MODULE.QualityOrchestrator(
            renderer=FakeRenderer(),
            judge=FakeJudge(
                {
                    "attempt-0": verdict(
                        MODULE.VerdictClass.HOLD,
                        68,
                        weakest=target(),
                    ),
                    "attempt-1": verdict(MODULE.VerdictClass.SHIP, 82),
                }
            ),
            candidates=FakeCandidates(),
            store=store,
            maximum_repairs=1,
        )
        report = orchestrator.run("world-power-mix")
        self.assertEqual(report.canonical_attempt_id, "attempt-1")
        self.assertEqual(store.canonical_attempt_id("world-power-mix"), "attempt-1")
        self.assertEqual(report.stopped_reason, "winner_shipped")

    def test_all_failed_previews_keep_baseline(self) -> None:
        store = FakeStore()
        orchestrator = MODULE.QualityOrchestrator(
            renderer=FakeRenderer(preview_pass=False),
            judge=FakeJudge(
                {
                    "attempt-0": verdict(
                        MODULE.VerdictClass.HOLD,
                        68,
                        weakest=target(),
                    )
                }
            ),
            candidates=FakeCandidates(),
            store=store,
            maximum_repairs=1,
        )
        report = orchestrator.run("world-power-mix")
        self.assertEqual(report.canonical_attempt_id, "attempt-0")
        self.assertTrue(
            any(
                "all candidate previews failed" in event.detail
                for event in report.events
            )
        )


if __name__ == "__main__":
    unittest.main()
