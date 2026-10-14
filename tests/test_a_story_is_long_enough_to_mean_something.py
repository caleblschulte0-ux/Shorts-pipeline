"""A story is long enough to say what its number MEANS.

Operator, 2026-10-14, of an 18-second, two-beat video about the penny
(each beat 15 words): "Why are they coming out so short". The 10-10 rule
(a beat is its number and what it means) only fired when beats averaged
under 15 words, and nothing held a story of two beats. Now beats under the
registry's `beat_min_words` (18) are retold longer, a story with fewer than
`min_beats` (3) is held before render, and the forge makes four or five.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO))

from shared import pacing  # noqa: E402


def story(beats, words=18):
    say = " ".join(["word"] * words)
    return {"slug": "s", "title": "t", "hook": "h", "closing": "c",
            "segments": [{"say": say} for _ in range(beats)]}


class TheRegistrySetsTheLength(unittest.TestCase):
    def test_the_budget_carries_the_floor_and_the_minimum(self):
        b = pacing.budget()
        self.assertGreaterEqual(b["beat_min_words"], 18)
        self.assertGreaterEqual(b["min_beats"], 3)


class ShortBeatsAreRetoldLonger(unittest.TestCase):
    def test_the_penny_is_short(self):
        # its two beats were 15 words each
        self.assertTrue(pacing.short(story(3, 15)))

    def test_a_full_beat_is_not(self):
        self.assertFalse(pacing.short(story(3, 22)))


class TwoBeatsIsNotAStory(unittest.TestCase):
    def test_two_beats_are_held(self):
        self.assertIn("only 2 beats", pacing.too_few_beats(story(2)))

    def test_three_are_enough(self):
        self.assertIsNone(pacing.too_few_beats(story(3)))

    def test_the_gate_holds_it(self):
        from scripts import editorial_gate as eg
        v = eg.pre_render_verdict(story(2), use_llm=False)
        self.assertFalse(v["ok"])
        self.assertTrue(any("only 2 beats" in r for r in v["reasons"]),
                        v["reasons"])

    def test_it_is_not_sent_for_a_rewrite_that_cannot_fix_it(self):
        # a rewrite keeps the beat count (rewrite_mailbox.validate), so a
        # beat-count hold must not read as a word reason
        from shared import rewrite_mailbox as rw
        self.assertFalse(any(p.startswith("length") for p in rw._WORD_PREFIX))


if __name__ == "__main__":
    unittest.main()
