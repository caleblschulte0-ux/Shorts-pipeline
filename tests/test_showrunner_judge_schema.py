"""A malformed/incomplete judge response must never read as a clean pass.

`failed_autofails()` only ever looks for checks that are PRESENT as dicts
with `present=True` — so a judge response with an empty or partial `checks`
object silently computed zero auto-fails, and `decide_verdict()` shipped it
at whatever score the (also-partial) `dimensions` produced. That is a
fail-open hole in the one gate CLAUDE.md calls sovereign: code may only ever
ADD blocks, and a missing hard-check answer is not evidence of a passing
video.

`validate_judge_response()` closes it: it is the schema check `review_video`
runs against the judge's raw JSON before trusting it for scoring, and it is
pure so this file can pin the contract without touching ffmpeg or a real
video.

    python -m unittest tests.test_showrunner_judge_schema -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from scripts import showrunner_review as sr            # noqa: E402

FULL_DIMS = {"hook": 4, "data_demo": 5, "mascot": 4, "craft": 3, "pace": 2,
             "payoff": 2}
CLEAN_CHECKS = {k: {"present": False, "evidence": "no issue seen at seg1:mid"}
                for k in sr.AUTOFAIL_CHECKS}


class TestOldBehaviorWasFailOpen(unittest.TestCase):
    """Pins the exact hole the finding described, so a regression is caught
    even if `validate_judge_response` is ever bypassed."""

    def test_empty_checks_computed_zero_autofails(self):
        self.assertEqual(sr.failed_autofails({}), [])

    def test_empty_checks_and_max_dims_used_to_ship(self):
        score = sr.compute_score(FULL_DIMS)
        self.assertEqual(sr.decide_verdict(score, {}), "ship")

    def test_a_check_present_without_a_present_key_was_ignored(self):
        checks = {"junk_imagery": {"evidence": "an AI-looking cutout in seg2"}}
        self.assertEqual(sr.failed_autofails(checks), [])


class TestValidateJudgeResponse(unittest.TestCase):
    def test_a_complete_response_has_no_problems(self):
        grades = {"dimensions": FULL_DIMS, "checks": CLEAN_CHECKS}
        self.assertEqual(sr.validate_judge_response(grades), [])

    def test_empty_checks_object_is_rejected(self):
        grades = {"dimensions": FULL_DIMS, "checks": {}}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any("checks." in p for p in problems))

    def test_missing_checks_key_entirely_is_rejected(self):
        grades = {"dimensions": FULL_DIMS}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any("checks" in p for p in problems))

    def test_one_omitted_check_is_rejected(self):
        checks = dict(CLEAN_CHECKS)
        del checks["dead_air"]
        grades = {"dimensions": FULL_DIMS, "checks": checks}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any(p.startswith("checks.dead_air") for p in problems))

    def test_a_check_missing_present_is_rejected(self):
        checks = dict(CLEAN_CHECKS)
        checks["junk_imagery"] = {"evidence": "looks fine"}
        grades = {"dimensions": FULL_DIMS, "checks": checks}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any(p == "checks.junk_imagery.present missing or "
                             "not boolean" for p in problems))

    def test_a_check_with_wrong_type_present_is_rejected(self):
        checks = dict(CLEAN_CHECKS)
        checks["dead_air"] = {"present": "false", "evidence": "static shot"}
        grades = {"dimensions": FULL_DIMS, "checks": checks}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any(p.startswith("checks.dead_air.present")
                             for p in problems))

    def test_a_check_with_empty_evidence_is_rejected(self):
        checks = dict(CLEAN_CHECKS)
        checks["empty_void"] = {"present": False, "evidence": "  "}
        grades = {"dimensions": FULL_DIMS, "checks": checks}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any(p.startswith("checks.empty_void.evidence")
                             for p in problems))

    def test_missing_dimension_is_rejected(self):
        dims = dict(FULL_DIMS)
        del dims["mascot"]
        grades = {"dimensions": dims, "checks": CLEAN_CHECKS}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any(p.startswith("dimensions.mascot") for p in problems))

    def test_out_of_range_dimension_is_rejected(self):
        dims = dict(FULL_DIMS)
        dims["hook"] = 9
        grades = {"dimensions": dims, "checks": CLEAN_CHECKS}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any(p.startswith("dimensions.hook") for p in problems))

    def test_bool_dimension_is_rejected(self):
        # bool is a subclass of int in Python — must not slip past isinstance(int).
        dims = dict(FULL_DIMS)
        dims["craft"] = True
        grades = {"dimensions": dims, "checks": CLEAN_CHECKS}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any(p.startswith("dimensions.craft") for p in problems))

    def test_missing_dimensions_object_entirely_is_rejected(self):
        grades = {"checks": CLEAN_CHECKS}
        problems = sr.validate_judge_response(grades)
        self.assertTrue(any(p.startswith("dimensions") for p in problems))

    def test_none_grades_is_rejected(self):
        problems = sr.validate_judge_response(None)
        self.assertTrue(problems)

    def test_all_five_autofail_checks_are_required_even_when_all_false(self):
        # Realistic case from the finding: a well-formed-looking response
        # that happens to answer only some of the mandatory checks.
        checks = {"junk_imagery": {"present": False, "evidence": "clean"}}
        grades = {"dimensions": FULL_DIMS, "checks": checks}
        problems = sr.validate_judge_response(grades)
        for k in set(sr.AUTOFAIL_CHECKS) - {"junk_imagery"}:
            self.assertTrue(any(p.startswith(f"checks.{k}") for p in problems),
                             f"expected a problem for missing check {k!r}")
        self.assertFalse(any(p.startswith("checks.junk_imagery")
                              for p in problems))


if __name__ == "__main__":
    unittest.main()
