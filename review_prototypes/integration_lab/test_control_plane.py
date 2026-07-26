from __future__ import annotations

from datetime import date
import unittest

from review_prototypes.retention_system.models import Beat
from .channel_control_plane import ChannelControlPlane, StoryInput


def beats(prefix: str, action: str):
    return (
        Beat(f"{prefix}-1", 1.5, 3.4, "setup", "baseline", "chart appears", action, 0.2, 0.1, 0.4),
        Beat(f"{prefix}-2", 3.4, 5.6, "escalation", "change begins", "chart grows", "pull", 0.5, 0.1, 0.5),
        Beat(f"{prefix}-3", 5.6, 7.8, "reversal", "expectation breaks", "objects collide", "race", 0.85, 0.1, 0.5),
        Beat(f"{prefix}-4", 7.8, 9.6, "payoff", "consequence lands", "scene resolves", "recover", 0.3, 0.1, 0.4),
    )


def story(slug: str, topic: str, shape: str, action: str, *, experiment=None, source=True):
    return StoryInput(
        slug=slug,
        claim="The expected result fails.",
        consequential_number="72%",
        expectation="steady growth",
        consequence="the old limit breaks",
        mascot_goal="hold the line",
        beats=beats(slug, action),
        topic_family=topic,
        story_shape=shape,
        performance_families=(action, "pull", "race", "recover"),
        source_verified=source,
        showrunner_decision="ship",
        quality_score=90,
        lowest_dimension=8.2,
        artifact_manifest_hash=f"manifest-{slug}",
        experiment_id=experiment,
    )


class ControlPlaneTests(unittest.TestCase):
    def test_full_fake_release_day(self):
        stories = (
            story("space", "space", "scale", "climb"),
            story("animal", "animals", "ranking", "carry"),
            story("history", "history", "timeline", "balance"),
        )
        result = ChannelControlPlane().prepare_release_day(
            stories,
            batch_size=3,
            publish_date=date(2026, 7, 27),
        )
        self.assertEqual(len(result.portfolio.selected), 3)
        self.assertEqual(len(result.schedule.slots), 3)
        self.assertTrue(all(item.report.passed for item in result.retention_packages))

    def test_unverified_source_is_held(self):
        stories = (
            story("space", "space", "scale", "climb", source=False),
            story("animal", "animals", "ranking", "carry"),
        )
        result = ChannelControlPlane().prepare_release_day(
            stories,
            batch_size=2,
            publish_date=date(2026, 7, 27),
        )
        self.assertEqual([item.slug for item in result.portfolio.selected], ["animal"])
        self.assertIn("space", result.portfolio.rejected)

    def test_competing_experiments_do_not_both_ship(self):
        stories = (
            story("space", "space", "scale", "climb", experiment="hook-a"),
            story("animal", "animals", "ranking", "carry", experiment="hook-b"),
            story("history", "history", "timeline", "balance"),
        )
        result = ChannelControlPlane().prepare_release_day(
            stories,
            batch_size=3,
            publish_date=date(2026, 7, 27),
        )
        experiments = {item.experiment_id for item in result.portfolio.selected if item.experiment_id}
        self.assertLessEqual(len(experiments), 1)


if __name__ == "__main__":
    unittest.main()
