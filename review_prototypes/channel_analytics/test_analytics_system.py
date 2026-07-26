from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from .analytics_models import ExperimentDefinition, ExperimentStatus, VideoObservation
from .evaluator import EvaluationPolicy, evaluate_experiment
from .experiment_store import ExperimentStore, ExperimentStoreError
from .performance_patterns import summarize_patterns


NOW = datetime(2026, 7, 25, tzinfo=timezone.utc)


def video(
    slug: str,
    *,
    views: int,
    shown: int,
    completions: int,
    shares: int,
    subscribers: int,
    watched_pct: float,
    days_ago: int = 1,
    premise: str = "hidden_number",
    visual: str = "rank_reveal",
    performance: tuple[str, ...] = ("balance ranking",),
) -> VideoObservation:
    duration = 40.0
    return VideoObservation(
        slug=slug,
        published_at=NOW - timedelta(days=days_ago),
        duration_seconds=duration,
        views=views,
        shown_in_feed=shown,
        swiped_away=shown - views,
        completed_views=completions,
        watched_seconds=views * duration * watched_pct,
        likes=int(views * 0.04),
        comments=int(views * 0.003),
        shares=shares,
        subscribers_gained=subscribers,
        premise_pattern=premise,
        visual_pattern=visual,
        performance_families=performance,
        domain="science",
        relationship="ranking",
    )


def definition(minimum_views: int = 1000, minimum_videos: int = 2) -> ExperimentDefinition:
    return ExperimentDefinition(
        experiment_id="hook-test-1",
        hypothesis="Immediate consequence hooks improve viewed rate.",
        control_label="hidden_number",
        treatment_label="immediate_consequence",
        isolated_variable="hook_structure",
        primary_metric="viewed_rate",
        guardrail_metrics=("completion_rate", "share_rate", "average_percentage_viewed"),
        minimum_views_per_arm=minimum_views,
        minimum_videos_per_arm=minimum_videos,
        created_at=NOW,
        status=ExperimentStatus.DRAFT,
    )


class ExperimentEvaluationTests(unittest.TestCase):
    def test_small_sample_continues(self) -> None:
        control = [video("c1", views=200, shown=400, completions=100, shares=1, subscribers=0, watched_pct=0.5)]
        treatment = [video("t1", views=180, shown=300, completions=100, shares=2, subscribers=1, watched_pct=0.6)]
        decision = evaluate_experiment(definition(), control, treatment)
        self.assertEqual(decision.decision, "continue")

    def test_strong_treatment_is_promoted(self) -> None:
        control = [
            video("c1", views=1800, shown=3000, completions=900, shares=7, subscribers=2, watched_pct=0.56),
            video("c2", views=1700, shown=2900, completions=860, shares=8, subscribers=2, watched_pct=0.55),
        ]
        treatment = [
            video("t1", views=2250, shown=3000, completions=1280, shares=15, subscribers=5, watched_pct=0.62),
            video("t2", views=2180, shown=2900, completions=1240, shares=14, subscribers=5, watched_pct=0.61),
        ]
        decision = evaluate_experiment(
            definition(),
            control,
            treatment,
            policy=EvaluationPolicy(posterior_draws=5000),
        )
        self.assertEqual(decision.decision, "promote")

    def test_guardrail_regression_rejects_treatment(self) -> None:
        control = [
            video("c1", views=1800, shown=3000, completions=1200, shares=12, subscribers=3, watched_pct=0.72),
            video("c2", views=1700, shown=2900, completions=1120, shares=11, subscribers=3, watched_pct=0.70),
        ]
        treatment = [
            video("t1", views=2250, shown=3000, completions=700, shares=8, subscribers=2, watched_pct=0.38),
            video("t2", views=2180, shown=2900, completions=680, shares=7, subscribers=2, watched_pct=0.37),
        ]
        decision = evaluate_experiment(
            definition(), control, treatment, policy=EvaluationPolicy(posterior_draws=5000)
        )
        self.assertEqual(decision.decision, "reject")
        self.assertIn("guardrails", decision.reason)


class ExperimentStoreTests(unittest.TestCase):
    def test_only_one_active_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = ExperimentStore(Path(td))
            first = definition()
            second = ExperimentDefinition(**{**first.__dict__, "experiment_id": "hook-test-2"})
            store.create(first)
            store.create(second)
            store.start(first.experiment_id)
            with self.assertRaises(ExperimentStoreError):
                store.start(second.experiment_id)
            store.complete(first.experiment_id, decision={"decision": "promote"})
            store.start(second.experiment_id)
            self.assertEqual(store.active_id(), second.experiment_id)


class PatternScoringTests(unittest.TestCase):
    def test_recent_overuse_reduces_score(self) -> None:
        recent = tuple(
            video(
                f"v{i}",
                views=1000,
                shown=1500,
                completions=600,
                shares=8,
                subscribers=2,
                watched_pct=0.65,
                days_ago=i,
                premise="same_pattern",
            )
            for i in range(5)
        )
        older = tuple(
            video(
                f"o{i}",
                views=1000,
                shown=1500,
                completions=600,
                shares=8,
                subscribers=2,
                watched_pct=0.65,
                days_ago=30 + i,
                premise="older_pattern",
            )
            for i in range(5)
        )
        results = summarize_patterns((*recent, *older), pattern_type="premise")
        by_name = {item.name: item for item in results}
        self.assertLess(
            by_name["same_pattern"].conservative_score,
            by_name["older_pattern"].conservative_score,
        )


if __name__ == "__main__":
    unittest.main()
