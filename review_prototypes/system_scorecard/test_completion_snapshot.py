from __future__ import annotations

import unittest

from .current_snapshot_completion import isolated_test_area_completion_snapshot


class CompletionSnapshotTests(unittest.TestCase):
    def test_all_isolated_test_area_percentages_are_100(self):
        report = isolated_test_area_completion_snapshot()
        self.assertTrue(report.complete)
        self.assertEqual(report.overall_percent, 100.0)
        self.assertTrue(all(value == 100.0 for value in report.gate_percentages.values()))
        self.assertTrue(all(value == 100.0 for value in report.capability_percentages.values()))
