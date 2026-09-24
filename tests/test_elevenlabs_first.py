"""ELEVENLABS FIRST, WHEN IT CAN — and the video says when it could not.

Operator, 2026-09-24: "this should start trying to use ElevenLabs when it
can. And if it doesn't use it tomorrow or it can't for some reason, come
ping me." So the narration chain is ElevenLabs -> Speechify -> local Kokoro,
each whole-video (the voice never switches mid-clip), and the engine used and
the reason ElevenLabs was not are written onto the video's sidecar and from
there into the posted log, where a check can read them.
"""
from __future__ import annotations

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

from data_learning import studio_render as R  # noqa: E402


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ElevenLabsWav(unittest.TestCase):
    def setUp(self):
        R._ELEVEN_DEAD = None
        self.tmp = Path(tempfile.mkdtemp())

    def test_no_key_says_so(self):
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "",
                                          "ELEVEN_LABS_API_KEY": ""}):
            self.assertFalse(R._elevenlabs_wav("hello", self.tmp / "a.wav"))
        self.assertIn("ELEVENLABS_API_KEY is not set", R._ELEVEN_DEAD)

    def test_a_line_becomes_24k_mono_wav(self):
        seen = {}

        def fake(req, timeout=0):
            seen["url"], seen["hdr"] = req.full_url, dict(req.headers)
            seen["body"] = json.loads(req.data)
            return _Resp(b"\x01\x00" * 24000)
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k",
                                          "ELEVENLABS_VOICE_ID": "v1"}), \
                mock.patch("urllib.request.urlopen", fake):
            self.assertTrue(R._elevenlabs_wav("hello", self.tmp / "a.wav"))
        self.assertIn("/v1/text-to-speech/v1?output_format=pcm_24000", seen["url"])
        self.assertEqual(seen["hdr"].get("Xi-api-key"), "k")
        self.assertEqual(seen["body"]["text"], "hello")
        import wave
        with wave.open(str(self.tmp / "a.wav")) as w:
            self.assertEqual((w.getnchannels(), w.getframerate()), (1, 24000))

    def test_quota_turns_it_off_for_the_run_with_the_reason(self):
        def fake(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 401, "no", {},
                                         io.BytesIO(b'{"detail":"quota_exceeded"}'))
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k"}), \
                mock.patch("urllib.request.urlopen", fake):
            self.assertFalse(R._elevenlabs_wav("hello", self.tmp / "a.wav"))
        self.assertIn("HTTP 401", R._ELEVEN_DEAD)


class TheChainAndTheRecord(unittest.TestCase):
    def test_elevenlabs_is_tried_before_speechify_and_kokoro(self):
        import inspect
        src = inspect.getsource(R.synth_narration)
        self.assertLess(src.index("_elevenlabs_wav("), src.index("_speechify_wav("))
        self.assertLess(src.index("_speechify_wav("), src.index("Kokoro("))
        self.assertIn('TTS_USED["why_not_elevenlabs"]', src)

    def test_the_engine_reaches_the_sidecar_and_the_posted_log(self):
        rsrc = (ROOT / "data_learning" / "studio_render.py").read_text()
        self.assertIn('_style["tts"] = dict(TTS_USED)', rsrc)
        psrc = (ROOT / "scripts" / "post_stories.py").read_text()
        self.assertIn('facts["tts"] = _st["tts"].get("engine")', psrc)
        self.assertIn('facts["tts_why_not_elevenlabs"]', psrc)

    def test_the_publishing_workflow_passes_the_key(self):
        wf = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        # The operator saved it as ELEVEN_LABS_API_KEY; either name works.
        for name in ("explainer.yml", "preview_explainer.yml"):
            wf = (ROOT / ".github" / "workflows" / name).read_text()
            self.assertIn("ELEVENLABS_API_KEY: ${{ secrets.ELEVENLABS_API_KEY"
                          " || secrets.ELEVEN_LABS_API_KEY }}", wf, name)

    def test_the_operators_spelling_of_the_key_is_read(self):
        seen = {}

        def fake(req, timeout=0):
            seen["hdr"] = dict(req.headers)
            return _Resp(b"\x01\x00" * 2400)
        R._ELEVEN_DEAD = ""
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "",
                                          "ELEVEN_LABS_API_KEY": "k2"}), \
                mock.patch("urllib.request.urlopen", fake):
            self.assertTrue(R._elevenlabs_wav("hi", Path(tempfile.mkdtemp()) / "a.wav"))
        self.assertEqual(seen["hdr"].get("Xi-api-key"), "k2")


if __name__ == "__main__":
    unittest.main()
