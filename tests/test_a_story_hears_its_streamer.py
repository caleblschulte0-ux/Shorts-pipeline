"""The story arm hears a streamer with the LARGE Whisper.

Backtest 15 (2026-10-09): Whisper-small heard "what do you to fucking do
it? Hold on wait?" and the critic docked cut after cut for lines a viewer
would have understood. THIRD_ASR=groq sends the audio to Groq's
large-v3-turbo; any failure falls back to the local model.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from third_capture import clip_edit as ce

ROOT = Path(__file__).resolve().parents[1]


class ItReadsGroqsWords(unittest.TestCase):
    def test_words_and_the_no_speech_rule(self):
        res = {"segments": [{"start": 0, "end": 2, "no_speech_prob": 0.1},
                            {"start": 2, "end": 4, "no_speech_prob": 0.9}],
               "words": [{"word": " Get", "start": 0.1, "end": 0.3},
                         {"word": "Ron", "start": 0.3, "end": 0.6},
                         {"word": "♪", "start": 1.0, "end": 1.2},
                         {"word": "hallucinated", "start": 2.5, "end": 3.0}]}
        self.assertEqual(ce.groq_words_from(res),
                         [{"w": "Get", "s": 0.1, "e": 0.3},
                          {"w": "Ron", "s": 0.3, "e": 0.6}])


class ItFallsBackToTheLocalModel(unittest.TestCase):
    def test_off_without_the_switch_or_the_key(self):
        with mock.patch.dict(os.environ, {"THIRD_ASR": "", "GROQ_API_KEY": "k"}):
            self.assertIsNone(ce._groq_words(Path("x.mp4")))
        with mock.patch.dict(os.environ, {"THIRD_ASR": "groq",
                                          "GROQ_API_KEY": ""}):
            self.assertIsNone(ce._groq_words(Path("x.mp4")))

    def test_a_failure_is_none_not_an_exception(self):
        with mock.patch.dict(os.environ, {"THIRD_ASR": "groq",
                                          "GROQ_API_KEY": "k"}):
            self.assertIsNone(ce._groq_words(Path("/nonexistent.mp4")))


class TheBacktestUsesIt(unittest.TestCase):
    def test_switch_is_on(self):
        wf = (ROOT / ".github" / "workflows" /
              "story-backtest.yml").read_text()
        self.assertIn("THIRD_ASR: groq", wf)


if __name__ == "__main__":
    unittest.main()
