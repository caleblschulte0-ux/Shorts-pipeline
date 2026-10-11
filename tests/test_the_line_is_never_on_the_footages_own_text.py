"""The one line of text never sits on the footage's OWN text.

Operator, 2026-10-09: "don't put captions over the captions of the
video. Like, you can't read either of them then". `own_captions` catches
a stream captioning its speech; the first Baller Bro sports samples
(2026-10-11) showed what it misses: a reposted clip's burned-in title
("Mike Ditka sings Da quickest...") and a show's subtitles, right in the
bottom third where our line went. `clip_edit.line_spot` reads the picture
the line goes on and moves the line to the top when the bottom is taken.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from third_capture import caption_line, clip_edit

PICTURE = "[0:v]scale=1080:1920[vout]"


def _clip(d: Path) -> Path:
    p = d / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=gray:s=270x480:d=2", str(p)], check=True)
    return p


class LineSpot(unittest.TestCase):
    def _spot(self, text_in):
        def ocr(img):
            name = Path(img).stem
            return ["mike", "ditka", "sings"] if any(
                name.endswith(b) for b in text_in) else ["ee"]
        with tempfile.TemporaryDirectory() as td, \
                mock.patch("shutil.which", return_value="/usr/bin/x"), \
                mock.patch.object(clip_edit, "_ocr_words", side_effect=ocr):
            return clip_edit.line_spot(_clip(Path(td)), PICTURE, 2.0, 100)

    def test_free_bottom_keeps_the_bottom_third(self):
        self.assertEqual(self._spot(())[0], caption_line.LINE_Y)

    def test_text_in_the_bottom_moves_the_line_to_the_top(self):
        y, why = self._spot(("_bottom",))
        self.assertEqual(y, caption_line.TOP_Y)
        self.assertIn("bottom third", why)

    def test_noise_is_not_text(self):
        self.assertFalse(clip_edit._has_text(["ee", "mmm"]))
        self.assertTrue(clip_edit._has_text(["mike", "ditka"]))

    def test_no_tesseract_is_the_old_place(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(clip_edit.line_spot(Path("x"), PICTURE, 2, 100),
                             (caption_line.LINE_Y, "unchecked"))

    def test_the_top_spot_is_clear_of_the_speech_captions(self):
        self.assertLess(caption_line.TOP_Y + 200, caption_line.SPEECH_Y)

    def test_the_edit_overlays_the_line_where_line_spot_said(self):
        src = Path(clip_edit.__file__).read_text()
        self.assertIn("line_spot(src, plain_vf, dur", src)
        self.assertNotIn('f"{caption_line.LINE_Y}', src)


if __name__ == "__main__":
    unittest.main()
