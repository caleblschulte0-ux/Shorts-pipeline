"""The TikTok link has to actually link, and the pipeline has to actually
fetch the token it links.

Three builds of the Shorts Media site (shorts-media.netlify.app) failed to
connect a single account. The last one stored accounts in Netlify Blobs from
a Lambda-compat function without calling connectLambda(event) and with
strong-consistency reads that such a function cannot make, so every OAuth
callback died on "The environment has not been configured to use Netlify
Blobs". Nothing in the pipeline asked the site for a token either — the
uploader only read a static TIKTOK_ACCESS_TOKEN that expires in 24 hours.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import uploaders  # noqa: E402

APP_JS = ROOT / "tiktok_app" / "netlify" / "functions" / "app.js"


class TheSiteLinksAnAccount(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_offline_end_to_end(self):
        r = subprocess.run(["node", str(ROOT / "tiktok_app" / "test_site.js")],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("FAIL", r.stdout)
        self.assertIn("callback stores the account", r.stdout)
        self.assertIn("broker hands main a fresh access token", r.stdout)

    def test_blobs_is_connected_and_never_read_strong(self):
        src = APP_JS.read_text(encoding="utf-8")
        self.assertIn("accounts.connect(event);", src)
        self.assertIn("connectLambda(event);", src)
        self.assertNotIn('getStore({ name: STORE_NAME, consistency: "strong" })', src)

    def test_the_confirmation_states_the_privacy_actually_chosen(self):
        # It said "visible only to you (Only me)" after every post, public
        # ones included — false the day the audit passes.
        src = APP_JS.read_text(encoding="utf-8")
        self.assertNotIn("<p>Your video is on your TikTok profile, visible only to you", src)
        self.assertIn('"&p=" + encodeURIComponent(privacy)', src)
        self.assertIn('PUBLIC_TO_EVERYONE: "visible to everyone"', src)

    def test_no_secret_is_committed(self):
        # This repo is public. The function carries placeholders only.
        src = APP_JS.read_text(encoding="utf-8")
        m = re.search(r"var CONFIG = \{(.*?)\};", src, re.S)
        self.assertIsNotNone(m)
        for mark in ("__TIKTOK_CLIENT_KEY__", "__TIKTOK_CLIENT_SECRET__",
                     "__SM_COOKIE_SECRET__"):
            self.assertIn(mark, m.group(1))


class TheDropBuilds(unittest.TestCase):
    def test_public_layout_base_becomes_root_layout_with_secrets(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_tiktok_drop as b
        with TemporaryDirectory() as d:
            base = Path(d) / "base.zip"
            with zipfile.ZipFile(base, "w") as z:
                z.writestr("public/index.html", "<h1>hi</h1>")
                z.writestr("public/privacy-policy/index.html", "p")
                z.writestr("netlify/functions/app.js", "old")
                z.writestr("netlify.toml", "old")
            out = b.build(base, {"client_key": "k", "client_secret": "s",
                                 "cookie_secret": "c"}, Path(d) / "o.zip")
            with zipfile.ZipFile(out) as z:
                names = set(z.namelist())
                fn = z.read("netlify/functions/app.js").decode()
            self.assertIn("index.html", names)
            self.assertIn("privacy-policy/index.html", names)
            self.assertIn('"s"', fn)
            self.assertNotIn("__TIKTOK_CLIENT_SECRET__", fn)
            self.assertNotIn("old", fn[:50])

    def test_missing_secret_refuses(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_tiktok_drop as b
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                b.fill(APP_JS.read_text(encoding="utf-8"), {"client_key": "k"})


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body
        self.ok = 200 <= status < 300
        self.text = json.dumps(body)

    def json(self):
        return self._body


OIDC_ENV = {"ACTIONS_ID_TOKEN_REQUEST_URL": "https://gh/oidc?x=1",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "req"}


class TheUploaderFetchesItsOwnToken(unittest.TestCase):
    def _run(self, env, accounts, channel="third"):
        calls = []

        def get(url, params=None, headers=None, timeout=None):
            calls.append(("GET", url, params))
            if url.startswith("https://gh/oidc"):
                self.assertEqual(params["audience"], uploaders.TIKTOK_BROKER)
                return _Resp(200, {"value": "jwt"})
            self.assertEqual(headers["Authorization"], "Bearer jwt")
            return _Resp(200, {"accounts": accounts})

        def post(url, headers=None, json=None, timeout=None):
            calls.append(("POST", url, json))
            self.assertEqual(headers["Authorization"], "Bearer jwt")
            return _Resp(200, {"access_token": "fresh"})

        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("requests.get", get), mock.patch("requests.post", post):
            tok = uploaders.TikTokUploader(channel=channel)._token()
        return tok, calls

    def test_single_linked_account_needs_no_config(self):
        tok, calls = self._run(OIDC_ENV, [{"open_id": "o1", "handle": "a"}])
        self.assertEqual(tok, "fresh")
        self.assertEqual(calls[-1][2], {"open_id": "o1"})

    def test_channel_handle_picks_the_account(self):
        tok, calls = self._run({**OIDC_ENV, "TIKTOK_HANDLE_THIRD": "@thirdbraindown"}, [])
        self.assertEqual(calls[-1][2], {"handle": "thirdbraindown"})
        self.assertFalse(any(c[1].endswith("/accounts") for c in calls))

    def test_two_linked_accounts_and_no_handle_refuses_to_guess(self):
        with self.assertRaises(uploaders.UploadError) as e:
            self._run(OIDC_ENV, [{"open_id": "1", "handle": "a"},
                                 {"open_id": "2", "handle": "b"}])
        self.assertIn("TIKTOK_HANDLE_THIRD", str(e.exception))

    def test_static_token_still_wins(self):
        with mock.patch.dict(os.environ, {**OIDC_ENV, "TIKTOK_ACCESS_TOKEN_THIRD": "s"},
                             clear=True):
            self.assertEqual(uploaders.TikTokUploader(channel="third")._token(), "s")

    def test_no_token_and_no_oidc_says_how(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(uploaders.UploadError) as e:
                uploaders.TikTokUploader(channel="third")._token()
        self.assertIn("id-token: write", str(e.exception))


class TheThirdWorkflowCanAsk(unittest.TestCase):
    def test_third_yml_grants_oidc_and_names_the_handle(self):
        wf = (ROOT / ".github" / "workflows" / "third.yml").read_text()
        self.assertRegex(wf, r"(?m)^permissions:\n(?:  .*\n)*?  id-token: write")
        self.assertIn("TIKTOK_HANDLE_THIRD: ${{ vars.TIKTOK_HANDLE_THIRD }}", wf)

    def test_every_publishing_channel_crossposts_through_the_shared_copy(self):
        for f, ch in [("run_third.py", "third"), ("run_trending_daily.py", "trending"),
                      ("post_stories.py", None), ("claim_reviews.py", "explainer")]:
            src = (ROOT / "scripts" / f).read_text()
            self.assertIn("from shared.crosspost import crosspost", src, f)
            if ch:
                self.assertIn(f'crosspost("{ch}"', src, f)
        for wf in ("third", "daily", "explainer", "claim_reviews", "tiktok_accounts"):
            text = (ROOT / ".github" / "workflows" / f"{wf}.yml").read_text()
            self.assertRegex(text, r"(?m)^permissions:\n(?:  .*\n)*?  id-token: write", wf)


class CrossPostGoesToTheChannelsOwnAccount(unittest.TestCase):
    def _run(self, env, handle_in_registry=""):
        from shared import crosspost as cp
        calls = []

        class FakeTT:
            def __init__(self, channel=""):
                self.channel = channel

            def upload(self, **kw):
                calls.append(self.channel)
                return uploaders.UploadResult("tiktok", "https://t/1")

        reg = {"tiktok": {"handle": handle_in_registry}}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("shared.uploaders.TikTokUploader", FakeTT), \
                mock.patch("shared.channel_registry.channel", lambda c: reg):
            out = cp.crosspost("trending", Path("v.mp4"), "t", "d", [])
        return out, calls

    def test_no_handle_means_no_tiktok_post(self):
        out, calls = self._run(OIDC_ENV)
        self.assertEqual(calls, [])
        self.assertEqual(out, {})

    def test_registry_handle_posts_as_that_channel(self):
        out, calls = self._run(OIDC_ENV, "ballerbro")
        self.assertEqual(calls, ["trending"])
        self.assertEqual(out, {"tiktok": "https://t/1"})

    def test_env_handle_overrides_registry(self):
        from shared import crosspost as cp
        with mock.patch.dict(os.environ, {"TIKTOK_HANDLE_TRENDING": "@x"}, clear=True):
            self.assertEqual(cp.tiktok_handle("trending"), "x")

    def test_every_publishing_channel_has_a_tiktok_slot_in_the_registry(self):
        reg = json.loads((ROOT / "config" / "channel_registry.json").read_text())
        for cid in ("trending", "explainer", "third"):
            self.assertIn("handle", reg["channels"][cid].get("tiktok", {}), cid)


class UnauditedPostsPrivatelyAndSaysSo(unittest.TestCase):
    def test_unaudited_refusal_retries_as_only_me(self):
        inits = []

        def post(url, headers=None, json=None, timeout=None):
            if url == uploaders.CREATOR_INFO_URL:
                return _Resp(200, {"data": {"privacy_level_options": [
                    "PUBLIC_TO_EVERYONE", "SELF_ONLY"]}})
            inits.append(json["post_info"]["privacy_level"])
            if json["post_info"]["privacy_level"] != "SELF_ONLY":
                return _Resp(403, {"error": {"code":
                    "unaudited_client_can_only_post_to_private_accounts"}})
            return _Resp(200, {"data": {"upload_url": "https://u", "publish_id": "p1"}})

        with TemporaryDirectory() as d:
            f = Path(d) / "v.mp4"
            f.write_bytes(b"x" * 10)
            with mock.patch.dict(os.environ, {"TIKTOK_ACCESS_TOKEN": "t"}, clear=True), \
                    mock.patch("requests.post", post), \
                    mock.patch("requests.put", lambda *a, **k: _Resp(201, {})):
                res = uploaders.TikTokUploader().upload(f, title="t", description="d")
        self.assertEqual(inits, ["PUBLIC_TO_EVERYONE", "SELF_ONLY"])
        self.assertEqual(res.raw["publish_id"], "p1")


class TheAuditProbePublishesNothing(unittest.TestCase):
    def _probe(self, init_status, init_body):
        sys.path.insert(0, str(ROOT / "scripts"))
        import tiktok_audit_probe as tp
        calls = []

        def post(url, headers=None, json=None, timeout=None):
            calls.append(url)
            if url == uploaders.CREATOR_INFO_URL:
                return _Resp(200, {"data": {"privacy_level_options": ["SELF_ONLY"]}})
            return _Resp(init_status, init_body)

        def put(*a, **k):
            raise AssertionError("the probe must never send video bytes")

        with mock.patch("requests.post", post), mock.patch("requests.put", put):
            return tp.probe("tok"), calls

    def test_accepted_public_init_means_audited(self):
        (verdict, _), calls = self._probe(200, {"data": {"publish_id": "p", "upload_url": "u"}})
        self.assertEqual(verdict, "audited")

    def test_unaudited_refusal_is_read_as_unaudited(self):
        (verdict, _), _ = self._probe(403, {"error": {"code":
            "unaudited_client_can_only_post_to_private_accounts"}})
        self.assertEqual(verdict, "unaudited")

    def test_it_never_calls_upload(self):
        src = (ROOT / "scripts" / "tiktok_audit_probe.py").read_text()
        self.assertNotRegex(src, r"\.upload\s*\(")


if __name__ == "__main__":
    unittest.main()
