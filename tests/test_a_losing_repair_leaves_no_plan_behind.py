"""A REPAIR THAT LOST THE A/B MUST NOT LEAVE ITS PLAN ON DISK.

`fusion-net-energy-gain`, 2026-09-16, read off the CI logs of runs #394 and
#399:

  10:48  render: seg0 bolt grid, seg1 bar race       -> BLOCK 48 (craft)
  10:5x  repair: seg1 -> pictorial_race+block_wall    -> scores 40
         "repair 1 scored 40 vs 48 — REVERTING to the better cut"
  11:25  persist: `create mode state/scene_plans/fusion-net-energy-gain.json`
  19:54  next run: "[studio] scene plan seg1: pictorial_race+block_wall"

The repair loop correctly kept the better video — and the losing repair's
plan was written to `state/scene_plans/{slug}.json` BEFORE the A/B, never
removed on revert, committed by the persist step, and honoured as
`plan_locked` by every later run. The bar race the showrunner had praised
("the 3.1-vs-2.0 bar race") was replaced by a chart before the next run
started, by a decision the pipeline itself had just rejected.

`scene_repair.propose(apply_plan=True)` writes the plan; `post_stories`
decides afterwards whether the repair stuck. So the plan file is
snapshotted before `propose` and put back — or removed, if it did not exist
— on the REVERTING branch. A repair only sticks if it scores higher; now
its plan only sticks under the same rule.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import post_stories as PS                       # noqa: E402


class TheHelpersExist(unittest.TestCase):
    def test_snapshot_and_restore_are_wired_into_the_repair_loop(self):
        import inspect
        src = inspect.getsource(PS.main)
        i = src.index("_sr2.propose(")
        j = src.index("REVERTING to the better cut")
        self.assertIn("_plan_snapshot(", src[:i],
                      "no plan snapshot is taken before propose()")
        self.assertIn("_plan_restore(", src[j:j + 600],
                      "the REVERTING branch does not put the plan back")


class ASnapshotRoundTrips(unittest.TestCase):

    def test_an_existing_plan_is_restored_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(PS, "_PLANS_DIR", Path(td)):
            pf = Path(td) / "fusion.json"
            before = {"2": {"viz": "trend", "perf": "ride"}}
            pf.write_text(json.dumps(before, indent=1))
            snap = PS._plan_snapshot("fusion")
            # the repair overwrites it with a losing plan
            pf.write_text(json.dumps({"1": {"viz": "pictorial_race",
                                            "perf": "block_wall"}}))
            PS._plan_restore("fusion", snap)
            self.assertEqual(json.loads(pf.read_text()), before)

    def test_a_plan_that_did_not_exist_is_removed_again(self):
        """The fusion case exactly: no plan before, a losing one after."""
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(PS, "_PLANS_DIR", Path(td)):
            pf = Path(td) / "fusion.json"
            snap = PS._plan_snapshot("fusion")
            self.assertIsNone(snap)
            pf.write_text(json.dumps({"1": {"viz": "pictorial_race",
                                            "perf": "block_wall"}}))
            PS._plan_restore("fusion", snap)
            self.assertFalse(pf.exists(),
                             "the losing repair's plan survived the revert")

    def test_restore_never_raises_into_the_run(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(PS, "_PLANS_DIR", Path(td) / "missing"):
            PS._plan_restore("fusion", None)            # nothing to do
            PS._plan_restore("fusion", '{"0": {}}')     # dir absent: mkdir


if __name__ == "__main__":
    unittest.main()
