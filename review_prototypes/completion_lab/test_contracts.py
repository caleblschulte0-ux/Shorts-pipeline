from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from .contracts import validate_judge_contract, validate_renderer_contract
from .fixtures import golden_story
from .services import FailingJudge, FailingRenderer, SyntheticJudge, SyntheticRenderer


class ContractTests(unittest.TestCase):
    def test_passing_contracts(self):
        with tempfile.TemporaryDirectory() as temp:
            story = golden_story()
            renderer = SyntheticRenderer()
            checks = validate_renderer_contract(renderer, story, Path(temp) / "render")
            self.assertTrue(all(check.passed for check in checks))
            render = renderer.render(story, Path(temp) / "judge", attempt_id="a")
            judge_checks = validate_judge_contract(SyntheticJudge(), story, render)
            self.assertTrue(all(check.passed for check in judge_checks))

    def test_failing_contracts_report_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            story = golden_story()
            renderer_checks = validate_renderer_contract(FailingRenderer(), story, Path(temp) / "bad")
            self.assertFalse(all(check.passed for check in renderer_checks))
            render = SyntheticRenderer().render(story, Path(temp) / "good", attempt_id="a")
            judge_checks = validate_judge_contract(FailingJudge(), story, render)
            self.assertFalse(all(check.passed for check in judge_checks))
