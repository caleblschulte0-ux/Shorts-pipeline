"""A repost laid into a phone frame is cut down to the picture inside it,
and a repair turns our word captions off when the judge saw them on the
footage's own text (2026-11-14 audit of 68 Baller Bro holds: "a small
letterboxed strip", "two thirds of blur", "our captions collide with the
clip's own burned-in captions")."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import run_sports as rs
from third_capture import shot_plan as sp

REPO = Path(__file__).resolve().parents[1]
need_ffmpeg = unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")


def _ff(out: Path, *args: str) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-pix_fmt",
                    "yuv420p", str(out)], check=True)
    return out


def _broadcast(tmp: Path) -> Path:
    return _ff(tmp / "b.mp4", "-f", "lavfi", "-i",
               "mandelbrot=s=640x360:r=25", "-t", "3")


class ThePostsOwnPicture(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.tmp = Path(self._d.name)

    def tearDown(self):
        self._d.cleanup()

    @need_ffmpeg
    def test_a_broadcast_on_blur_is_its_picture(self):
        b = _broadcast(self.tmp)
        post = _ff(self.tmp / "p.mp4", "-i", str(b), "-filter_complex",
                   "[0:v]split[a][c];[a]scale=540:960:force_original_aspect"
                   "_ratio=increase,crop=540:960,gblur=sigma=24[bg];"
                   "[c]scale=540:-2[fg];[bg][fg]overlay=0:(H-h)/2")
        w, h, x, y = sp.picture_area(post)
        # the blur right at the picture's edge is a little sharp too
        self.assertTrue(w == 540 and 290 <= h <= 380 and 260 <= y <= 340,
                        (w, h, x, y))

    @need_ffmpeg
    def test_a_broadcast_on_black_is_its_picture(self):
        b = _broadcast(self.tmp)
        post = _ff(self.tmp / "p.mp4", "-i", str(b), "-vf",
                   "scale=540:-2,pad=540:960:0:(oh-ih)/2:black")
        w, h, x, y = sp.picture_area(post)
        self.assertTrue(w == 540 and 290 <= h <= 330, (w, h, x, y))

    @need_ffmpeg
    def test_a_real_picture_is_left_whole(self):
        self.assertIsNone(sp.picture_area(_broadcast(self.tmp)))

    @need_ffmpeg
    def test_a_face_against_a_dark_backdrop_is_not_padding(self):
        b = _broadcast(self.tmp)
        # a tall close-up: sharp middle, soft dark (not black) sides
        post = _ff(self.tmp / "p.mp4", "-f", "lavfi", "-i",
                   "color=c=0x303038:s=540x960:d=3", "-i", str(b),
                   "-filter_complex",
                   "[1:v]crop=200:360,scale=380:960[fg];"
                   "[0:v][fg]overlay=80:0")
        self.assertIsNone(sp.picture_area(post))

    def test_the_cut_uses_it(self):
        src = (REPO / "third_capture" / "clip_edit.py").read_text()
        self.assertIn("_spa.picture_area(raw)", src)
        self.assertIn('"crop={}:{}:{}:{}".format(*area)', src)

    def test_a_caption_clash_turns_our_words_off_on_the_repair(self):
        self.assertTrue(rs.words_collide({
            "one_line": "Real Kerr presser, but our captions collide with "
                        "the clip's own burned-in captions"}))
        self.assertTrue(rs.words_collide({
            "problems": ["our word captions sit on top of the broadcast "
                         "scorebug"]}))
        self.assertFalse(rs.words_collide(
            {"one_line": "The payoff never lands"}))
        src = (REPO / "third_capture" / "clip_edit.py").read_text()
        self.assertIn('direct.get("speech") or "") == "off"', src)


if __name__ == "__main__":
    unittest.main()
