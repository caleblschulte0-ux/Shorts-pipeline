from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from review_prototypes.full_video_proof.models import StoryProof, SuiteRunProof
from review_prototypes.observability.event_log import HashChainedEventLog
from review_prototypes.release_safety.controller import ReleaseController
from review_prototypes.release_safety.models import ReleaseCandidate
from review_prototypes.release_safety.repository import ReleaseRepository

from .control_plane import ReviewControlPlane


SLUGS = ("a", "b", "c", "d", "e", "f")


def proof_run(run_id: str, score: float = 92.0) -> SuiteRunProof:
    stories = tuple(
        StoryProof(
            slug=slug,
            score=score,
            dimensions={"clarity": 8.5, "payoff": 8.3},
            hard_failures=(),
            effective_fps=29,
            duplicate_ratio=0.05,
            decorative_mascot_failures=0,
            video_sha256=f"video-{run_id}-{slug}",
            verdict_sha256=f"verdict-{run_id}-{slug}",
            watched_video=True,
        )
        for slug in SLUGS
    )
    return SuiteRunProof(run_id, "suite-v1", "judge-v4", "abc", stories, f"manifest-{run_id}")


def candidate(release_id: str) -> ReleaseCandidate:
    return ReleaseCandidate(
        release_id=release_id,
        slug="a",
        attempt_id="attempt-a",
        video_sha256="video-r2-a",
        verdict_sha256="verdict-r2-a",
        proof_run_id="r2",
        score=92,
        hard_failures=(),
        readiness={"sources": True, "retention": True, "showrunner": True, "proof": True},
    )


class SprintThreeControlPlaneTests(unittest.TestCase):
    def test_passing_proof_allows_release_and_audit_chain_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plane = ReviewControlPlane(
                HashChainedEventLog(root / "events.jsonl"),
                ReleaseController(ReleaseRepository(root / "releases"), minimum_score=85),
            )
            result = plane.execute(
                runs=(proof_run("r1"), proof_run("r2")),
                phase=3,
                expected_slugs=SLUGS,
                candidates=(candidate("release-1"),),
            )
            self.assertTrue(result.proof.passed)
            self.assertTrue(result.releases[0].promoted)
            self.assertTrue(result.event_log_verified)

    def test_failed_proof_blocks_release_even_when_candidate_is_strong(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            plane = ReviewControlPlane(
                HashChainedEventLog(root / "events.jsonl"),
                ReleaseController(ReleaseRepository(root / "releases")),
            )
            result = plane.execute(
                runs=(proof_run("r1", 70), proof_run("r2", 70)),
                phase=3,
                expected_slugs=SLUGS,
                candidates=(candidate("release-1"),),
            )
            self.assertFalse(result.proof.passed)
            self.assertFalse(result.releases[0].promoted)
            self.assertIsNone(result.releases[0].state.canonical_release_id)


if __name__ == "__main__":
    unittest.main()
