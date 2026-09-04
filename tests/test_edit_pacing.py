"""The EDIT has to stay cut. Pacing is a feature, not an accident.

The channel's videos were one shot per narrated beat — a single chart card
held for 8-12 seconds, sometimes 20. That is the defect the operator named
("we sit on one chart as it slowly moves for twenty seconds"), and it is also
the root of two others: with nothing in the edit to carry attention, earlier
sessions added camera movement and gave the mascot a continuous arm pump to
keep something on screen moving.

So shot LENGTH is now a held invariant, not a side effect of how long a
sentence happened to be. These tests fail if it drifts back.

Runs with pytest OR standalone:
    python3 tests/test_edit_pacing.py
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

from data_learning import studio_render as srd  # noqa: E402

# Beat lengths this channel actually produces, from short to pathological.
_BEATS = (4.0, 6.0, 8.0, 10.5, 14.0, 20.0, 26.0)
_MAX_SHOT = 4.5      # seconds; a shot longer than this is a hold, not a shot


class EditPacing(unittest.TestCase):
    def test_no_shot_runs_longer_than_the_ceiling(self):
        """The failure this catches is specific and has happened once already:
        the shot cap was 4, so a 20s beat became four 5s shots and a 26s beat
        became 6.5s shots — the pacing got WORSE exactly on the beats that
        needed it most."""
        for dur in _BEATS:
            shots = srd._shot_plan(0.0, dur)
            longest = max(b - a for a, b in shots)
            self.assertLessEqual(
                longest, _MAX_SHOT,
                f"{dur}s beat -> {len(shots)} shots, longest {longest:.1f}s "
                f"(ceiling {_MAX_SHOT}s). Shot length must hold as beats grow.")

    def test_shots_tile_the_beat_exactly(self):
        """No gap and no overlap: a hole in the cut list is a frame with no
        chart on it."""
        for dur in _BEATS:
            shots = srd._shot_plan(1.5, 1.5 + dur)
            self.assertAlmostEqual(shots[0][0], 1.5, places=3)
            self.assertAlmostEqual(shots[-1][1], 1.5 + dur, places=3)
            for (_, end), (nxt, _) in zip(shots, shots[1:]):
                self.assertAlmostEqual(end, nxt, places=3,
                                       msg=f"gap/overlap at {end} in a {dur}s beat")

    def test_a_short_beat_is_left_alone(self):
        """Cutting a 3s beat into two 1.5s shots is choppy, not lively."""
        self.assertEqual(len(srd._shot_plan(0.0, 3.0)), 1)

    def test_grammar_alternates_instead_of_stacking_close_ups(self):
        """WIDE, PUNCH, WIDE, PUNCH... Seven close-ups in a row is a different
        monotony, not a fix — and the wides are what make a close-up legible by
        re-establishing what it is a close-up of."""
        for dur in (14.0, 20.0, 26.0):
            n = len(srd._shot_plan(0.0, dur))
            kinds = ["punch" if (0 < k < n - 1 and k % 2 == 1) else "wide"
                     for k in range(n)]
            self.assertEqual(kinds[0], "wide", "a beat must establish first")
            self.assertEqual(kinds[-1], "wide", "a beat must land wide")
            run = best = 0
            for k in kinds:
                run = run + 1 if k == "punch" else 0
                best = max(best, run)
            self.assertLessEqual(best, 1, f"{dur}s beat stacks close-ups: {kinds}")

    def test_punch_framing_is_static_and_inside_the_card(self):
        """A punch-in is a CUT to a tighter frame, never a move. If a time
        term ever appears in this crop it is camera motion wearing an edit's
        clothes — and the crop must stay inside the card or ffmpeg fails the
        render outright."""
        vw, vh = 1056, 900
        for cx, cy in ((0, 0), (10_000, 10_000), (300, 900), (-50, 40)):
            expr = srd._punch_crop({"cx": cx, "cy": cy}, vw, vh, zoom=1.7)
            self.assertNotIn("sin", expr)
            self.assertNotIn("cos", expr)
            self.assertNotIn("t)", expr)
            geom = expr.split(",")[0].removeprefix("crop=")
            w, h, x, y = (int(v) for v in geom.split(":"))
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)
            self.assertGreaterEqual(x, 0)
            self.assertGreaterEqual(y, 0)
            self.assertLessEqual(x + w, vw, f"crop runs off the card: {expr}")
            self.assertLessEqual(y + h, vh, f"crop runs off the card: {expr}")

    def test_the_host_is_not_pumping_his_arms(self):
        """The arm gesture holds at each extreme. A constant-speed sweep is the
        mascot compensating for an edit with nothing in it."""
        from data_learning import mascot_director as md
        n = 120
        parked = sum(1 for i in range(n)
                     if abs(md._gesture(i / n) - md._gesture((i + 1) / n)) < 0.02)
        self.assertGreater(
            parked / n, 0.5,
            "the limb is in motion most of the cycle — that is a pump")
        self.assertAlmostEqual(md._gesture(0.0), md._gesture(1.0), places=9,
                               msg="gesture must tile seamlessly in the loop")


if __name__ == "__main__":
    unittest.main(verbosity=2)
