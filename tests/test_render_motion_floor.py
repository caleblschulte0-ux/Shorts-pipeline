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

    def test_the_breath_is_in_the_final_chain(self):
        """RETUNED 2026-08-16: the per-frame budget moved OFF the mascot
        idle and onto the whole-frame CAMERA BREATH. The first fix for the
        11-day outage put ~6 px/frame on the idle — gate satisfied, but 6.0
        rad/s is a 0.95 Hz jiggle at ~1080 px/s^2, stacked on a card float
        at a different frequency, and the operator watched the result and
        called it "this weird fucking shaking motion". Both constraints are
        pinned now: the gate budget on the breath, an acceleration ceiling
        on everything that oscillates."""
        self.assertIn("_cf.crop_vf(W, H)", SRC,
                      "the whole-frame camera breath is gone — with a calm "
                      "idle, nothing else clears the temporal gate on a "
                      "still beat")

    def test_the_breath_clears_the_gate_budget(self):
        from shared import camera_float as cf
        self.assertGreaterEqual(
            cf.px_per_frame(cf.FLOAT_A, cf.FLOAT_WX, FPS),
            cf.MIN_PX_PER_FRAME)

    def test_there_is_still_an_idle_at_all(self):
        self.assertTrue(idle_terms(),
                        "the mascot's hover is gone — a frozen host reads "
                        "as a sticker even while the frame drifts")

    def test_no_oscillating_layer_reads_as_shake(self):
        """Acceleration = A*C^2 px/s^2 is what the eye objects to. The
        jiggle the operator called out measured ~1080; the breath sits
        under 200. Every sinusoid in this renderer stays an order of
        magnitude below the jiggle — met by LOWERING FREQUENCY, never by
        making the motion invisible (that is the other ditch, and it cost
        eleven days of zero posts)."""
        for amp, coeff in idle_terms():
            accel = amp * coeff * coeff
            self.assertLessEqual(
                accel, 120,
                f"{amp}*sin({coeff}*t) accelerates at {accel:.0f} px/s^2 — "
                f"a visible jiggle; 'weird shaking' shipped the last time "
                f"this crept up")

    def test_the_jiggle_values_cannot_come_back(self):
        for dead in ("+30*sin(6.0*t)", "+34*sin(5.4*t)"):
            self.assertNotIn(dead, SRC,
                             f"{dead} is the 0.95 Hz idle the operator "
                             f"called 'weird shaking'")

    def test_the_invisible_values_cannot_come_back_either(self):
        """The opposite ditch: the ORIGINAL idle moved 0.26 px/frame,
        invisible to the detector, and the channel posted nothing for
        eleven days."""
        for dead in ("+6*sin(1.3*t)", "+9*sin(2.1*t)"):
            self.assertNotIn(dead, SRC)


class TestTheBuildWindowStaysBounded(unittest.TestCase):
    """A build stretched over a longer window has a SMALLER per-frame delta,
    so 'render more frames' makes the metric strictly worse. Measured: the
    same growing bar over 40 s scored 0.0 effective fps; over 8 s, 3.8."""

    def test_the_frame_cap_is_documented_as_a_tradeoff(self):
        self.assertIn("min(1200", SRC.replace(" ", ""),
                      "the build frame cap moved without updating this test")


if __name__ == "__main__":
    unittest.main()
