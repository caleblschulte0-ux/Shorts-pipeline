"""A story's line of text does not sit on the footage's OWN text.

Search 31 (2026-10-14) cut the first story over 80, Pikaboo and Payo at
88, and for its whole second half the hook line sat on top of the stream's
own on-screen text: the clip arm has moved its line off a repost's
burned-in captions since 2026-10-11 (`clip_edit.line_spot`), and the story
arm drew every beat's line at the bottom third without asking. Operator,
2026-10-09: *"don't put captions over the captions of the video. Like, you
can't read either of them then"*.

Real ffmpeg and tesseract on a synthesized framed beat; the shot plan is
stubbed to hand that beat back as the framed picture.
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

from third_capture import caption_line, clip_edit, shot_plan, story  # noqa: E402

HAVE_TOOLS = bool(shutil.which("ffmpeg") and shutil.which("tesseract"))


def _beat(path: Path, burned: str | None) -> Path:
    vf = "format=yuv420p"
    if burned:
        tf = path.with_suffix(".txt")
        tf.write_text(burned)
        vf = (f"drawtext=fontfile={story.CAPTION_FONT}:textfile={tf}:"
              "fontcolor=white:fontsize=72:x=(w-tw)/2:y=1440:"
              "borderw=6:bordercolor=black," + vf)
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", "color=c=0x305070:size=1080x1920:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                    "-t", "3", "-vf", vf, "-c:v", "libx264",
                    "-preset", "ultrafast", "-c:a", "aac", "-shortest",
                    str(path)], check=True)
    return path


@unittest.skipUnless(HAVE_TOOLS, "ffmpeg/tesseract unavailable")
class TheLineMovesOffTheFootagesText(unittest.TestCase):
    def setUp(self):
        self.td = Path(self.enterContext(tempfile.TemporaryDirectory()))
        story._AN_CACHE.clear()

    def _line_y(self, burned):
        src = _beat(self.td / f"src_{bool(burned)}.mp4", burned)
        cmds = []
        real_run = story._run

        def run(cmd):
            cmds.append(cmd)
            return real_run(cmd)

        def build(video, work, analyze_on=None, an=None):
            out = Path(work) / f"framed_{bool(burned)}.mp4"
            shutil.copy(src, out)
            return out, {"layout": "facecam_gameplay"}
        with mock.patch.object(shot_plan, "analyze",
                               return_value={"sw": 1080, "sh": 1920,
                                             "subjects": []}), \
                mock.patch.object(shot_plan, "build", side_effect=build), \
                mock.patch.object(story, "_run", side_effect=run):
            story._extract_segment(
                src, self.td / f"seg_{bool(burned)}.mp4", self.td,
                f"t{bool(burned)}", start=0.0, end=2.5, words=[],
                captions=[{"kind": "title", "text": "Pikaboo duels Payo",
                           "at": 0.0, "secs": 2.5}])
        vf = cmds[-1][cmds[-1].index("-vf") + 1]
        ys = {int(p.split("y=", 1)[1].split(":", 1)[0])
              for p in vf.split(",") if p.startswith("drawtext") and "y=" in p}
        self.assertEqual(len(ys), 1, vf)
        return ys.pop()

    def test_clean_footage_keeps_the_bottom_third(self):
        self.assertEqual(self._line_y(None), caption_line.LINE_Y)

    def test_footage_with_its_own_text_there_moves_the_line_up(self):
        self.assertEqual(
            self._line_y("FOLLOW ME FOR MORE CLIPS"), caption_line.TOP_Y,
            "the hook line was drawn over the footage's own text")

    def test_a_failed_read_falls_back_to_the_bottom_third(self):
        with mock.patch.object(clip_edit, "line_spot",
                               side_effect=RuntimeError("boom")):
            y, taken = story._line_spot(Path("nope.mp4"), Path("nope.mp4"),
                                        "", self.td, "x", 0.0, 2.0, "hook")
        self.assertEqual((y, taken), (caption_line.LINE_Y, False))


if __name__ == "__main__":
    unittest.main()
