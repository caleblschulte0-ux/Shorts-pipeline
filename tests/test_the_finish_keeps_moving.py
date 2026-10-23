"""AFTER THE PAYOFF THE WORLD MOVES — AND SO DOES DATA, THROUGH THE FINISH.

2026-10-22/23: three explainers in two days (lightning deaths, hearing
aids, data-center water) had no closing scene, so the closing was the last
beat's FINISHED picture (`subject_scenes.wordless_finish`, u held at 1).
Data's last act is one-shot: it plays for `ACT_S` and holds. A second in,
nothing in the frame moved past the cadence gate's block threshold, and the
gate held all three: "max_dup_run 48/67 frames > 45 — a frozen stretch
outside any intentional hold". Measured on the saved scenes with the gate's
own detector: 71 and 98 frames before, 5 and 32 after.

The gate does not move. Through a finish Data now takes the result in, his
own reaction, then reading it, then again, so he is never still longer than
`REST_S`. Never a cheer: the finish does not know the story earned one.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from data_learning import subject_scenes as SS          # noqa: E402


def still_world(cr, t, u, pts, host):
    """A world with nothing in it that moves: only Data can."""
    cr.set_source_rgb(0.55, 0.62, 0.70)
    cr.paint()
    cr.set_source_rgb(0.35, 0.30, 0.25)
    cr.rectangle(0, 1300, SS.W, SS.H - 1300)
    cr.fill()
    host("shock" if u > 0.9 else "think", 540, 1400, 360)


class _Ins:
    items: list = []


class TheFinishKeepsMoving(unittest.TestCase):

    def _max_run(self, scene, secs):
        import showrunner_review as SR
        td = Path(tempfile.mkdtemp())
        SS.render_build(scene, _Ins(), td, "f", int(secs * 30))
        mp4 = td / "f.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30",
                        "-i", str(td / "f_build%02d.png"), "-pix_fmt", "yuv420p",
                        str(mp4)], check=True)
        ev = SR._temporal_evidence(mp4, td)
        self.assertTrue(ev.get("measured"), ev)
        return ev["max_dup_run"]

    def test_a_wordless_finish_is_never_a_frozen_stretch(self):
        from data_learning.quality_milestones import active_phase
        ceiling = active_phase().max_dup_run_frames
        run = self._max_run(SS.wordless_finish(still_world), 4.0)
        self.assertLessEqual(run, ceiling,
                             f"the finish froze for {run} frames, so the gate "
                             "holds the whole video")

    def test_data_takes_it_in_and_never_cheers(self):
        self.assertNotIn("cheer", SS.FINISH_ACTS)
        step = int((SS.ACT_S + SS.REST_S) * 30)
        roles = [SS.finish_role("shock", f)[0] for f in (0, step, 2 * step)]
        self.assertEqual(roles, ["shock", "think", "shock"])
        beats = [SS.finish_role("shock", f)[1] for f in (0, step, 2 * step)]
        self.assertEqual(len(set(beats)), 3, "each act must replay, not hold")

    def test_only_the_finish_is_changed(self):
        self.assertTrue(getattr(SS.wordless_finish(still_world), "finish", False))
        self.assertFalse(getattr(still_world, "finish", False))


if __name__ == "__main__":
    unittest.main()
