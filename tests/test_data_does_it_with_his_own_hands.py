"""Data does the work with his own hands, on the thing, as it is done.

Operator, 2026-10-15, of a warehouse beat where Data pulled a rope and a
row of garage doors rolled up: "why is he not, like, lifting up the garage
doors himself ... we just get too stuck in the pre-made animations ... we
don't ever make ones on the fly". Every act a brain scene could give him
was a named, pre-made one, so "lifts" came out as a rope and "opens" as a
valve. A GRIP has no pre-made motion: the scene puts his two hands on two
of its own points, frame by frame, and they are MEASURED to land there.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_learning import mascot_director as M  # noqa: E402

try:
    import cairo  # noqa: F401
    from data_learning import scene_author as SA
    from data_learning import subject_scenes as SS
except Exception:  # noqa: BLE001
    SS = SA = None

TEAL = tuple(int(M.R.TEAL[i:i + 2], 16) for i in (1, 3, 5))


class TheGripResolves(unittest.TestCase):
    def test_it_is_an_act_with_an_animator(self):
        self.assertIn("grip", M.TOOL_ACTS)
        self.assertIs(M.ANIMATORS["grip"], M._a_grip)

    def test_a_hand_job_asks_for_hands_not_a_rope_or_a_valve(self):
        for cause in ("Data lifts the garage door as the robots roll out",
                      "Data opens the barn door", "Data carries the crate in"):
            self.assertEqual(M.tool_for_cause(cause)[1], "grip", cause)

    @unittest.skipIf(SA is None, "no cairo")
    def test_the_brain_is_told_to_make_it(self):
        p = SA.build_prompt("t", "topic", "say", [("2012", 1.0), ("2025", 9.0)], "")
        self.assertIn('host("grip"', p)
        self.assertIn("lifting up the garage", p)
        self.assertIn("grip", SA.ROLES)


@unittest.skipIf(SS is None, "no cairo")
class HisHandsLandOnThePoints(unittest.TestCase):
    def _hand_near(self, img, x, y, r=12):
        best = 1e9
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                px = img.getpixel((int(x + dx), int(y + dy)))[:3]
                best = min(best, sum(abs(a - b) for a, b in zip(px, TEAL)))
        return best < 60

    def test_the_hands_follow_a_rising_edge(self):
        import cairo
        from PIL import Image
        x, fy, h = 540, 1400, 230
        for edge in (fy - 60, fy - 130, fy - 200):       # crouch to overhead
            hands = [(x - 60, edge), (x + 60, edge)]
            self.assertEqual(SA.grip_problems([("grip", hands, x, fy, h)]), [])
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
            cr = cairo.Context(surf)
            cr.set_source_rgb(1, 1, 1)
            cr.paint()
            box = SS.place_host(cr, "grip", 0.5, None, x, fy, h, 0, hands=hands,
                                lower="brace")
            if box is None:
                self.skipTest("no rasteriser")
            surf.flush()
            img = Image.frombuffer("RGBA", (SS.W, SS.H), bytes(surf.get_data()),
                                   "raw", "BGRA", 0, 1).convert("RGB")
            for hx, hy in hands:
                self.assertTrue(self._hand_near(img, hx, hy),
                                f"no hand at {(hx, hy)} (edge {edge})")


@unittest.skipIf(SA is None, "no cairo")
class AGripIsChecked(unittest.TestCase):
    def test_out_of_reach_is_refused_not_stretched(self):
        got = SA.grip_problems([("grip", [(480, 700), (600, 700)], 540, 1400, 230)])
        self.assertTrue(got and "past his reach" in got[0], got)

    def test_a_grip_needs_two_hands(self):
        self.assertTrue(SA.grip_problems([("grip", None, 540, 1400, 230)]))

    def test_hands_belong_to_a_grip(self):
        self.assertTrue(SA.grip_problems([("point", [(1, 1), (2, 2)], 540, 1400, 230)]))


if __name__ == "__main__":
    unittest.main()
