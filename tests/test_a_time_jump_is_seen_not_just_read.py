"""A time jump is SEEN, not just read (operator, 2026-10-29).

Of Ohnepixel's mini story, where "11 minutes later" came up over a
four-second shot and then gave way to the title again: *"we don't need to
change the title ... back ... we can keep that as 11 minutes later. B, let
that clip play out a little bit longer. Let us see that he was playing 11
minutes later."* So the jump's line stays up for its whole beat, and the
beat runs at least `TIME_JUMP_MIN_S` from its own source.
"""
import unittest

from third_capture import story, story_director


def _edl(overlay, start=3.4, end=7.8, dur=40.0):
    return {"is_story": True, "structure": "chronological",
            "central_question": "did he really quit?",
            "title": "Ohnepixel swears he quit this game",
            "premise": "He says he quit, then is caught playing it again.",
            "hook_overlay": "Ohnepixel swears he quit",
            "beats": [
                {"source_id": "a", "start": 3.0, "end": 14.0,
                 "role": "setup", "purpose": "he says he quit",
                 "link": "so"},
                {"source_id": "b", "start": start, "end": end,
                 "role": "payoff", "purpose": "he is playing it again",
                 "context_overlay": overlay, "link": "but"}]}, \
        {"a": 30.0, "b": dur}


class TheJumpPlaysOut(unittest.TestCase):
    def test_a_short_time_jump_beat_runs_on_in_its_source(self):
        edl, durs = _edl("11 minutes later")
        v = story_director.validate_edl(edl, durs)
        b = v["beats"][-1]
        self.assertGreaterEqual(b["end"] - b["start"],
                                story_director.TIME_JUMP_MIN_S - 1e-6)

    def test_never_past_the_source(self):
        edl, durs = _edl("11 minutes later", dur=9.0)
        v = story_director.validate_edl(edl, durs)
        self.assertLessEqual(v["beats"][-1]["end"], 9.0)

    def test_a_beat_with_no_jump_is_left_alone(self):
        edl, durs = _edl("")
        v = story_director.validate_edl(edl, durs)
        self.assertAlmostEqual(v["beats"][-1]["end"], 7.8)

    def test_the_director_is_told(self):
        self.assertIn("SEES what changed", story_director._PLAN_SYSTEM)


class TheJumpStaysTheLine(unittest.TestCase):
    def test_the_jump_is_on_screen_the_whole_beat(self):
        caps = story.beat_captions(1, 7.0, "Ohnepixel swears he quit",
                                   "11 minutes later", "")
        self.assertTrue(caps)
        self.assertTrue(all(c["text"] == "11 minutes later" for c in caps))
        self.assertAlmostEqual(caps[-1]["at"] + caps[-1]["secs"], 7.0)


if __name__ == "__main__":
    unittest.main()


class TheJumpEndsOnAFinishedThought(unittest.TestCase):
    """2026-10-30: the first run with the rule ran Ohnepixel's jump beat on
    to "one of the greatest us" and the critic marked it down."""

    def test_the_new_end_lands_after_a_sentence(self):
        ws = [{"w": "one", "s": 9.6, "e": 9.9},
              {"w": "of", "s": 9.9, "e": 10.1},
              {"w": "the", "s": 10.1, "e": 10.3},
              {"w": "greatest", "s": 10.3, "e": 10.6},
              {"w": "ever.", "s": 10.6, "e": 11.0},
              {"w": "okay", "s": 12.0, "e": 12.3}]
        beats = [{"source_id": "b", "start": 3.4, "end": 7.8,
                  "context_overlay": "11 minutes later"}]
        out = story_director._time_jumps_play_out(
            beats, {"b": 40.0}, [], {"b": ws})
        self.assertAlmostEqual(out[0]["end"], 11.1)

    def test_in_silence_the_minimum_is_enough(self):
        beats = [{"source_id": "b", "start": 3.4, "end": 7.8,
                  "context_overlay": "11 minutes later"}]
        out = story_director._time_jumps_play_out(beats, {"b": 40.0}, [],
                                                  {"b": []})
        self.assertAlmostEqual(out[0]["end"],
                               3.4 + story_director.TIME_JUMP_MIN_S)


class TheJumpIsShownOnce(unittest.TestCase):
    def test_one_entry_from_the_cut(self):
        caps = story.beat_captions(1, 9.0, "Ohnepixel swears he quit",
                                   "11 minutes later", "")
        self.assertEqual(len(caps), 1)
        self.assertEqual(caps[0]["at"], 0.0)


class AnApprovedStoryIsNotReLitigated(unittest.TestCase):
    """Operator, 2026-10-29, on three backtest passes: "yeah, whatever.
    Seems like you get the basic idea." The next morning the critic scored
    the same xQc edit 79, an old refusal skipped the NoPixel one, and no
    story posted."""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        cls.src = (Path(__file__).resolve().parents[1] / "scripts"
                   / "run_third.py").read_text()

    def test_an_old_refusal_does_not_skip_it(self):
        self.assertIn('if _was and cluster.get("proven_edl"):', self.src)

    def test_only_the_approved_edit_counts(self):
        self.assertIn('_approved = bool(cluster.get("proven_edl")) and '
                      'edl is not None', self.src)

    def test_the_operator_is_the_bar(self):
        i = self.src.index("def _passes(rv):")
        self.assertIn("if _approved:\n                            return True",
                      self.src[i:i + 200])

    def test_it_is_rendered_as_approved_not_reread(self):
        self.assertIn("_tr_n = 0 if (_audience or _mstory or _approved)",
                      self.src)
