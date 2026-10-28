"""Every scene is its own place, and nothing in it looks stamped out.

Operator, 2026-10-25, on viewers commenting "this is AI": *"I like our art
style, but it does have a certain clunky Claude generatedness to it."* The
contact sheet of saved scenes showed why: nearly all of them stood in front
of ONE backdrop, `landscape()`'s low sun, its three clouds and its grey
sixteen-building skyline, because prompt rule 13 told the brain to start
there. The rest were the brain's own: grids of identical copies, props
floating at the wrong scale, every comparison drawn as dashed marks, and a
small Data off to the side.

`landscape(time=, seed=)` places the sky for THIS scene. Called as before it
draws exactly what it always drew, so every saved scene renders unchanged and
no STANDARD bump (and its day of recertifying) is needed.
"""
import unittest

try:
    import cairo
    import numpy as np
    HAVE_CAIRO = True
except ImportError:  # pragma: no cover
    HAVE_CAIRO = False


# The backdrop as it stood before 2026-10-28, kept verbatim as the oracle the
# default call is held to (the pattern of tests/test_captions.py).
def _oracle():
    import math
    from data_learning.subject_scenes import (SETTINGS, SUN, W, H, vgrad, glow,
                                              ridge, solid, treeline, haze,
                                              _mix3)
    def _old_landscape(cr, t=0.0, kind="field", horizon=1170):
        """Paints a whole outdoor setting (kind: field, desert, snow, coast,
        town) under a low sun; returns the ground's top y.

        Far to near: sky, sun, clouds, two ridges under haze, ground whose
        stripes run to the horizon."""
        sky0, sky1, sky2, far, near, g0, g1 = SETTINGS.get(kind, SETTINGS["field"])
        vgrad(cr, [(0, sky0), (0.45, sky1), (0.8, sky2), (1, sky2)], 0, horizon + 20)
        glow(cr, SUN[0], SUN[1], 520, (255, 236, 196), 0.55)
        glow(cr, SUN[0], SUN[1], 140, (255, 250, 232), 0.9)
        for cx, cy, s in ((760, 380, 1.0), (300, 520, 0.7), (930, 640, 0.6)):
            cx = (cx + t * 6 * s) % (W + 300) - 150      # clouds drift slowly
            for dx, r in ((-80, 60), (0, 85), (90, 65), (170, 45)):
                cr.save()
                cr.translate(cx + dx * s, cy)
                cr.scale(1, 0.55)
                cr.arc(0, 0, r * s, 0, 2 * math.pi)
                cr.restore()
            cr.set_source_rgba(1, 0.98, 0.95, 0.55)
            cr.fill()
        ridge(cr, horizon - 60, 90, 0.3, 4)
        solid(cr, far, edge=False, rim=False)
        if kind == "town":                                # a far skyline
            for i in range(16):
                bw, bh = 40 + (i * 29) % 40, 60 + (i * 53) % 140
                cr.rectangle(i * 70 - 10, horizon - 20 - bh, bw, bh + 20)
            solid(cr, near, edge=False, rim=False)
        else:
            ridge(cr, horizon - 20, 70, 2.1, 5)
            solid(cr, near, edge=False, rim=False)
        if kind == "field":
            treeline(cr, horizon - 20, _mix3(near, (40, 70, 40), 0.35))
        haze(cr, horizon - 170, horizon + 30, sky2, a=0.45)
        if kind == "coast":                               # the sea, then the beach
            vgrad(cr, [(0, (96, 150, 180)), (1, (48, 104, 140))], horizon, horizon + 160)
            horizon += 160
        vgrad(cr, [(0, g0), (0.4, _mix3(g0, g1, 0.4)), (1, g1)], horizon, H)
        vx = W / 2
        for k in range(-9, 10):                          # stripes run to the horizon
            cr.move_to(vx + k * 40, horizon)
            cr.line_to(vx + k * 420, H)
            cr.line_to(vx + k * 420 + 210, H)
            cr.line_to(vx + k * 40 + 20, horizon)
            cr.close_path()
            cr.set_source_rgba(1, 1, 0.85, 0.05 if k % 2 else 0.0)
            cr.fill()
        return horizon
    return _old_landscape


def _draw(**kw):
    from data_learning import subject_scenes as SS
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
    cr = cairo.Context(surf)
    y = SS.landscape(cr, 0.5, **kw)
    surf.flush()
    a = np.ndarray((SS.H, SS.W, 4), np.uint8, surf.get_data()).copy()
    return y, a


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheBackdropBelongsToTheScene(unittest.TestCase):
    def test_different_scenes_get_visibly_different_skies(self):
        for kind in ("field", "town", "coast"):
            skies = [_draw(kind=kind, time=tm, seed=sd)[1][:1000, :, :3].astype(int)
                     for tm, sd in (("dawn", "pilots"), ("night", "olympics"),
                                    ("overcast", "rent"), ("day", "pilots"))]
            for i in range(len(skies)):
                for j in range(i + 1, len(skies)):
                    self.assertGreater(float(abs(skies[i] - skies[j]).mean()), 8.0,
                                       (kind, i, j))

    def test_the_same_time_still_differs_by_seed(self):
        a = _draw(kind="town", time="dusk", seed="pilots")[1][:1000, :, :3].astype(int)
        b = _draw(kind="town", time="dusk", seed="olympics")[1][:1000, :, :3].astype(int)
        self.assertGreater(float(abs(a - b).mean()), 2.0)

    def test_the_same_seed_is_the_same_picture(self):
        a = _draw(kind="field", time="night", seed="x")[1]
        b = _draw(kind="field", time="night", seed="x")[1]
        self.assertTrue((a == b).all())

    def test_every_variant_fills_the_frame(self):
        from data_learning import subject_scenes as SS
        for kind in SS.SETTINGS:
            for tm in SS.TIMES:
                y, a = _draw(kind=kind, time=tm, seed=kind)
                self.assertEqual(int((a[..., 3] < 255).sum()), 0, (kind, tm))
                self.assertTrue(900 < y < 1500, (kind, tm, y))

    def test_the_default_call_is_the_old_backdrop(self):
        """Saved scenes call landscape(cr, t, kind): they must not move, so no
        STANDARD bump is needed. Pixel for pixel against the old code."""
        from data_learning import subject_scenes as SS
        old = _oracle()
        for kind in SS.SETTINGS:
            for t in (0.0, 3.7):
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
                y0 = old(cairo.Context(surf), t, kind)
                surf.flush()
                a = np.ndarray((SS.H, SS.W, 4), np.uint8, surf.get_data()).copy()
                surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
                y1 = SS.landscape(cairo.Context(surf), t, kind)
                surf.flush()
                b = np.ndarray((SS.H, SS.W, 4), np.uint8, surf.get_data()).copy()
                self.assertEqual(y0, y1, kind)
                self.assertTrue((a == b).all(), (kind, t))


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheBrainIsToldWhatLooksGenerated(unittest.TestCase):
    def setUp(self):
        from data_learning import scene_author as SA
        self.p = SA.build_prompt("t", "x", "y", [["a", 1.0]], "")

    def test_it_builds_the_stories_own_place(self):
        self.assertIn("THIS story's own place", self.p)
        self.assertIn("time=", self.p)
        self.assertIn("seed=HERO", self.p)
        self.assertIn('A bare landscape(cr, t, "town") is', self.p)

    def test_scale_is_shown_with_real_things_first(self):
        self.assertIn("prefer REAL THINGS", self.p)
        self.assertIn("use one at most", self.p)

    def test_data_is_big_enough_to_read(self):
        self.assertIn("height 280-340", self.p)
        self.assertNotIn("height 180-240", self.p)

    def test_nothing_is_copy_pasted_nothing_floats(self):
        self.assertIn("NOTHING IS COPY-PASTED, NOTHING FLOATS", self.p)
        self.assertIn("contact_shadow()", self.p)

    def test_the_kit_line_names_the_new_arguments(self):
        from data_learning import scene_author as SA
        line = next(ln for ln in SA._sigs().splitlines()
                    if ln.strip().startswith("landscape("))
        for n in ("time=None", "seed=None", "dawn", "returns the ground's top y"):
            self.assertIn(n, line)


if __name__ == "__main__":
    unittest.main()
