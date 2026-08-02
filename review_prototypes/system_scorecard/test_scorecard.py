from __future__ import annotations

import unittest

from .current_snapshot import isolated_review_snapshot
from .scorecard import CapabilityStatus, SystemScorecard


class ScorecardTests(unittest.TestCase):
    def test_prototype_without_wiring_is_not_near_complete(self):
        report = SystemScorecard().evaluate(
            (
                CapabilityStatus("demo", 10, 1, 1, 1, 0.5, 0, 0, ("tests",)),
            )
        )
        self.assertLess(report.overall_percent, 70)
        self.assertEqual(report.stage_percentages["production_wired"], 0.0)

    def test_invalid_proof_order_is_rejected(self):
        item = CapabilityStatus("bad", 1, 1, 1, 1, 1, 0.2, 0.8)
        with self.assertRaises(ValueError):
            item.validate()

    def test_current_snapshot_exposes_integration_gap(self):
        report = isolated_review_snapshot()
        self.assertLess(report.stage_percentages["production_wired"], 10.0)
        self.assertTrue(any("production_integration" in gap for gap in report.critical_gaps))


if __name__ == "__main__":
    unittest.main()
