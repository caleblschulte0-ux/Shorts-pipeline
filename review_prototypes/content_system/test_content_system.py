from __future__ import annotations

from datetime import date
from pathlib import Path
import unittest

from .content_models import ContentValidationError, Dataset
from .content_queue import QueueHistoryItem, QueuePlanner
from .premise_engine import PremisePolicy, rank_candidates
from .source_registry import DatasetRegistry, SourcePolicy
from .story_compiler import CompileRequest, StoryCompiler


def dataset_payload(*, key="grocery", officiality="official", title="Grocery price rise since 2020"):
    return {
        "key": key,
        "title": title,
        "unit": "percent",
        "geography": "United States",
        "time_coverage": "2020-2026",
        "source": {
            "name": "CPI components",
            "publisher": "U.S. Bureau of Labor Statistics",
            "url": "https://www.bls.gov",
            "officiality": officiality,
            "access_date": "2026-06-04",
        },
        "notes": "Cumulative change.",
        "points": [
            {"label": "Eggs", "value": 86},
            {"label": "Coffee", "value": 48},
            {"label": "Bread", "value": 32},
        ],
        "baseline": {"label": "All groceries", "value": 24.1},
    }


class SourceRegistryTests(unittest.TestCase):
    def test_official_dataset_passes_policy(self) -> None:
        dataset = Dataset.from_dict(dataset_payload())
        registry = DatasetRegistry(Path("."), policy=SourcePolicy(maximum_age_days=500))
        issues = registry.audit_dataset(dataset, as_of=date(2026, 7, 25))
        self.assertFalse([issue for issue in issues if issue.severity == "block"])

    def test_illustrative_dataset_is_blocked(self) -> None:
        dataset = Dataset.from_dict(dataset_payload(officiality="illustrative"))
        issues = DatasetRegistry(Path(".")).audit_dataset(dataset, as_of=date(2026, 7, 25))
        self.assertIn("unpublishable_officiality", {issue.code for issue in issues})

    def test_future_source_date_is_blocked(self) -> None:
        payload = dataset_payload()
        payload["source"]["access_date"] = "2027-01-01"
        dataset = Dataset.from_dict(payload)
        issues = DatasetRegistry(Path(".")).audit_dataset(dataset, as_of=date(2026, 7, 25))
        self.assertIn("future_access_date", {issue.code for issue in issues})


class PremiseEngineTests(unittest.TestCase):
    def test_generates_source_specific_ranked_premises(self) -> None:
        dataset = Dataset.from_dict(dataset_payload())
        ranked = rank_candidates(dataset, policy=PremisePolicy(minimum_score=60))
        self.assertTrue(ranked[0].eligible)
        self.assertIn("86", ranked[0].hook + ranked[0].title)
        self.assertGreaterEqual(ranked[0].score, 60)

    def test_repeated_pattern_receives_penalty(self) -> None:
        dataset = Dataset.from_dict(dataset_payload())
        clean = rank_candidates(dataset, policy=PremisePolicy(minimum_score=0))[0]
        repeated = rank_candidates(
            dataset,
            policy=PremisePolicy(minimum_score=0),
            recent_patterns=(clean.visual_form,),
        )
        matching = next(item for item in repeated if item.visual_form == clean.visual_form)
        self.assertLess(matching.score, clean.score)


class StoryCompilerTests(unittest.TestCase):
    def test_compiles_source_bound_story(self) -> None:
        dataset = Dataset.from_dict(dataset_payload())
        result = StoryCompiler(premise_policy=PremisePolicy(minimum_score=60)).compile(
            CompileRequest(slug="Grocery Surprise", datasets=(dataset,), target_seconds=24)
        )
        result.story.validate()
        self.assertEqual(result.story.slug, "grocery-surprise")
        self.assertEqual(len(result.story.claims), 1)
        self.assertGreaterEqual(len(result.story.beats), 2)

    def test_claim_tampering_is_rejected(self) -> None:
        dataset = Dataset.from_dict(dataset_payload())
        result = StoryCompiler(premise_policy=PremisePolicy(minimum_score=60)).compile(
            CompileRequest(slug="grocery", datasets=(dataset,))
        )
        claim = result.story.claims[0]
        bad = claim.__class__(
            **{**claim.__dict__, "expected_numbers": (999.0,) * len(claim.expected_numbers)}
        )
        with self.assertRaises(ContentValidationError):
            bad.validate_against(dataset)


class QueuePlannerTests(unittest.TestCase):
    def test_queue_rejects_recent_duplicate(self) -> None:
        dataset = Dataset.from_dict(dataset_payload())
        story = StoryCompiler(premise_policy=PremisePolicy(minimum_score=60)).compile(
            CompileRequest(slug="grocery", datasets=(dataset,))
        ).story
        history = (
            QueueHistoryItem(
                slug="old-grocery",
                title=story.premise.title,
                domain=story.premise.domain,
                visual_form=story.premise.visual_form,
                performance_families=tuple(beat.visual.mascot_objective for beat in story.beats),
                dataset_keys=(dataset.key,),
            ),
        )
        plan = QueuePlanner().plan((story,), history=history)
        self.assertFalse(plan.selected)
        self.assertEqual(len(plan.rejected), 1)


if __name__ == "__main__":
    unittest.main()
