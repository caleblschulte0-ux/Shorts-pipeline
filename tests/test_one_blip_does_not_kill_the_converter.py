"""2026-11-11: loader.to's page fetched eight videos for the day's cut-ins
and montages, one HTTP/2 reset marked it dead for the run, and all 27
downloads after it failed. Cut-ins and montages came back empty and the
clips shipped plain. A converter is given up on only after `DEAD_AFTER`
failures in a row, or at once when it does not exist or refuses us."""
from __future__ import annotations

import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from funnel import yt_convert as yc


class OneBlipDoesNotKillTheConverter(unittest.TestCase):
    def setUp(self):
        yc._DEAD.clear()
        yc._FAILS.clear()
        self.addCleanup(yc._DEAD.clear)
        self.addCleanup(yc._FAILS.clear)

    def _fetch(self, route, tmp):
        with mock.patch.object(yc, "ROUTES", (("page", route),)), \
             mock.patch.object(yc, "_hosts", lambda kind: ["https://p"]), \
             mock.patch.object(yc, "_ytdlp", lambda *a: None), \
             mock.patch.object(yc, "_save", lambda u, h, out: True), \
             mock.patch.object(yc, "_to_mp4", lambda raw, out: out), \
             mock.patch.object(yc, "_probe", lambda p: 30.0), \
             mock.patch.object(yc, "_api_meta", lambda vid: {}):
            return yc.fetch("https://youtu.be/abcdefghijk", Path(tmp) / "a.mp4")

    def test_a_reset_then_the_next_video_still_fetches(self):
        calls = {"n": 0}

        def route(host, vid):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionResetError("HTTP/2 stream 1 reset by server")
            return "https://file", {}, {"duration": 30}

        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(self._fetch(route, tmp))
            self.assertNotIn("https://p", yc._DEAD)
            self.assertIsNotNone(self._fetch(route, tmp))
        self.assertEqual(yc._FAILS, {})

    def test_three_in_a_row_gives_it_up(self):
        for _ in range(yc.DEAD_AFTER):
            yc._failed("https://p", ConnectionResetError("reset"))
        self.assertIn("https://p", yc._DEAD)

    def test_a_host_that_does_not_exist_is_given_up_at_once(self):
        yc._failed("https://gone", urllib.error.URLError(
            "[Errno -2] Name or service not known"))
        self.assertIn("https://gone", yc._DEAD)

    def test_forbidden_is_given_up_at_once(self):
        yc._failed("https://no", urllib.error.HTTPError(
            "https://no", 403, "Forbidden", {}, None))
        self.assertIn("https://no", yc._DEAD)


if __name__ == "__main__":
    unittest.main()
