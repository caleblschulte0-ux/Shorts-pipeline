"""A collar is a band ON the neck, never a hoop floating over the head.

Operator, 2026-10-16, of the rabies video, whose dogs each wore a blue
outline ring stroked round the head with a tag on it: "look how shit
these collars look what is this". The brain had no dog in its kit and drew
the collar the cheapest way a ring can be drawn. The kit now has `dog`,
whose collar is a solid band from the neck's back edge to the throat, and
prompt rule 21 says every worn thing is drawn that way. MEASURED here:
the collar's pixels land on the dog, not in the air around it.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

try:
    import cairo
    from data_learning import scene_author as SA
    from data_learning import subject_scenes as SS
except Exception:  # noqa: BLE001
    cairo = SA = SS = None


def _alpha(collar, s=2.0, flip=False, t=0.4):
    w, h = 700, 560
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    hang = SS.dog(cr, 300, 500, s, t, flip=flip, collar=collar)
    surf.flush()
    buf = bytes(surf.get_data())
    stride = surf.get_stride()
    px = {}
    for y in range(h):
        row = buf[y * stride:(y + 1) * stride]
        for x in range(w):
            b, g, r, a = row[4 * x:4 * x + 4]
            if a > 200:
                px[(x, y)] = (r, g, b)
    return px, hang


@unittest.skipIf(SS is None, "no cairo")
class ADogIsInTheKit(unittest.TestCase):
    def test_it_resolves_for_the_brain(self):
        self.assertIn("dog", SA.KIT_NAMES)
        self.assertIs(SA.kit_globals()["dog"], SS.dog)
        for coat in SS.COATS:
            SS.dog(cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)),
                   5, 5, 0.1, 0.0, coat=coat, collar=(40, 90, 200))

    def test_the_prompt_says_a_worn_thing_wraps_the_body(self):
        ask = SA.build_prompt("Rabies", "dogs", "a dog bite starts it",
                              [["dogs", 99]], "%")
        self.assertIn("21. WHAT IS WORN WRAPS THE BODY", ask)
        self.assertIn("dog(cr", ask)
        self.assertIn("floating as an outline ring", SA._LOOK_AGAIN)

    def test_a_new_rule_retires_scenes_drawn_before_it(self):
        self.assertGreaterEqual(SA.STANDARD, "2026-10-16.2")


@unittest.skipIf(SS is None, "no cairo")
class TheCollarIsOnTheNeck(unittest.TestCase):
    def test_the_band_lands_on_the_dog_not_around_it(self):
        for flip in (False, True):
            bare, _ = _alpha(None, flip=flip)
            worn, hang = _alpha((40, 90, 200), flip=flip)
            changed = [p for p, c in worn.items() if bare.get(p) != c]
            self.assertGreater(len(changed), 150, "no collar was drawn")
            hx, hy = hang
            band = [p for p in changed
                    if (p[0] - hx) ** 2 + (p[1] - hy) ** 2 > 18 ** 2]
            off = [p for p in band if p not in bare]
            self.assertLess(len(off) / len(band), 0.08,
                            f"{len(off)} of {len(band)} collar pixels are off "
                            f"the dog (flip={flip})")

    def test_it_is_a_band_not_a_ring_round_the_head(self):
        bare, _ = _alpha(None)
        worn, hang = _alpha((40, 90, 200))
        blue = [p for p, c in worn.items()
                if c[2] > c[0] + 60 and bare.get(p) != c]
        self.assertTrue(blue)
        xs = [p[0] for p in blue]
        ys = [p[1] for p in blue]
        # a hoop round a head is as wide as the head; a band across a neck
        # is a short diagonal strip
        self.assertLess(max(xs) - min(xs), 80)
        self.assertLess(max(ys) - min(ys), 80)


if __name__ == "__main__":
    unittest.main()
