"""A LINE A PAID VOICE ALREADY READ IS NEVER BOUGHT TWICE.

2026-10-08: the explainer voiced every render the showrunner judged (about
45 a day, to post 4) and the showrunner never hears the audio. ElevenLabs'
40,000-credit month went in two days, two videos ever shipped with it, and
Speechify's free 500k characters sit near the cap for the same reason. A
redraft that keeps its words must reuse the lines it already paid for; one
that changes a word pays for that line only.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import tempfile
import unittest
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


class _Counter:
    def __init__(self, body: bytes):
        self.n, self.body = 0, body

    def __call__(self, req, timeout=0):
        self.n += 1
        return _Resp(self.body)


def _wav_b64() -> bytes:
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(b"\x01\x00" * 24000)
    return json.dumps({"audio_data": base64.b64encode(buf.getvalue()).decode()}).encode()


class ElevenLabsLines(unittest.TestCase):
    def setUp(self):
        R._ELEVEN_DEAD = None
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {"ELEVENLABS_API_KEY": "k", "ELEVENLABS_VOICE_ID": "v1",
                    "TTS_CACHE_DIR": str(self.tmp / "cache")}

    def test_the_same_line_is_bought_once(self):
        api = _Counter(b"\x01\x00" * 24000)
        with mock.patch.dict(os.environ, self.env), \
                mock.patch("urllib.request.urlopen", api):
            self.assertTrue(R._elevenlabs_wav("hello", self.tmp / "a.wav"))
            self.assertTrue(R._elevenlabs_wav("hello", self.tmp / "b.wav"))
        self.assertEqual(api.n, 1)
        self.assertEqual((self.tmp / "a.wav").read_bytes(),
                         (self.tmp / "b.wav").read_bytes())

    def test_a_changed_word_or_voice_is_a_new_line(self):
        api = _Counter(b"\x01\x00" * 24000)
        with mock.patch.dict(os.environ, self.env), \
                mock.patch("urllib.request.urlopen", api):
            R._elevenlabs_wav("hello", self.tmp / "a.wav")
            R._elevenlabs_wav("hello there", self.tmp / "b.wav")
            with mock.patch.dict(os.environ, {"ELEVENLABS_VOICE_ID": "v2"}):
                R._elevenlabs_wav("hello", self.tmp / "c.wav")
        self.assertEqual(api.n, 3)

    def test_without_the_cache_dir_nothing_changes(self):
        api = _Counter(b"\x01\x00" * 24000)
        env = dict(self.env, TTS_CACHE_DIR="")
        with mock.patch.dict(os.environ, env), \
                mock.patch("urllib.request.urlopen", api):
            R._elevenlabs_wav("hello", self.tmp / "a.wav")
            R._elevenlabs_wav("hello", self.tmp / "b.wav")
        self.assertEqual(api.n, 2)

    def test_no_key_still_says_why(self):
        with mock.patch.dict(os.environ, dict(self.env, ELEVENLABS_API_KEY="",
                                              ELEVEN_LABS_API_KEY="")):
            self.assertFalse(R._elevenlabs_wav("hello", self.tmp / "a.wav"))
        self.assertIn("ELEVENLABS_API_KEY is not set", R._ELEVEN_DEAD)


class SpeechifyLines(unittest.TestCase):
    def setUp(self):
        R._SPEECHIFY_DEAD = False
        R._SPEECHIFY_MODEL_OK = None
        self.tmp = Path(tempfile.mkdtemp())
        self.env = {"SPEECHIFY_API_KEY": "k", "SPEECHIFY_VOICE": "henry",
                    "SPEECHIFY_MODEL": "simba-3.2",
                    "TTS_CACHE_DIR": str(self.tmp / "cache")}

    def test_the_same_line_is_bought_once(self):
        api = _Counter(_wav_b64())
        with mock.patch.dict(os.environ, self.env), \
                mock.patch("urllib.request.urlopen", api):
            self.assertTrue(R._speechify_wav("hello", self.tmp / "a.wav"))
            self.assertTrue(R._speechify_wav("hello", self.tmp / "b.wav"))
            self.assertTrue(R._speechify_wav("goodbye", self.tmp / "c.wav"))
        self.assertEqual(api.n, 2)


class TheWorkflowKeepsTheCache(unittest.TestCase):
    def test_explainer_persists_and_points_at_it(self):
        y = (ROOT / ".github/workflows/explainer.yml").read_text()
        self.assertIn("path: cache/tts/", y)
        self.assertIn("TTS_CACHE_DIR: cache/tts", y)


if __name__ == "__main__":
    unittest.main()
