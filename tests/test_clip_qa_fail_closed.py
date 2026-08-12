"""third_capture/clip_qa.review() must fail CLOSED on an internal crash.

Regression for the doctor finding 653acb99b575: the outer exception handler
in review() used to set verdict="pass" on ANY internal QA exception (a
probe/vision/contact-sheet crash), and scripts/run_third.py treats any
non-"fail" verdict as ship-it with no further gate downstream. A QA crash
is not evidence the clip is fine — it must withhold the clip, exactly like
every other fail-closed gate in this pipeline (CLAUDE.md, showrunner
section).

    python -m unittest tests.test_clip_qa_fail_closed -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from third_capture import clip_qa  # noqa: E402


class TestReviewFailsClosedOnInternalError(unittest.TestCase):
    def test_mechanical_crash_yields_fail_not_pass(self):
        boom = RuntimeError("simulated ffprobe/mechanical crash")
        with patch.object(clip_qa, "_mechanical", side_effect=boom):
            result = clip_qa.review(
                Path("/nonexistent/does-not-matter.mp4"), {}, Path("/tmp"))

        self.assertEqual(result["verdict"], "fail")
        joined = "; ".join(result["problems"])
        self.assertIn("qa internal error", joined)
        self.assertIn("failed closed", joined)
        self.assertIn("RuntimeError", joined)

    def test_review_never_raises_even_on_crash(self):
        with patch.object(clip_qa, "_mechanical",
                           side_effect=OSError("disk gone")):
            try:
                result = clip_qa.review(
                    Path("/nonexistent/x.mp4"), {}, Path("/tmp"))
            except Exception as e:  # noqa: BLE001
                self.fail(f"review() raised instead of failing closed: {e}")
        self.assertEqual(result["verdict"], "fail")


if __name__ == "__main__":
    unittest.main()
