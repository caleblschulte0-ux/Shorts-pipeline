"""EVERY `temporal_gate` BLOCK ON THIS CHANNEL IS THE LAST FEW SECONDS.

33 of 228 verdicts, and the shape never varies:

    max_dup_run 79 frames > 45 — a frozen stretch starting at t=30.46s of
    38.92s (~3.3s frozen)               buybacks-beat-dividends, 2026-09-09
    max_dup_run 56 frames > 45 — starting at t=36.25s of 43.04s
                                        colorado-wolves-return, 2026-09-09
    max_dup_run 51 frames > 45 — starting at t=40.92s of 46.38s
                                        melatonin-kids-er-surge, 2026-09-09

Two causes, both in `render_scene`, and both a shared helper being used for a
case it was not written for.

**`_stagger` truncated a single-element build to 80% of the beat.** Its `0.8`
overlaps CONSECUTIVE elements — each finishes a fifth of a span early so the
next is already moving — and with one element there is nothing to overlap
with. A beat is one machine now that a machine IS the picture, so every scene
beat reached its final state at r=0.8 and held there.

**And the host's clock was the element's reveal.** The charts hit this years
ago and fixed it: reveal saturates so the finished picture can be READ, so
anything driven by it stops moving for the rest of the beat, which is why
`charts._beat()` exists. `render_scene` owns its own frame loop and never went
near it — so on top of a frozen picture sat a frozen mascot, and a still host
on a finished picture is the WHOLE FRAME holding still.

Measured over a 60-frame build with the gate's own detector (max over 12x12
blocks of mean abs gray diff at 192px, threshold 6.0), longest frozen run:

    gauge      14 -> 0       tower   25 -> 7
    funnel     12 -> 0       nest    12 -> 7
    staircase   8 -> 0       pipes    4 -> 2

Runs standalone:  python3 tests/test_the_beat_does_not_freeze_at_eighty_percent.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import charts, viz_scene as vs   # noqa: E402


class ASingleElementBuildsAcrossTheWHOLEBeat(unittest.TestCase):
    """`_stagger`'s overlap is for consecutive elements. One element has none
    to overlap with, and paying the fifth anyway is a fifth of every beat spent
    holding a finished picture."""

    def test_one_element_is_still_arriving_at_the_end(self):
        self.assertLess(vs._stagger(0.85, 0, 1), 1.0,
                        "a lone element finishes before the beat does")
        self.assertLess(vs._stagger(0.95, 0, 1), 1.0)

    def test_it_still_lands_exactly_on_the_finished_picture(self):
        """The anchors are taken from the last frame, so r=1.0 must mean
        finished — a build that is still moving at the final frame breaks
        every ring the studio hangs off it."""
        self.assertEqual(vs._stagger(1.0, 0, 1), 1.0)

    def test_the_overlap_survives_for_MULTIPLE_elements(self):
        """Removing it there would make a multi-element scene arrive in
        lockstep, which is the thing the stagger exists to prevent."""
        self.assertEqual(vs._stagger(0.5, 0, 2), 1.0, "element 0 of 2 late")
        self.assertGreater(vs._stagger(0.45, 0, 2), vs._stagger(0.45, 1, 2))

    def test_a_lone_element_is_never_AHEAD_of_a_staggered_one(self):
        for r in (0.1, 0.3, 0.6, 0.9):
            self.assertLessEqual(vs._stagger(r, 0, 1), vs._stagger(r, 0, 2))


class TheHostsClockIsTheBEAT(unittest.TestCase):
    """`charts._beat()` exists precisely for this and the scene kit never got
    it. `render_scene` owns its own loop, so `viz_scene._BEAT_PHASE` is the
    same idea on that side of the fence."""

    def tearDown(self):
        vs._BEAT_PHASE = None

    def test_outside_a_beat_there_is_no_phase(self):
        vs._BEAT_PHASE = None
        self.assertIsNone(charts.beat_phase())

    def test_the_beat_phase_overrides_a_saturated_reveal(self):
        """The whole point: the element is finished at reveal 1.0 and the host
        is at 0.6 of his performance, not pinned to the payoff pose."""
        import numpy as np
        vs._BEAT_PHASE = None
        pinned = vs.scene_host("point", 1.0)
        vs._BEAT_PHASE = 0.6
        moving = vs.scene_host("point", 1.0)
        vs._BEAT_PHASE = None
        a = np.asarray(pinned.convert("RGBA"), dtype="int16")
        b = np.asarray(moving.convert("RGBA"), dtype="int16")
        self.assertFalse(a.shape == b.shape and np.array_equal(a, b),
                         "the host ignored the beat phase")

    def test_charts_beat_phase_is_live_only_during_a_build(self):
        self.assertFalse(charts._TOUR_LIVE)
        self.assertIsNone(charts.beat_phase())

    def test_render_scene_publishes_and_then_CLEARS_the_phase(self):
        """A stale phase leaking out is how the next beat starts mid-gesture."""
        import inspect
        src = inspect.getsource(vs.render_scene)
        self.assertIn("_BEAT_PHASE = f / max(1, frames)", src)
        self.assertIn("_BEAT_PHASE = None", src)


class TheTailACTUALLYMoves(unittest.TestCase):
    """The measurement, not the argument. Renders a real build and runs the
    cadence gate's own detector over it."""

    FRAMES = 40
    THRESHOLD = 6.0        # the gate's own: max over 12x12 blocks at 192px
    CEILING = 12           # build-frames; 25 was the worst before

    def _runs(self, kind):
        import numpy as np
        from PIL import Image
        from tests._machine_samples import SAMPLES
        import tempfile
        ins = SAMPLES[kind]
        ins.scene = getattr(vs, f"{kind}_scene")(ins)
        if not ins.scene:
            self.skipTest(f"{kind} builder declined this sample")
        orig = ins.kind
        ins.kind = "scene"
        try:
            with tempfile.TemporaryDirectory() as td:
                p, _ = charts.render_story_build(ins, Path(td), kind,
                                                 frames=self.FRAMES,
                                                 full_by=0.78)
                self.assertIsNotNone(p, kind)
                fs = sorted(Path(td).glob(f"{kind}_build*.png"))
                imgs = [np.asarray(Image.open(f).convert("L")
                                   .resize((192, 192)), dtype=np.float32)
                        for f in fs]
        finally:
            ins.kind = orig
        best = run = 0
        for i in range(1, len(imgs)):
            dif = np.abs(imgs[i] - imgs[i - 1])
            worst = max(dif[r * 16:(r + 1) * 16, c * 16:(c + 1) * 16].mean()
                        for r in range(12) for c in range(12))
            run = run + 1 if worst < self.THRESHOLD else 0
            best = max(best, run)
        return best

    def test_no_machine_beat_holds_a_long_frozen_run(self):
        bad = {}
        for kind in ("gauge", "funnel", "staircase", "tower", "pipes"):
            if kind not in vs._MACHINE_DRAW:
                continue
            r = self._runs(kind)
            if r > self.CEILING:
                bad[kind] = r
        self.assertEqual(bad, {}, f"frozen runs (build frames): {bad}")


if __name__ == "__main__":
    unittest.main()
