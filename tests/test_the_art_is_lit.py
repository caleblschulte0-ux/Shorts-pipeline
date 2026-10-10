"""The art is LIT, not flat — and that is measured.

Operator, 2026-10-05: "the art in general on the B clips needs to be
better." Every subject was a flat-filled polygon with a hard edge in a
world of soft gradients: the hero band of posted brain scenes measured up
to 55% exact-colour slabs. Held here:

  * the paint kit has ONE light model (illustrated.solid / box / cylinder /
    disc / contact_shadow / haze / vignette / edge) and every name reaches
    the brain's sandbox and the teachers;
  * a lit solid is not a slab: the same shape drawn with solid() measures
    far less flat than cr.fill();
  * the verifier refuses a scene whose hero band is mostly flat, names the
    kit to fix it, and accepts the same scene lit;
  * a flat scene saved before the light is refused on load, so it is
    redrawn under the new rules instead of shipped again;
  * the brain is told the rule and shown teachers that obey it;
  * every teacher passes the craft check (held with the rest of verify by
    tests/test_the_brain_draws_the_scene.py).
"""
from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import cairo  # noqa: F401
    HAVE_CAIRO = True
except Exception:  # noqa: BLE001
    HAVE_CAIRO = False

LIGHT = ("solid", "box", "cylinder", "disc", "contact_shadow", "haze", "vignette", "edge")

FLAT = '''
def scene(cr, t, u, pts, host):
    """HERO: a gold ingot on a bench
    SUBSTANCE: gold
    CAUSE: Data lifts the ingot onto the bench
    """
    rows = by_time([(str(l), float(v)) for l, v in pts])
    vgrad(cr, [(0.0, (70, 70, 130)), (1.0, (10, 10, 20))], 0, H)
    cr.set_source_rgba(*_c((212, 160, 60)))
    cr.rectangle(120, 600, 840, 820)
    cr.fill()
    lab, val = rows[-1]
    fit_readout(cr, f"{val:.1f}", lab, 80, 520)
    host("point" if u < 0.2 else "haul", 300 + 400 * u, 1500, 220)
'''

LIT = FLAT.replace('''    cr.set_source_rgba(*_c((212, 160, 60)))
    cr.rectangle(120, 600, 840, 820)
    cr.fill()''', '''    contact_shadow(cr, 540, 1420, 900)
    box(cr, 120, 1420, 700, 760, (212, 160, 60), finish="metal")
    vignette(cr)''')


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheKitHasOneLight(unittest.TestCase):
    def test_every_light_name_reaches_the_brain_and_the_teachers(self):
        from data_learning import scene_author as SA, subject_scenes as SS, illustrated as I
        g = SA.kit_globals()
        for n in LIGHT + ("KEY", "FINISHES"):
            self.assertIn(n, SA.KIT_NAMES, n)
            self.assertIn(n, g, n)
            self.assertTrue(hasattr(SS, n), n)
            self.assertTrue(hasattr(I, n), n)
        self.assertEqual(len(I.KEY), 2)
        self.assertLess(I.KEY[1], 0)                       # from above

    def test_a_lit_solid_is_not_a_slab(self):
        import cairo
        from data_learning import scene_author as SA, subject_scenes as SS, illustrated as I

        def frame(lit):
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
            cr = cairo.Context(surf)
            I.vgrad(cr, [(0.0, (70, 70, 130)), (1.0, (10, 10, 20))])
            cr.rectangle(120, 600, 840, 820)
            if lit:
                I.solid(cr, (212, 160, 60))
            else:
                cr.set_source_rgba(*I._c((212, 160, 60)))
                cr.fill()
            surf.flush()
            return SA.flat_fraction(surf)
        self.assertGreater(frame(False), 0.5)
        self.assertLess(frame(True), 0.20)

    def test_every_primitive_renders_and_is_lit(self):
        import cairo
        from data_learning import scene_author as SA, subject_scenes as SS, illustrated as I
        draws = {
            "box": lambda cr: I.box(cr, 150, 1400, 700, 800, (212, 160, 60)),
            "cylinder": lambda cr: I.cylinder(cr, 150, 1400, 700, 800, (120, 140, 160), finish="metal"),
            "disc": lambda cr: I.disc(cr, 540, 1000, 400, (80, 160, 230), finish="gloss"),
            "solid-ice": lambda cr: (cr.rectangle(120, 600, 840, 820), I.solid(cr, (190, 220, 240), finish="ice")),
            "solid-glass": lambda cr: (cr.arc(540, 1000, 400, 0, 6.3), I.solid(cr, (90, 200, 220), finish="glass")),
        }
        for name, d in draws.items():
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
            cr = cairo.Context(surf)
            I.vgrad(cr, [(0.0, (70, 70, 130)), (1.0, (10, 10, 20))])
            I.contact_shadow(cr, 540, 1400, 800)
            d(cr)
            I.haze(cr, 0, 800, (60, 60, 120), 0.3)
            I.vignette(cr)
            surf.flush()
            self.assertLess(SA.flat_fraction(surf), 0.20, name)


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheVerifierMeasuresIt(unittest.TestCase):
    PTS = [["2019", 1.05], ["2025", 4.41]]

    def test_a_flat_hero_is_refused_and_told_the_kit(self):
        from data_learning import scene_author as SA
        probs = SA.craft_problems(SA.compile_scene(FLAT), self.PTS)
        self.assertEqual(len(probs), 1, probs)
        self.assertIn("clip art", probs[0])
        for n in ("solid(", "box()", "contact_shadow()", "vignette()"):
            self.assertIn(n, probs[0])
        self.assertIn("craft check" if False else "clip art",
                      " ".join(SA.verify(SA.compile_scene(FLAT), self.PTS)))

    def test_the_same_hero_lit_passes(self):
        from data_learning import scene_author as SA
        self.assertEqual(SA.craft_problems(SA.compile_scene(LIT), self.PTS), [])
        self.assertEqual([p for p in SA.verify(SA.compile_scene(LIT), self.PTS) if "clip art" in p], [])

    def test_a_flat_scene_saved_before_the_light_is_refused_on_load(self):
        from data_learning import scene_author as SA
        from unittest import mock
        lines = []
        seg = {"illustrated_scene": FLAT}
        with mock.patch("shared.rewrite_mailbox._dataset",
                        return_value={"points": [{"label": "2019", "value": 1.05},
                                                 {"label": "2025", "value": 4.41}]}):
            self.assertIsNone(SA.saved_scene(seg, log=lines.append))
            self.assertTrue(any("clip art" in ln for ln in lines), lines)
            self.assertIsNotNone(SA.saved_scene({"illustrated_scene": SA.stamped(LIT)}, log=lines.append))
            story = {"hook_scene": FLAT, "hook_data": 0, "segments": [seg]}
            self.assertIsNone(SA.saved_bookend(story, "hook", 1, log=lines.append))
            story["hook_scene"] = SA.stamped(LIT)
            self.assertIsNotNone(SA.saved_bookend(story, "hook", 1, log=lines.append))

    def test_the_threshold_is_where_the_posted_scenes_failed(self):
        from data_learning import scene_author as SA
        # teachers measure <= 0.07 under the metric; the posted flat scenes
        # 0.15-0.25; the flat fixture 0.58
        self.assertLessEqual(SA.FLAT_MAX, 0.15)
        self.assertGreaterEqual(SA.FLAT_MAX, 0.08)


class TheBrainIsToldAndShown(unittest.TestCase):
    def test_the_prompt_carries_the_rule_and_the_signatures(self):
        from data_learning import scene_author as SA
        p = SA.build_prompt("t", "x", "y", [["a", 1.0]], "")
        self.assertIn("THE ART IS LIT, NOT FLAT", p)
        for n in LIGHT:
            self.assertIn(f"  {n}(", p, n)

    def test_the_prompt_teachers_use_the_light(self):
        from data_learning import subject_scenes as SS
        for fn in (SS.amazon_where_it_goes, SS.coffee_drought, SS.bird_flu_barn):
            src = inspect.getsource(fn)
            self.assertTrue(any(f"{n}(" in src for n in ("solid", "box", "cylinder", "disc")), fn.__name__)
            self.assertIn("contact_shadow(", src, fn.__name__)


if __name__ == "__main__":
    unittest.main()
