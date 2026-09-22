"""THE PRIMARY TEXT BRAIN MUST BE A MODEL GROQ STILL SERVES.

Groq retired `llama-3.3-70b-versatile` on 2026-08-16. Every `_call_llm`
from that day 404'd on Groq and fell through to Gemini's free tier, which
the same run then exhausted — so the Gemini JUDGE fallback was 429 by the
time a rendered video needed it. Five weeks, every run, every check green.

Held here: the pin is not on Groq's published shutdown list; the third
channel's author pins the same model; a stale env pin of a retired id is
corrected in the request rather than sent; gpt-oss gets a reasoning budget
and enough completion tokens for its JSON.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import script_generator as SG                    # noqa: E402


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _capture(payload_holder):
    def fake_urlopen(req, timeout=0):
        payload_holder.append(json.loads(req.data))
        return _Resp(json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode())
    return fake_urlopen


class ThePinIsAlive(unittest.TestCase):
    def test_the_default_is_not_a_retired_model(self):
        self.assertNotIn(SG.DEFAULT_GROQ_MODEL, SG.RETIRED_GROQ_MODELS)
        self.assertIn("llama-3.3-70b-versatile", SG.RETIRED_GROQ_MODELS)

    def test_the_third_channel_pins_the_same_model(self):
        src = (ROOT / "third_capture" / "author.py").read_text()
        self.assertIn(f'MODEL = "{SG.DEFAULT_GROQ_MODEL}"', src)
        for dead in SG.RETIRED_GROQ_MODELS:
            self.assertNotIn(f'"{dead}"', src)

    def test_a_retired_env_pin_is_corrected_not_sent(self):
        sent = []
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "k"}), \
                mock.patch.object(SG.urllib.request, "urlopen", _capture(sent)):
            SG._call_groq("s", "u", model="llama-3.3-70b-versatile")
        self.assertEqual(sent[0]["model"], SG.DEFAULT_GROQ_MODEL)

    def test_gpt_oss_gets_a_reasoning_budget_and_room_for_json(self):
        sent = []
        with mock.patch.dict("os.environ", {"GROQ_API_KEY": "k"}), \
                mock.patch.object(SG.urllib.request, "urlopen", _capture(sent)):
            SG._call_groq("s", "u")
        body = sent[0]
        self.assertEqual(body["reasoning_effort"], "low")
        self.assertGreaterEqual(body["max_tokens"], 4000)
        self.assertEqual(body["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
