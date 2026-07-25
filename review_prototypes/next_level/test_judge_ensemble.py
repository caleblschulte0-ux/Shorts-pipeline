"""Standalone review examples for judge_ensemble.py.

Run manually from the repository root if desired:
    python review_prototypes/next_level/test_judge_ensemble.py

No workflow invokes this file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "judge_ensemble", HERE / "judge_ensemble.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def objective(*, fps: float = 30.0, clipping: bool = False):
    return MODULE.ObjectiveEvidence(
        render_complete=True,
        audio_present=True,
        text_overflow=False,
        clipping=clipping,
        safe_area_violations=0,
        temporal=MODULE.TemporalEvidence(
            effective_fps=fps,
            duplicate_ratio=0.05,
            longest_duplicate_run=2,
            longest_unmarked_static_seconds=0.10,
        ),
        artifact_hashes_present=True,
    )


def diagnosis():
    return MODULE.SceneDiagnosis(
        scene_id="segment_1",
        scene_index=1,
        start_seconds=6.0,
        end_seconds=10.0,
        failure_class="weak_payoff",
        visible_evidence="The scene ends before the consequence lands.",
        root_cause="Timeline omits recovery and settle.",
        repair_goal="Add impact, reaction, and settle without extending dead air.",
    )


def primary(*, score: float = 92.0, failures=()):
    return MODULE.VisionVerdict(
        score=score,
        dimensions={
            "clarity": 9.0,
            "craft": 9.0,
            "mascot": 9.0,
            "payoff": 8.5,
        },
        hard_failure_labels=tuple(failures),
        evidence_timestamps=(1.2, 8.7),
        weakest_scene=diagnosis(),
        watched_video=True,
        judge_version="taste-v4",
    )


def adversarial(*, labels=(), confidence: float = 0.0):
    return MODULE.AdversarialVerdict(
        objection_labels=tuple(labels),
        confidence=confidence,
        watched_video=True,
        judge_version="adversarial-v2",
    )


class JudgeEnsembleTests(unittest.TestCase):
    def test_objective_failure_rejects_even_high_scoring_video(self) -> None:
        verdict = MODULE.adjudicate(
            objective(clipping=True),
            primary(score=96.0),
            adversarial(),
            phase=3,
        )
        self.assertEqual(verdict.decision, MODULE.Decision.REJECT)
        self.assertIn("visual_clipping", verdict.objective_failures)

    def test_missing_vision_evidence_holds(self) -> None:
        verdict = MODULE.adjudicate(
            objective(),
            None,
            adversarial(),
            phase=1,
        )
        self.assertEqual(verdict.decision, MODULE.Decision.HOLD)
        self.assertIn("missing primary vision evidence", verdict.reasons)

    def test_credible_adversarial_objection_is_not_averaged_away(self) -> None:
        verdict = MODULE.adjudicate(
            objective(),
            primary(score=94.0),
            adversarial(labels=("rubric_gaming",), confidence=0.88),
            phase=3,
        )
        self.assertEqual(verdict.decision, MODULE.Decision.HOLD)
        self.assertTrue(verdict.disagreements)

    def test_clean_independent_evidence_ships(self) -> None:
        verdict = MODULE.adjudicate(
            objective(),
            primary(score=93.0),
            adversarial(),
            phase=3,
        )
        self.assertEqual(verdict.decision, MODULE.Decision.SHIP)

    def test_ship_beats_higher_scoring_hold(self) -> None:
        incumbent = MODULE.adjudicate(
            objective(),
            primary(score=91.0),
            adversarial(),
            phase=3,
        )
        challenger = MODULE.adjudicate(
            objective(),
            primary(score=99.0),
            adversarial(labels=("meaningless_motion",), confidence=0.95),
            phase=3,
        )
        self.assertIs(MODULE.compare_combined(incumbent, challenger), incumbent)


if __name__ == "__main__":
    unittest.main()
