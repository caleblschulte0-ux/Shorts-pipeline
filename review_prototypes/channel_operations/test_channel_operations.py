from __future__ import annotations

from datetime import date
import unittest

from .models import ReleaseCandidate
from .portfolio import PortfolioPlanner
from .readiness import ReadinessGate
from .scheduler import ReleaseScheduler


def candidate(
    slug: str,
    topic: str,
    shape: str,
    performance: str,
    *,
    quality: float = 88.0,
    experiment: str | None = None,
    ship: str = "ship",
):
    return ReleaseCandidate(
        slug=slug,
        topic_family=topic,
        story_shape=shape,
        hook_pattern=f"hook-{shape}",
        performance_families=(performance,),
        quality_score=quality,
        lowest_dimension=8.0,
        source_verified=True,
        retention_passed=True,
        showrunner_decision=ship,
        experiment_id=experiment,
        freshness_score=0.9,
        reaction_prediction=0.6,
        artifact_manifest_hash=f"hash-{slug}",
    )


class ChannelOperationsTests(unittest.TestCase):
    def test_readiness_fails_closed_on_missing_manifest(self):
        item = candidate("a", "space", "scale", "climb")
        item = ReleaseCandidate(**{**item.__dict__, "artifact_manifest_hash": ""})
        decision = ReadinessGate().evaluate(item)
        self.assertFalse(decision.eligible)
        self.assertIn("artifact manifest hash missing", decision.reasons)

    def test_portfolio_selects_diverse_batch(self):
        items = [
            candidate("a", "space", "scale", "climb", quality=94),
            candidate("b", "space", "scale", "climb", quality=93),
            candidate("c", "animals", "ranking", "race", quality=90),
            candidate("d", "history", "timeline", "carry", quality=89),
            candidate("e", "body", "comparison", "balance", quality=88),
        ]
        result = PortfolioPlanner().select(items, batch_size=4)
        self.assertEqual(len(result.selected), 4)
        self.assertGreaterEqual(len({item.topic_family for item in result.selected}), 3)

    def test_only_one_experiment_can_enter_batch(self):
        items = [
            candidate("a", "space", "scale", "climb", experiment="hook-a"),
            candidate("b", "animals", "ranking", "race", experiment="hook-b"),
            candidate("c", "history", "timeline", "carry"),
        ]
        result = PortfolioPlanner().select(items, batch_size=3)
        experiment_ids = {item.experiment_id for item in result.selected if item.experiment_id}
        self.assertLessEqual(len(experiment_ids), 1)

    def test_scheduler_spaces_releases(self):
        items = [
            candidate("a", "space", "scale", "climb"),
            candidate("b", "animals", "ranking", "race"),
            candidate("c", "history", "timeline", "carry"),
        ]
        result = ReleaseScheduler().schedule(items, publish_date=date(2026, 7, 27))
        self.assertEqual(len(result.slots), 3)
        self.assertEqual((result.slots[1].publish_at - result.slots[0].publish_at).seconds, 7200)

    def test_scheduler_rejects_multiple_experiments(self):
        items = [
            candidate("a", "space", "scale", "climb", experiment="x"),
            candidate("b", "animals", "ranking", "race", experiment="y"),
        ]
        with self.assertRaises(ValueError):
            ReleaseScheduler().schedule(items, publish_date=date(2026, 7, 27))


if __name__ == "__main__":
    unittest.main()
