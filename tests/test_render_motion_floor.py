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


class TestTheMotionBudgetIsCarriedByRealMotion(unittest.TestCase):
    """WHERE THE PER-FRAME BUDGET LIVES — third and final answer.

    1. Originally on the mascot IDLE at 0.26 px/frame: invisible to the
       detector, eleven days of zero posts.
    2. Then on a 6 px/frame idle: gate satisfied, and the operator watched
       it and called it "this weird fucking shaking motion".
    3. Then on a whole-frame CAMERA BREATH: calmer, still fake, and the
       operator called it out again on 2026-08-25 — *"rip it out all the
       way, it's a cancer, I want no semblance of the camera shake to
       exist."*

    All three tried to satisfy a motion DETECTOR without giving a viewer
    anything more to look at. The budget now comes from motion that is
    actually part of the show:

      * `charts._perf_phase` — struggle reps across the whole beat, so the
        sprite changes nearly every frame instead of one arc smeared over
        fifteen seconds;
      * `charts._tour_index` / `_tour_tip` — the host WALKS the ranking and
        keeps moving after the build finishes, which is exactly the window
        the float existed to cover.

    The rule that survives all three attempts, and the reason this file is
    still here: a beat that measures short needs MORE REAL MOTION. Never a
    camera that moves to fool the meter.
    """

    def test_no_camera_breath_in_the_final_chain(self):
        self.assertNotIn("crop_vf", SRC,
                         "the camera float is retired (2026-08-25 ruling)")
        self.assertNotIn("camera_float", SRC)

    def test_no_idle_oscillator_survives(self):
        """The sprite bob was the last of the family. Two oscillations in
        different phases is what read as shaking in the first place."""
        self.assertEqual(idle_terms(), [],
                         f"a time-driven idle is back: {idle_terms()}")

    def test_the_performance_still_animates_every_frame(self):
        """Without reps the beat really is a still image — this is the
        replacement for the idle, and it is limb motion inside the sprite
        rather than the sprite sliding around."""
        charts = (ROOT / "data_learning" / "charts.py").read_text()
        self.assertIn("def _perf_phase(", charts)
        body = charts.split("def _bake_host(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_perf_phase(phase)", body)

    def test_the_host_keeps_moving_after_the_build_finishes(self):
        """The specific window the float was covering: `reveal` saturates at
        `full_by` and then sits at 1.0, so anything derived from it stops.
        The tour runs on beat progress instead."""
        charts = (ROOT / "data_learning" / "charts.py").read_text()
        build = charts.split("def render_story_build(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_TOUR = f / max(1, frames)", build)
        from data_learning import charts as C
        self.assertGreater(C._tour_index(5, 0.1), C._tour_index(5, 0.5))

    def test_the_jiggle_values_cannot_come_back(self):
        for dead in ("+30*sin(6.0*t)", "+34*sin(5.4*t)"):
            self.assertNotIn(dead, SRC,
                             f"{dead} is the 0.95 Hz idle the operator "
                             f"called 'weird shaking'")

    def test_the_invisible_values_cannot_come_back_either(self):
        """The opposite ditch: the ORIGINAL idle moved 0.26 px/frame,
        invisible to the detector, and the channel posted nothing for
        eleven days. Neither ditch is the answer — real motion is."""
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
