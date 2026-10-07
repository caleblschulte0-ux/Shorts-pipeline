"""IT IS A SHOT, NOT A DIAGRAM.

Operator, 2026-10-07, on the new look's barn — a front-on elevation over an
empty field: "still very much lacking". On the same beat drawn as a shot (a
low sun, hills fading far to near, the barn in three-quarter view throwing a
long shadow, hens right by the camera): "ok now we are talking ... how
replicable is this?"

Replicable means the shot is in the KIT, not in one hand-drawn scene: the
setting, the three-quarter building, the cast shadow, the near-camera layer
are kit names the brain is given with their contracts, rule 13 tells it to
use them, and the barn itself is THE SHOT the prompt holds every scene to.
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

SHOT = ("landscape", "foreground", "building", "cast_shadow", "ridge",
        "treeline", "hen", "SUN", "SETTINGS")


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheShotIsInTheKit(unittest.TestCase):
    def test_every_shot_name_resolves_and_is_given_to_the_brain(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        for n in SHOT:
            self.assertIn(n, SA.KIT_NAMES, n)
            self.assertTrue(hasattr(SS, n), n)

    def test_every_setting_kind_fills_the_frame_and_looks_different(self):
        import numpy as np
        from data_learning import subject_scenes as SS
        seen = []
        for kind in SS.SETTINGS:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
            cr = cairo.Context(surf)
            y = SS.landscape(cr, 0.0, kind)
            SS.foreground(cr, kind)
            surf.flush()
            a = np.ndarray((SS.H, SS.W, 4), np.uint8, surf.get_data()).copy()
            self.assertEqual(int((a[..., 3] < 255).sum()), 0, kind)
            self.assertTrue(900 < y < 1500, (kind, y))
            seen.append(a[..., :3].mean(axis=(0, 1)))
        for i in range(len(seen)):
            for j in range(i + 1, len(seen)):
                self.assertGreater(float(abs(seen[i] - seen[j]).sum()), 6.0)

    def test_a_building_tells_the_scene_where_its_front_is(self):
        from data_learning import subject_scenes as SS
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
        for roof in ("gable", "gambrel", "flat"):
            b = SS.building(cairo.Context(surf), 150, 650, 1440, 380,
                            (196, 56, 42), roof=roof)
            self.assertEqual((b["x0"], b["x1"], b["base"], b["top"]),
                             (150, 650, 1440, 1060))
            self.assertLessEqual(b["peak"], b["top"])

    def test_the_contracts_reach_the_brain(self):
        from data_learning import scene_author as SA
        sigs = SA._sigs()
        line = next(ln for ln in sigs.splitlines() if ln.strip().startswith("building("))
        self.assertIn('{"x0","x1","top","base","peak"}', line)
        line = next(ln for ln in sigs.splitlines() if ln.strip().startswith("landscape("))
        self.assertIn("returns the ground's top y", line)


@unittest.skipUnless(HAVE_CAIRO, "pycairo not installed")
class TheBrainIsHeldToTheShot(unittest.TestCase):
    def test_the_prompt_carries_the_rule_and_the_shot(self):
        from data_learning import scene_author as SA, subject_scenes as SS
        p = SA.build_prompt("t", "x", "y", [["a", 1.0]], "")
        self.assertIn("IT IS A SHOT, NOT A DIAGRAM", p)
        self.assertIn(inspect.getsource(SS.bird_flu_barn), p)

    def test_the_shot_is_a_teacher_so_every_teacher_check_holds_it(self):
        from data_learning import subject_scenes as SS
        self.assertIn(SS.bird_flu_barn, SS.TEACHERS["bird-flu-species-jump"])
        src = inspect.getsource(SS.bird_flu_barn)
        for n in ("landscape(", "building(", "foreground(", "hen("):
            self.assertIn(n, src)


if __name__ == "__main__":
    unittest.main()
