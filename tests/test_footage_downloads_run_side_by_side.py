"""2026-11-11: the only converter that answers from GitHub's runners
takes minutes a video, and footage was fetched one video at a time, so a
montage's budget went on two or three candidates. `_downloads` keeps
`PARALLEL` running ahead of the one being judged, in candidate order."""
from __future__ import annotations

import time
import unittest
from pathlib import Path
from unittest import mock

from funnel import find_footage as ff


class DownloadsRunSideBySide(unittest.TestCase):
    def test_three_slow_downloads_take_the_time_of_one(self):
        def slow(url, out):
            time.sleep(0.6)
            return Path(url)

        cands = [{"url": f"v{i}"} for i in range(3)]
        t = time.monotonic()
        with mock.patch.object(ff, "download", slow), \
             mock.patch.object(ff, "PARALLEL", 3):
            got = [(k, str(p)) for k, _v, p in
                   ff._downloads(cands, lambda i: Path(f"o{i}"))]
        self.assertLess(time.monotonic() - t, 1.5)
        self.assertEqual(got, [(0, "v0"), (1, "v1"), (2, "v2")])

    def test_a_failed_download_is_none_and_the_rest_go_on(self):
        def flaky(url, out):
            if url == "v1":
                raise RuntimeError("boom")
            return Path(url)

        cands = [{"url": f"v{i}"} for i in range(3)]
        with mock.patch.object(ff, "download", flaky):
            got = [p for _k, _v, p in ff._downloads(cands, lambda i: Path("o"))]
        self.assertEqual(got, [Path("v0"), None, Path("v2")])

    def test_stopping_early_starts_nothing_more(self):
        calls = []

        def rec(url, out):
            calls.append(url)
            return Path(url)

        cands = [{"url": f"v{i}"} for i in range(10)]
        with mock.patch.object(ff, "download", rec), \
             mock.patch.object(ff, "PARALLEL", 2):
            for k, _v, _p in ff._downloads(cands, lambda i: Path("o")):
                break
        time.sleep(0.1)
        self.assertLessEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
