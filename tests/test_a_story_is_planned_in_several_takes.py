"""A story is planned in several TAKES, and the best one is cut.

Story backtests 7-9 (2026-10-08): a plan that opened at 58 never climbed
past ~66 by repair, while a different cut of the same footage reached 78.
The director now writes `story_takes` alternate cuts in one call, every
take meets every law on its own, the table read reads each, and the best
is repaired and rendered. Same critic, same 80 on the render.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_a_story_has_a_narrator_per_beat import _edl     # noqa
from tests.test_a_story_is_repaired_before_it_is_dropped import (  # noqa
    EDL, _Harness, _review)
from third_capture import story_director as sd                   # noqa


def _reports():
    return [{"source_id": s, "channel": "rakai", "duration_s": d,
             "summary": "rakai", "transcript_lines": "rakai talks"}
            for s, d in (("a", 30.0), ("b", 40.0), ("c", 25.0))]


class TheDirectorWritesTakes(unittest.TestCase):
    def plan(self, out, takes=3):
        with mock.patch.object(sd, "_brain", return_value=out) as b:
            e = sd.plan_story(_reports(), takes=takes)
        return e, b.call_args[0][0]

    def test_it_is_asked_for_takes(self):
        _, user = self.plan(_edl(None))
        self.assertIn("WRITE 3 DIFFERENT TAKES", user)
        _, user = self.plan(_edl(None), takes=1)
        self.assertNotIn("DIFFERENT TAKES", user)

    def test_every_valid_take_is_kept_and_the_first_is_returned(self):
        a, b = _edl(None), _edl(None)
        a["title"], b["title"] = "Take A", "Take B"
        e, _ = self.plan({"is_story": True, "takes": [a, b]})
        self.assertEqual(e["title"], "Take A")
        self.assertEqual([t["title"] for t in sd.last_takes()],
                         ["Take A", "Take B"])

    def test_a_take_that_breaks_a_law_is_dropped_alone(self):
        bad, good = _edl(None), _edl(None)
        bad["beats"] = bad["beats"][:1]            # one beat is no story
        good["title"] = "Good"
        e, _ = self.plan({"is_story": True, "takes": [bad, good]})
        self.assertEqual(e["title"], "Good")
        self.assertEqual(len(sd.last_takes()), 1)

    def test_a_single_plan_still_works(self):
        e, _ = self.plan(_edl(None))
        self.assertIsNotNone(e)
        self.assertEqual(len(sd.last_takes()), 1)

    def test_not_a_story_is_still_editorial(self):
        e, _ = self.plan({"is_story": False, "why": "two unrelated moments"})
        self.assertIsNone(e)
        self.assertTrue(sd.last_rejection()["editorial"])


class TheBestTakeIsCut(_Harness):
    def test_the_take_that_reads_best_is_rendered(self):
        a, b = dict(EDL, title="Take A"), dict(EDL, title="Take B")

        # what plan_story leaves behind when the director wrote two takes
        self.addCleanup(sd._LAST_TAKES.clear)
        sd._LAST_TAKES[:] = [a, b]
        led = self.run_attempt(
            [_review(False, 55), _review(True, 82), _review(True, 85)],
            plan=a, spec_extra={"story_table_reads": 1})
        self.assertIsNotNone(led)
        self.assertIn("Take B", led["authored_title"])


class TheKnobsAreConfig(unittest.TestCase):
    def test_takes_and_wider_moments_are_in_the_channel_config(self):
        cap = json.loads((ROOT / "state" / "third_packages"
                          / "default_clip.json").read_text())["capture"]
        self.assertGreaterEqual(cap["story_takes"], 2)
        self.assertGreaterEqual(cap["story_moment_before_s"], 240)
        self.assertGreaterEqual(cap["story_moment_after_s"], 240)


if __name__ == "__main__":
    unittest.main()
