from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from .fixtures import FIXED_TODAY, alternate_story, golden_story
from .models import Fault, PipelineStatus
from .pipeline import CompletionPipeline


class PipelineTests(unittest.TestCase):
    def test_golden_pipeline_ships_deterministically(self):
        results = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as temp:
                result = CompletionPipeline(Path(temp), today=FIXED_TODAY).run(golden_story())
                self.assertEqual(result.status, PipelineStatus.SHIPPED)
                self.assertEqual(result.metadata["proof_runs"], 2)
                self.assertGreaterEqual(result.score or 0, 90)
                self.assertEqual(result.reasons, ())
                results.append(result.canonical_release_id)
        self.assertEqual(results[0], results[1])

    def test_all_fail_closed_faults(self):
        faults = (
            Fault.MISSING_SOURCE,
            Fault.STALE_SOURCE,
            Fault.RENDER_CRASH,
            Fault.MISSING_VIDEO,
            Fault.MALFORMED_VERDICT,
            Fault.JUDGE_UNWATCHED,
            Fault.LOW_SCORE,
            Fault.VERSION_DRIFT,
            Fault.PROOF_TAMPER,
            Fault.RELEASE_TAMPER,
            Fault.AUDIT_TAMPER,
        )
        for fault in faults:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                result = CompletionPipeline(Path(temp), today=FIXED_TODAY).run(golden_story(), fault=fault)
                self.assertEqual(result.status, PipelineStatus.HELD)
                self.assertTrue(result.reasons)

    def test_verified_rollback_and_missing_target(self):
        with tempfile.TemporaryDirectory() as temp:
            pipeline = CompletionPipeline(Path(temp), today=FIXED_TODAY)
            rolled_back = pipeline.exercise_rollback(golden_story(), alternate_story())
            self.assertTrue(rolled_back.startswith(golden_story().slug))
        with tempfile.TemporaryDirectory() as temp:
            pipeline = CompletionPipeline(Path(temp), today=FIXED_TODAY)
            with self.assertRaises(ValueError):
                pipeline.exercise_rollback(golden_story(), alternate_story(), fault=Fault.ROLLBACK_WITHOUT_TARGET)
        invalid = replace(golden_story(), source=replace(golden_story().source, publisher=""))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "first release"):
                CompletionPipeline(Path(temp), today=FIXED_TODAY).exercise_rollback(invalid, alternate_story())
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "second release"):
                CompletionPipeline(Path(temp), today=FIXED_TODAY).exercise_rollback(golden_story(), invalid)
