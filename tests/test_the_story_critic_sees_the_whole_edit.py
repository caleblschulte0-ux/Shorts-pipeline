"""The critic judges the cut a viewer gets — every word on screen, every
word spoken.

Story backtest #5 (2026-10-06): all eleven cuts were marked down for
missing context, including the ones whose narrator SAID it. The critic
samples frames (a 1-2s overlay falls between them) and reads the source
transcript (a voice-over is not in it). The same run showed the hook as
"EMIRU FIGHTS A MATTRESS OUT OF A": an 8-word hook was trimmed to 7 words
and left dangling, and a long hook was wider than the frame anyway.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import shot_plan, story, story_director     # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
LONG = "EMIRU FIGHTS A MATTRESS OUT OF A BOX"


def _edl(hook):
    return {"is_story": True, "premise": "p", "central_question": "q?",
            "structure": "chronological", "title": "t",
            "hook_overlay": hook,
            "beats": [{"source_id": "a", "start": 0, "end": 10,
                       "link": "so", "role": "setup", "purpose": "the claim"},
                      {"source_id": "b", "start": 0, "end": 10,
                       "link": "so", "role": "payoff", "purpose": "the proof"}]}


class TheHookIsNeverCutMidPhrase(unittest.TestCase):
    def test_a_trim_does_not_end_on_a_dangling_word(self):
        out = story_director.validate_edl(_edl(LONG),
                                          {"a": 60.0, "b": 60.0})
        self.assertEqual(out["hook_overlay"], "EMIRU FIGHTS A MATTRESS")

    def test_a_hook_that_fits_is_untouched(self):
        out = story_director.validate_edl(_edl("KAI SAYS REGGIE IS LYING"),
                                          {"a": 60.0, "b": 60.0})
        self.assertEqual(out["hook_overlay"], "KAI SAYS REGGIE IS LYING")


class OnScreenTextFitsTheFrame(unittest.TestCase):
    def test_a_long_line_wraps_inside_the_frame(self):
        lines, size = story._wrap(LONG, 64)
        self.assertLessEqual(len(lines), 2)
        for line in lines:
            self.assertLessEqual(story._text_w(line, size), story.MAX_TEXT_W)
        self.assertEqual(" ".join(lines), LONG, "no word is lost")
        self.assertGreater(len(lines[-1].split()), 1, "no orphan word")

    def test_a_short_line_stays_one_line_at_full_size(self):
        self.assertEqual(story._wrap("HE DIES", 52), (["HE DIES"], 52))

    def test_each_line_is_its_own_centred_draw(self):
        with tempfile.TemporaryDirectory() as td:
            f = story._overlay_draw(LONG, Path(td), "h", y=230, size=64,
                                    start=0.0, dur=2.5)
        self.assertEqual(f.count("drawtext="), len(story._wrap(LONG, 64)[0]))
        self.assertEqual(f.count("x=(w-tw)/2"), f.count("drawtext="))

    def test_an_overlay_stays_up_long_enough_to_read(self):
        self.assertGreaterEqual(
            story._read_secs("THE MATTRESS TAKES OVER THE ROOM", 1.3), 2.3)
        self.assertEqual(story._read_secs("HE DIES", 1.3), 1.3)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class TheLedgerSaysWhatTheEditAdded(unittest.TestCase):
    def setUp(self):
        self.td = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.src = self.td / "src.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error",
                        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440",
                        "-t", "4", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        str(self.src)], check=True)
        story._AN_CACHE.clear()

    def test_title_overlay_and_text_line_are_recorded(self):
        edl = {"structure": "chronological", "premise": "p",
               "hook_overlay": LONG,
               "narration": {"text": "Emiru is unboxing a mattress.",
                             "over_beat": 0},
               "beats": [{"source_id": "S", "start": 0.2, "end": 1.6,
                          "link": "so", "role": "setup", "purpose": "a"},
                         {"source_id": "S", "start": 1.8, "end": 3.2,
                          "link": "so", "role": "payoff", "purpose": "b",
                          "context_overlay": "LATER ON STREAM"}],
               "ending": {"duration": 0.3}}
        srcinfo = {"S": {"path": str(self.src), "words": [],
                         "duration_s": 4.0, "source_url": "S"}}
        with mock.patch.object(shot_plan, "analyze",
                               return_value={"sw": 1280, "sh": 720,
                                             "subjects": []}), \
                mock.patch.object(shot_plan, "build",
                                  return_value=(None, {"layout": "wide"})):
            led = story.render_story(edl, srcinfo, self.td / "story.mp4",
                                     self.td / "w")
        kinds = {}
        for o in led["on_screen"]:
            kinds.setdefault(o["kind"], o)
        self.assertEqual(kinds["title"]["text"], LONG)
        self.assertEqual(kinds["overlay"]["text"], "LATER ON STREAM")
        self.assertAlmostEqual(kinds["overlay"]["at"], 1.4, places=1)
        self.assertIs(led["used_narration"], False)
        self.assertTrue((self.td / "story.mp4").exists(),
                        "the wrapped title renders through real ffmpeg")


class TheCriticIsToldWhatTheEditAdded(unittest.TestCase):
    def test_the_text_and_overlays_are_in_the_critics_brief(self):
        seen = {}

        def brain(user, *a, **k):
            seen["user"] = user
            return {"publish": False, "story_score": 50, "problems": []}
        edl = story_director.validate_edl(_edl("KAI SAYS REGGIE IS LYING"),
                                          {"a": 60.0, "b": 60.0})
        with mock.patch.object(story_director, "_brain", side_effect=brain):
            story_director.review_rough_cut(
                edl, "", None, 20.0,
                [{"at": 2.5, "kind": "text", "secs": 2.5,
                  "text": "Reggie is Kai Cenat's cousin"},
                 {"at": 9.0, "kind": "overlay", "secs": 1.5,
                  "text": "MINUTES LATER"}])
        self.assertIn('ON-SCREEN TEXT: "Reggie is Kai Cenat\'s cousin"',
                      seen["user"])
        self.assertIn('ON-SCREEN OVERLAY: "MINUTES LATER"', seen["user"])
        self.assertNotIn("VOICE-OVER", seen["user"])

    def test_both_review_sites_pass_it(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertEqual(src.count('led["duration_s"], led.get("on_screen"))'),
                         2)


if __name__ == "__main__":
    unittest.main()
