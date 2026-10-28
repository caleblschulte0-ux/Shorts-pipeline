"""A sports cut ends on a finished sentence and never captions over the
broadcast's own graphics.

The first Baller Bro dry run (2026-10-11) passed one cut in seven. Of the
six the showrunner blocked, two ended "mid-sentence on 'YOUR' instead of
on the laugh" and "mid-sentence on 'tough start in'", and two put our
text on the footage's own: "the caption is garbled and printed over the
ESPN scorebug" and "our text sits on top of the broadcast's cropped
lower-third". `clip_edit.finish_the_line` carries a cut past a sentence
still being spoken; `clip_edit.line_spot(..., speech=True)` reads the
band the word captions pop in, and the edit burns no words there when
the footage has text in it.
"""
import ast
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from third_capture import caption_line, clip_edit
from third_capture.clip_edit import finish_the_line

PICTURE = "[0:v]scale=1080:1920[vout]"


def _w(text, s, e):
    return {"w": text, "s": s, "e": e}


# "... you know what he did to YOUR | face" then a laugh at 11.5
WORDS = [_w("he", 8.0, 8.3), _w("did", 8.35, 8.7), _w("to", 8.75, 9.0),
         _w("your", 9.8, 10.2), _w("face", 10.25, 10.6),
         _w("haha", 11.5, 11.9)]


class TheCutNeverEndsMidSentence(unittest.TestCase):
    def test_a_word_across_the_end_is_finished(self):
        self.assertAlmostEqual(finish_the_line(WORDS, 10.0, 60.0),
                               10.6 + clip_edit.FINISH_TAIL_S)

    def test_a_word_just_after_the_end_is_finished(self):
        self.assertAlmostEqual(finish_the_line(WORDS, 9.7, 60.0),
                               10.6 + clip_edit.FINISH_TAIL_S)

    def test_a_cut_in_a_pause_stays(self):
        self.assertEqual(finish_the_line(WORDS, 11.0, 60.0), 11.0)
        self.assertEqual(finish_the_line(WORDS, 30.0, 60.0), 30.0)

    def test_it_never_runs_past_the_source(self):
        self.assertEqual(finish_the_line(WORDS, 10.0, 10.9), 10.9)

    def test_it_only_moves_the_end_later(self):
        for t1 in (8.1, 8.5, 9.0, 9.9, 10.4, 11.6):
            self.assertGreaterEqual(finish_the_line(WORDS, t1, 60.0), t1)

    def test_a_speaker_who_never_pauses_is_left_alone(self):
        ramble = [_w("w", 5 + i * 0.3, 5 + i * 0.3 + 0.25)
                  for i in range(60)]
        self.assertEqual(finish_the_line(ramble, 7.0, 60.0), 7.0)

    def test_the_edit_runs_it_before_the_closing_guard(self):
        src = Path(clip_edit.__file__).read_text()
        body = src[src.index("def edit("):]
        self.assertLess(body.index("finish_the_line(words, t1, src_dur)"),
                        body.index("_closing_guard(raw, t0, t1)"))


def _clip(d: Path) -> Path:
    p = d / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=gray:s=270x480:d=2", str(p)], check=True)
    return p


class NoWordsOverTheScorebug(unittest.TestCase):
    def _spot(self, text_in):
        def ocr(img):
            name = Path(img).stem
            return ["espn", "dallas", "cowboys"] if any(
                name.endswith(b) for b in text_in) else ["ee"]
        with tempfile.TemporaryDirectory() as td, \
                mock.patch("shutil.which", return_value="/usr/bin/x"), \
                mock.patch.object(clip_edit, "_ocr_words", side_effect=ocr):
            return clip_edit.line_spot(_clip(Path(td)), PICTURE, 2.0, 100,
                                       speech=True)

    def test_a_scorebug_in_the_speech_band_is_seen(self):
        y, _, taken = self._spot(("_speech",))
        self.assertTrue(taken)
        # and the line leaves it room: two sets of words stacked touching
        # read as one mess (LeBron and the Knicks fan, 2026-10-26)
        self.assertEqual(y, caption_line.TOP_Y)

    def test_with_the_top_taken_too_the_line_stays_at_the_bottom(self):
        y, _, taken = self._spot(("_speech", "_top"))
        self.assertTrue(taken)
        self.assertEqual(y, caption_line.LINE_Y)

    def test_a_clean_speech_band_keeps_the_words(self):
        self.assertFalse(self._spot(())[2])

    def test_no_tesseract_keeps_the_words(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(
                clip_edit.line_spot(Path("x"), PICTURE, 2, 100, speech=True),
                (caption_line.LINE_Y, "unchecked", False))

    def test_the_edit_drops_the_words_when_the_band_is_taken(self):
        tree = ast.parse(Path(clip_edit.__file__).read_text())
        edit = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "edit")
        code = ast.unparse(edit)
        self.assertIn("speech=True", code)
        i = code.index("if _speech_taken and words and (not own_subs):")
        self.assertIn("build_ass([], credit, dur", code[i:i + 300])


if __name__ == "__main__":
    unittest.main()
