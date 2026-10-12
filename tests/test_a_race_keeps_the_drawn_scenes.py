"""A posting run that loses the push race keeps the scenes the predraw saved.

2026-10-12: the predraw saved three stories' last scenes at 21:05; at 21:07
a posting run that had checked out at 18:20 lost the race, took its own copy
of every story, and those scenes were gone. A scene only one side has is
kept while both sides still tell the story in the same words.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "scripts"))

import merge_state_json as M  # noqa: E402


def story(**kw):
    s = {"slug": "s", "hook": "h", "closing": "c",
         "segments": [{"say": "one"}, {"say": "two"}]}
    s.update(kw)
    return s


class ARaceKeepsTheDrawnScenes(unittest.TestCase):
    def test_the_predraws_scenes_survive_a_stale_run(self):
        theirs = story(hook_scene="H", hook_data=0, closing_scene="C",
                       closing_data=1,
                       segments=[{"say": "one", "illustrated_scene": "A"},
                                 {"say": "two", "illustrated_scene": "B"}])
        ours = story(rendered_mechanics=True,
                     segments=[{"say": "one", "illustrated_scene": "A"},
                               {"say": "two"}])
        got = M.merge_stories({"stories": [theirs]}, {"stories": [ours]})["stories"][0]
        self.assertEqual(got["segments"][1]["illustrated_scene"], "B")
        self.assertEqual((got["hook_scene"], got["closing_scene"]), ("H", "C"))
        self.assertTrue(got["rendered_mechanics"])

    def test_a_retold_story_does_not_get_its_old_pictures_back(self):
        theirs = story(hook_scene="H",
                       segments=[{"say": "one", "illustrated_scene": "A"},
                                 {"say": "two", "illustrated_scene": "B"}])
        ours = story(hook="new hook",
                     segments=[{"say": "one"}, {"say": "a new line"}])
        got = M.merge_stories({"stories": [theirs]}, {"stories": [ours]})["stories"][0]
        self.assertNotIn("hook_scene", got)
        self.assertEqual(got["segments"][0]["illustrated_scene"], "A")
        self.assertNotIn("illustrated_scene", got["segments"][1])

    def test_ours_wins_where_both_have_one(self):
        theirs = story(segments=[{"say": "one", "illustrated_scene": "OLD"},
                                 {"say": "two"}])
        ours = story(segments=[{"say": "one", "illustrated_scene": "NEW"},
                               {"say": "two"}])
        got = M.merge_stories({"stories": [theirs]}, {"stories": [ours]})["stories"][0]
        self.assertEqual(got["segments"][0]["illustrated_scene"], "NEW")


if __name__ == "__main__":
    unittest.main()
