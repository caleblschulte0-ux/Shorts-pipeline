from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from .acceptance import assess_runs
from .models import StoryProof, SuiteRunProof
from .runner import FullVideoProofRunner, ProofRunConfig
from .store import ProofStore, ProofStoreError


SLUGS = ("a", "b", "c", "d", "e", "f")


def story(slug: str, score: float = 92.0, fps: float = 29.0) -> StoryProof:
    return StoryProof(
        slug=slug,
        score=score,
        dimensions={"clarity": 8.6, "payoff": 8.4},
        hard_failures=(),
        effective_fps=fps,
        duplicate_ratio=0.05,
        decorative_mascot_failures=0,
        video_sha256=f"video-{slug}",
        verdict_sha256=f"verdict-{slug}",
        watched_video=True,
    )


def run(run_id: str, scores=None, version="suite-v1") -> SuiteRunProof:
    scores = scores or [92] * 6
    return SuiteRunProof(
        run_id=run_id,
        suite_version=version,
        judge_version="judge-v4",
        renderer_commit="abc123",
        stories=tuple(story(slug, score) for slug, score in zip(SLUGS, scores)),
        artifact_manifest_sha256=f"manifest-{run_id}",
    )


class FakeExecutor:
    def execute(self, slug: str, run_id: str) -> StoryProof:
        return story(slug, 91)


class FullVideoProofTests(unittest.TestCase):
    def test_two_stable_runs_pass_phase_three(self) -> None:
        assessment = assess_runs([run("r1"), run("r2")], 3, SLUGS)
        self.assertTrue(assessment.passed, assessment.reasons)

    def test_one_story_collapse_blocks_suite(self) -> None:
        assessment = assess_runs([run("r1"), run("r2", [92, 92, 92, 92, 92, 70])], 3, SLUGS)
        self.assertFalse(assessment.passed)
        self.assertTrue(any("lowest score" in reason for reason in assessment.reasons))

    def test_version_change_blocks_consecutive_claim(self) -> None:
        assessment = assess_runs([run("r1"), run("r2", version="suite-v2")], 1, SLUGS)
        self.assertFalse(assessment.passed)
        self.assertTrue(any("versions" in reason for reason in assessment.reasons))

    def test_store_is_append_only_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ProofStore(Path(temp))
            store.save(run("r1"))
            self.assertTrue(store.verify("r1"))
            with self.assertRaises(ProofStoreError):
                store.save(run("r1"))
            (Path(temp) / "r1" / "proof.json").write_text("{}", encoding="utf-8")
            self.assertFalse(store.verify("r1"))

    def test_runner_executes_complete_ordered_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runner = FullVideoProofRunner(FakeExecutor(), ProofStore(Path(temp)))
            proof = runner.run(ProofRunConfig("r1", "suite-v1", "judge-v4", "abc", SLUGS))
            self.assertEqual(tuple(item.slug for item in proof.stories), SLUGS)
            self.assertTrue((Path(temp) / "r1" / "proof.json").is_file())


if __name__ == "__main__":
    unittest.main()
