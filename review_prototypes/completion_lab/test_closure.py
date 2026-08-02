from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from .closure import CAPABILITIES, TestEvidence, build_closure_report, write_closure_artifact
from .evidence import CapabilityEvidence, ClosureScorecard, GATES
from .registry import complete_test_evidence, intentionally_incomplete_evidence


class ClosureTests(unittest.TestCase):
    def test_complete_scope_is_100_percent(self):
        report = build_closure_report(complete_test_evidence())
        self.assertTrue(report.complete)
        self.assertEqual(report.overall_percent, 100.0)
        self.assertTrue(all(value == 100.0 for value in report.gate_percentages.values()))
        self.assertTrue(all(value == 100.0 for value in report.capability_percentages.values()))
        self.assertEqual(report.missing, ())

    def test_incomplete_scope_cannot_write_completion_artifact(self):
        report = build_closure_report(intentionally_incomplete_evidence())
        self.assertFalse(report.complete)
        self.assertTrue(report.missing)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                write_closure_artifact(Path(temp) / "completion.json", report)

    def test_complete_artifact_is_explicitly_isolated(self):
        report = build_closure_report(complete_test_evidence())
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "completion.json"
            write_closure_artifact(path, report)
            data = json.loads(path.read_text())
            self.assertEqual(data["overall_percent"], 100.0)
            self.assertFalse(data["production_pipeline_modified"])
            self.assertEqual(data["scope"], "isolated_review_test_area")

    def test_validation_failures(self):
        with self.assertRaises(ValueError):
            ClosureScorecard().evaluate(())
        with self.assertRaises(ValueError):
            CapabilityEvidence("", {gate: True for gate in GATES}, ("e",)).validate()
        with self.assertRaises(ValueError):
            CapabilityEvidence("x", {"designed": True}, ("e",)).validate()
        with self.assertRaises(ValueError):
            CapabilityEvidence("x", {gate: True for gate in GATES}, ()).validate()
        with self.assertRaises(ValueError):
            TestEvidence("", CAPABILITIES[0], ("designed",)).validate()
        with self.assertRaises(ValueError):
            TestEvidence("x", "unknown", ("designed",)).validate()
        with self.assertRaises(ValueError):
            TestEvidence("x", CAPABILITIES[0], ()).validate()
        with self.assertRaises(ValueError):
            TestEvidence("x", CAPABILITIES[0], ("bad",)).validate()
