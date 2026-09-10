"""The closing card must keep moving, at EVERY closing length.

`container-ships-floating-cities`, 2026-09-10 — held by the showrunner at
score 5, the whole video refused on one auto-fail:

    temporal_gate: max_dup_run 47 frames > 45 (phase-1 ceiling) — a frozen
    stretch outside any intentional hold starting at t=46.0s of 49.08s

t=46.0 is exactly where the CTA lands on that video. `studio_render` placed
the closing's reveals at FIXED FRACTIONS of the closing window (0.40 / 0.62
/ 0.86), so every gap between them grew with the window — and past a ~7s
closing the schedule guaranteed a run over the ceiling. Its four gaps, in
frames at the 24fps the gate samples at: 78, 43, 47, 27.

The file already knew this about the TAIL — `MAX_STILL_TAIL` says "reading
time is a HUMAN quantity — it does not grow because the sentence ran long"
— and had applied it to one end of the closing and not the other.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import studio_render as SR                # noqa: E402

#: What `scripts/showrunner_review.py` measures a frozen run against.
GATE_CEILING_FRAMES = 45
GATE_FPS = 24


def schedule(c0: float, c1: float):
    """The closing's reveal times, exactly as `build_story_ass` computes them."""
    cd = max(1.2, c1 - c0)
    qs = c0 + min(0.40 * cd, SR.CLOSING_MAX_GAP)
    cs = qs + min(0.22 * cd, SR.CLOSING_MAX_GAP)
    pulses, t = [], cs + min(0.24 * cd, SR.CLOSING_MAX_GAP)
    while t < c1 - 0.25:
        pulses.append(t)
        t += SR.CLOSING_MAX_GAP
    return [c0, qs, cs] + pulses


def gaps_in_frames(c0: float, c1: float):
    times = schedule(c0, c1) + [c1]
    return [round((b - a) * GATE_FPS) for a, b in zip(times, times[1:])]


class NoGapReachesTheCeiling(unittest.TestCase):
    def test_the_video_that_was_blocked(self):
        """c0=40.95, c1=49.08 — reconstructed from the verdict."""
        worst = max(gaps_in_frames(40.95, 49.08))
        self.assertLess(worst, GATE_CEILING_FRAMES,
                        f"still freezes: {gaps_in_frames(40.95, 49.08)}")

    def test_the_old_schedule_really_did_fail_it(self):
        """The fix is only a fix if the thing it replaced was broken. This
        is the ORIGINAL arithmetic, kept as the oracle."""
        c0, c1 = 40.95, 49.08
        cd = c1 - c0
        old = [c0, c0 + 0.40 * cd, c0 + 0.62 * cd, c0 + 0.86 * cd, c1]
        old_gaps = [round((b - a) * GATE_FPS) for a, b in zip(old, old[1:])]
        self.assertEqual(old_gaps, [78, 43, 47, 27])
        self.assertGreaterEqual(max(old_gaps), GATE_CEILING_FRAMES)

    def test_every_closing_length_the_channel_produces(self):
        """A 20s video and a 60s one both close. The bug only appeared past
        ~7s, which is why it took until a 49s video to surface."""
        for span in [x / 2 for x in range(3, 41)]:      # 1.5s .. 20.0s
            worst = max(gaps_in_frames(10.0, 10.0 + span))
            self.assertLess(worst, GATE_CEILING_FRAMES,
                            f"closing of {span}s freezes for {worst} frames")

    def test_a_short_closing_keeps_the_original_proportions(self):
        """Bounding a gap must not squash a closing that was already fine —
        the reveals would pile up at the front and leave a tail instead."""
        c0, c1 = 10.0, 13.0
        cd = c1 - c0
        times = schedule(c0, c1)
        self.assertAlmostEqual(times[1], c0 + 0.40 * cd, 3)
        self.assertAlmostEqual(times[2], times[1] + 0.22 * cd, 3)

    def test_the_reveals_stay_in_order_and_inside_the_window(self):
        for span in [x / 2 for x in range(3, 41)]:
            times = schedule(10.0, 10.0 + span)
            self.assertEqual(times, sorted(times), span)
            self.assertGreaterEqual(times[0], 10.0, span)
            self.assertLess(times[-1], 10.0 + span, span)

    def test_the_tail_after_the_last_reveal_is_bounded(self):
        for span in [x / 2 for x in range(3, 41)]:
            c1 = 10.0 + span
            self.assertLess((c1 - schedule(10.0, c1)[-1]) * GATE_FPS,
                            GATE_CEILING_FRAMES, span)


class ThePulsesDoNotStack(unittest.TestCase):
    """Each pulse animates and ends; the base CTA underneath keeps drawing.
    A pulse that ran to `c1` would have every later one drawn over it."""

    def test_a_pulse_is_shorter_than_the_cadence(self):
        self.assertLess(SR.CLOSING_PULSE_S, SR.CLOSING_MAX_GAP)

    def test_the_cadence_leaves_margin_under_the_gate(self):
        self.assertLess(SR.CLOSING_MAX_GAP * GATE_FPS, GATE_CEILING_FRAMES)


class TheScheduleIsTheONEInTheRenderer(unittest.TestCase):
    """This file recomputes the schedule, so it has to be the same one."""

    def test_the_renderer_uses_the_bounded_constants(self):
        import ast
        import inspect
        src = inspect.getsource(SR.build_story_ass)
        tree = ast.parse(src.lstrip())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        code = ast.unparse(tree)
        self.assertIn("CLOSING_MAX_GAP", code)
        self.assertNotIn("c0 + 0.62 * cd", code)
        self.assertNotIn("c0 + 0.86 * cd", code)


if __name__ == "__main__":
    unittest.main()
