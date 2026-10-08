"""The voice is handed WORDS — nothing it could misread.

Operator, 2026-10-08: *"whatever you feeding to the TTS needs to be in word
format everything and anything it could mis read or will read in a way that
sound unnatural"*. `shared/spoken.say` is the one place written narration
becomes spoken narration; these hold it over every line in the queue.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import spoken as SP  # noqa: E402

CFG = json.loads((ROOT / "data_learning" / "niche.config.json").read_text())
#: Anything an engine has to guess at: a digit, a symbol, letters in
#: capitals ("US" is read "us", "ONE" is spelled out).
LEFT_FOR_THE_ENGINE = re.compile(
    r"\S*[\d%$€£¥°²³/&+~#×@^*<>=_|\\]\S*|\b[A-Z]{2,}\b")


def _queue_lines():
    for s in CFG["stories"]:
        for line in [s.get("hook"), s.get("closing"), s.get("question"),
                     *[g.get("say") for g in s.get("segments") or []]]:
            if line:
                yield s["slug"], line


class EveryQueuedLineIsWords(unittest.TestCase):
    def test_nothing_is_left_for_the_engine_to_guess(self):
        left = [(slug, m.group(0), line)
                for slug, line in _queue_lines()
                for m in LEFT_FOR_THE_ENGINE.finditer(SP.say(line))]
        self.assertEqual(left[:10], [], f"{len(left)} tokens left")


class ItSaysWhatAPersonSays(unittest.TestCase):
    CASES = {
        "242 mph": "two hundred forty two miles per hour",
        "900°F": "nine hundred degrees Fahrenheit",
        "-5°C": "minus five degrees Celsius",
        "30.4 M km²": "thirty point four million square kilometers",
        "8,776‑sq‑mi": "eight thousand seven hundred seventy six square miles",
        "the 1990s": "the nineteen nineties",
        "the '90s": "the nineties",
        "the 21st century": "the twenty first century",
        "5x more": "five times more",
        "9/11": "nine eleven",
        "1/3 of it": "one third of it",
        "S&P 500": "S and P five hundred",
        "the US": "the U S",
        "the WHO": "the W H O",
        "NASA": "Nasa",
        "ONE MILLION": "one million",
        "29147": "twenty nine thousand one hundred forty seven",
        "1,121 qubits": "one thousand one hundred twenty one qubits",
        "In 1816": "In eighteen sixteen",
        "in 2009": "in two thousand nine",
        "2000 billion": "two thousand billion",
        "1500 meters": "one thousand five hundred meters",
        "2010-2020": "twenty ten to twenty twenty",
        "an 11-year cycle": "an eleven-year cycle",
        "20%+": "more than twenty percent",
        "~20": "about twenty",
        "61% vs 59%": "sixty one percent versus fifty nine percent",
        "$1.5B": "one point five billion dollars",
        "$4,200": "four thousand two hundred dollars",
        "0.74 mm": "zero point seven four millimeters",
        "1.27 million": "one point two seven million",
        "CO2": "C O two",
        "7 billion": "seven billion",
        "12,000,000": "twelve million",
    }

    def test_each_case(self):
        for written, spoken in self.CASES.items():
            self.assertEqual(SP.say(written), spoken, written)


class ThereIsOneVoiceText(unittest.TestCase):
    def test_the_explainer_hands_the_voice_spoken_text(self):
        from data_learning import studio_render as sr
        self.assertEqual(sr._tts_text("242 mph in the US"),
                         SP.say("242 mph in the US"))

    def test_the_old_speller_is_gone(self):
        tree = ast.parse((ROOT / "data_learning" / "studio_render.py").read_text())
        defs = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertFalse(defs & {"_card", "_year", "_spell_numbers", "_say_num"})

    def test_trending_keeps_its_shorthand_from_the_same_module(self):
        """Trending times captions and cues from a transcript of its audio,
        which comes back in digits, so it reads digits — through the moved
        normaliser, not a copy of it."""
        import make_explainer_stacked as mes
        self.assertIs(mes.normalize_for_tts, SP.shorthand)
        self.assertEqual(SP.shorthand("$650-900B and 25%"),
                         "650 to 900 billion dollars and 25 percent")


if __name__ == "__main__":
    unittest.main()
