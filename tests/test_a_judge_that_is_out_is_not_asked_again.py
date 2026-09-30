"""A judge that has said it is out of budget is not asked again this run.

2026-09-27..29 the headless brain answered "You've hit your weekly limit"
and every render still retried it three times with sleeps, while the free
Gemini fallback took 429s from the same stampede. The breaker only SKIPS a
judge that cannot answer; with nobody left the gate still fails closed.
"""
import unittest
from unittest import mock

from scripts import showrunner_review as sr


class AJudgeThatIsOutIsNotAskedAgain(unittest.TestCase):
    def setUp(self):
        sr._OUT.clear()

    def tearDown(self):
        sr._OUT.clear()

    def test_a_limit_stops_the_retries_and_the_next_render_skips_claude(self):
        calls = []

        def claude(prompt, labeled):
            calls.append(1)
            raise RuntimeError("claude CLI rc=1: You've hit your weekly limit"
                               " · resets Sep 30, 12am (UTC)")

        with mock.patch.object(sr, "_headless_claude_judge", claude), \
             mock.patch.object(sr, "_gemini_judge",
                               return_value={"ok": 1}) as gem, \
             mock.patch.dict("os.environ", {"GEMINI_API_KEY": "k"}), \
             mock.patch("time.sleep"):
            self.assertEqual(sr._judge("p", [])[1], "gemini-fallback")
            self.assertEqual(len(calls), 1, "a limit is not retried")
            self.assertEqual(sr._judge("p", [])[1], "gemini-fallback")
            self.assertEqual(len(calls), 1, "the next render skips claude")
            self.assertEqual(gem.call_count, 2)

    def test_an_ordinary_failure_is_still_retried(self):
        calls = []

        def claude(prompt, labeled):
            calls.append(1)
            raise RuntimeError("claude CLI rc=1: no JSON in output")

        with mock.patch.object(sr, "_headless_claude_judge", claude), \
             mock.patch.dict("os.environ", {"GEMINI_API_KEY": "",
                                            "SHOWRUNNER_RETRIES": "3"}), \
             mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError):
                sr._judge("p", [])
        self.assertEqual(len(calls), 3)

    def test_nobody_left_still_fails_closed(self):
        def out(*a):
            raise RuntimeError("HTTP Error 429: Too Many Requests")

        with mock.patch.object(sr, "_headless_claude_judge", out), \
             mock.patch.object(sr, "_gemini_judge", out), \
             mock.patch.dict("os.environ", {"GEMINI_API_KEY": "k"}), \
             mock.patch("time.sleep"):
            with self.assertRaises(RuntimeError):
                sr._judge("p", [])
            with self.assertRaises(RuntimeError) as cm:
                sr._judge("p", [])
        self.assertIn("out of budget", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
