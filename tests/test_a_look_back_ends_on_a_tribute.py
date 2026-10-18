"""A clip that LOOKS BACK on someone ends on a tribute: the clip plays as
it is, then a real song over a montage of them.

Operator, 2026-10-18: *"when Kevin Durant was talking about how sad he
was that him and Russ aren't playing anymore, you play just that clip,
and then after that clip's done, play some sad music, and then cut to,
like, clips of them playing together ... Not what you just did, not two
overlays on top ... they're two different situations"*.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from funnel import find_footage, songs
from third_capture import author, moves, outro

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
OUTRO = {"song": "see_you_again", "who": "Kevin Durant Russell Westbrook",
         "looks": ["Durant and Westbrook celebrating on the Thunder",
                   "Westbrook lob to Durant"]}


class TheAuthorMarksIt(unittest.TestCase):
    def test_an_outro_needs_a_song_who_and_two_shots(self):
        self.assertEqual(outro.parse(OUTRO)["song"], "see_you_again")
        self.assertIsNone(outro.parse({**OUTRO, "song": "stock piano"}))
        self.assertIsNone(outro.parse({**OUTRO, "looks": ["one shot"]}))
        self.assertIsNone(outro.parse({**OUTRO, "who": ""}))
        self.assertIsNone(outro.parse(None))

    def test_the_author_keeps_it_and_is_told_what_it_is(self):
        out = author._postprocess(
            {"title": "Kevin Durant Misses Playing With Russ",
             "hook": "KD on Russ 🥀", "hashtags": ["kevindurant"],
             "series": "drama", "edit": {"mood": "", "outro": OUTRO}},
            "Kevin Durant", "kd talks about russ", 30.0)
        self.assertEqual(out["edit"]["outro"]["who"], OUTRO["who"])
        self.assertIn("you play just that clip", author.SYSTEM)

    def test_it_is_not_a_cut_in(self):
        # two different situations: the cut-ins stay, the outro is extra
        self.assertIn("- broll:", author.SYSTEM)
        self.assertIn("- outro:", author.SYSTEM)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class TheClipPlaysThenTheTribute(unittest.TestCase):
    def _media(self, td: Path):
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "color=c=red:s=1280x720:r=30:d=14", "-f", "lavfi", "-i",
             "sine=f=300:d=14", "-shortest", "-c:v", "libx264", "-c:a",
             "aac", str(td / "src.mp4")], check=True)
        for c in ("blue", "green"):
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 f"color=c={c}:s=1280x720:r=30:d=3", "-c:v", "libx264",
                 str(td / f"{c}.mp4")], check=True)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "sine=f=600:d=30", "-ac", "2", str(td / "song.wav")],
            check=True)

    def _edit(self, td: Path, shots: list[str], item=OUTRO):
        from third_capture import clip_edit
        it = iter(shots)

        def find(who, look, **k):
            c = next(it, None)
            return c and {"path": str(td / f"{c}.mp4"), "url": c,
                          "title": c, "from_s": 0, "secs": 2.8}
        words = [{"w": w, "s": i * 0.5, "e": i * 0.5 + 0.4}
                 for i, w in enumerate(
                     ("me and him used to be so good together " * 3).split())]
        with mock.patch.object(songs, "get",
                               return_value=td / "song.wav"), \
                mock.patch.object(find_footage, "find", side_effect=find):
            return clip_edit.edit(
                td / "src.mp4", td / "out.mp4", credit="r/nba",
                hook="KD on Russ", words=words,
                direct={"mood": "sad", "mood_at": 3, "outro": item})

    def _px(self, path: Path, t: float) -> bytes:
        return subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path),
             "-frames:v", "1", "-vf", "crop=8:8:536:200,scale=1:1", "-f",
             "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, check=True).stdout

    def test_the_montage_follows_the_clip_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self._media(td)
            led = self._edit(td, ["blue", "green"])
            self.assertEqual(led["outro"]["shots"], ["blue", "green"])
            # no sad bed or grey under the words: the song comes after
            self.assertEqual(led["moves"], [])
            dur = outro._seconds(td / "out.mp4")
            self.assertAlmostEqual(dur, led["duration_s"], delta=0.3)
            clip = self._px(td / "out.mp4", 3.0)
            self.assertGreater(clip[0], clip[2] + 60)      # red, in colour
            end = self._px(td / "out.mp4", dur - 3.4)
            self.assertGreater(end[2] + end[1], end[0] + 40)  # the footage

    def test_a_shot_that_will_not_join_is_dropped_not_the_tribute(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self._media(td)
            (td / "broken.mp4").write_bytes(b"not a video")
            led = self._edit(td, ["blue", "broken", "green"], item={
                **OUTRO, "looks": OUTRO["looks"] + ["Durant dunk on OKC"]})
            self.assertEqual(led["outro"]["shots"], ["blue", "green"])

    def test_one_shot_is_not_a_tribute(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self._media(td)
            led = self._edit(td, ["blue"])
            self.assertIsNone(led["outro"])
            self.assertLess(outro._seconds(td / "out.mp4"), 13.0)


if __name__ == "__main__":
    unittest.main()
