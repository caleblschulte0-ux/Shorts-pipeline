"""A clip starts and ends on a WHOLE THOUGHT.

Operator, 2026-10-29, of Ernie Johnson's retirement tribute: Chuck's last
words in the clip were "one of my great mentors was Joe Morgan" and then it
cut to the montage of Ernie, "so why didn't we cut it before he gets to
talking about ... this Joe Morgan guy?" The window was cut by seconds (the
author's numbers, then trim_front's cap); now the brain reads the
transcript as sentences and picks the first and last, under the same cap.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.append(str(REPO / "scripts"))

from scripts import sports_samples as ss  # noqa: E402


def _words(text_by_sentence):
    out, t = [], 0.0
    for sent in text_by_sentence:
        for w in sent.split():
            out.append({"w": w, "s": t, "e": t + 0.4})
            t += 0.5
        t += 0.8                       # a pause between sentences
    return out


ERNIE = _words([
    "Ernie you have been the best partner I ever had.",
    "You made all of us better every single night.",
    "I love you man.",
    "One of my great mentors was Joe Morgan.",
    "He told me a story about Jackie Robinson.",
])
C = {"post_title": "Chuck pays tribute to Ernie Johnson"}


class TheTranscriptIsReadAsSentences(unittest.TestCase):
    def test_sentences_break_on_stops_and_pauses(self):
        s = ss.sentences(ERNIE)
        self.assertEqual(len(s), 5)
        self.assertTrue(s[3]["text"].startswith("One of my great mentors"))


class TheClipEndsBeforeANewStory(unittest.TestCase):
    def test_the_brain_picks_the_sentences_and_the_cut_follows(self):
        edit = {"cut": {"start": 0.0, "end": 30.0},
                "outro": {"shows": "Ernie Johnson hosting"}}
        s = ss.sentences(ERNIE)
        with mock.patch.object(ss, "_brain", return_value={
                "first": 0, "last": 2, "why": "ends on I love you"}) as b:
            ss.whole_thought(C, edit, ERNIE, 30.0)
        user, system = b.call_args[0]
        self.assertIn("Joe Morgan", system)        # the rule, with its case
        self.assertIn("a montage of Ernie Johnson hosting", user)
        self.assertIn("[3]", user)
        self.assertLessEqual(edit["cut"]["end"], s[3]["s"])
        self.assertGreaterEqual(edit["cut"]["end"], s[2]["e"])
        self.assertEqual(edit["cut"]["start"], 0.0)

    def test_an_answer_over_the_cap_is_refused(self):
        long = _words(["word " * 40 + "end."] * 3)
        edit = {"cut": {"start": 1.0, "end": 9.0}, "outro": {"who": "x"}}
        with mock.patch.object(ss, "_brain",
                               return_value={"first": 0, "last": 2}):
            ss.whole_thought(C, edit, long, 200.0)
        self.assertEqual(edit["cut"], {"start": 1.0, "end": 9.0})

    def test_no_brain_leaves_the_cut(self):
        edit = {"cut": {"start": 1.0, "end": 9.0}}
        with mock.patch.object(ss, "_brain", return_value=None):
            ss.whole_thought(C, edit, ERNIE, 30.0)
        self.assertEqual(edit["cut"], {"start": 1.0, "end": 9.0})

    def test_make_asks_for_it(self):
        import inspect
        src = inspect.getsource(ss.make)
        self.assertIn("whole_thought(c, meta[\"edit\"], words, dur)", src)


if __name__ == "__main__":
    unittest.main()
