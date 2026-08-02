"""Standalone review examples for semantic_scene_planner.py.

Run manually from the repository root if desired:
    python review_prototypes/next_level/test_semantic_scene_planner.py

No workflow invokes this file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "semantic_scene_planner", HERE / "semantic_scene_planner.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SemanticScenePlannerTests(unittest.TestCase):
    def test_trend_intent_selects_trend_capability(self) -> None:
        visualizations, performances = MODULE.default_capabilities()
        intent = MODULE.StoryIntent(
            claim="The value accelerates upward.",
            data_shape="trend",
            relationship="acceleration",
            direction="up",
            required_takeaway="The increase becomes faster over time.",
            emotional_read="alarming",
            required_affordances=frozenset({"moving_endpoint"}),
            forbidden_distortions=frozenset({"imply_categorical_ranking"}),
        )
        plans = MODULE.rank_candidates(intent, visualizations, performances)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].visualization, "trend_line")
        self.assertEqual(plans[0].performance_family, "resisted_growth")

    def test_dominance_intent_rejects_trend_visual(self) -> None:
        visualizations, performances = MODULE.default_capabilities()
        intent = MODULE.StoryIntent(
            claim="One source outweighs all others.",
            data_shape="part_to_whole",
            relationship="dominance",
            direction="stable_high",
            required_takeaway="One side dominates the whole.",
            emotional_read="overwhelming",
            required_affordances=frozenset({"beam"}),
        )
        plans = MODULE.rank_candidates(intent, visualizations, performances)
        self.assertTrue(plans)
        self.assertTrue(all(plan.visualization != "trend_line" for plan in plans))
        self.assertEqual(plans[0].performance_family, "overwhelmed_balance")

    def test_diversity_penalty_does_not_validate_wrong_candidate(self) -> None:
        visualizations, performances = MODULE.default_capabilities()
        history = MODULE.DiversityWindow(
            total_scenes=20,
            performance_counts={"overwhelmed_balance": 12},
            visualization_counts={"weighted_balance": 12},
        )
        intent = MODULE.StoryIntent(
            claim="The value rises.",
            data_shape="trend",
            relationship="increase",
            direction="up",
            required_takeaway="The value increases.",
            emotional_read="alarming",
        )
        plans = MODULE.rank_candidates(
            intent, visualizations, performances, history=history
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].performance_family, "resisted_growth")

    def test_strict_helper_explains_incompatibility(self) -> None:
        visualizations, performances = MODULE.default_capabilities()
        trend = next(v for v in visualizations if v.name == "trend_line")
        balance = next(
            p for p in performances if p.family == "overwhelmed_balance"
        )
        intent = MODULE.StoryIntent(
            claim="One side dominates.",
            data_shape="part_to_whole",
            relationship="dominance",
            direction="stable_high",
            required_takeaway="One side dominates.",
        )
        with self.assertRaises(MODULE.IncompatibleCandidate):
            MODULE.require_candidate(intent, trend, balance)


if __name__ == "__main__":
    unittest.main()
