"""The closing lands on a picture the viewer has not seen yet.

"seg4 shows the same frame seg3 ended on, so the payoff adds nothing new to
see" (Waymo, local re-render, 2026-09-25). The last beat's window runs to
the end of the closing, so its last visual started mid-beat and the closing
replayed it, shrunk, under the takeaway. `payoff_spans` gives the closing its
own span: the beat's other pictures share the time before it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import studio_render as sr  # noqa: E402


class ThePayoffGetsItsOwnSpan(unittest.TestCase):
    def test_the_last_picture_opens_at_the_closing(self):
        spans = sr.payoff_spans(33.4, 52.8, 45.8, 2)
        self.assertEqual(spans, [(33.4, 45.8), (45.8, 52.8)])

    def test_three_pictures_share_the_time_before_it(self):
        spans = sr.payoff_spans(20.0, 52.8, 45.8, 3)
        self.assertEqual(len(spans), 3)
        self.assertAlmostEqual(spans[1][1], 45.8)
        self.assertEqual(spans[2], (45.8, 52.8))
        for (a, b), (c, _d) in zip(spans, spans[1:]):
            self.assertAlmostEqual(b, c)             # consecutive, no gap

    def test_one_picture_or_too_little_time_keeps_the_even_split(self):
        self.assertEqual(sr.payoff_spans(33.4, 52.8, 45.8, 1),
                         [(33.4, 52.8)])
        short = sr.payoff_spans(40.0, 52.8, 45.8, 3)   # 5.8s for two spans
        self.assertEqual(short, sr._visual_spans(40.0, 52.8, 3))

    def test_the_master_uses_it_and_does_not_replay_a_fresh_picture(self):
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn("payoff_spans(start, end, windows[-1][0], len(kinds))",
                      src)
        self.assertIn("0.0 if t0 >= _close0 - 0.05 else", src)


if __name__ == "__main__":
    unittest.main()
