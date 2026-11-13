"""Instagram + Facebook Reels (2026-11-13, operator: "we need to sign up
for this meta auto posting. Posting on Facebook, posting on Instagram").

The old uploader POSTed a Facebook Page to `/{page}/media`, an Instagram-
only edge, so Facebook could never have worked, and both needed the file on
a public host nobody had. Now: Facebook goes through `/{page}/video_reels`
with the Page's own token, Instagram through a resumable REELS container,
and both send the BYTES to rupload.facebook.com. Which accounts a channel
posts to lives in the registry (`channels.<id>.meta`) and nothing posts
until `post` is true there AND a token exists."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import uploaders  # noqa: E402
from scripts import meta_post_release as mp  # noqa: E402


class _Resp:
    def __init__(self, body, ok=True, status=200):
        self._b, self.ok, self.status_code, self.text = body, ok, status, str(body)

    def json(self):
        return self._b


def _mp4():
    f = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    f.write(b"\x00" * 1024)
    f.close()
    return Path(f.name)


class FacebookUsesVideoReels(unittest.TestCase):
    def test_start_bytes_finish_with_page_token(self):
        calls = []

        def post(url, data=None, timeout=None, headers=None):
            calls.append((url, data if isinstance(data, dict) else "BYTES", headers))
            if url.endswith("/video_reels") and data["upload_phase"] == "start":
                return _Resp({"video_id": "V1", "upload_url": "https://rupload.facebook.com/video-upload/v21.0/V1"})
            if "rupload" in url:
                return _Resp({"success": True})
            return _Resp({"success": True})

        def get(url, params=None, timeout=None):
            return _Resp({"access_token": "PAGE_TOKEN", "id": "P1"})

        with mock.patch.dict(os.environ, {"META_ACCESS_TOKEN": "SYS"}, clear=True), \
                mock.patch("requests.post", post), mock.patch("requests.get", get):
            res = uploaders.FacebookUploader(channel="explainer", target_id="P1").upload(
                _mp4(), title="t", description="d", tags=["a"])
        self.assertEqual(res.url, "https://www.facebook.com/reel/V1/")
        urls = [c[0] for c in calls]
        self.assertTrue(urls[0].endswith("/P1/video_reels"))
        self.assertIn("rupload.facebook.com", urls[1])
        self.assertEqual(calls[1][2]["Authorization"], "OAuth PAGE_TOKEN")
        self.assertEqual(calls[2][1]["upload_phase"], "finish")
        self.assertEqual(calls[2][1]["video_state"], "PUBLISHED")
        self.assertNotIn("/media", "".join(urls))


class InstagramIsResumable(unittest.TestCase):
    def test_container_bytes_poll_publish(self):
        calls = []

        def post(url, data=None, timeout=None, headers=None):
            calls.append((url, data if isinstance(data, dict) else "BYTES"))
            if url.endswith("/IG1/media"):
                return _Resp({"id": "C1", "uri": "https://rupload.facebook.com/ig-api-upload/v21.0/C1"})
            if url.endswith("/media_publish"):
                return _Resp({"id": "M1"})
            return _Resp({"success": True})

        def get(url, params=None, timeout=None):
            if url.endswith("/C1"):
                return _Resp({"status_code": "FINISHED"})
            return _Resp({"permalink": "https://www.instagram.com/reel/abc/"})

        with mock.patch.dict(os.environ, {"META_ACCESS_TOKEN": "SYS"}, clear=True), \
                mock.patch("requests.post", post), mock.patch("requests.get", get), \
                mock.patch("time.sleep", lambda s: None):
            res = uploaders.InstagramUploader(channel="third", target_id="IG1").upload(
                _mp4(), title="t", description="d")
        self.assertEqual(res.url, "https://www.instagram.com/reel/abc/")
        self.assertEqual(calls[0][1]["upload_type"], "resumable")
        self.assertEqual(calls[0][1]["media_type"], "REELS")
        self.assertNotIn("video_url", calls[0][1])
        self.assertEqual(calls[1][1], "BYTES")
        self.assertTrue(calls[2][0].endswith("/IG1/media_publish"))


class NothingPostsUntilTheRegistrySaysSo(unittest.TestCase):
    def test_off_by_default(self):
        with mock.patch.dict(os.environ, {"META_ACCESS_TOKEN": "SYS"}, clear=True):
            for ch in ("explainer", "third", "trending"):
                self.assertEqual(mp.targets(ch), {}, ch)

    def test_on_needs_a_token_and_ids(self):
        cfg = {"post": True, "instagram_id": "IG1", "facebook_page_id": ""}
        with mock.patch.object(mp, "meta_cfg", lambda ch: cfg):
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(mp.targets("explainer"), {})
            with mock.patch.dict(os.environ, {"META_ACCESS_TOKEN": "SYS"}, clear=True):
                self.assertEqual(mp.targets("explainer"), {"instagram": "IG1"})

    def test_registry_has_the_switch_for_every_publishing_channel(self):
        for ch in ("explainer", "third", "trending"):
            self.assertIn("post", mp.meta_cfg(ch), ch)


class CrosspostNoLongerNeedsAPublicHost(unittest.TestCase):
    def test_no_reels_public_host(self):
        src = (ROOT / "shared" / "crosspost.py").read_text()
        self.assertNotIn("REELS_PUBLIC_HOST", src)
        self.assertNotIn('_env("REELS_PUBLIC_HOST")', (ROOT / "shared" / "uploaders.py").read_text())


if __name__ == "__main__":
    unittest.main()
