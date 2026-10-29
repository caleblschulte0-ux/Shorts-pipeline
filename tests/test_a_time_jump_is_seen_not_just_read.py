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
