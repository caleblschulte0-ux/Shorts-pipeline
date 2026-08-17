"""A still on screen must keep moving for as long as it is on screen.

2026-08-11, from the showrunner's own words: "the last ~11s freezes on one
repeated clock still", "one dark wallet still frozen for the last ten
seconds". Both reddit stories blocked, on a day the media worker had
finally delivered good topical images ("solid topical shots for the first
half") — the pictures were right and the panels still died.

The cause was a Ken Burns push written as `min(zoom+0.0007, 1.07)`. Two
independent faults in one expression:

  * IT CAPS. (1.07-1.00)/0.0007 = 100 frames = 3.3 s. Every panel held on
    screen longer than that froze solid for the remainder.
  * ITS MOVING PHASE WAS ALREADY INVISIBLE. 0.0007 zoom/frame is ~0.4 px
    of edge movement per frame, sub-pixel once the temporal detector
    downscales — so the panel measured 0.0 effective fps even before the
    cap, dup ratio 1.00, a 280-frame frozen run on a 14 s panel.

Measured through `showrunner_review._temporal_evidence` on a 14 s panel:

    old expression                   ->  0.0 fps  dup 1.00  run 280
    duration-scaled ramp + orbit     -> 13.4 fps  dup 0.44  run 13   PASS

The rule these tests keep: any motion applied to a still must be expressed
so that it lasts the panel's OWN length (never a fixed cap), and must carry
enough per-frame displacement for the gate to see. A pure pan cannot do the
second over a long panel — slow enough to last 20 s is sub-pixel again —
which is why the drift is cyclic.

    python -m unittest tests.test_still_panels_never_freeze -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_RAW = (ROOT / "make_reddit_story.py").read_text()
#: Live code only. The comment at the fix deliberately QUOTES the dead
#: expression to explain what went wrong, and a naive substring check on the
#: whole file flags that explanation as the bug it is warning about.
SRC = "\n".join(l for l in _RAW.splitlines()
                if not l.lstrip().startswith("#"))
FPS = 30.0
#: px/frame that measured above the floor (4.4 measured 13.4 fps).
MIN_PX_PER_FRAME = 3.5


class TestThePushCannotCapEarly(unittest.TestCase):

    def test_the_frozen_expression_is_gone(self):
        self.assertNotIn("zoom+0.0007", SRC,
                         "this is the push that capped after 3.3s and froze "
                         "every longer panel")

    def test_the_zoom_is_scaled_to_THIS_panel_length(self):
        """`on/<frames>` ties the ramp to the panel's own frame count, so a
        2 s panel and a 20 s panel both finish their travel exactly at the
        end. A constant per-frame increment cannot do that."""
        self.assertRegex(SRC, r"zoompan=z='min\(1\+0\.\d+\*on/\{?_?frames",
                         "the zoom must be a function of the panel's own "
                         "frame count, not a fixed increment with a cap")

    def test_the_frame_count_comes_from_the_panel_duration(self):
        self.assertIn("_frames = max(1, int(round(dur * FPS)))", SRC)


class TestTheDriftIsBigEnoughToSee(unittest.TestCase):

    def terms(self):
        """Every `A*sin(C*...)` / `A*cos(C*...)` drift term as (amp, coeff)."""
        return [(float(a), float(c)) for a, c in
                re.findall(r"(\d+(?:\.\d+)?)\*(?:sin|cos)\((\d+(?:\.\d+)?)\*on",
                           SRC)]

    def test_there_is_a_drift_at_all(self):
        self.assertTrue(self.terms(),
                        "without a cyclic drift a long panel is sub-pixel "
                        "however the zoom is written")

    def test_every_drift_clears_the_per_frame_budget(self):
        for amp, coeff in self.terms():
            px = amp * coeff / FPS
            self.assertGreaterEqual(
                px, MIN_PX_PER_FRAME,
                f"drift {amp}*f({coeff}*on) moves {px:.2f} px/frame — under "
                f"{MIN_PX_PER_FRAME}, which is where panels measured below "
                f"the 11 fps floor")

    def test_the_drift_stays_gentle(self):
        """The budget must be met with amplitude, not frequency — a fast
        oscillation would pass the gate and look like a shake."""
        for _amp, coeff in self.terms():
            self.assertLess(coeff / (2 * 3.14159), 1.5,
                            "drift above ~1.5 Hz reads as a shake, not a float")

    def test_the_drift_is_cyclic_not_a_one_way_pan(self):
        """A one-way pan slow enough to last a long panel is sub-pixel; only
        a cyclic drift holds its per-frame rate at any duration."""
        joined = " ".join(f"{a}*{c}" for a, c in self.terms())
        self.assertTrue(joined, "no cyclic terms found")
        self.assertRegex(SRC, r"\*sin\(", "expected an oscillating x drift")
        self.assertRegex(SRC, r"\*cos\(", "expected an oscillating y drift")


if __name__ == "__main__":
    unittest.main()
