"""THE EXPLAINER'S NARRATOR IS A GEMINI VOICE, DIRECTED LIKE A PERSON.

caaleb, 2026-10-16, after fourteen voice-lab rounds of clones that sounded
"robotic" and did not "talk like a normal person": of six Google Gemini
voices reading a spoken script under a director's note, "I like these
voices." What these tests hold:

  * Gemini voices the narration FIRST, and Chatterbox is still ahead of
    anything paid; a video it cannot voice whole goes to the next engine;
  * the direction sits ABOVE a `#### TRANSCRIPT` heading (a prose note was
    read aloud in the lab), and the line is the only thing after it;
  * a per-day 429 turns that model off and the next one is tried; a
    per-minute 429 waits the delay Google names;
  * every line is LISTENED to, and one that will not come out right is a
    fallback, never a shipped ad-lib;
  * a line it voiced is never asked for again (the free quota is daily);
  * the voice is ONE setting, and an unknown one resolves to the default.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import gemini_voice as gv  # noqa: E402

PCM = b"\x01\x00" * 24000 * 2          # two seconds


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok(req, timeout=None):
    return _Resp(json.dumps({"candidates": [{"content": {"parts": [
        {"inlineData": {"data": base64.b64encode(PCM).decode()}}]}}]}).encode())


def _http(code, body):
    return urllib.error.HTTPError("u", code, "x", {}, io.BytesIO(body.encode()))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        gv._DEAD.clear()
        self.env = mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"})
        self.env.start()
        self.trim = mock.patch.object(gv, "_trim", lambda w: None)
        self.trim.start()

    def tearDown(self):
        self.env.stop(); self.trim.stop()
        gv._DEAD.clear()


class TheDirectionIsNotReadAloud(Base):
    def test_the_line_is_all_that_follows_the_transcript_heading(self):
        sent = {}

        def cap(req, timeout=None):
            sent.update(json.loads(req.data))
            return _ok(req)
        with mock.patch("urllib.request.urlopen", cap):
            ok, _ = gv.voice_line("Sand is running out.", self.tmp / "a.wav")
        self.assertTrue(ok)
        text = sent["contents"][0]["parts"][0]["text"]
        head, said = text.split("#### TRANSCRIPT\n")
        self.assertEqual(said, "Sand is running out.")
        self.assertIn("DIRECTOR'S NOTES", head)
        cfg = sent["generationConfig"]
        self.assertEqual(cfg["responseModalities"], ["AUDIO"])
        self.assertEqual(cfg["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]
                         ["voiceName"], gv.DEFAULT_VOICE)


class TheQuotaIsRespected(Base):
    def test_a_per_day_429_turns_the_model_off_and_tries_the_next(self):
        used = []

        def f(req, timeout=None):
            used.append(req.full_url.split("/")[-1].split(":")[0])
            if len(used) == 1:
                raise _http(429, '{"quotaId": "GenerateRequestsPerDayPerProject"}')
            return _ok(req)
        with mock.patch("urllib.request.urlopen", f), mock.patch("time.sleep"):
            ok, model = gv.voice_line("hi there", self.tmp / "a.wav")
        self.assertTrue(ok)
        self.assertEqual(used, list(gv.MODELS[:2]))
        self.assertIn(gv.MODELS[0], gv._DEAD)
        self.assertEqual(model, gv.MODELS[1])

    def test_a_per_minute_429_waits_the_named_delay(self):
        n = {"i": 0}
        slept = []

        def f(req, timeout=None):
            n["i"] += 1
            if n["i"] == 1:
                raise _http(429, '{"quotaId": "PerMinute", "retryDelay": "12s"}')
            return _ok(req)
        with mock.patch("urllib.request.urlopen", f), \
                mock.patch("time.sleep", slept.append):
            ok, model = gv.voice_line("hi there", self.tmp / "a.wav")
        self.assertTrue(ok)
        self.assertEqual(slept, [12.0])
        self.assertEqual(model, gv.MODELS[0])
        self.assertFalse(gv._DEAD)

    def test_every_model_off_means_not_available(self):
        for m in gv.MODELS:
            gv._DEAD[m] = "quota"
        self.assertFalse(gv.available())


class EveryLineIsListenedTo(Base):
    def test_a_line_that_ad_libs_twice_is_a_fallback(self):
        with mock.patch("urllib.request.urlopen", _ok), \
                mock.patch("engines.chatterbox_tts.heard",
                           lambda w, t, n=None: (False, "said 'uh'")):
            self.assertIsNone(gv.maybe_voice(["one two"], [self.tmp / "a.wav"]))
        self.assertIn("would not come out right", gv.LAST_FAILURE)

    def test_a_redraw_that_comes_out_right_is_kept(self):
        seen = []

        def heard(w, t, n=None):
            seen.append(t)
            return len(seen) > 1, "mumbled"
        with mock.patch("urllib.request.urlopen", _ok), \
                mock.patch("engines.chatterbox_tts.heard", heard):
            out = gv.maybe_voice(["one two"], [self.tmp / "a.wav"])
        self.assertEqual(out, [self.tmp / "a.wav"])

    def test_no_key_is_none_never_a_raise(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            self.assertIsNone(gv.maybe_voice(["a"], [self.tmp / "a.wav"]))
        with mock.patch("urllib.request.urlopen", side_effect=RuntimeError("x")), \
                mock.patch("time.sleep"):
            self.assertIsNone(gv.maybe_voice(["a"], [self.tmp / "a.wav"]))


class ALineIsVoicedOnce(Base):
    def test_the_renderer_reuses_a_cached_line(self):
        from data_learning import studio_render as R
        calls = {"n": 0}

        def voice(texts, outs, normalize=None):
            calls["n"] += len(texts)
            for o in outs:
                gv._write(PCM, Path(o))
            return outs
        env = {"TTS_CACHE_DIR": str(self.tmp / "cache")}
        with mock.patch.object(gv, "maybe_voice", voice), \
                mock.patch.dict(os.environ, env):
            self.assertIsNotNone(R._gemini_lines(["a line", "b line"], self.tmp))
            self.assertIsNotNone(R._gemini_lines(["a line", "c line"], self.tmp))
        self.assertEqual(calls["n"], 3)
        self.assertEqual(R.TTS_USED["voice"], f"gemini {gv.DEFAULT_VOICE}")

    def test_a_failure_is_recorded_for_the_posted_log(self):
        from data_learning import studio_render as R
        gv.LAST_FAILURE = None

        def voice(texts, outs, normalize=None):
            gv.LAST_FAILURE = "line 0: quota"
            return None
        with mock.patch.object(gv, "maybe_voice", voice):
            self.assertIsNone(R._gemini_lines(["a"], self.tmp))
        self.assertEqual(R.TTS_USED["why_not_gemini"], "line 0: quota")
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        self.assertIn('facts["tts_why_not_gemini"]', src)


class OneVoiceOneSetting(unittest.TestCase):
    def test_the_setting_picks_a_known_voice_or_the_default(self):
        with mock.patch.dict(os.environ, {"GEMINI_TTS_VOICE": "orus"}):
            self.assertEqual(gv.voice(), "Orus")
        with mock.patch.dict(os.environ, {"GEMINI_TTS_VOICE": "nonsense"}):
            self.assertEqual(gv.voice(), gv.DEFAULT_VOICE)

    def test_the_publishing_workflow_names_the_voice_and_holds_the_key(self):
        wf = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        self.assertIn("GEMINI_TTS_VOICE: ${{ vars.GEMINI_TTS_VOICE || 'Charon' }}", wf)
        self.assertIn("GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}", wf)

    def test_gemini_goes_first(self):
        import ast
        import inspect
        from data_learning import studio_render as R
        src = inspect.getsource(R.synth_narration)
        calls = [n.func.id for n in ast.walk(ast.parse(src.lstrip()))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        order = [c for c in calls if c in ("_gemini_lines", "_chatterbox_lines",
                                           "_elevenlabs_wav", "_speechify_wav")]
        self.assertEqual(order[0], "_gemini_lines")


if __name__ == "__main__":
    unittest.main()
