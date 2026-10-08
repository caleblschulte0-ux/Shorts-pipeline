"""The narrator gets one line per beat, not one line per story.

Story backtests 2026-10-07: ten rendered cuts, none reached 80, and every
near-miss was refused for context the footage never says out loud — who a
person is, how the bag got into the sewer, that the ban came minutes later.
The cut was allowed ONE narration line for all of it, so a repair could
explain one gap and leave the rest. Every line is still held to the same
rules: <=15 words, a reason, no motive-claiming, grounded in the sources.
"""
import unittest

from third_capture import story_director as sd


def _edl(narration):
    return {
        "is_story": True, "premise": "A challenges B, B answers",
        "central_question": "who wins", "ending_emotion": "surprise",
        "structure": "chronological", "structure_reason": "timeline works",
        "title": "A Challenges B", "hook_overlay": "HE CALLED HIM OUT",
        "target_duration": 45,
        "beats": [
            {"source_id": "a", "start": 2, "end": 10, "role": "setup",
             "purpose": "show the challenge", "transition": "hard_cut",
             "context_overlay": "", "effects": []},
            {"source_id": "b", "start": 5, "end": 14, "role": "escalation",
             "purpose": "it grows", "transition": "hard_cut",
             "context_overlay": "", "effects": []},
            {"source_id": "c", "start": 3, "end": 15, "role": "payoff",
             "purpose": "show the answer", "transition": "hard_cut",
             "context_overlay": "", "effects": []},
        ],
        "ending": {"type": "reaction_hold", "duration": 1.2},
        "narration": narration,
    }


DUR = {"a": 30.0, "b": 40.0, "c": 25.0}


def _line(text, beat, why="the footage never says it"):
    return {"text": text, "over_beat": beat, "essential_because": why}


class ANarratorLinePerBeat(unittest.TestCase):
    def test_a_list_keeps_one_line_per_beat_in_order(self):
        v = sd.validate_edl(_edl([_line("Later that stream, Rakai lost the bag.", 2),
                                  _line("Rakai is a streamer from Atlanta.", 0)]),
                            DUR)
        self.assertIsNotNone(v)
        self.assertEqual([n["over_beat"] for n in v["narration_lines"]], [0, 2])
        self.assertEqual(v["narration"]["over_beat"], 0)

    def test_a_second_line_on_the_same_beat_is_dropped(self):
        v = sd.validate_edl(_edl([_line("Rakai is a streamer.", 1),
                                  _line("Rakai is also a gamer.", 1)]), DUR)
        self.assertEqual(len(v["narration_lines"]), 1)

    def test_the_old_one_line_form_still_works(self):
        v = sd.validate_edl(_edl(_line("Rakai is a streamer.", 1)), DUR)
        self.assertEqual(v["narration"]["over_beat"], 1)
        self.assertEqual(len(v["narration_lines"]), 1)

    def test_every_line_meets_the_same_rules(self):
        long = " ".join(["word"] * 16)
        v = sd.validate_edl(_edl([_line(long, 0), _line("ok then.", 1, why=""),
                                  _line("Rakai is a streamer.", 2)]), DUR)
        self.assertEqual([n["over_beat"] for n in v["narration_lines"]], [2])

    def test_grounding_drops_only_the_invented_line(self):
        reports = [{"source_id": "a", "channel": "rakai", "game": "Just Chatting",
                    "transcript_lines": "rakai lost the bag in the sewer"}]
        edl = {"narration": _line("Rakai lost the bag in the sewer.", 0),
               "narration_lines": [
                   _line("Rakai lost the bag in the sewer.", 0),
                   _line("Nobody expected the president to call.", 1)]}
        rs = []
        out = sd._ground(edl, reports, rs)
        self.assertEqual([n["over_beat"] for n in out["narration_lines"]], [0])
        self.assertEqual(out["narration"]["over_beat"], 0)
        self.assertTrue(any(r.startswith("narration dropped") for r in rs))

    def test_the_renderer_speaks_every_line(self):
        import inspect
        from third_capture import story
        src = inspect.getsource(story.render_story)
        self.assertIn("narration_lines", src)
        self.assertIn("narr_by_beat", src)


if __name__ == "__main__":
    unittest.main()


class ABeatRoleIsReadNotRefusedForAWord(unittest.TestCase):
    """Backtests 2026-10-07/08 lost three repairs to "unknown beat role
    'turn'" / 'evidence' / 'proof'."""

    def test_synonyms_are_read(self):
        e = _edl(None)
        e["beats"][1]["role"] = "Turn"
        e["beats"][0]["role"] = "evidence"
        v = sd.validate_edl(e, DUR)
        self.assertIsNotNone(v)
        self.assertEqual(v["beats"][1]["role"], "climax")
        self.assertEqual(v["beats"][0]["role"], "context")

    def test_a_word_that_means_nothing_is_still_refused(self):
        e = _edl(None)
        e["beats"][1]["role"] = "vibes"
        self.assertIsNone(sd.validate_edl(e, DUR))
