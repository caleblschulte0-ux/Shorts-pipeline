from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from .engine import RepairEngine
from .models import (
    Decision,
    SceneCandidate,
    SceneDiagnosis,
    TemporalMetrics,
    Verdict,
)
from .repository import AttemptRepository, RepositoryError


def diagnosis() -> SceneDiagnosis:
    return SceneDiagnosis(
        scene_id="segment_1",
        scene_index=1,
        start_seconds=5.0,
        end_seconds=9.0,
        failure_class="weak_payoff",
        visible_evidence="The consequence never lands.",
        root_cause="The timeline stops after the reveal.",
        repair_goal="Add consequence, reaction, and settle.",
    )


def verdict(
    score: float,
    decision: Decision = Decision.HOLD,
) -> Verdict:
    return Verdict(
        decision=decision,
        score=score,
        dimensions={
            "clarity": score / 10,
            "craft": score / 10,
            "payoff": score / 10,
        },
        hard_failures=(),
        temporal=TemporalMetrics(29.0, 0.04, 2, 0.1),
        weakest_scene=(
            None if decision is Decision.SHIP else diagnosis()
        ),
        watched_video=True,
        judge_version="fake-v1",
    )


class FakeRenderer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    @staticmethod
    def _write(destination: Path, marker: str) -> None:
        (destination / "video.mp4").write_bytes(marker.encode())
        (destination / "scene_plan.json").write_text(
            json.dumps({"marker": marker}),
            encoding="utf-8",
        )
        (destination / "scenes").mkdir()
        (destination / "scenes" / "segment_1.txt").write_text(
            marker,
            encoding="utf-8",
        )

    def render_baseline(self, slug: str, destination: Path) -> None:
        self.calls.append("baseline")
        self._write(destination, "baseline")

    def render_candidate(
        self,
        slug,
        incumbent,
        candidate,
        destination,
    ) -> None:
        self.calls.append(candidate.candidate_id)
        self._write(destination, candidate.candidate_id)


class FakeJudge:
    def __init__(self, scores) -> None:
        self.scores = iter(scores)

    def judge(self, slug: str, rendered_dir: Path) -> Verdict:
        item = next(self.scores)
        return verdict(*item) if isinstance(item, tuple) else verdict(item)


class FakeGenerator:
    def propose(self, slug, target, incumbent, *, count):
        return (
            SceneCandidate(
                "candidate_a",
                target.scene_id,
                "trend_line",
                "resisted_growth",
                target.repair_goal,
                "Makes the consequence visible.",
            ),
            SceneCandidate(
                "candidate_b",
                target.scene_id,
                "weighted_balance",
                "overwhelmed_balance",
                target.repair_goal,
                "Turns the imbalance into a physical payoff.",
            ),
            SceneCandidate(
                "candidate_c",
                target.scene_id,
                "stack",
                "buried_by_scale",
                target.repair_goal,
                "Shows scale through accumulation.",
            ),
        )[:count]


class FirstRanker:
    def select(self, slug, diagnosis, candidates):
        return candidates[0]


class RuntimeTests(unittest.TestCase):
    def make_engine(self, root: Path, scores, *, repairs=2):
        return RepairEngine(
            repository=AttemptRepository(root / "repository"),
            renderer=FakeRenderer(),
            judge=FakeJudge(scores),
            candidate_generator=FakeGenerator(),
            preview_ranker=FirstRanker(),
            work_root=root / "work",
            maximum_repairs=repairs,
        )

    def test_worse_repair_does_not_replace_incumbent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            engine = self.make_engine(root, [70, 55], repairs=1)
            result = engine.run("demo", run_id="run-a")
            canonical = engine.repository.canonical("demo")
            self.assertEqual(result.canonical_attempt_id, "attempt_0")
            self.assertEqual(
                canonical.identity.attempt_id,
                "attempt_0",
            )
            self.assertEqual(
                (canonical.path / "video.mp4").read_bytes(),
                b"baseline",
            )
            self.assertTrue(
                any(
                    step.kind == "challenger_rejected"
                    for step in result.steps
                )
            )

    def test_better_repair_is_promoted_as_complete_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            engine = self.make_engine(
                root,
                [70, (91, Decision.SHIP)],
                repairs=1,
            )
            result = engine.run("demo", run_id="run-b")
            canonical = engine.repository.canonical("demo")
            self.assertEqual(result.stopped_reason, "repaired_to_ship")
            self.assertEqual(
                canonical.identity.attempt_id,
                "attempt_1",
            )
            self.assertEqual(
                (canonical.path / "video.mp4").read_bytes(),
                b"candidate_a",
            )
            self.assertTrue(
                (canonical.path / "manifest.json").is_file()
            )
            self.assertTrue(
                (
                    canonical.path
                    / "scenes"
                    / "segment_1.txt"
                ).is_file()
            )

    def test_tampering_breaks_manifest_verification(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            engine = self.make_engine(
                root,
                [(91, Decision.SHIP)],
                repairs=0,
            )
            engine.run("demo", run_id="run-c")
            canonical = engine.repository.canonical("demo")
            (canonical.path / "video.mp4").write_bytes(b"tampered")
            with self.assertRaises(RepositoryError):
                engine.repository.canonical("demo")

    def test_reject_is_not_promoted_after_budget_exhaustion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rejected = Verdict(
                decision=Decision.REJECT,
                score=40,
                dimensions={"clarity": 4, "craft": 4},
                hard_failures=("clipping",),
                temporal=TemporalMetrics(18, 0.4),
                weakest_scene=diagnosis(),
                watched_video=True,
                judge_version="fake-v1",
            )

            class OneJudge:
                def judge(self, slug, rendered_dir):
                    return rejected

            engine = RepairEngine(
                repository=AttemptRepository(root / "repository"),
                renderer=FakeRenderer(),
                judge=OneJudge(),
                candidate_generator=FakeGenerator(),
                preview_ranker=FirstRanker(),
                work_root=root / "work",
                maximum_repairs=0,
            )
            result = engine.run("demo", run_id="run-d")
            self.assertIsNone(result.canonical_attempt_id)
            self.assertEqual(
                result.stopped_reason,
                "budget_exhausted_no_promotable_attempt",
            )


if __name__ == "__main__":
    unittest.main()
