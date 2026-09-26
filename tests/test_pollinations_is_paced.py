"""Pollinations' keyless tier answers one request at a time.

2026-09-26: every trending backfill got its first image and then 429, 429,
429, fired half a second apart — and five stories shipped with no pictures
("no beat is shown on screen"). Calls are paced, a 429 is retried after a
wait, and a process-wide budget stops a dead service eating the render.
"""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from funnel import gemini_images as G  # noqa: E402


def _http429():
    return urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Paced(unittest.TestCase):
    def setUp(self):
        G._POLL.update(last=0.0, spent=0.0)
        self.slept = []

    def _run(self, answers):
        calls = iter(answers)

        def urlopen(req, timeout=None):
            a = next(calls)
            if isinstance(a, Exception):
                raise a
            return _Resp(a)

        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(G.urllib.request, "urlopen", urlopen), \
                mock.patch("time.sleep", lambda s: self.slept.append(s)):
            out = [G._pollinations_image("a cat", Path(td) / f"{i}.png",
                                         64, 64, None) for i in range(2)]
            return [bool(o) for o in out]

    def test_a_429_is_waited_out_and_retried(self):
        got = self._run([b"x" * 5000, _http429(), b"y" * 5000])
        self.assertEqual(got, [True, True])
        self.assertTrue(any(s >= G.POLLINATIONS_BACKOFF_S for s in self.slept))

    def test_calls_are_spaced(self):
        self._run([b"x" * 5000, b"y" * 5000])
        self.assertTrue(self.slept)
        self.assertLessEqual(max(self.slept), G.POLLINATIONS_MIN_GAP_S + 0.01)

    def test_a_spent_budget_fails_fast(self):
        G._POLL["spent"] = G.POLLINATIONS_BUDGET_S
        got = self._run([b"x" * 5000, _http429()])
        self.assertEqual(got, [True, False])

    def test_other_errors_are_not_retried(self):
        err = urllib.error.HTTPError("u", 500, "boom", {}, None)
        got = self._run([err, b"y" * 5000])
        self.assertEqual(got, [False, True])


if __name__ == "__main__":
    unittest.main()
