"""Built, not a toy (operator, 2026-10-28).

Of one NYC noise video, its brick walk-up looked good and its red rotary
phone looked like "shit ai slop" — and, when the fix was a rule about WHAT
to draw: "it's an art style issue not a what we are drawing issue". The
walk-up is drawn from hundreds of small parts; the phone was one smooth
box, a dozen discs and a plastic shine on every one of them.

The two scenes are kept verbatim in tests/fixtures as they were posted.
"""
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

FIX = ROOT / "tests" / "fixtures"
PTS = [["Noise", 18.0], ["Everything else", 82.0]]


def _scene(name):
    from data_learning import scene_author as SA
    return SA.compile_scene((FIX / name).read_text())


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class ThePhoneIsAToyAndTheWalkUpIsBuilt(unittest.TestCase):
    def test_the_phone_is_refused(self):
        from data_learning import scene_author as SA
        probs = SA.detail_problems(_scene("nyc_noise_giant_phone_2026-10-27.py.txt"), PTS)
        self.assertTrue(probs)
        self.assertIn("rule 25", probs[0])
        self.assertIn("seams()", probs[0])

    def test_the_walk_up_passes(self):
        from data_learning import scene_author as SA
        self.assertEqual(SA.detail_problems(
            _scene("nyc_noise_walkup_2026-10-27.py.txt"), PTS), [])

    def test_the_bars_pass(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        for fn, rows in ((SS.bird_flu_barn, SA.SHOT_ROWS),
                         (SS.recycling_pile, SA.PILE_ROWS),
                         (SS.checkout_lanes, SA.CHECKOUT_ROWS)):
            with self.subTest(bar=fn.__name__):
                self.assertEqual(SA.detail_problems(fn, rows), [])

    def test_a_new_draw_is_held_to_it(self):
        from data_learning import scene_author as SA
        probs = SA.verify(_scene("nyc_noise_giant_phone_2026-10-27.py.txt"), PTS)
        self.assertTrue(any("small parts" in p for p in probs), probs)

    def test_data_and_the_words_are_not_counted(self):
        from data_learning import scene_author as SA
        bare = SA.compile_scene('''
def scene(cr, t, u, pts, host):
    """HERO: nothing
    SUBSTANCE: air
    CAUSE: Data stands
    """
    vgrad(cr, [(0.0, (30, 30, 60)), (1.0, (10, 10, 20))], 0, H)
    fit_readout(cr, "18", "Noise", 80, 520)
    host("think", 500, 1500, 300)
''')
        self.assertLess(SA.detail_count(bare, PTS), 5)


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class ThereIsNoPlasticShine(unittest.TestCase):
    def _brightest(self, finish):
        import cairo
        import numpy as np
        from data_learning import illustrated as I
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 400)
        cr = cairo.Context(surf)
        cr.rectangle(40, 40, 320, 320)
        I.solid(cr, (196, 38, 36), finish=finish, edge=False, rim=False)
        surf.flush()
        a = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(400, 400, 4)
        return int(a[60:340, 60:340, :3].min(axis=2).max())   # the whitest pixel

    def test_gloss_is_lit_like_matte(self):
        self.assertLessEqual(self._brightest("gloss") - self._brightest("matte"), 2)

    def test_metal_still_catches_the_light(self):
        self.assertGreater(self._brightest("metal") - self._brightest("matte"), 20)


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheKitHasTheParts(unittest.TestCase):
    def test_seams_and_trim_resolve_in_the_kit(self):
        from data_learning import scene_author as SA, illustrated as I
        g = SA.kit_globals()
        self.assertIs(g["seams"], I.seams)
        self.assertIs(g["trim"], I.trim)

    def test_they_draw_small_parts(self):
        from data_learning import scene_author as SA
        fn = SA.compile_scene('''
def scene(cr, t, u, pts, host):
    """HERO: a shed
    SUBSTANCE: wood
    CAUSE: Data stands
    """
    vgrad(cr, [(0.0, (30, 30, 60)), (1.0, (10, 10, 20))], 0, H)
    cr.rectangle(200, 900, 600, 500)
    solid(cr, (140, 100, 70))
    seams(cr, 200, 900, 800, 1400, (140, 100, 70), n=20)
    trim(cr, 400, 1100, 600, 1300, (220, 210, 190))
    host("think", 900, 1500, 300)
''')
        self.assertGreaterEqual(SA.detail_count(fn, PTS), 40)

    def test_the_prompt_asks_for_it_with_the_number(self):
        from data_learning import scene_author as SA
        p = SA.build_prompt("t", "x", "say", PTS, "", "", None)
        self.assertIn("BUILT, NOT A TOY", p)
        self.assertIn(f"fewer than {SA.DETAIL_MIN}", p)
        self.assertIn("gloss is a satin", p)


class TheSavedScenesKeepPosting(unittest.TestCase):
    def test_the_last_standard_is_in_grace(self):
        from data_learning import scene_author as SA
        self.assertIn("2026-10-28", SA.GRACE)
        self.assertNotEqual(SA.STANDARD, "2026-10-28")

    def test_the_posting_run_does_not_hold_an_old_scene_to_it(self):
        """Only the predraw (STRICT) re-judges a saved scene for detail."""
        from data_learning import scene_author as SA
        seen = []
        real = SA.verify
        try:
            SA.verify = lambda *a, **k: seen.append(k.get("detail")) or ["stop"]
            for strict in (False, True):
                SA.STRICT = strict
                SA.recertify(None, "x", PTS, log=lambda m: None)
        finally:
            SA.verify = real
            SA.STRICT = False
        self.assertEqual(seen, [False, True])


if __name__ == "__main__":
    unittest.main()
