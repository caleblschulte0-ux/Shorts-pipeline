"""TikTok posts only where the registry turns it on (explainer and third),
and the uploader asks the site for the registry's handle, so a channel
needs no TIKTOK_HANDLE_<CHANNEL> repo variable to post."""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import crosspost, uploaders  # noqa: E402


class OnlyTheExplainerPostsToTikTok(unittest.TestCase):
    def test_registry_switches(self):
        self.assertTrue(crosspost.tiktok_posting_on("explainer"))
        self.assertTrue(crosspost.tiktok_posting_on("third"))
        self.assertFalse(crosspost.tiktok_posting_on("trending"))
        self.assertFalse(crosspost.tiktok_posting_on("no-such-channel"))

    def test_a_static_token_cannot_turn_an_off_channel_on(self):
        env = {"TIKTOK_ACCESS_TOKEN": "t", "TIKTOK_ACCESS_TOKEN_THIRD": "t",
               "TIKTOK_HANDLE_THIRD": "third.brain.down"}
        env = {"TIKTOK_ACCESS_TOKEN": "t", "TIKTOK_ACCESS_TOKEN_TRENDING": "t",
               "TIKTOK_HANDLE_TRENDING": "ballerbro2.1"}
        with mock.patch.dict(os.environ, env, clear=True):
            for ch in ("trending",):
                ready, why = crosspost._tiktok_ready(ch)
                self.assertFalse(ready)
                self.assertIn("off", why)
            self.assertEqual(crosspost._tiktok_ready("explainer"), (True, ""))


class TheUploaderUsesTheRegistryHandle(unittest.TestCase):
    def test_broker_is_asked_for_the_registry_handle(self):
        asked = []

        class R:
            ok = True
            status_code = 200
            def json(self):
                return {"access_token": "fresh"}

        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(uploaders, "_tiktok_broker_auth", return_value={}), \
                mock.patch.object(uploaders, "tiktok_linked_accounts",
                                  side_effect=AssertionError("should not guess")), \
                mock.patch("requests.post",
                           side_effect=lambda url, **k: asked.append(k["json"]) or R()):
            self.assertEqual(uploaders._tiktok_broker_token("explainer"), "fresh")
        self.assertEqual(asked, [{"handle": "shortexplainer1"}])


class APostedVideoCanBeSentByHand(unittest.TestCase):
    def test_only_a_posted_video_of_a_tiktok_channel(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import tiktok_post_release as t
        self.assertEqual(t.channel_of("video-explainer-20261008-x-1"), "explainer")
        with self.assertRaises(SystemExit):
            t.channel_of("v1.0")
        self.assertFalse(t.passed_the_gate("explainer", "never posted"))
        import json
        log = json.loads((ROOT / t.POSTED_LOGS["explainer"]).read_text())
        posted = [u["title"] for u in log["uploads"] if u.get("state") == "posted"]
        self.assertTrue(t.passed_the_gate("explainer", posted[-1]))


class TikTokFollowsTheYouTubeSlot(unittest.TestCase):
    def _run(self, publish_at):
        from shared import release_video
        calls = []

        class FakeTT:
            def __init__(self, channel=""):
                pass

            def upload(self, **kw):
                calls.append(kw)
                return uploaders.UploadResult("tiktok", "https://t/1", {"publish_id": "p"})

        with mock.patch.object(release_video, "available", return_value=(True, "")), \
                mock.patch.object(release_video, "publish",
                                  return_value="https://g/releases/tag/video-explainer-x"), \
                mock.patch.object(release_video, "attach_json",
                                  side_effect=lambda *a: calls.append(a)), \
                mock.patch.object(crosspost, "_tiktok_ready", return_value=(True, "")), \
                mock.patch("shared.uploaders.TikTokUploader", FakeTT):
            out = crosspost.crosspost("explainer", Path("v.mp4"), "t", "d", [],
                                      publish_at=publish_at)
        return out, calls

    def test_a_future_slot_is_queued_not_posted(self):
        out, calls = self._run("2999-01-01T00:00:00Z")
        self.assertEqual(calls, [])
        self.assertTrue(out["tiktok"].startswith("queued"))

    def test_now_posts_and_marks_the_release(self):
        out, calls = self._run(None)
        self.assertEqual(out["tiktok"], "https://t/1")
        self.assertEqual(calls[-1][0], "video-explainer-x")
        self.assertEqual(calls[-1][1], "tiktok.json")

    def test_due_is_the_slot_and_never_history(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import tiktok_post_release as t
        from datetime import datetime, timezone
        now = datetime(2026, 10, 9, 3, 40, tzinfo=timezone.utc)
        self.assertTrue(t.is_due({"publish_at": "2026-10-09T03:30:00Z"}, now))
        self.assertFalse(t.is_due({"publish_at": "2026-10-09T05:30:00Z"}, now))
        self.assertFalse(t.is_due({"publish_at": "2026-10-08T20:14:17Z"}, now))

    def test_third_log_shape_is_read(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import json
        import tiktok_post_release as t
        log = json.loads((ROOT / t.POSTED_LOGS["third"]).read_text())
        title = list(log["posted"].values())[-1]["title"]
        self.assertTrue(t.passed_the_gate("third", title))


class FiveHashtags(unittest.TestCase):
    def test_caption_keeps_the_first_five(self):
        cap = uploaders.cap_hashtags(
            "Title\n\nsee https://x.com/p#frag\n\n#a #b #c #a #d #e #f #g")
        self.assertEqual(cap, "Title\n\nsee https://x.com/p#frag\n\n#a #b #c #d #e")


if __name__ == "__main__":
    unittest.main()
