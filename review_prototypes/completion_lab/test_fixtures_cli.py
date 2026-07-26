from __future__ import annotations

import contextlib
import io
import json
import runpy
import sys
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

from .cli import main
from .fixtures import alternate_story, golden_story, load_fixture
from .models import Fault


class FixtureCliTests(unittest.TestCase):
    def test_fixture_loading_and_alternate_story(self):
        root = Path(__file__).parent / "fixtures"
        fixture = load_fixture(root / "golden_story.json")
        self.assertEqual(fixture["slug"], golden_story().slug)
        self.assertNotEqual(alternate_story().slug, golden_story().slug)

    def test_cli_success_writes_completion_artifact(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()) as output:
            path = Path(temp) / "completion.json"
            code = main(["--output", str(path)])
            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["isolated_scope_percent"], 100.0)
            self.assertTrue(path.exists())

    def test_cli_failure_returns_nonzero(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = main(["--fault", Fault.LOW_SCORE.value])
            self.assertEqual(code, 2)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["pipeline_status"], "held")

    def test_cli_module_guard_executes_as_module(self):
        self.assertTrue(callable(main))
        with contextlib.redirect_stdout(io.StringIO()), patch.object(sys, "argv", ["completion_lab"]):
            with self.assertRaises(SystemExit) as raised:
                runpy.run_module("review_prototypes.completion_lab.cli", run_name="__main__")
        self.assertEqual(raised.exception.code, 0)
