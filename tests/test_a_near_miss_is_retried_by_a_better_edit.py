"""A story the CRITIC refused is retried once the edit can do more.

2026-10-07: the story backtest re-tried nothing it had rendered before.
Every near-miss (Buddha/xQc at 72, Sodapoppin at 70) was refused when a cut
could carry one narrator line, remembered, and then skipped by every later
run, live and backtest alike, after the edit learned to do what the critic
had asked for. The director's "not a story" is about the footage and stands.
"""
import unittest

from third_capture import clip_memory as cm

A, B = "https://clips.twitch.tv/AaaA", "https://clips.twitch.tv/BbbB"


class ANearMissIsRetried(unittest.TestCase):
    def test_a_cut_refused_by_an_older_edit_is_tried_again(self):
        mem = {"stories_tried": [{"members": sorted([cm._key(A), cm._key(B)]),
                                  "why": "rendered; critic scored 72 after 2 "
                                         "revision(s)", "d": "2026-10-07"}]}
        self.assertIsNone(cm.already_tried(mem, [A, B]))

    def test_a_cut_refused_by_this_edit_is_not(self):
        mem = {}
        cm.note_story_tried(mem, [A, B], why="rendered; critic scored 70",
                            rendered=True)
        self.assertIsNotNone(cm.already_tried(mem, [A, B]))
        self.assertEqual(mem["stories_tried"][0]["edit"], cm.EDIT_VERSION)

    def test_not_a_story_still_stands(self):
        mem = {}
        cm.note_story_tried(mem, [A, B],
                            why="director judged: not a story — unrelated")
        self.assertIsNotNone(cm.already_tried(mem, [A, B]))

    def test_the_run_marks_a_critic_refusal_as_rendered(self):
        from pathlib import Path
        src = Path("scripts/run_third.py").read_text()
        i = src.index('f"rendered; critic scored')
        self.assertIn("rendered=True", src[i:i + 300])


if __name__ == "__main__":
    unittest.main()
