"""No hand ever crosses onto Data's face, and he does not slide around.

Both of these are operator findings from watching shipped videos:

    "the fucking mascot's tweaking out all over the screen all the time.
     In his hands, they're always covering his face."

Two separate defects with one common cause — poses and motion were each
authored against a mental picture rather than measured against the rig:

  * HANDS ON THE FACE. Measured across every pose primitive the director can
    produce, 15 of 32 put a hand inside the head disc at some point in its arc.
    `_a_stretched` ended with a hand 6px from the centre of his face and
    `_a_overwhelmed` put BOTH there. Nothing had ever checked a wrist against
    the head, so each new authored pose was free to do it again — which is why
    the fix is a keep-out at the ONE place an arm is drawn, and why this test
    sweeps every primitive rather than the handful that were visibly wrong.
  * SLIDING. He glided into position at the start of every window. With three
    beats that was three moves; the monotonic edit re-stages him per SPAN, so
    it became eight — one every four seconds.

Runs with pytest OR standalone:
    python3 data_learning/tests/test_hands_off_the_face.py
"""
from __future__ import annotations

import inspect
import math
import re
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import mascot_director as md  # noqa: E402
from scripts import build_mascot_svg as rig  # noqa: E402

_STUDIO = (_REPO / "data_learning" / "studio_render.py").read_text()
_HAND = re.compile(r'<circle cx="([-\d.]+)" cy="([-\d.]+)" r="19"')


def _flat(o) -> str:
    if isinstance(o, str):
        return o
    if isinstance(o, (list, tuple)):
        return "".join(_flat(x) for x in o)
    return ""


def _primitives():
    for name, fn in sorted(vars(md).items()):
        if not (name.startswith("_a_") and callable(fn) and name != "_a_pose"):
            continue
        try:
            if len(inspect.signature(fn).parameters) != 2:
                continue
        except (TypeError, ValueError):
            continue
        yield name, fn


def _hands(svg: str):
    for m in _HAND.finditer(svg):
        yield float(m.group(1)), float(m.group(2))


class HandsOffTheFace(unittest.TestCase):
    def test_no_primitive_ever_puts_a_hand_on_the_face(self):
        """The whole arc of every pose, not just its resting frame. Several of
        these were clean at t=0 and t=1 and covered his face in the middle."""
        worst = {}
        for name, fn in _primitives():
            for i in range(81):
                try:
                    svg = _flat(fn(i / 80.0, "price_tag"))
                except Exception:  # noqa: BLE001 — a broken prim is another test
                    break
                for x, y in _hands(svg):
                    d = math.hypot(x - rig.HEAD_C[0], y - rig.HEAD_C[1])
                    if d < rig.FACE_KEEPOUT:
                        worst[name] = min(worst.get(name, 1e9), round(d, 1))
        self.assertEqual(worst, {},
                         f"hands on the face (keep-out {rig.FACE_KEEPOUT}): {worst}")

    def test_the_presets_and_the_static_expressions_are_clear_too(self):
        for name in md.POSE_PRESETS:
            spec = md.author_performance("cost", name, "", "bars")
            for x, y in _hands(_flat(md.compose_svg(spec))):
                d = math.hypot(x - rig.HEAD_C[0], y - rig.HEAD_C[1])
                self.assertGreaterEqual(d, rig.FACE_KEEPOUT, f"{name}: {d}")

    def test_the_keepout_is_enforced_at_the_one_place_arms_are_drawn(self):
        """Fixing the 15 offending coordinate sets by hand would leave the next
        authored pose free to do it again. Every pose in the system routes
        through `arm()`, so that is where the constraint lives."""
        src = inspect.getsource(rig.arm)
        self.assertIn("_off_face", src)

    def test_a_wrist_shoved_into_the_face_comes_back_out(self):
        for wx, wy in ((170, 114), (170, 120), (141, 123), (206, 114),
                       (152, 84), (130, 90)):
            ox, oy = rig._off_face(wx, wy)
            d = math.hypot(ox - rig.HEAD_C[0], oy - rig.HEAD_C[1])
            self.assertGreaterEqual(d, rig.FACE_KEEPOUT, f"({wx},{wy})->({ox},{oy})")

    def test_the_push_keeps_the_gesture_pointing_where_it_was(self):
        """A radial push would rotate the gesture; for the overhead grips it
        would also slide the hand off the chart element it is baked onto. A
        sideways reach stays sideways, an overhead reach stays overhead."""
        ox, _ = rig._off_face(206, 114)          # reaching right
        self.assertGreater(ox, rig.HEAD_C[0], "a rightward reach went left")
        _, oy = rig._off_face(152, 84)           # reaching up
        self.assertLess(oy, rig.HEAD_C[1], "an overhead reach came down")

    def test_a_hand_already_clear_is_left_exactly_alone(self):
        for wx, wy in ((70, 300), (260, 250), (170, 400)):
            self.assertEqual(rig._off_face(wx, wy), (wx, wy))


class HeDoesNotSlide(unittest.TestCase):
    def test_the_host_holds_one_position_for_a_whole_span(self):
        """His overlay x/y must be constants. A `_piecewise` there is the
        sweep-in returning: eight of them in a video is the 'tweaking out all
        over the screen' the operator watched."""
        blk = _STUDIO[_STUDIO.index("Mascots — Data IS PLACED"):]
        blk = blk[:blk.index("NO CAMERA MOTION")]
        self.assertNotIn("_piecewise", blk, "the glide is back")
        self.assertIn('xe = f"{tlx:.0f}"', blk)
        self.assertIn('ye = f"{tly:.0f}"', blk)

    def test_no_oscillation_rides_on_top(self):
        blk = _STUDIO[_STUDIO.index("Mascots — Data IS PLACED"):]
        blk = blk[:blk.index("NO CAMERA MOTION")]
        for bad in ("sin(", "cos("):
            self.assertNotIn(bad, blk, f"{bad} is a bob/sway coming back")


if __name__ == "__main__":
    unittest.main(verbosity=2)
