"""Regression checks for the 2026-08-31 Data Explainer shake fix.

The shared camera motion still serves Trending, so the Explainer's calmer
profile must be channel-scoped: same temporal-QA displacement, substantially
less acceleration, and no change to the default profile.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import camera_float as cf  # noqa: E402


class TestExplainerCameraProfile(unittest.TestCase):

    def test_default_profile_is_unchanged_for_other_channels(self):
        self.assertEqual(
            cf.profile_constants("default"),
            (44, 2.1, 1.7),
            "an Explainer visual fix must not silently retune Trending")

    def test_explainer_keeps_the_motion_floor(self):
        amp, wx, wy = cf.profile_constants("explainer")
        self.assertGreaterEqual(cf.px_per_frame(amp, wx, 30.0), cf.MIN_PX_PER_FRAME)
        # The second axis can be slightly under the x target, but must remain
        # safely above the measured 2.3 px/frame failure region.
        self.assertGreaterEqual(cf.px_per_frame(amp, wy, 30.0), 2.6)

    def test_explainer_is_materially_calmer_than_the_old_breath(self):
        amp, wx, wy = cf.profile_constants("explainer")
        old_ax = cf.DEFAULT_FLOAT_A * cf.DEFAULT_FLOAT_WX ** 2
        old_ay = cf.DEFAULT_FLOAT_A * cf.DEFAULT_FLOAT_WY ** 2
        self.assertLessEqual(amp * wx ** 2, old_ax * 0.60)
        self.assertLessEqual(amp * wy ** 2, old_ay * 0.80)

    def test_explainer_axes_are_nearly_coherent_not_beating_oscillators(self):
        _, wx, wy = cf.profile_constants("explainer")
        self.assertLessEqual(abs(wx - wy), 0.10)

    def test_extra_crop_stays_bounded(self):
        amp, _, _ = cf.profile_constants("explainer")
        self.assertLessEqual(amp / 1080.0, 0.07)

    def test_workflow_selects_explainer_profile(self):
        env = dict(os.environ)
        env["GITHUB_WORKFLOW"] = "Explainer Stories"
        env.pop("CAMERA_FLOAT_PROFILE", None)
        code = (
            "from shared import camera_float as c; "
            "print(c.PROFILE, c.FLOAT_A, c.FLOAT_WX, c.FLOAT_WY)"
        )
        out = subprocess.check_output(
            [sys.executable, "-c", code], cwd=ROOT, env=env, text=True).strip()
        self.assertEqual(out, "explainer 72 1.22 1.15")

    def test_explicit_default_override_is_available_for_ab_comparison(self):
        env = dict(os.environ)
        env["GITHUB_WORKFLOW"] = "Explainer Stories"
        env["CAMERA_FLOAT_PROFILE"] = "default"
        code = (
            "from shared import camera_float as c; "
            "print(c.PROFILE, c.FLOAT_A, c.FLOAT_WX, c.FLOAT_WY)"
        )
        out = subprocess.check_output(
            [sys.executable, "-c", code], cwd=ROOT, env=env, text=True).strip()
        self.assertEqual(out, "default 44 2.1 1.7")


if __name__ == "__main__":
    unittest.main()
