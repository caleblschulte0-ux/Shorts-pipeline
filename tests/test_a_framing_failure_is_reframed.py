"""A story the critic passed is not dropped for its FRAMING.

2026-10-08, story backtest 5: the first story a backtest critic ever passed
(Lacy's Fortnite "retirement", 82) was thrown away by the clip QA because
"the same streamer appears twice in the same frame, once as a close crop
and once as a wide shot". The edit was fine; the shot layout was not. The
same edit is re-rendered as one subject-centred picture per beat, and it
ships only if the critic passes it again at the floor and the QA passes it.
"""
from __future__ import annotations

import unittest
from unittest import mock

from third_capture import story as story_mod

from tests.test_a_story_is_repaired_before_it_is_dropped import (
    _Harness, _review)

FAIL = {"verdict": "fail", "vision": {},
        "problems": ["vision: the same streamer appears twice in the "
                     "same frame"]}
PASS = {"verdict": "pass", "problems": [], "vision": {}}


class AFramingFailureIsReframed(_Harness):
    def _run(self, reviews, qas):
        return self.run_attempt(reviews, qa=qas)

    def test_the_same_edit_reframed_ships_when_both_judges_pass_it(self):
        led = self._run([_review(True, 82), _review(True, 81)],
                        [FAIL, PASS])
        self.assertIsNotNone(led)
        calls = story_mod.render_story.call_args_list
        self.assertTrue(calls[-1].kwargs.get("safe_framing"))
        self.assertEqual(led["narrative_score"], 81)

    def test_a_reframed_cut_the_critic_marks_down_does_not_ship(self):
        led = self._run([_review(True, 82), _review(True, 70)],
                        [FAIL, PASS])
        self.assertIsNone(led)

    def test_a_reframed_cut_the_qa_still_refuses_does_not_ship(self):
        led = self._run([_review(True, 82), _review(True, 85)],
                        [FAIL, FAIL])
        self.assertIsNone(led)
        whys = " ".join(v.get("why", "") for v in self.verdicts())
        self.assertIn("appears twice", whys)


class TheSafeFramingIsOnePicture(unittest.TestCase):
    def test_cover_crop_is_a_single_subject_centred_window(self):
        class S:
            cx, cy, presence, talk = 1100, 300, 1.0, 0.0
        with mock.patch.object(story_mod, "_source_analysis",
                               return_value={"sw": 1280, "sh": 720,
                                             "subjects": [S()]}):
            vf = story_mod._cover_crop("x.mp4")
        self.assertEqual(vf, "crop=405:720:875:0,scale=1080:1920")
        self.assertNotIn("split", vf)
        self.assertNotIn("overlay", vf)


if __name__ == "__main__":
    unittest.main()
