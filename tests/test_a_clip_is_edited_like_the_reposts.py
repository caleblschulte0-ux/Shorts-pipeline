"""A Twitch clip is edited the way the big repost channels edit it.

Operator, 2026-10-09: *"The fucking overlays we do suck. That weird
slowdown thing we do never works, and then we speed up randomly after it
... do a gray overlay and do that specific sad song whenever something sad
happens, or like do the freaking the dead rose with the crying face ...
Also, don't put captions over the captions of the video."*
"""
from __future__ import annotations

import inspect
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from third_capture import caption_line, clip_edit, mood

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


class NoSlowdownNoSpeedup(unittest.TestCase):
    def test_the_auto_editor_is_not_called(self):
        src = inspect.getsource(clip_edit.edit)
        self.assertNotIn("ae.build(", src)
        self.assertIn("program = cut", src)

    def test_no_stickers_slams_or_replay_stamps(self):
        src = inspect.getsource(clip_edit.edit)
        for gone in ("speedlines", "EMOJI_DIR", '"word"', "boxcolor="):
            self.assertNotIn(gone, src)

    def test_a_story_drops_any_replay_or_flash(self):
        from third_capture import story_director as sd
        src = inspect.getsource(sd.validate_edl)
        self.assertNotIn('"replay"', src)


class OneLineOfText(unittest.TestCase):
    def test_sentence_case_and_the_emoji_stay_with_their_word(self):
        lines, _ = caption_line.wrap("LOS THOUGHT HE ENDED STREAM")
        self.assertEqual(" ".join(lines), "Los thought he ended stream")
        if caption_line.has_emoji_font():
            lines, _ = caption_line.wrap(
                "Kai finds out his best friend was posting their texts "
                "the whole time 🥀")
            self.assertTrue(lines[-1].endswith("time 🥀"))

    def test_it_renders_full_width_and_fits(self):
        with tempfile.TemporaryDirectory() as td:
            p = caption_line.render("Los thought he ended stream 😭",
                                    Path(td) / "l.png")
            from PIL import Image
            im = Image.open(p)
            self.assertEqual(im.width, caption_line.CANVAS_W)
            bb = im.getbbox()
            self.assertGreater(bb[0], 0)
            self.assertLess(bb[2], caption_line.CANVAS_W)

    def test_it_sits_in_the_bottom_third_clear_of_the_speech_captions(self):
        self.assertGreaterEqual(caption_line.LINE_Y, 1920 * 2 // 3)
        # a two-line speech caption (Anton 116, centred) ends above it
        self.assertLess(caption_line.SPEECH_Y + 116 // 2 + 20,
                        caption_line.LINE_Y)
        self.assertIn(f"\\pos(540,{caption_line.SPEECH_Y})",
                      clip_edit._POP_FX)
        from third_capture import story
        self.assertEqual(story.CAPTION_Y, caption_line.LINE_Y)


class ASadTurnGoesGrey(unittest.TestCase):
    def test_only_sad_gets_the_treatment(self):
        self.assertIsNone(mood.treatment("", 3, 20))
        self.assertIsNone(mood.treatment("funny", 3, 20))
        t = mood.treatment("sad", 6.5, 20)
        self.assertEqual(t["at"], 6.5)
        self.assertIn("hue=s=", t["vf"])
        self.assertIn("gte(t,6.50)", t["vf"])

    def test_the_author_says_when(self):
        from third_capture import author
        out = author._postprocess(
            {"title": "Kai Cenat Breaks Down Saying Goodbye To Chat",
             "hook": "Kai says goodbye 🥀", "hashtags": ["kaicenat"],
             "series": "drama", "edit": {"mood": "sad", "mood_at": 7.2}},
            "kaicenat", "kai says goodbye to chat", 20.0)
        self.assertEqual((out["edit"]["mood"], out["edit"]["mood_at"]),
                         ("sad", 7.2))
        self.assertEqual(out["hook"], "Kai says goodbye 🥀")

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
    def test_the_piano_is_made_and_mixes_under_the_voice(self):
        bed = mood.bed()
        self.assertTrue(bed.exists())
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "o.m4a"
            t = mood.treatment("sad", 1.0, 4.0)
            g = mood.audio_graph(t, "0:a", "1:a", 4.0, "a")
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                 "sine=f=220:d=4", "-i", str(bed), "-filter_complex", g,
                 "-map", "[a]", "-t", "4", str(out)], check=True)
            self.assertGreater(out.stat().st_size, 1000)


@unittest.skipUnless(HAVE_FFMPEG and shutil.which("tesseract"),
                     "ffmpeg or tesseract unavailable")
class NoCaptionsOverCaptions(unittest.TestCase):
    def _video(self, td: Path, burned: bool) -> tuple[Path, list]:
        lines = ["somebody stole my chair", "where did everybody go",
                 "this stream is cursed", "nobody believes me today"]
        words, filt = [], []
        for i, ln in enumerate(lines):
            for j, w in enumerate(ln.split()):
                words.append({"w": w, "s": i * 2.0 + j * 0.4,
                              "e": i * 2.0 + j * 0.4 + 0.35})
            f = td / f"l{i}.txt"
            f.write_text(ln.upper())
            filt.append(f"drawtext=textfile={f}:fontsize=64:fontcolor=white"
                        f":borderw=4:x=(w-text_w)/2:y=h*0.8"
                        f":enable='between(t,{i * 2.0},{i * 2.0 + 2.0})'")
        out = td / ("b.mp4" if burned else "n.mp4")
        vf = ",".join(filt) if burned else "null"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=1280x720:rate=30:d=8", "-vf", vf,
                        str(out)], check=True)
        return out, words

    def test_a_captioned_stream_is_seen(self):
        with tempfile.TemporaryDirectory() as td:
            v, w = self._video(Path(td), True)
            self.assertTrue(clip_edit.own_captions(v, w))

    def test_an_uncaptioned_one_is_not(self):
        with tempfile.TemporaryDirectory() as td:
            v, w = self._video(Path(td), False)
            self.assertFalse(clip_edit.own_captions(v, w))

    def test_the_edit_skips_its_own_captions_then(self):
        src = inspect.getsource(clip_edit.edit)
        self.assertIn("own_captions(cut, words)", src)
        self.assertIn("[] if own_subs else words", src)


if __name__ == "__main__":
    unittest.main()


def test_a_two_line_hook_is_balanced_not_an_orphan():
    from third_capture import caption_line as c
    lines, _ = c.wrap("CaseOh finds out what an EF4 is 😳")
    assert len(lines) == 2
    assert len(lines[1].split()) >= 3, lines   # never a lone "is 😳"
