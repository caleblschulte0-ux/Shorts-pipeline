"""THE SCALE IS IN THE SHOT, AND THE ART IS CRISP.

Operator, 2026-10-07: "pouring milk into a bottle to signify the increase is
good but there is no scale or context ... it's hard to grasp what's being
talked about. This is like an add-on / overlay issue, not a whole art
issue. And also the new art style has like a felt feel almost, I want it to
be crisp and clean."

A bar strip laid over the top of every beat was tried the same day and
refused: "freaking boxes on top of like the video doesn't help ... it just
needs to be able to more easily glance at it and gauge the scale." So the
scale is drawn ON the subject — `then_mark`, `ghost`, `times_ticks` in the
kit, prompt rule 14 — and no overlay is laid over a scene. And the paper
grain that read as felt is off.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import cairo
    HAVE_CAIRO = True
except Exception:  # noqa: BLE001
    HAVE_CAIRO = False


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheScaleIsInTheShot(unittest.TestCase):
    def test_the_scale_pieces_resolve_and_reach_the_brain(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        sigs = SA._sigs()
        for n in ("then_mark", "ghost", "times_ticks"):
            self.assertIn(n, SA.KIT_NAMES)
            self.assertTrue(callable(getattr(SS, n)))
            self.assertIn(f"  {n}(", sigs)

    def test_no_overlay_is_laid_over_the_scene(self):
        from data_learning import subject_scenes as SS
        self.assertFalse(hasattr(SS, "context_strip"))
        src = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertNotIn("context=True", src)

    def test_the_brain_is_told_to_put_it_on_the_subject(self):
        from data_learning import scene_author as SA
        p = SA.build_prompt("t", "x", "y", [["a", 1.0]], "")
        self.assertIn("THE SCALE IS IN THE PICTURE", p)
        self.assertIn("ghost()", p)

    def test_tick_labels_pass_the_number_check(self):
        from data_learning import scene_author as SA
        allowed = SA._allowed_numbers([("2019", 353.0), ("2060", 1014.0)])
        for tok in ("1", "2", "3"):
            self.assertTrue(SA._num_ok(tok, allowed, 1014.0), tok)

    def test_the_marks_draw_and_consume_their_path(self):
        from data_learning import subject_scenes as SS
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
        cr = cairo.Context(surf)
        cr.rectangle(100, 100, 300, 300)
        SS.ghost(cr)
        self.assertFalse(cr.has_current_point())
        box = SS.then_mark(cr, 100, 400, 500, "2019")
        self.assertEqual(len(box), 4)
        SS.times_ticks(cr, 600, 1400, 200, 3)


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheArtIsCrispNotFelt(unittest.TestCase):
    def test_no_grain_on_a_solid(self):
        import numpy as np
        from data_learning import illustrated as I
        self.assertFalse(I.GRAIN)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surf)
        cr.set_source_rgb(0.5, 0.2, 0.2)
        cr.paint()
        before = np.ndarray((200, 200, 4), np.uint8, surf.get_data()).copy()
        cr.rectangle(0, 0, 200, 200)
        I.grain(cr)
        cr.new_path()
        surf.flush()
        after = np.ndarray((200, 200, 4), np.uint8, surf.get_data())
        self.assertTrue((before == after).all())

    def test_the_wash_is_light(self):
        from data_learning import illustrated as I
        self.assertLessEqual(I.FINISH, 0.3)


if __name__ == "__main__":
    unittest.main()
