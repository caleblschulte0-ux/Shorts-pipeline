"""A scene must MOVE — measured the way the reviewer measures.

2026-09-12 the explainer held 16 of 17 videos, and `temporal_gate` was 10 of
the 16. Eight were `effective_fps` under the 11.0 floor, five clustered at
10.7-10.9 — missing by under 3%, which is not "bad videos", it is one
systematic cause.

Measured on a real render, windowed by second:

    window   dup%   eff_fps   what is on screen
     8-12s     0%      24.0   a CHART
     2- 6s   85-92%    2-3.5  a brain-authored SCENE
    16-20s   88-90%    2.5-3  a brain-authored SCENE

Charts sweep their marks hundreds of pixels across a beat, so adjacent
frames differ. The ozone scene shrinks its circle about 0.34px per frame at
1080 — 0.06px at the detector's 192px downscale. Geometrically perfect,
frozen to anything measuring.

CLAUDE.md already records this exact lesson ("a slow glide across a whole
visual is a sub-pixel change per frame ... five machines were geometrically
perfect and measured as frozen") and `MotionMustBeVISIBLE` holds the 42
machines to it. Brain-authored mechanics are not in `_MACHINE_DRAW`, so that
test never covered them — the same blind spot that let `_draw_flat_timeline`
go unmeasured for weeks.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import viz_scene as vs                    # noqa: E402


def _spec(body, name="probe"):
    return {"mechanic": name, "concept": "c", "code": body}


class _Ins:
    slug = "t"
    topic = "t"
    unit = "count"


#: A mark that sweeps most of the frame across the beat — what a chart does,
#: and what measures at a clean 24fps.
SWEEPS = "d.rectangle([0, 0, 40, int(20 + reveal * (H - 100))], fill=rgba(TEXT, 255))"
#: The bug: a correct, smooth, tiny glide. 70px over the whole beat.
GLIDES = "d.ellipse([100, 100 + int(reveal * 70), 300, 300 + int(reveal * 70)], fill=rgba(TEXT, 255))"
#: Draws the same thing whatever the reveal.
STILL = "d.rectangle([100, 100, 400, 400], fill=rgba(TEXT, 255))"


def _env():
    """The sandbox `_run_mechanic_frame` expects. The PIL handles are NOT
    optional — leaving them out made every probe raise `KeyError: '_Image'`,
    and the probe's broad `except` turned that into `True`. A fixture that
    silently allows everything would have made this whole file pass while
    testing nothing."""
    from PIL import Image, ImageChops, ImageDraw, ImageOps
    return {"values": [1.0, 2.0, 3.0], "labels": ["a", "b", "c"],
            "vmax": 3.0, "n": 3, "images": {},
            "subject_image": lambda *_a, **_k: None,
            "_Image": Image, "_ImageDraw": ImageDraw,
            "_ImageOps": ImageOps, "_ImageChops": ImageChops}


def _probe(code):
    with mock.patch.object(vs, "_mechanic_env", return_value=_env()):
        return vs.mechanic_motion_ok(_spec(code), _Ins())


class TheFIXTUREActuallyRuns(unittest.TestCase):
    """A guard on this file's own honesty. The first version of `_env` left
    out the PIL handles, every probe raised `KeyError: '_Image'`, the broad
    `except` returned True, and the suite passed while measuring nothing."""

    def test_the_probe_really_renders(self):
        import time
        t = time.time()
        _probe(SWEEPS)
        self.assertGreater(time.time() - t, 0.02,
                           "the probe returned too fast to have rendered — "
                           "it is short-circuiting on an exception again")


class ItMeasuresWhatTheGateMeasures(unittest.TestCase):
    def test_a_mark_that_sweeps_the_frame_passes(self):
        self.assertTrue(_probe(SWEEPS))

    def test_a_scene_that_draws_the_same_thing_every_frame_is_refused(self):
        self.assertFalse(_probe(STILL))

    def test_a_correct_but_TINY_glide_is_refused(self):
        """This is the actual bug: nothing is wrong with the drawing, the
        motion is simply below what the reviewer can see."""
        self.assertFalse(_probe(GLIDES))


class ItComparesADJACENTFrames(unittest.TestCase):
    """THE FIRST VERSION OF THIS PROBE GOT THE INTERVAL WRONG and it is worth
    holding: it sampled six points spread across the ENTIRE reveal, where of
    course everything moves. It passed `banned-barrel-drain`, which had just
    measured 88-90% duplicate frames in a real render. A probe that measures
    a different interval than the gate is not a probe."""

    def test_the_step_is_one_sampled_frame_not_a_slice_of_the_reveal(self):
        step = 1.0 / (vs._MOTION_SAMPLE_FPS * vs._MOTION_BEAT_S)
        self.assertLess(step, 0.01, "the step is a chunk of the reveal again")
        self.assertAlmostEqual(vs._MOTION_SAMPLE_FPS, 24.0,
                               msg="the reviewer samples at 24fps")

    def test_it_downscales_to_the_detectors_width(self):
        self.assertEqual(vs._DETECTOR_W, 192)

    def test_it_uses_the_reviewers_own_detector(self):
        import ast
        import inspect
        src = inspect.getsource(vs.mechanic_motion_ok)
        tree = ast.parse(src.lstrip())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        code = ast.unparse(tree)
        self.assertIn("_max_block_diff", code)
        self.assertIn("BLOCK_MOTION_THRESH", code)


class TheThresholdIsNotAnOverCorrection(unittest.TestCase):
    """The gate's budget is a ratio over the WHOLE video (0.45), not per
    beat. A totally frozen scene that is one of three beats contributes about
    0.33 and the video still passes, because the chart beats measure clean.
    Refusing every smooth animation would trade a blocked video for an
    all-chart video and throw away the scenes this channel is liked for."""

    def test_moving_anywhere_is_enough(self):
        self.assertEqual(vs._MOTION_MIN_POINTS, 1)

    def test_it_tests_several_points_across_the_beat(self):
        """A scene can move at one end and stall at the other — an ease-out
        that asymptotes is the classic."""
        self.assertGreaterEqual(len(vs._MOTION_AT), 4)
        self.assertLess(min(vs._MOTION_AT), 0.3)
        self.assertGreater(max(vs._MOTION_AT), 0.7)

    def test_a_scene_that_moves_only_at_the_start_survives(self):
        code = ("p = 0.0 if reveal > 0.25 else reveal * 4\n"
                "d.rectangle([0, 0, 40, int(20 + p * (H - 100))], "
                "fill=rgba(TEXT, 255))")
        self.assertTrue(_probe(code))


class ItNeverKillsARender(unittest.TestCase):
    def test_a_throwing_mechanic_is_allowed_through_not_crashed_on(self):
        """The probe is an opinion, not a gate. A broken mechanic is caught
        by `mechanic_dry_ok`'s existing run, which has its own handling."""
        self.assertTrue(_probe("raise ValueError('boom')"))

    def test_no_reviewer_means_no_opinion(self):
        with mock.patch.dict(sys.modules,
                             {"scripts.showrunner_review": None}):
            self.assertTrue(_probe(STILL))


class TheDryRunASKSTheQuestion(unittest.TestCase):
    def test_dry_ok_checks_motion_too(self):
        import ast
        import inspect
        src = inspect.getsource(vs.mechanic_dry_ok)
        tree = ast.parse(src.lstrip())
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = ""
        self.assertIn("mechanic_motion_ok", ast.unparse(tree))

    def test_it_still_rejects_a_mechanic_that_draws_nothing(self):
        with mock.patch.object(vs, "_mechanic_env", return_value=_env()), \
             mock.patch.object(vs, "validate_mechanic", return_value=True):
            self.assertFalse(vs.mechanic_dry_ok(_spec("pass"), _Ins()))


if __name__ == "__main__":
    unittest.main()
