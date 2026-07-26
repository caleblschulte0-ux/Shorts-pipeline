from __future__ import annotations

import unittest

from .current_snapshot_sprint3 import isolated_review_snapshot_sprint3


class SprintThreeSnapshotTests(unittest.TestCase):
    def test_snapshot_remains_honest_about_production(self):
        report = isolated_review_snapshot_sprint3()
        self.assertEqual(report.stage_percentages["production_wired"], 0.0)
        self.assertEqual(report.stage_percentages["production_proven"], 0.0)
        self.assertAlmostEqual(report.overall_percent, 46.5, places=1)
        self.assertGreater(report.stage_percentages["implemented"], 70)
        self.assertTrue(any("production" in gap for gap in report.critical_gaps))


if __name__ == "__main__":
    unittest.main()
