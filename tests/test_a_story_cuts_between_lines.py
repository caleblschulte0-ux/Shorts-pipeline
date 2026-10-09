"""A story's beats start and stop BETWEEN lines, never inside one.

Backtest 14 (2026-10-09): the critic docked nearly every cut for opening
mid-sentence, a line "cut off at the splice", or an ending "mid-sentence on
'And I have messages of me expressing, bro.'" `story.snap_beat` moves a
beat's edges to the edges of the phrase they land in, in the plan the
critic reads and in the render alike.
"""
from __future__ import annotations

import unittest

from third_capture import story


def _line(text, at, step=0.3):
    out = []
    for w in text.split():
        out.append({"w": w, "s": round(at, 2), "e": round(at + step - 0.05, 2)})
        at += step
    return out


# two phrases with a clear pause between them
WORDS = (_line("so I texted him every single day", 10.0)       # 10.0-12.05
         + _line("and he posted all of it online", 13.0))      # 13.0-15.05


class ItStartsWhereALineStarts(unittest.TestCase):
    def test_a_start_mid_line_moves_back_to_the_line(self):
        s, _ = story.snap_beat(WORDS, 11.0, 20.0)
        self.assertAlmostEqual(s, 9.95, places=2)

    def test_a_start_mid_word_never_cuts_the_word(self):
        s, _ = story.snap_beat(WORDS, 13.4, 20.0)    # inside "he"
        self.assertLessEqual(s, 13.3)

    def test_a_start_in_a_pause_stays(self):
        s, _ = story.snap_beat(WORDS, 12.5, 20.0)
        self.assertEqual(s, 12.5)


class ItEndsWhereALineEnds(unittest.TestCase):
    def test_an_end_mid_line_runs_on_to_the_line_end(self):
        _, e = story.snap_beat(WORDS, 0.0, 13.5)
        self.assertAlmostEqual(e, 15.15, places=2)

    def test_an_end_in_a_pause_stays(self):
        _, e = story.snap_beat(WORDS, 0.0, 12.5)
        self.assertEqual(e, 12.5)

    def test_too_far_to_the_line_end_still_never_cuts_a_word(self):
        long = _line(" ".join(["word"] * 30), 0.0)    # one 9-second phrase
        _, e = story.snap_beat(long, 0.0, 2.1)       # inside a word
        w = [x for x in long if x["s"] < 2.1][-1]
        self.assertGreaterEqual(e, w["e"])
        self.assertLess(e, 2.1 + story.SNAP_ON + 0.2)


class AJOrLCutKeepsItsOverlap(unittest.TestCase):
    def test_the_bridged_edges_are_kept(self):
        self.assertEqual(story.snap_beat(WORDS, 11.0, 13.5, keep_start=True,
                                         keep_end=True), (11.0, 13.5))

    def test_an_l_cut_keeps_the_previous_beats_end(self):
        edl = {"beats": [
            {"source_id": "a", "start": 9.0, "end": 13.5, "role": "setup"},
            {"source_id": "a", "start": 20.0, "end": 24.0, "role": "payoff",
             "transition": "l_cut"}], "hook_overlay": "h"}
        led = story.plan_ledger(edl, {"a": {"words": WORDS,
                                            "duration_s": 30.0}})
        self.assertEqual(led["beats"][0]["end"], 13.5)


class NoWordsNoChange(unittest.TestCase):
    def test_silence(self):
        self.assertEqual(story.snap_beat([], 3.0, 9.0), (3.0, 9.0))


class ThePlanAndTheRenderAgree(unittest.TestCase):
    def test_both_snap(self):
        import inspect
        self.assertIn("snap_beat(", inspect.getsource(story.plan_ledger))
        self.assertIn("snap_beat(", inspect.getsource(story.render_story))

    def test_the_ledger_carries_the_snapped_edges(self):
        edl = {"beats": [
            {"source_id": "a", "start": 11.0, "end": 13.5, "role": "setup"},
            {"source_id": "a", "start": 13.0, "end": 14.0, "role": "payoff"}],
            "hook_overlay": "h"}
        led = story.plan_ledger(edl, {"a": {"words": WORDS,
                                            "duration_s": 30.0}})
        self.assertAlmostEqual(led["beats"][0]["start"], 9.95, places=2)
        self.assertAlmostEqual(led["beats"][0]["end"], 15.15, places=2)


if __name__ == "__main__":
    unittest.main()
