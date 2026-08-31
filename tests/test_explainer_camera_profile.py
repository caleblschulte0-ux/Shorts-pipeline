"""Regression checks for the 2026-08-31 Data Explainer shake fix.

Operator ruling: Data Explainer gets no added camera movement of any kind.
Trending keeps its existing shared profile unchanged.
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

    def test_explainer_profile_is_literal_zero_motion(self):
        self.assertEqual(cf.profile_constants("explainer"), (0, 0.0, 0.0))

    def test_explainer_crop_contains_no_time_varying_expression(self):
        amp, wx, wy = cf.profile_constants("explainer")
        vf = cf.crop_vf(1080, 1920, amp=amp, wx=wx, wy=wy)
        self.assertEqual(vf, "scale=1080:1920,crop=1080:1920:x=0:y=0")
        self.assertNotIn("*t", vf)
        self.assertNotIn("sin(", vf)
        self.assertNotIn("cos(", vf)

    def test_explainer_overlay_is_fixed(self):
        amp, wx, wy = cf.profile_constants("explainer")
        x, y = cf.overlay_xy(12, 26, amp=amp, wx=wx, wy=wy)
        self.assertEqual((x, y), ("12", "26"))

    def test_workflow_selects_explainer_profile(self):
        env = dict(os.environ)
        env["GITHUB_WORKFLOW"] = "Explainer Stories"
        env.pop("CAMERA_FLOAT_PROFILE", None)
        code = (
            "from shared import camera_float as c; "
            "print(c.PROFILE, c.FLOAT_A, c.FLOAT_WX, c.FLOAT_WY); "
            "print(c.crop_vf(1080, 1920))"
        )
        out = subprocess.check_output(
            [sys.executable, "-c", code], cwd=ROOT, env=env, text=True).splitlines()
        self.assertEqual(out[0], "explainer 0 0.0 0.0")
        self.assertEqual(out[1], "scale=1080:1920,crop=1080:1920:x=0:y=0")

    def test_direct_studio_render_selects_explainer_profile(self):
        env = dict(os.environ)
        env.pop("GITHUB_WORKFLOW", None)
        env.pop("CAMERA_FLOAT_PROFILE", None)
        code = (
            "import sys; sys.argv[0]='data_learning/studio_render.py'; "
            "from shared import camera_float as c; "
            "print(c.PROFILE, c.FLOAT_A, c.FLOAT_WX, c.FLOAT_WY)"
        )
        out = subprocess.check_output(
            [sys.executable, "-c", code], cwd=ROOT, env=env, text=True).strip()
        self.assertEqual(out, "explainer 0 0.0 0.0")

    def test_explicit_default_override_remains_available(self):
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
