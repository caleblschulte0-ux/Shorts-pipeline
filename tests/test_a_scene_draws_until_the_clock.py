"""A scene keeps drawing while the video's clock lasts.

2026-10-12: the explainer spent five hours on twelve stories and posted none.
Most beats gave up after three refused drafts with half the video's drawing
budget unused, each draft tripping a different check. The bar is the same;
a scene now gets `ATTEMPTS` drafts, and the clock still stops it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import scene_author as SA  # noqa: E402

BAD = "def scene(cr, t, u, pts, host):\n    raise ValueError('nope')\n"


class ASceneDrawsUntilTheClock(unittest.TestCase):
    def tearDown(self):
        SA._DEADLINE = None

    def test_more_than_three_drafts(self):
        self.assertGreaterEqual(SA.ATTEMPTS, 5)
        calls = []
        SA.set_budget(3600)
        with mock.patch.object(SA, "ask_brain",
                               side_effect=lambda *a, **k: calls.append(1) or BAD):
            fn, why = SA.author("t", "x", "say", [["a", 1.0], ["b", 2.0]],
                                log=lambda m: None)
        self.assertIsNone(fn)
        self.assertEqual(len(calls), SA.ATTEMPTS)

    def test_the_clock_still_stops_it(self):
        calls = []
        SA.set_budget(30)                       # under the 90s floor
        with mock.patch.object(SA, "ask_brain",
                               side_effect=lambda *a, **k: calls.append(1) or BAD):
            fn, why = SA.author("t", "x", "say", [["a", 1.0], ["b", 2.0]],
                                log=lambda m: None)
        self.assertEqual(calls, [])
        self.assertIn("budget is spent", why)


if __name__ == "__main__":
    unittest.main()
