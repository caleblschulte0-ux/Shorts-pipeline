from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from .controller import ReleaseController
from .models import ReleaseCandidate
from .repository import ReleaseRepository, ReleaseRepositoryError


def candidate(release_id: str, score: float = 90.0) -> ReleaseCandidate:
    return ReleaseCandidate(
        release_id=release_id,
        slug="demo",
        attempt_id=f"attempt-{release_id}",
        video_sha256=f"video-{release_id}",
        verdict_sha256=f"verdict-{release_id}",
        proof_run_id="proof-r2",
        score=score,
        hard_failures=(),
        readiness={"sources": True, "retention": True, "showrunner": True, "proof": True},
    )


class ReleaseSafetyTests(unittest.TestCase):
    def test_valid_release_promotes_and_low_score_holds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = ReleaseRepository(Path(temp))
            controller = ReleaseController(repo, minimum_score=80)
            self.assertTrue(controller.submit(candidate("r1", 91)).promoted)
            held = controller.submit(candidate("r2", 70))
            self.assertFalse(held.promoted)
            self.assertEqual(repo.state().canonical_release_id, "r1")

    def test_quarantine_current_release_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = ReleaseRepository(Path(temp))
            controller = ReleaseController(repo)
            controller.submit(candidate("r1"))
            controller.submit(candidate("r2", 92))
            repo.quarantine("r2", "post-release anomaly")
            state = repo.rollback()
            self.assertEqual(state.canonical_release_id, "r1")
            self.assertIn("r2", state.quarantined_release_ids)

    def test_tampered_release_cannot_promote(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = ReleaseRepository(Path(temp))
            repo.record(candidate("r1"))
            path = Path(temp) / "records" / "r1" / "manifest.json"
            payload = json.loads(path.read_text())
            payload["score"] = 100
            path.write_text(json.dumps(payload))
            with self.assertRaises(ReleaseRepositoryError):
                repo.promote("r1")

    def test_no_prior_release_means_rollback_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = ReleaseRepository(Path(temp))
            with self.assertRaises(ReleaseRepositoryError):
                repo.rollback()


if __name__ == "__main__":
    unittest.main()
