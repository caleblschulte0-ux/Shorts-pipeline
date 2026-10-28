"""The basics of a Baller Bro edit (operator, 2026-10-28: "we need to fix
basic stuff ... we won't play clips that don't make sense, or if we're
going to play a clip in the middle of a video that it times up right").

A cut-in lands on the word that names it, or is not cut in; and a
landscape source with its own subtitles is shown whole, never cropped
through them.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from third_capture import cut_in, shot_plan  # noqa: E402


def _w(text, s):
    return {"w": text, "s": s, "e": s + 0.3}


WORDS = [_w("I", 0.5), _w("just", 0.8), _w("watched", 1.1), _w("Luka", 6.0),
         _w("whining", 7.0), _w("the", 9.0), _w("whole", 9.3), _w("game", 9.6)]


class ACutInLandsOnItsWord(unittest.TestCase):
    def test_it_moves_onto_the_word(self):
        got = cut_in.snap([{"who": "Luka Doncic", "look": "x", "at": 3.5,
                            "said": "Luka"}], WORDS)
        self.assertEqual(got[0]["at"], round(6.0 - cut_in.LEAD_S, 2))

    def test_said_wins_over_the_name(self):
        got = cut_in.snap([{"who": "Luka Doncic", "look": "x", "at": 8.0,
                            "said": "whole game"}], WORDS)
        self.assertEqual(got[0]["at"], round(9.3 - cut_in.LEAD_S, 2))

    def test_nothing_said_near_it_is_not_cut_in(self):
        self.assertEqual(cut_in.snap(
            [{"who": "Stephen Curry", "look": "x", "at": 6.0,
              "said": "Steph"}], WORDS), [])

    def test_the_cut_clock_is_shifted_back_to_the_source(self):
        # words on the cut's clock, the author's seconds on the source's
        cut = [{**w, "s": w["s"] - 2.0} for w in WORDS]
        got = cut_in.snap([{"who": "Luka", "look": "x", "at": 5.0,
                            "said": "Luka"}], cut, offset=2.0)
        self.assertEqual(got[0]["at"], round(6.0 - cut_in.LEAD_S, 2))

    def test_no_transcript_leaves_it(self):
        it = [{"who": "Luka", "look": "x", "at": 5.0, "said": "Luka"}]
        self.assertEqual(cut_in.snap(it, []), it)

    def test_the_author_is_asked_for_the_word_and_parse_keeps_it(self):
        got = cut_in.parse([{"who": "Luka", "at": 5, "said": "Luka"}])
        self.assertEqual(got[0]["said"], "Luka")
        src = (REPO / "third_capture" / "author.py").read_text()
        self.assertIn('"said": str', src)
        edit = (REPO / "third_capture" / "clip_edit.py").read_text()
        self.assertIn("cut_in.snap(direct[\"broll\"], words, offset=t0)",
                      edit)


def _clip(d: Path, w: int, h: int) -> Path:
    p = d / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"color=c=gray:s={w}x{h}:d=2", str(p)], check=True)
    return p


class SubtitlesAreNeverCroppedThrough(unittest.TestCase):
    def test_wide_text_in_most_frames_is_subtitles(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(shot_plan, "_text_span", return_value=0.8):
            self.assertTrue(shot_plan.burned_subtitles(
                _clip(Path(td), 320, 180), 2.0))

    def test_a_scorebug_or_a_logo_is_not(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(shot_plan, "_text_span", return_value=0.2):
            self.assertFalse(shot_plan.burned_subtitles(
                _clip(Path(td), 320, 180), 2.0))

    def test_build_shows_it_whole(self):
        an = {"sw": 1920, "sh": 1080, "subjects": []}
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(shot_plan, "burned_subtitles",
                                  return_value=True), \
                mock.patch.object(shot_plan, "_probe_wh_dur",
                                  return_value=(1920, 1080, 10.0)):
            path, summary = shot_plan.build(Path("x.mp4"), Path(td), an=an)
        self.assertIsNone(path)
        self.assertIn("subtitles", summary["reason"])


if __name__ == "__main__":
    unittest.main()
