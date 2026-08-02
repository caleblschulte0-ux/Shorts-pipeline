from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from review_prototypes.attempt_store import AttemptStore


class AttemptStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.attempts = root / "attempts"
        self.canonical = root / "canonical"
        self.inputs = root / "inputs"
        self.inputs.mkdir()
        self.store = AttemptStore(self.attempts, self.canonical)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _video(self, name: str, payload: bytes) -> Path:
        path = self.inputs / name
        path.write_bytes(payload)
        return path

    def _attempt(self, attempt_id: str, score: float, marker: str, *, verdict: str = "block"):
        return self.store.record_attempt(
            slug="example-story",
            run_id="run-1",
            attempt_id=attempt_id,
            scene_plan={"marker": marker},
            verdict={
                "verdict": verdict,
                "score": score,
                "hard_failures": [],
                "dimensions": {"clarity": score, "payoff": score - 5},
                "temporal": {"effective_fps": 27, "duplicate_ratio": 0.05},
            },
            video_path=self._video(f"{attempt_id}.mp4", marker.encode()),
        )

    def test_losing_repair_does_not_replace_incumbent(self) -> None:
        incumbent = self._attempt("attempt_0", 68, "baseline")
        candidate = self._attempt("attempt_1", 54, "worse")

        first = self.store.promote(incumbent)
        winner = self.store.choose_better(incumbent, candidate)
        promoted = self.store.promote(winner)

        self.assertEqual(winner.attempt_id, "attempt_0")
        self.assertEqual((promoted / "video.mp4").read_bytes(), b"baseline")
        plan = json.loads((promoted / "scene_plan.json").read_text())
        self.assertEqual(plan["marker"], "baseline")
        self.assertEqual(first, promoted)

    def test_better_repair_is_promoted_as_complete_state(self) -> None:
        incumbent = self._attempt("attempt_0", 68, "baseline")
        candidate = self._attempt("attempt_1", 76, "better")

        self.store.promote(incumbent)
        winner = self.store.choose_better(incumbent, candidate)
        promoted = self.store.promote(winner)

        self.assertEqual(winner.attempt_id, "attempt_1")
        self.assertEqual((promoted / "video.mp4").read_bytes(), b"better")
        plan = json.loads((promoted / "scene_plan.json").read_text())
        verdict = json.loads((promoted / "verdict.json").read_text())
        self.assertEqual(plan["marker"], "better")
        self.assertEqual(verdict["score"], 76)

    def test_ship_beats_higher_scoring_block(self) -> None:
        blocked = self._attempt("attempt_0", 95, "blocked", verdict="block")
        shipped = self._attempt("attempt_1", 86, "shipped", verdict="ship")
        winner = self.store.choose_better(blocked, shipped)
        self.assertEqual(winner.attempt_id, "attempt_1")


if __name__ == "__main__":
    unittest.main()
