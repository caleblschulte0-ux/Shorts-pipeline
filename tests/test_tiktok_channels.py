"""TikTok posts only where the registry turns it on (explainer for now),
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
        self.assertFalse(crosspost.tiktok_posting_on("trending"))
        self.assertFalse(crosspost.tiktok_posting_on("third"))
        self.assertFalse(crosspost.tiktok_posting_on("no-such-channel"))

    def test_a_static_token_cannot_turn_an_off_channel_on(self):
        env = {"TIKTOK_ACCESS_TOKEN": "t", "TIKTOK_ACCESS_TOKEN_THIRD": "t",
               "TIKTOK_HANDLE_THIRD": "third.brain.down"}
        with mock.patch.dict(os.environ, env, clear=True):
            for ch in ("third", "trending"):
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


if __name__ == "__main__":
    unittest.main()
