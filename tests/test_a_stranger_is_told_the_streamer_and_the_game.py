"""A stranger is told whose stream it is and what game it is.

Story backtest 2026-10-07: every story that reached the critic and missed
the 80 bar missed it for missing context — "a stranger doesn't know who
Forsen is, or that this is Terraria"; "Snack is never explained". Nobody on
stream says those things, so the director was not allowed to either.
Twitch says them: the clip's broadcaster and its category. These tests hold
that those facts reach the director, the scout and the grounding check.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import clip_edit, story_director, storyline  # noqa: E402

REPORT = {"source_id": "S1", "channel": "forsen", "game": "Terraria",
          "duration_s": 30.0, "summary": "a boss fight in lava",
          "people": [], "dialogue_beats": [], "visual_beats": [],
          "transcript_lines": "[0.0] oh no oh no the lava",
          "emotional_state": [], "missing_context": []}


class TheDirectorSeesTheGame(unittest.TestCase):
    def test_the_scene_report_lists_the_game(self):
        self.assertIn("game=Terraria", story_director._fmt_reports([REPORT]))

    def test_no_game_prints_nothing(self):
        r = dict(REPORT, game="")
        self.assertNotIn("game=", story_director._fmt_reports([r]))

    def test_the_prompts_tell_it_to_name_them(self):
        self.assertIn("A STRANGER DOES NOT KNOW THE STREAMER OR THE GAME",
                      story_director._PLAN_SYSTEM)
        self.assertIn("game=", story_director._REVISE_SYSTEM)


class NamingThemIsGrounded(unittest.TestCase):
    def test_a_line_naming_streamer_and_game_survives(self):
        self.assertTrue(story_director.narration_grounded(
            "Forsen fights through lava in Terraria", [REPORT]))

    def test_a_game_the_metadata_does_not_say_is_still_refused(self):
        self.assertFalse(story_director.narration_grounded(
            "Forsen speedruns Minecraft hardcore tournament", [REPORT]))


class TheScoutSeesTheGame(unittest.TestCase):
    def test_the_catalogue_line_carries_it(self):
        corpus = storyline.from_discovery([
            {"url": "https://www.twitch.tv/forsen/clip/A", "title": "lava",
             "channel": "forsen", "views": 5000, "age_h": 5,
             "game": "Terraria"},
            {"url": "https://www.twitch.tv/forsen/clip/B", "title": "boss",
             "channel": "forsen", "views": 4000, "age_h": 6, "game": ""}])
        lines, _ = storyline.build_catalogue(corpus)
        self.assertTrue(any("game=Terraria" in ln for ln in lines))
        self.assertEqual(sum("game=" in ln for ln in lines), 1)


class GameNamesNeverRaise(unittest.TestCase):
    def test_no_credentials_means_no_names(self):
        with mock.patch.object(clip_edit, "_helix_creds", return_value=None):
            self.assertEqual(clip_edit.helix_game_names(["999"]),
                             {"999": ""})

    def test_an_api_failure_means_no_names(self):
        clip_edit._HELIX_GAMES.pop("998", None)
        with mock.patch.object(clip_edit, "_helix_creds",
                               return_value=("a", "b")), \
                mock.patch.object(clip_edit, "_helix_headers",
                                  side_effect=RuntimeError("down")):
            self.assertEqual(clip_edit.helix_game_names(["998"]),
                             {"998": ""})


if __name__ == "__main__":
    unittest.main()
