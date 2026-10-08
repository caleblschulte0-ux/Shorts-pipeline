"""A story knows what the stream was.

Story backtest 9 (2026-10-08): the best cut, Lacy quitting Fortnite and
admitting the throw, scored 76 and 78 and was marked down because "a
stranger never learns what the qualifier was". Nobody on stream says it;
the streamer's own broadcast title does, and Twitch returns it for every
VOD a clip was cut from. The director and the narrator may now use it,
and the grounding floor counts it as a source.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import clip_edit, story_director as sd       # noqa: E402

REPORT = {"source_id": "a", "channel": "lacy", "game": "Fortnite",
          "duration_s": 30.0, "summary": "lacy uninstalls the game",
          "transcript_lines": "it's done now we almost had it",
          "stream_title": "FNCS QUALIFIERS DAY 2 | grinding"}


class TheStreamTitleIsASource(unittest.TestCase):
    def test_the_director_sees_it(self):
        self.assertIn("stream_title='FNCS QUALIFIERS DAY 2 | grinding'",
                      sd._fmt_reports([REPORT]))

    def test_a_narrator_line_from_it_is_grounded(self):
        line = "Lacy was streaming the FNCS qualifiers."
        self.assertTrue(sd.narration_grounded(line, [REPORT]))
        bare = {k: v for k, v in REPORT.items() if k != "stream_title"}
        self.assertFalse(sd.narration_grounded(line, [bare]))


class TwitchIsAsked(unittest.TestCase):
    def test_titles_are_fetched_once_and_cached(self):
        clip_edit._HELIX_VIDEOS.clear()
        resp = mock.Mock()
        resp.json.return_value = {"data": [{"id": "77", "title": "FNCS"}]}
        resp.raise_for_status.return_value = None
        with mock.patch.object(clip_edit, "_helix_creds",
                               return_value=("i", "s")), \
                mock.patch.object(clip_edit, "_helix_headers",
                                  return_value={}), \
                mock.patch("requests.get", return_value=resp) as get:
            self.assertEqual(clip_edit.helix_video_titles(["77", None]),
                             {"77": "FNCS"})
            clip_edit.helix_video_titles(["77"])
        self.assertEqual(get.call_count, 1)

    def test_no_credentials_is_no_title_not_an_error(self):
        clip_edit._HELIX_VIDEOS.clear()
        with mock.patch.object(clip_edit, "_helix_creds", return_value=None):
            self.assertEqual(clip_edit.helix_video_titles(["5"]), {"5": ""})

    def test_the_story_attempt_attaches_it(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertIn('r["stream_title"] = _tt[', src)


if __name__ == "__main__":
    unittest.main()
