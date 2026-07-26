from __future__ import annotations

import unittest

from .adapters import (
    AdapterError,
    ShowrunnerVerdictAdapter,
    VisionRankingAdapter,
)
from .models import Decision, SceneCandidate, SceneDiagnosis


def diagnosis_payload():
    return {
        "scene_id": "segment_1",
        "scene_index": 1,
        "start_seconds": 5.0,
        "end_seconds": 9.0,
        "failure_class": "weak_payoff",
        "visible_evidence": "The consequence never lands.",
        "root_cause": "The timeline ends too early.",
        "repair_goal": "Add consequence and settle.",
    }


def base_payload():
    return {
        "verdict": "block",
        "score": 68,
        "dimensions": {
            "clarity": 7,
            "craft": 6,
            "payoff": 5,
        },
        "temporal": {
            "effective_fps": 29,
            "duplicate_ratio": 0.05,
        },
        "weakest_scene": diagnosis_payload(),
        "watched_video": True,
        "judge_version": "showrunner-v4",
    }


class AdapterTests(unittest.TestCase):
    def test_clean_block_maps_to_hold(self):
        verdict = ShowrunnerVerdictAdapter.from_payload(
            base_payload()
        )
        self.assertEqual(verdict.decision, Decision.HOLD)
        self.assertEqual(
            verdict.weakest_scene.scene_id,
            "segment_1",
        )

    def test_block_with_hard_failure_maps_to_reject(self):
        payload = base_payload()
        payload["auto_fails"] = [
            "clipping: mascot outside frame"
        ]
        verdict = ShowrunnerVerdictAdapter.from_payload(payload)
        self.assertEqual(verdict.decision, Decision.REJECT)

    def test_missing_structured_diagnosis_fails_closed(self):
        payload = base_payload()
        payload.pop("weakest_scene")
        with self.assertRaises(AdapterError):
            ShowrunnerVerdictAdapter.from_payload(payload)

    def test_ship_requires_proof_video_was_watched(self):
        payload = base_payload()
        payload["verdict"] = "ship"
        payload.pop("weakest_scene")
        payload["watched_video"] = False
        with self.assertRaises(AdapterError):
            ShowrunnerVerdictAdapter.from_payload(payload)

    def test_vision_ranking_selects_known_candidate(self):
        diagnosis = SceneDiagnosis.from_dict(
            diagnosis_payload()
        )
        candidates = (
            SceneCandidate(
                "a",
                diagnosis.scene_id,
                "trend",
                "pull",
                diagnosis.repair_goal,
                "A",
            ),
            SceneCandidate(
                "b",
                diagnosis.scene_id,
                "stack",
                "carry",
                diagnosis.repair_goal,
                "B",
            ),
        )
        ranker = VisionRankingAdapter(
            {
                diagnosis.scene_id: {
                    "watched_previews": True,
                    "ordered_candidate_ids": ["b", "a"],
                }
            }
        )
        self.assertEqual(
            ranker.select(
                "demo",
                diagnosis,
                candidates,
            ).candidate_id,
            "b",
        )


if __name__ == "__main__":
    unittest.main()
