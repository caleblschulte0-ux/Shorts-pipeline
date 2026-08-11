"""Motion in this renderer must be big enough for the GATE to see it.

The explainer channel posted nothing from 2026-07-30 to 2026-08-10 — eleven
days — and every run looked healthy: workflows fired, four videos rendered,
the showrunner refused all four. The reason was arithmetic, not taste. The
temporal grade compares CONSECUTIVE frames; the mascot's idle moved him
`6*1.3/30` = 0.26 px per frame and the chart build grew sub-pixel per frame,
so a video that looks like it is animating reads as a still image to the
detector — 0.8-2.3 effective fps against an 11.0 floor.

The lesson, and the thing these tests exist to keep: **motion tuned for
smoothness is not automatically motion the gate can measure.** Anything here
that animates has to clear a per-frame displacement budget, and the honest
unit for that budget is pixels-per-frame, not amplitude.

Calibrated on synthetic explainer frames through the reviewer's own
detector (see the comment at the idle expression in studio_render.py):

    0.26 px/frame ->  0.0 fps   1.00 dup    (the old idle: total failure)
    2.3  px/frame ->  8.9 fps   0.63 dup    (still under the floor)
    6.0  px/frame -> 20.0 fps   0.17 dup    PASSES

    python -m unittest tests.test_render_motion_floor -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SRC = (ROOT / "data_learning" / "studio_render.py").read_text()

#: The export rate the idle expressions are sampled at.
FPS = 30.0
#: Pixels of per-frame displacement measured to clear the phase-1 floor with
#: margin. 2.3 px/frame measured 8.9 fps (fails); 6.0 measured 20.0 (passes).
MIN_PX_PER_FRAME = 5.0


def idle_terms() -> list[tuple[float, float]]:
    """Every `+A*sin(C*t)` idle in the mascot overlay, as (amplitude, coeff)."""
    return [(float(a), float(c))
            for a, c in re.findall(r"\+(\d+(?:\.\d+)?)\*sin\((\d+(?:\.\d+)?)\*t\)",
                                   SRC)]


class TestTheMascotIdleIsMeasurable(unittest.TestCase):

    def test_there_is_still_an_idle_at_all(self):
        self.assertTrue(idle_terms(),
                        "the mascot's continuous idle is gone — a parked host "
                        "is what the temporal grade reads as a held frame")

    def test_every_idle_clears_the_per_frame_budget(self):
        """A*C/30 is the displacement between consecutive frames. This is the
        exact check that would have caught the 11-day outage on the day the
        idle was written."""
        for amp, coeff in idle_terms():
            px = amp * coeff / FPS
            self.assertGreaterEqual(
                px, MIN_PX_PER_FRAME,
                f"idle {amp}*sin({coeff}*t) moves {px:.2f} px/frame — under "
                f"{MIN_PX_PER_FRAME}, which measured below the 11 fps floor. "
                f"Raise the AMPLITUDE (frequency reads as nervous).")

    def test_the_old_broken_values_cannot_come_back(self):
        """Named explicitly so a future 'that looks jittery, tone it down'
        edit fails loudly instead of silently darkening the channel."""
        for dead in ("+6*sin(1.3*t)", "+9*sin(2.1*t)"):
            self.assertNotIn(dead, SRC,
                             f"{dead} is the idle that produced 0.26 px/frame "
                             f"and eleven days of zero posts")

    def test_the_idle_stays_a_float_not_a_jitter(self):
        """The budget must be met with amplitude, not by spinning the
        frequency up — that would pass the gate and look terrible."""
        for _amp, coeff in idle_terms():
            self.assertLess(coeff / (2 * 3.14159), 1.5,
                            "idle frequency above ~1.5 Hz reads as a shake")


class TestTheBuildWindowStaysBounded(unittest.TestCase):
    """A build stretched over a longer window has a SMALLER per-frame delta,
    so 'render more frames' makes the metric strictly worse. Measured: the
    same growing bar over 40 s scored 0.0 effective fps; over 8 s, 3.8."""

    def test_the_frame_cap_is_documented_as_a_tradeoff(self):
        self.assertIn("min(1200", SRC.replace(" ", ""),
                      "the build frame cap moved without updating this test")


if __name__ == "__main__":
    unittest.main()
