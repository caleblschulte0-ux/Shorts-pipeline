"""Standalone review examples for quality_state_machine.py.

Run manually from the repository root if desired:
    python review_prototypes/next_level/test_quality_state_machine.py

No workflow invokes this file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "quality_state_machine", HERE / "quality_state_machine.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


SLUGS = (
    "carbon-climb",
    "population-giants",
    "world-power-mix",
    "grocery-squeeze",
    "ocean-unexplored",
    "two-americas-cost",
)


def make_run(
    run_id: str,
    scores,
    *,
    lowest_dimension: float,
    hook: float,
    payoff: float,
    families=None,
    failures=None,
):
    families = families or (
        "resisted_growth",
        "finish_line_overtake",
        "overwhelmed_balance",
        "budget_squeeze",
        "scale_discovery",
        "weighted_carry",
    )
    failures = failures or {}
    stories = tuple(
        MODULE.StoryResult(
            slug=slug,
            score=float(score),
            lowest_dimension=lowest_dimension,
            hard_failures=tuple(failures.get(slug, ())),
            effective_fps=29.0,
            duplicate_ratio=0.05,
            decorative_mascot_failures=0,
            hook_score=hook,
            payoff_score=payoff,
            performance_family_counts={families[index]: 1},
            artifact_manifest_hash=f"manifest:{run_id}:{slug}",
        )
        for index, (slug, score) in enumerate(zip(SLUGS, scores))
    )
    return MODULE.BenchmarkRun(
        run_id=run_id,
        suite_version="suite-v2",
        judge_version="judge-v4",
        renderer_commit="commit-abc",
        stories=stories,
        complete_video_count=6,
    )


class QualityStateMachineTests(unittest.TestCase):
    def test_one_run_cannot_claim_phase_one(self) -> None:
        run = make_run(
            "run-1",
            [72, 73, 74, 75, 76, 77],
            lowest_dimension=6.5,
            hook=7.0,
            payoff=7.0,
        )
        assessment = MODULE.assess_phase([run], 1)
        self.assertFalse(assessment.passed)
        self.assertIn("requires 2 consecutive runs", assessment.reasons)

    def test_two_stable_70_runs_reach_phase_one_only(self) -> None:
        runs = [
            make_run(
                "run-1",
                [68, 70, 71, 72, 73, 74],
                lowest_dimension=6.2,
                hook=6.5,
                payoff=6.5,
            ),
            make_run(
                "run-2",
                [69, 70, 72, 73, 74, 75],
                lowest_dimension=6.2,
                hook=6.5,
                payoff=6.5,
            ),
        ]
        state = MODULE.assess_state(runs)
        self.assertEqual(state.highest_phase, 1)

    def test_repetitive_90_runs_do_not_reach_phase_three(self) -> None:
        repeated = ("resisted_growth",) * 6
        runs = [
            make_run(
                "run-1",
                [90, 91, 92, 93, 94, 95],
                lowest_dimension=8.4,
                hook=8.5,
                payoff=8.5,
                families=repeated,
            ),
            make_run(
                "run-2",
                [91, 92, 93, 94, 95, 96],
                lowest_dimension=8.4,
                hook=8.5,
                payoff=8.5,
                families=repeated,
            ),
        ]
        assessment = MODULE.assess_phase(runs, 3)
        self.assertFalse(assessment.passed)
        self.assertTrue(
            any(
                "dominant performance family share" in reason
                for reason in assessment.reasons
            )
        )

    def test_two_diverse_90_runs_reach_phase_three(self) -> None:
        runs = [
            make_run(
                "run-1",
                [88, 90, 91, 92, 93, 94],
                lowest_dimension=8.3,
                hook=8.4,
                payoff=8.4,
            ),
            make_run(
                "run-2",
                [87, 90, 92, 93, 94, 95],
                lowest_dimension=8.3,
                hook=8.4,
                payoff=8.4,
            ),
        ]
        state = MODULE.assess_state(runs)
        self.assertEqual(state.highest_phase, 3)

    def test_regression_report_catches_single_story_collapse(self) -> None:
        baseline = make_run(
            "baseline",
            [85, 85, 85, 85, 85, 85],
            lowest_dimension=7.5,
            hook=8.0,
            payoff=8.0,
        )
        challenger = make_run(
            "challenger",
            [85, 85, 85, 85, 85, 70],
            lowest_dimension=7.5,
            hook=8.0,
            payoff=8.0,
        )
        report = MODULE.compare_regression(baseline, challenger)
        self.assertFalse(report.passed)
        self.assertTrue(
            any("two-americas-cost" in reason for reason in report.reasons)
        )


if __name__ == "__main__":
    unittest.main()
