"""`shared/uploaders.py` — the module that actually talks to YouTube.

Audit finding G: this was the highest-value untested module in the repo. It
is the last thing that runs before a video becomes public, it holds the
guard that stops the pipeline posting to the WRONG CHANNEL, and it is where
a title/description/tag limit is enforced for real. Everything upstream can
be perfect and still ship garbage if this file is wrong.

None of these tests touch the network. The Google client is a stub; what is
under test is the logic this repo owns — secret resolution, the channel
guard, request-body assembly, and the best-effort paths that must never lose
an already-uploaded video.

    python -m unittest tests.test_uploaders -v
"""
from __future__ import annotations

import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from shared import uploaders as up                      # noqa: E402


# --------------------------------------------------------------------------
# A stub Google API client. Records what the uploader asked it to do.
# --------------------------------------------------------------------------
class FakeRequest:
    def __init__(self, recorder, key, payload, chunks=1):
        self.recorder, self.key, self.payload = recorder, key, payload
        self._chunks = chunks

    def next_chunk(self):
        self._chunks -= 1
        if self._chunks > 0:
            return (None, None)              # still uploading
        self.recorder[self.key] = self.payload
        return (None, {"id": "VID123"})

    def execute(self):
        self.recorder[self.key] = self.payload
        return {"id": "VID123"}


class FakeVideos:
    def __init__(self, rec, chunks=1):
        self.rec, self.chunks = rec, chunks

    def insert(self, *, part, body, media_body):
        return FakeRequest(self.rec, "insert",
                           {"part": part, "body": body}, self.chunks)


class FakeFailing:
    def __init__(self, exc):
        self.exc = exc

    def set(self, **kw):
        raise self.exc

    def insert(self, **kw):
        raise self.exc


class FakeService:
    def __init__(self, rec, chunks=1, thumb_exc=None, cap_exc=None):
        self.rec, self.chunks = rec, chunks
        self.thumb_exc, self.cap_exc = thumb_exc, cap_exc

    def videos(self):
        return FakeVideos(self.rec, self.chunks)

    def thumbnails(self):
        if self.thumb_exc:
            return FakeFailing(self.thumb_exc)
        return FakeRequest(self.rec, "thumbnail", True)

    def captions(self):
        if self.cap_exc:
            return FakeFailing(self.cap_exc)
        return FakeRequest(self.rec, "captions", True)


def install_google_stub():
    """Stand in for googleapiclient.http.MediaFileUpload."""
    mod = types.ModuleType("googleapiclient")
    http = types.ModuleType("googleapiclient.http")

    class MediaFileUpload:
        def __init__(self, path, **kw):
            self.path, self.kw = path, kw

    http.MediaFileUpload = MediaFileUpload
    mod.http = http
    return {"googleapiclient": mod, "googleapiclient.http": http}


class UploadCase(unittest.TestCase):
    """A YouTubeUploader wired to a stub service."""

    def setUp(self):
        self.rec: dict = {}
        self.up = up.YouTubeUploader.__new__(up.YouTubeUploader)
        self.up.channel = ""
        self.svc = FakeService(self.rec)
        self.up._service = lambda: self.svc
        self.up._guard_channel = lambda svc: None
        self.tmp = Path(os.environ.get("TMPDIR", "/tmp")) / "ul_test.mp4"
        self.tmp.write_bytes(b"\x00")
        self._mods = install_google_stub()
        self._patch = mock.patch.dict(sys.modules, self._mods)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.tmp.unlink(missing_ok=True)

    def do(self, **kw):
        kw.setdefault("title", "t")
        kw.setdefault("description", "d")
        kw.setdefault("localizations", {})     # don't reach for the translator
        return self.up.upload(self.tmp, **kw)

    def body(self):
        return self.rec["insert"]["body"]


# --------------------------------------------------------------------------
class TestSecretHygiene(unittest.TestCase):
    """Credentials arrive by phone paste. They arrive dirty."""

    def test_it_strips_the_junk_a_phone_paste_adds(self):
        got = up._clean_secret_strings(
            {"token": "  <abc123>\n", "nested": ["'x' ", {"k": '"y"'}]})
        self.assertEqual(got["token"], "abc123")
        self.assertEqual(got["nested"][0], "x")
        self.assertEqual(got["nested"][1]["k"], "y")

    def test_it_leaves_non_strings_alone(self):
        got = up._clean_secret_strings({"n": 5, "b": True, "z": None})
        self.assertEqual(got, {"n": 5, "b": True, "z": None})

    def test_inline_json_wins_over_a_file_path(self):
        with mock.patch.dict(os.environ, {"X_JSON": '{"a": " b "}',
                                          "X_PATH": "/nope/never"},
                             clear=False):
            p = up._resolve_secret("X_PATH", "X_JSON", "t_inline.json")
        self.assertEqual(json.loads(p.read_text())["a"], "b",
                         "inline secrets must be cleaned on the way to disk")

    def test_it_falls_back_to_a_path_when_there_is_no_inline_value(self):
        env = {k: v for k, v in os.environ.items() if k != "X_JSON"}
        env["X_PATH"] = "/some/creds.json"
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(str(up._resolve_secret("X_PATH", "X_JSON", "t.json")),
                             "/some/creds.json")

    def test_unparseable_json_is_still_written_rather_than_dropped(self):
        """A malformed secret should fail at auth with a real error, not
        vanish here and look like 'missing env var'."""
        with mock.patch.dict(os.environ, {"X_JSON": "{not json"}, clear=False):
            p = up._resolve_secret("X_PATH", "X_JSON", "t_bad.json")
        self.assertEqual(p.read_text(), "{not json")

    def test_missing_everything_names_both_variables(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("X_JSON", "X_PATH")}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(up.UploadError) as ctx:
                up._resolve_secret("X_PATH", "X_JSON", "t.json")
        self.assertIn("X_JSON", str(ctx.exception))
        self.assertIn("X_PATH", str(ctx.exception))

    def test_env_raises_an_UploadError_not_a_KeyError(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(up.UploadError):
                up._env("DEFINITELY_NOT_SET")


class TestTheWrongChannelGuard(unittest.TestCase):
    """The one guard standing between this repo and posting to the wrong
    account. There is no undo for a public upload."""

    def _uploader(self, title="My Channel", cid="UC123", handle="@mych"):
        u = up.YouTubeUploader.__new__(up.YouTubeUploader)
        u.whoami = lambda svc=None: {"id": cid, "title": title,
                                     "handle": handle}
        return u

    def test_a_mismatch_REFUSES_the_upload(self):
        u = self._uploader()
        with mock.patch.dict(os.environ,
                             {"YOUTUBE_EXPECTED_CHANNEL": "Some Other"}):
            with self.assertRaises(up.UploadError) as ctx:
                u._guard_channel(None)
        self.assertIn("refusing to upload", str(ctx.exception))

    def test_it_matches_on_title_id_or_handle(self):
        u = self._uploader()
        for expected in ("My Channel", "my channel", "UC123", "@mych", "mych"):
            with mock.patch.dict(os.environ,
                                 {"YOUTUBE_EXPECTED_CHANNEL": expected}):
                u._guard_channel(None)          # must not raise

    def test_unset_is_a_no_op(self):
        env = {k: v for k, v in os.environ.items()
               if k != "YOUTUBE_EXPECTED_CHANNEL"}
        with mock.patch.dict(os.environ, env, clear=True):
            self._uploader()._guard_channel(None)

    def test_the_guard_runs_BEFORE_the_video_is_sent(self):
        """Order matters: a guard that fires after insert() has already
        published the video to the wrong channel is decoration."""
        src = (ROOT / "shared" / "uploaders.py").read_text()
        fn = src.split("def upload(self, file_path", 1)[1]
        self.assertLess(fn.index("_guard_channel"), fn.index("videos().insert"),
                        "the channel guard must run before the insert")


class TestTheRequestBody(UploadCase):
    """What YouTube is actually told. Every limit here is a real API limit."""

    def test_scheduled_uploads_go_up_private(self):
        self.do(publish_at="2026-08-02T13:00:00Z")
        st = self.body()["status"]
        self.assertEqual(st["privacyStatus"], "private")
        self.assertEqual(st["publishAt"], "2026-08-02T13:00:00Z")

    def test_unscheduled_uploads_go_up_public(self):
        self.do()
        self.assertEqual(self.body()["status"]["privacyStatus"], "public")
        self.assertNotIn("publishAt", self.body()["status"])

    def test_synthetic_media_is_declared(self):
        """This channel uses synthetic voiceover and AI imagery. Not
        declaring it is a policy problem, not a style choice."""
        self.do()
        self.assertIs(self.body()["status"]["containsSyntheticMedia"], True)

    def test_not_made_for_kids(self):
        self.do()
        self.assertIs(self.body()["status"]["selfDeclaredMadeForKids"], False)

    def test_title_is_truncated_to_100(self):
        self.do(title="x" * 250)
        self.assertEqual(len(self.body()["snippet"]["title"]), 100)

    def test_description_is_truncated_to_5000(self):
        self.do(description="y" * 9000)
        self.assertEqual(len(self.body()["snippet"]["description"]), 5000)

    def test_tags_are_capped_at_30(self):
        self.do(tags=[f"t{i}" for i in range(80)])
        self.assertEqual(len(self.body()["snippet"]["tags"]), 30)

    def test_no_tags_is_an_empty_list_not_a_crash(self):
        self.do(tags=None)
        self.assertEqual(self.body()["snippet"]["tags"], [])

    def test_audio_language_defaults_to_the_snippet_language(self):
        self.do(default_language="en")
        sn = self.body()["snippet"]
        self.assertEqual(sn["defaultLanguage"], "en")
        self.assertEqual(sn["defaultAudioLanguage"], "en")

    def test_audio_language_can_differ(self):
        self.do(default_language="en", audio_language="es")
        self.assertEqual(self.body()["snippet"]["defaultAudioLanguage"], "es")

    def test_localizations_switch_on_the_localizations_part(self):
        self.do(localizations={"es": {"title": "T", "description": "D"}})
        self.assertIn("localizations", self.rec["insert"]["part"])
        self.assertEqual(self.body()["localizations"]["es"]["title"], "T")

    def test_no_localizations_leaves_the_part_alone(self):
        self.do(localizations={})
        self.assertEqual(self.rec["insert"]["part"], "snippet,status")
        self.assertNotIn("localizations", self.body())

    def test_localized_strings_are_truncated_too(self):
        self.do(localizations={"es": {"title": "t" * 300,
                                      "description": "d" * 9000}})
        loc = self.body()["localizations"]["es"]
        self.assertEqual(len(loc["title"]), 100)
        self.assertEqual(len(loc["description"]), 5000)

    def test_a_translator_failure_never_blocks_the_upload(self):
        """Auto-localize is a reach-and-hope. It must degrade to English."""
        bad = types.ModuleType("shared.localize")
        bad.translate_metadata = mock.Mock(side_effect=RuntimeError("no key"))
        with mock.patch.dict(sys.modules, {"shared.localize": bad}):
            res = self.up.upload(self.tmp, title="t", description="d")
        self.assertEqual(res.url, "https://youtube.com/shorts/VID123")

    def test_the_returned_url_is_a_shorts_url(self):
        self.assertEqual(self.do().url, "https://youtube.com/shorts/VID123")

    def test_a_resumable_upload_runs_to_completion(self):
        self.up._service = lambda: FakeService(self.rec, chunks=4)
        self.assertEqual(self.do().url, "https://youtube.com/shorts/VID123")


class TestNothingLosesAnUploadedVideo(UploadCase):
    """Once insert() returns, the video EXISTS. Every step after it is
    decoration and must never raise."""

    def test_a_thumbnail_403_does_not_lose_the_video(self):
        self.up._service = lambda: FakeService(
            self.rec, thumb_exc=RuntimeError("403 not eligible"))
        thumb = self.tmp.with_suffix(".jpg")
        thumb.write_bytes(b"\xff")
        try:
            res = self.do(thumbnail=str(thumb))
        finally:
            thumb.unlink(missing_ok=True)
        self.assertEqual(res.url, "https://youtube.com/shorts/VID123")

    def test_a_captions_403_does_not_lose_the_video(self):
        self.up._service = lambda: FakeService(
            self.rec, cap_exc=RuntimeError("403 needs force-ssl"))
        srt = self.tmp.with_suffix(".srt")
        srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n")
        try:
            res = self.do(captions_srt=str(srt))
        finally:
            srt.unlink(missing_ok=True)
        self.assertEqual(res.url, "https://youtube.com/shorts/VID123")

    def test_a_missing_thumbnail_file_is_simply_skipped(self):
        res = self.do(thumbnail="/definitely/not/here.jpg")
        self.assertEqual(res.url, "https://youtube.com/shorts/VID123")
        self.assertNotIn("thumbnail", self.rec)

    def test_a_missing_caption_file_is_simply_skipped(self):
        self.do(captions_srt="/definitely/not/here.srt")
        self.assertNotIn("captions", self.rec)


class TestUploadToIsBatchSafe(unittest.TestCase):
    """One dead platform must not take the others down with it."""

    def test_an_unknown_target_is_skipped_not_fatal(self):
        self.assertEqual(up.upload_to(["not_a_platform"], Path("/x.mp4"),
                                      title="t", description="d"), [])

    def test_blank_targets_are_ignored(self):
        self.assertEqual(up.upload_to(["", "  "], Path("/x.mp4"),
                                      title="t", description="d"), [])

    def test_one_failure_does_not_abort_the_batch(self):
        ok = mock.Mock()
        ok.return_value.upload.return_value = up.UploadResult(
            "good", "https://example/1", {})
        bad = mock.Mock()
        bad.return_value.upload.side_effect = up.UploadError("nope")
        with mock.patch.dict(up.REGISTRY, {"bad": bad, "good": ok},
                             clear=False):
            res = up.upload_to(["bad", "good"], Path("/x.mp4"),
                               title="t", description="d")
        self.assertEqual([r.platform for r in res], ["good"])

    def test_an_unexpected_crash_is_contained_too(self):
        boom = mock.Mock()
        boom.return_value.upload.side_effect = ValueError("surprise")
        ok = mock.Mock()
        ok.return_value.upload.return_value = up.UploadResult(
            "good", "https://example/1", {})
        with mock.patch.dict(up.REGISTRY, {"boom": boom, "good": ok},
                             clear=False):
            res = up.upload_to(["boom", "good"], Path("/x.mp4"),
                               title="t", description="d")
        self.assertEqual([r.platform for r in res], ["good"])


if __name__ == "__main__":
    unittest.main()
