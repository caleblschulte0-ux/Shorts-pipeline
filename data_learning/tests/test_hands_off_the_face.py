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


class ArmsGoBehindTheHead(unittest.TestCase):
    """The wrist keep-out alone was not enough, and the next render proved it:
    the hands were overhead exactly as asked and the ARMS reaching up to them
    ran across his face. An arm is a 32px stroke, not its endpoint."""

    def test_the_head_is_drawn_after_the_arms(self):
        src = inspect.getsource(rig.assemble)
        body = src[src.index("return ("):]
        self.assertLess(body.index("arms"), body.index("head()"),
                        "arms are drawn over the face again")

    def test_the_torso_is_still_drawn_before_the_arms(self):
        """Behind the HEAD, not behind the body — sleeves belong over the
        coat."""
        src = inspect.getsource(rig.assemble)
        body = src[src.index("return ("):]
        self.assertLess(body.index("coat()"), body.index("arms"))

    def test_a_raised_arm_is_occluded_rather_than_flung_aside(self):
        """The rejected fix bent the elbow and slid the wrist until the arm
        cleared the head — which needed the hands out at the frame edges,
        wrecking the pose and sliding the hands off the chart element they are
        baked onto for STRICT_CONTACT. Drawing order moves nothing."""
        self.assertFalse(hasattr(rig, "_clear_arm"))
        wx, wy = rig._off_face(156, 45)          # a fist clamped overhead
        self.assertLess(abs(wx - 156), 40, "the overhead grip was flung aside")


class HeIsCalm(unittest.TestCase):
    """Measured, because "too much movement" is otherwise a matter of taste and
    every previous tuning was done by eye. Over one visual the shipped poses
    whipped the body through 56 degrees at 248 deg/s (`_a_race_sprint`), snapped
    at 513 deg/s (`_a_discover`), and reversed direction five times
    (`_a_balance_beam`) — a swing, not an act."""

    _ROT = re.compile(r"rotate\(([-\d.]+),170,210\)")
    _TR = re.compile(r"translate\(0,([-\d.]+)\)")

    def _composed(self, fn_name):
        spec = {"action": fn_name.replace("_a_", ""), "prop": "price_tag"}
        for i in range(41):
            yield md.compose_anim(spec, i / 40.0)

    def test_no_pose_tilts_the_body_past_the_bound(self):
        for name, _fn in _primitives():
            for svg in self._composed(name):
                for m in self._ROT.finditer(svg):
                    self.assertLessEqual(abs(float(m.group(1))), md.TILT_MAX,
                                         f"{name} tilts past TILT_MAX")

    def test_no_pose_bobs_past_the_bound(self):
        for name, _fn in _primitives():
            for svg in self._composed(name):
                for m in self._TR.finditer(svg):
                    self.assertLessEqual(abs(float(m.group(1))), md.BOB_MAX,
                                         f"{name} bobs past BOB_MAX")

    def test_the_bound_is_applied_at_the_one_place_a_transform_is_written(self):
        """32 primitives were each authored against a mental picture of how big
        a lean reads, and nothing compared them. Same failure as the hands, in
        a different dimension — so the same shape of fix."""
        src = inspect.getsource(md.compose_anim)
        self.assertIn("TILT_MAX", src)
        self.assertIn("BOB_MAX", src)
        self.assertIn("BODY_DAMP", src)

    def test_damping_keeps_the_shape_of_an_action(self):
        """A bound that flattened every pose to zero would 'pass' this file and
        ship a mannequin. Damping is proportional, so a big authored lean is
        still bigger than a small one."""
        self.assertGreater(md.BODY_DAMP, 0.0)
        self.assertLess(md.BODY_DAMP, 1.0)
        big = max(-md.TILT_MAX, min(md.TILT_MAX, 20.0 * md.BODY_DAMP))
        small = max(-md.TILT_MAX, min(md.TILT_MAX, 4.0 * md.BODY_DAMP))
        self.assertGreater(big, small)

    def test_the_action_lasts_as_long_as_the_visual_it_is_about(self):
        """It was a flat 2.2s, so a complete dramatic arc — setup, action,
        payoff — ran about twice per visual and fourteen times per video.
        Nothing in the narration cycles that fast."""
        self.assertIn("seconds=_span", _STUDIO)
        self.assertNotIn("seconds=2.2", _STUDIO)


class NoTremor(unittest.TestCase):
    """The periodic-motion ban had a hole exactly the width of a hand.

    tests/test_no_camera_shake.py reads `bob` and `tilt` — the body transform —
    and passed the whole time the pose primitives carried
    `math.sin(t * math.pi * 14) * 3.0` ON THE HAND COORDINATES: seven full
    oscillations of both fists inside a single visual. Stacked on top of
    `_perf_phase` running FOUR ping-pong reps of the entire arc, that is what
    the operator watched: "he needs to not be doing so much constant random,
    like, jerking around ... it looks like he's having a seizure the whole
    time."

    So the rule is stated where it can be checked: inside one visual, no part
    of him may oscillate more than about once. A single strain-and-release is
    an action; six are a symptom.
    """

    _SRC = (_REPO / "data_learning" / "mascot_director.py").read_text()

    # A multi-phase action legitimately changes direction at each phase
    # boundary (resist -> tug -> land is three), so the bound is set above that
    # and below the tremors: the worst offenders measured TWELVE.
    _MAX_REVERSALS = 6

    @staticmethod
    def _reversals(seq):
        sg = [1 if seq[i + 1] > seq[i] else (-1 if seq[i + 1] < seq[i] else 0)
              for i in range(len(seq) - 1)]
        sg = [x for x in sg if x]
        return sum(1 for i in range(len(sg) - 1) if sg[i] != sg[i + 1])

    def test_no_hand_oscillates_more_than_an_action_would(self):
        """MEASURED, not pattern-matched. The first version of this test read
        the source for `math.pi * N` and was simply wrong — `sin(x*pi*2)` is
        ONE cycle, not two — so it flagged honest single-swing poses and would
        have been "fixed" by loosening it. Counting direction changes in the
        rendered hand path asks the real question and cannot be argued with."""
        worst = {}
        for name, fn in _primitives():
            xs, ys = [], []
            for i in range(61):
                try:
                    svg = _flat(fn(i / 60.0, "price_tag"))
                except Exception:  # noqa: BLE001
                    break
                hands = list(_hands(svg))
                if hands:
                    xs.append(hands[0][0])
                    ys.append(hands[0][1])
            if len(ys) > 5:
                r = max(self._reversals(xs), self._reversals(ys))
                if r > self._MAX_REVERSALS:
                    worst[name] = r
        self.assertEqual(worst, {}, f"hands vibrating rather than acting: {worst}")

    def test_the_performance_arc_runs_about_once_per_visual(self):
        """`_perf_phase` reps. Four meant eight direction reversals of the
        whole body inside one ~6s visual."""
        import inspect
        from data_learning import charts as _ch
        src = inspect.getsource(_ch._perf_phase)
        line = [l for l in src.splitlines() if "u = (t / 0.8)" in l]
        self.assertTrue(line, "the struggle rep count moved — re-pin it")
        reps = float(line[0].split("*")[-1].strip())
        self.assertLessEqual(reps, 1.0, f"{reps} reps per visual is flailing")

    def test_the_phase_still_lands_on_the_payoff(self):
        """Calmer must not mean broken: phase 1.0 has to be the climax pose or
        the action never resolves."""
        from data_learning import charts as _ch
        self.assertAlmostEqual(_ch._perf_phase(1.0), 1.0, places=6)
        self.assertAlmostEqual(_ch._perf_phase(0.0), 0.0, places=6)

    def test_the_arc_is_not_flattened_to_nothing(self):
        """A pose that never moves would pass every assertion above and ship a
        statue — the defect this channel spent eleven days on."""
        from data_learning import charts as _ch
        vals = [_ch._perf_phase(i / 40.0) for i in range(41)]
        self.assertGreater(max(vals) - min(vals), 0.5, "the host stopped acting")


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
