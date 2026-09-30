"""A published video becomes a GitHub Release asset (the Shorts Media
library reads those), best-effort, and never blocks the post."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import crosspost, release_video  # noqa: E402


class _Resp:
    def __init__(self, status, body=None, text=""):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


ENV = {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r", "GITHUB_SHA": "abc"}


class TheReleaseIsTheLibraryEntry(unittest.TestCase):
    def _mp4(self, d):
        p = Path(d) / "v.mp4"
        p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"x" * 100)
        return p

    def test_creates_the_release_and_attaches_the_file(self):
        calls = []

        def post(url, headers=None, json=None, data=None, timeout=None):
            calls.append((url, json, headers.get("Content-Type")))
            if url.endswith("/releases"):
                return _Resp(201, {"html_url": "https://github.com/o/r/releases/tag/x",
                                   "upload_url": "https://up/{?name,label}", "assets": []})
            return _Resp(201, {})

        with TemporaryDirectory() as d, mock.patch.dict(os.environ, ENV, clear=True), \
                mock.patch("requests.post", post):
            url = release_video.publish(self._mp4(d), "Cargo Ships Got Bigger",
                                        "six times #ships", "trending")
        self.assertEqual(url, "https://github.com/o/r/releases/tag/x")
        create, upload = calls
        self.assertTrue(create[1]["tag_name"].startswith("video-trending-"))
        self.assertEqual(create[1]["name"], "Cargo Ships Got Bigger")
        self.assertEqual(create[1]["body"], "six times #ships")
        self.assertEqual(create[1]["target_commitish"], "abc")
        self.assertEqual(upload[0], "https://up/?name=cargo-ships-got-bigger.mp4")
        self.assertEqual(upload[2], "video/mp4")

    def test_a_rerun_finds_the_existing_release_and_does_not_upload_twice(self):
        posts = []

        def post(url, headers=None, json=None, data=None, timeout=None):
            posts.append(url)
            return _Resp(422, text="already_exists")

        def get(url, headers=None, timeout=None):
            self.assertTrue(url.endswith("/releases/tags/" + release_video.release_tag(
                "third", "Same Clip", self.current)))
            return _Resp(200, {"html_url": "https://github.com/o/r/releases/tag/y",
                               "upload_url": "https://up/{?name}",
                               "assets": [{"name": "same-clip.mp4"}]})

        with TemporaryDirectory() as d, mock.patch.dict(os.environ, ENV, clear=True), \
                mock.patch("requests.post", post), mock.patch("requests.get", get):
            self.current = self._mp4(d)
            url = release_video.publish(self.current, "Same Clip", "", "third")
        self.assertEqual(url, "https://github.com/o/r/releases/tag/y")
        self.assertEqual(len(posts), 1, "no asset upload when it is already there")

    def test_without_a_token_it_says_so_and_does_nothing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(release_video.available(), (False, "no GITHUB_TOKEN"))


class CrosspostPublishesTheRelease(unittest.TestCase):
    def test_release_first_then_tiktok_and_a_failure_is_only_a_warning(self):
        seen = []
        with TemporaryDirectory() as d, mock.patch.dict(os.environ, ENV, clear=True), \
                mock.patch.object(release_video, "publish",
                                  side_effect=lambda *a, **k: seen.append(a) or "https://rel"), \
                mock.patch.object(crosspost, "_tiktok_ready", return_value=(False, "no token")):
            mp4 = Path(d) / "v.mp4"
            mp4.write_bytes(b"x")
            out = crosspost.crosspost("trending", mp4, "T", "D", ["a"])
        self.assertEqual(out, {"github_release": "https://rel"})
        self.assertEqual(seen[0][:4], (mp4, "T", "D", "trending"))
        with TemporaryDirectory() as d, mock.patch.dict(os.environ, ENV, clear=True), \
                mock.patch.object(release_video, "publish", side_effect=RuntimeError("boom")), \
                mock.patch.object(crosspost, "_tiktok_ready", return_value=(False, "no token")):
            mp4 = Path(d) / "v.mp4"
            mp4.write_bytes(b"x")
            self.assertEqual(crosspost.crosspost("trending", mp4, "T", "D", []), {})


if __name__ == "__main__":
    unittest.main()
