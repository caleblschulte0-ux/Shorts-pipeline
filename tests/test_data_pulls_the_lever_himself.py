"""Data pulls the scene's own lever, with his own hands.

Operator, 2026-10-22, of the Gen Z drinking video: "make data actually
interact with stuff ... the beer tap. He just sits there and he's spinning a
circle, whatever. Why is he not pulling the lever down on the tap? ... It's
simple stuff like that ... We need to take large strides in."

The scene drew its own tap and swung its handle on a clock of its own, while
Data stood beside it performing `tap` — an act that brings a red valve wheel
of its own and turns it in the air. 41 saved scenes did the same with `tap`
or `crank`. Now a brain scene draws a lever or a wheel with the kit (`lever`,
`handwheel`), each returns the two points his hands grip, one number drives
both, and the verifier MEASURES his hands on the scene drawn without him.
"""
import ast
import inspect
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

SHIPPED = (REPO / "tests" / "fixtures" / "beer_tap_spun_a_wheel_2026-10-21.py.txt")
PTS = [["~20 years ago", 72.0], ["2023", 59.0], ["2025", 50.0]]
SAY = ("Drinking among young adults fell from most of them to just half. "
       "Skipping a drink is now as common as ordering one.")


class NoActBringsItsOwnMechanism(unittest.TestCase):
    def test_the_mechanism_acts_are_not_brain_roles(self):
        for act in M.MECHANISM_ACTS:
            self.assertIn(act, M.ANIMATORS, act)        # machines still use them
            self.assertNotIn(act, M.TOOL_ACTS, act)

    @unittest.skipIf(SA is None, "no cairo")
    def test_the_verifier_does_not_offer_them(self):
        for act in M.MECHANISM_ACTS:
            self.assertNotIn(act, SA.ROLES)
            p = SA.build_prompt("t", "x", "y", [["a", 1.0]], "")
            self.assertNotIn(f"  {act}: ", p)

    def test_working_a_mechanism_asks_for_hands(self):
        for cause in ("Data cranks the lock gates shut",
                      "Data turns the valve at the hourglass neck",
                      "Data pulls the power lever down notch by notch",
                      "Data works the tap and drains the beer"):
            self.assertEqual(M.tool_for_cause(cause)[1], "grip", cause)

    @unittest.skipIf(SA is None, "no cairo")
    def test_a_named_part_is_found_whatever_the_verb(self):
        self.assertEqual(SA.mechanism_in("Data works the tap at the tower's foot"), "tap")
        self.assertEqual(SA.mechanism_in("Data taps the brass sand valve"), "valve")
        self.assertEqual(SA.mechanism_in("Data wheels his telescope out by hand"), "")


@unittest.skipIf(SS is None, "no cairo")
class TheKitResolves(unittest.TestCase):
    """CLAUDE.md: a name looked up with a silent default is a capability
    that does not exist. Every new name is a real function the brain gets."""

    def test_every_new_name_is_in_the_kit(self):
        g = SA.kit_globals()
        for name in ("lever", "lever_pull", "handwheel"):
            self.assertIn(name, SA.KIT_NAMES)
            self.assertTrue(callable(g[name]), name)

    def test_follow_is_a_real_stance_and_the_legs_follow_the_hands(self):
        sh = M.R.SHL[1]
        got = [M.follow_lower([0, y, 0], [0, y, 0]) for y in (sh - 60, sh + 50, sh + 120)]
        self.assertEqual(got, ["stand", "brace", "crouch"])
        for y in (sh - 60, sh + 50, sh + 120):
            spec = M.grip_spec([200, y, -10], [240, y, 10], "follow")
            self.assertIn(spec["pose"]["lower"], M._LOWER)

    def test_lever_pull_is_one_arc_not_a_sine(self):
        src = inspect.getsource(SS.lever_pull)
        names = {n.attr for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Attribute)}
        self.assertNotIn("sin", names)
        vals = [SS.lever_pull(k / 100) for k in range(101)]
        top = vals.index(max(vals))
        self.assertEqual(max(vals), 1.0)
        self.assertEqual(vals[0], 0.0)
        self.assertEqual(vals[-1], 0.0)
        self.assertEqual(vals[:top + 1], sorted(vals[:top + 1]))       # down...
        self.assertEqual(vals[top:], sorted(vals[top:], reverse=True))  # ...and up

    def _surf(self):
        import cairo
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, SS.W, SS.H)
        cr = cairo.Context(s)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        return s, cr

    def _inked(self, s, x, y):
        from PIL import Image
        s.flush()
        img = Image.frombuffer("RGBA", (SS.W, SS.H), bytes(s.get_data()),
                               "raw", "BGRA", 0, 1)
        return img.getpixel((int(x), int(y)))[:3] != (255, 255, 255)

    def test_the_hands_are_on_the_drawn_part_and_move_with_it(self):
        for draw, a, b in ((SS.lever, 0.0, 1.0), (SS.handwheel, 0.0, 0.3)):
            s0, cr0 = self._surf()
            h0 = draw(cr0, 540, 900, a)
            s1, cr1 = self._surf()
            h1 = draw(cr1, 540, 900, b)
            self.assertEqual(len(h0), 2)
            for (x, y) in h0:
                self.assertTrue(self._inked(s0, x, y), (draw.__name__, x, y))
            for (x, y) in h1:
                self.assertTrue(self._inked(s1, x, y), (draw.__name__, x, y))
            moved = max(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in zip(h0, h1))
            self.assertGreater(moved, 30, draw.__name__)


@unittest.skipIf(SA is None, "no cairo")
class HisHandsAreMeasuredOnWhatMoves(unittest.TestCase):
    def test_hands_moving_through_still_air_are_refused(self):
        still = [((300.0 + k, 900.0), 0) for k in range(10)]
        self.assertTrue(SA.hands_problems(still))
        on = [((300.0 + k, 900.0), 200) for k in range(10)]
        self.assertEqual(SA.hands_problems(on), [])
        self.assertEqual(SA.hands_problems(still[:2]), [])    # holding, not working

    def test_a_patch_counts_what_changed_under_the_hand(self):
        import numpy as np
        a = np.zeros((100, 100, 4), np.uint8)
        b = a.copy()
        b[40:60, 40:60, :3] = 255
        self.assertGreater(SA._patch_changed(a, b, 50, 50), SA.HAND_CHANGED)
        self.assertEqual(SA._patch_changed(a, b, 5, 5, r=4), 0)


@unittest.skipIf(SA is None, "no cairo")
class TheBeerTap(unittest.TestCase):
    """The scene that shipped, and the scene that replaced it."""

    def test_the_shipped_scene_is_refused(self):
        fn = SA.compile_scene(SHIPPED.read_text())
        probs = " | ".join(SA.verify(fn, PTS, SAY))
        self.assertIn("host('tap')", probs)
        self.assertIn("own hands", probs)

    def test_a_lever_that_moves_by_itself_beside_his_hands_is_refused(self):
        """His hands go through the motions of a pull a foot away from the
        lever, which swings on its own clock: the pantomime, measured."""
        code = SHIPPED.read_text().replace(
            'host("tap", px, 1480, 220, beat=j)',
            'host("grip", px, 1480, 220, hands=[(px + 40, 1300 + 60 * flow), '
            '(px + 60, 1320 + 60 * flow)])')
        fn = SA.compile_scene(code)
        probs = " | ".join(SA.verify(fn, PTS, SAY))
        self.assertIn("still air", probs)

    def test_the_saved_scene_pulls_the_lever(self):
        import json
        cfg = json.loads((REPO / "data_learning" / "niche.config.json").read_text())
        story = next(s for s in cfg["stories"] if s.get("slug") == "genz-drinking-decline")
        code = story["segments"][0]["illustrated_scene"]
        # drawn to the lever's standard, which the posting run still accepts
        self.assertIn(SA.standard_of(code), (SA.STANDARD,) + SA.GRACE)
        self.assertIn("hands=hands", code)
        self.assertIn("lever(", code)
        fn = SA.compile_scene(code)
        self.assertEqual(SA.verify(fn, PTS, SAY), [])


@unittest.skipIf(SA is None, "no cairo")
class TheBrainIsTold(unittest.TestCase):
    def test_rule_22_is_in_the_prompt(self):
        p = SA.build_prompt("t", "x", "y", [["a", 1.0]], "")
        self.assertIn("HE PULLS THE SCENE'S OWN LEVER", p)
        self.assertIn("pulling the lever down on the tap", p)
        self.assertIn('lower="follow"', p)

    def test_older_scenes_are_rejudged(self):
        self.assertGreaterEqual(SA.STANDARD, "2026-10-22")


if __name__ == "__main__":
    unittest.main()
