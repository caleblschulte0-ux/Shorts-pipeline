"""ElevenLabs is tried first on every channel, and never costs a video.

Operator, 2026-09-24: "i have a elevn labs account that i pay for how do we
hook that up". shared/elevenlabs.py is the one door; these tests hold its
promises without touching the network: one voice per video, never raises,
a refusing account is dead for the run, a budget checked before a video
starts, each channel's voice in the registry, the key on every narrating
render step, and every narration path asking ElevenLabs before its old voice.
"""
from __future__ import annotations

import inspect
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from shared import elevenlabs as EL          # noqa: E402


def _pcm(seconds=0.5, sr=EL.SR):
    import numpy as np
    n = int(seconds * sr)
    return (0.2 * np.sin(np.arange(n) * 2 * np.pi * 220 / sr) * 32767).astype("<i2").tobytes()


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http(code, body=b"{}"):
    return urllib.error.HTTPError("https://api.elevenlabs.io", code, "x", {}, io.BytesIO(body))


class TheDoor(unittest.TestCase):
    def setUp(self):
        EL._dead, EL._spent, EL._listed = None, 0, True
        EL._logged.clear()
        self.env = mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=False)
        self.env.start()
        os.environ.pop("ELEVENLABS_VOICE_ID", None)
        os.environ.pop("ELEVENLABS_MAX_CHARS_PER_RUN", None)
        self.sleep = mock.patch.object(EL.time, "sleep", lambda s: None)
        self.sleep.start()

    def tearDown(self):
        self.env.stop()
        self.sleep.stop()
        EL._dead, EL._spent = None, 0

    def test_no_key_changes_nothing(self):
        calls = []
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "", "ELEVEN_LABS_API_KEY": ""}):
            self.assertFalse(EL.available("curiosity"))
            self.assertIsNone(EL.speak("hello", "curiosity", _opener=lambda *a: calls.append(a)))
        self.assertEqual(calls, [])

    def test_the_operators_secret_name_works_too(self):
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "", "ELEVEN_LABS_API_KEY": "his-key"}):
            self.assertEqual(EL.key(), "his-key")

    def test_a_line_comes_back_as_samples_at_the_rate_asked(self):
        seen = []

        def opener(url, body, headers):
            seen.append((url, json.loads(body), headers))
            return _Resp(_pcm(0.5))
        a = EL.speak("A quiet line.", "curiosity", sr=48000, _opener=opener)
        self.assertIsNotNone(a)
        self.assertAlmostEqual(len(a) / 48000, 0.5, places=2)
        url, body, headers = seen[0]
        cfg = EL.voice_for("curiosity")
        self.assertIn(cfg["voice_id"], url)
        self.assertIn("output_format=pcm_24000", url)
        self.assertEqual(body["model_id"], cfg["model"])
        self.assertEqual(headers["xi-api-key"], "test-key")
        self.assertEqual(EL._spent, len("A quiet line."))

    def test_a_refusing_account_is_dead_for_the_run(self):
        calls = []

        def opener(*a):
            calls.append(a)
            raise _http(401, b'{"detail":{"status":"quota_exceeded"}}')
        self.assertIsNone(EL.speak("one", "trending", _opener=opener))
        self.assertIsNone(EL.speak("two", "explainer", _opener=opener))
        self.assertEqual(len(calls), 1, "a dead account was asked again")
        self.assertFalse(EL.available("third"))

    def test_a_busy_account_is_retried_then_answers(self):
        n = {"i": 0}

        def opener(*a):
            n["i"] += 1
            if n["i"] < 3:
                raise _http(429)
            return _Resp(_pcm(0.3))
        self.assertIsNotNone(EL.speak("line", "third", _opener=opener))
        self.assertEqual(n["i"], 3)

    def test_an_unknown_voice_falls_back_without_killing_the_account(self):
        self.assertIsNone(EL.speak("line", "third", _opener=lambda *a: (_ for _ in ()).throw(_http(404))))
        self.assertIsNone(EL._dead)
        self.assertTrue(EL.available("third"))

    def test_a_model_without_a_speed_is_asked_again_without_one(self):
        bodies = []

        def opener(url, body, headers):
            b = json.loads(body)
            bodies.append(b)
            if "speed" in b["voice_settings"]:
                raise _http(422, b"speed not supported")
            return _Resp(_pcm(0.3))
        self.assertIn("speed", EL.voice_for("curiosity"), "the sleep film asks for a slow read")
        self.assertIsNotNone(EL.speak("slowly now", "curiosity", _opener=opener))
        self.assertEqual(len(bodies), 2)
        self.assertNotIn("speed", bodies[1]["voice_settings"])

    def test_a_video_that_would_break_the_budget_never_starts(self):
        with mock.patch.dict(os.environ, {"ELEVENLABS_MAX_CHARS_PER_RUN": "100"}):
            self.assertTrue(EL.can_afford(["x" * 60]))
            self.assertFalse(EL.can_afford(["x" * 60, "y" * 60]))

    def test_every_line_or_none(self):
        n = {"i": 0}

        def fake_speak(text, channel, sr=EL.SR, _opener=None):
            import numpy as np
            n["i"] += 1
            return None if n["i"] == 3 else np.zeros(2400, dtype="float32")
        with tempfile.TemporaryDirectory() as td, mock.patch.object(EL, "speak", fake_speak):
            outs = [Path(td) / f"s{i}.wav" for i in range(4)]
            self.assertFalse(EL.speak_all(["a", "b", "c", "d"], "explainer", outs))
            self.assertEqual([o.exists() for o in outs], [False] * 4, "half a video was left in the new voice")
            n["i"] = -10
            self.assertTrue(EL.speak_all(["a", "b", "c", "d"], "explainer", outs))
            self.assertTrue(all(o.exists() for o in outs))

    def test_never_raises(self):
        def opener(*a):
            raise ConnectionResetError("boom")
        self.assertIsNone(EL.speak("line", "trending", _opener=opener))
        self.assertIsNone(EL.speak("line", "no-such-channel", _opener=opener))


class TheVoiceIsPolicy(unittest.TestCase):
    def test_every_channel_names_its_voice_in_the_registry(self):
        from shared import channel_registry as CR
        reg = CR.load()
        for cid in reg["channels"]:
            v = (reg["channels"][cid].get("voice") or {}).get("elevenlabs") or {}
            self.assertTrue(re.fullmatch(r"[A-Za-z0-9]{20}", v.get("voice_id", "")), cid)
            self.assertTrue(v.get("model", "").startswith("eleven_"), cid)
            self.assertEqual(EL.voice_for(cid)["voice_id"], v["voice_id"])

    def test_one_env_overrides_every_channel(self):
        with mock.patch.dict(os.environ, {"ELEVENLABS_VOICE_ID": "abcdefghijklmnopqrst"}):
            self.assertEqual(EL.voice_for("trending")["voice_id"], "abcdefghijklmnopqrst")


class EveryChannelAsksFirst(unittest.TestCase):
    STEPS = {"daily": "Run daily orchestrator", "explainer": "Run", "third": "Render + upload",
             "curiosity": "Render, judge, publish", "longform": "Build + upload long-form"}

    def test_the_key_reaches_every_narrating_render_step(self):
        for wf, step in self.STEPS.items():
            lines = (REPO / ".github" / "workflows" / f"{wf}.yml").read_text().split("\n")
            starts = [i for i, l in enumerate(lines) if l.strip() == f"- name: {step}"]
            self.assertTrue(starts, wf)
            ok = False
            for i in starts:
                j = i + 1
                while j < len(lines) and not re.match(r"\s*- name:", lines[j]):
                    if "ELEVENLABS_API_KEY: ${{ secrets.ELEVEN_LABS_API_KEY }}" in lines[j]:
                        ok = True
                    j += 1
            self.assertTrue(ok, f"{wf}.yml step {step!r} does not carry ELEVENLABS_API_KEY")

    def test_every_narration_path_asks_elevenlabs_before_its_old_voice(self):
        import make_explainer_stacked as MES
        from data_learning import longform_render as LR
        from data_learning import ori_sleep as OS
        from data_learning import studio_render as SR
        from third_capture import compose as TC
        from third_capture import sim_video as SV
        paths = [
            (SR.synth_narration, "EL.speak_all", "SPEECHIFY_API_KEY"),
            (LR.synth_narration, "EL.speak_all", "_synth_kokoro"),
            (MES.tts, "EL.speak_all", "_tts_gemini"),
            (TC.make_audio, "EL.speak_all", "_tts("),
            (SV.compose_sim, "EL.speak_all", "_tts("),
            (OS.render, "EL.available", "voice=voice, workers=workers"),
        ]
        for fn, first, then in paths:
            src = inspect.getsource(fn)
            self.assertIn(first, src, fn.__qualname__)
            self.assertLess(src.index(first), src.index(then), f"{fn.__module__}.{fn.__qualname__}")


class TheSleepFilmKeepsOneVoice(unittest.TestCase):
    """A film ElevenLabs cannot finish is re-narrated WHOLE with Kokoro."""

    def _render(self, speak):
        from data_learning import ori_sleep as OS
        sys.path.insert(0, str(REPO / "tests"))
        import test_ori_sleep as T

        class Kokoro(T.FakeVoice):
            def __init__(self, *a, **k):
                pass
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}), \
                mock.patch.object(EL, "speak", speak), mock.patch.object(OS, "Voice", Kokoro):
            EL._dead, EL._spent = None, 0
            meta = OS.render(T._episode(), Path(td) / "f.mp4", max_seconds=6, workers=1)
            return meta

    def test_elevenlabs_narrates_when_it_can(self):
        import numpy as np
        meta = self._render(lambda text, channel, sr=EL.SR, _opener=None: np.zeros(int(0.8 * sr), "float32"))
        self.assertTrue(str(meta.get("voice", "")).startswith("elevenlabs:"), meta.get("voice"))

    def test_a_line_it_cannot_speak_sends_the_whole_film_to_kokoro(self):
        import numpy as np
        from data_learning import ori_sleep as OS
        n = {"i": 0}

        def speak(text, channel, sr=EL.SR, _opener=None):
            n["i"] += 1
            return None if n["i"] > 2 else np.zeros(int(0.8 * sr), "float32")
        meta = self._render(speak)
        self.assertEqual(meta.get("voice"), OS.VOICE)
        self.assertGreater(n["i"], 2)


if __name__ == "__main__":
    unittest.main()
