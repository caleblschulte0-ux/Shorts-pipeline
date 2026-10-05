"""A story beat is FRAMED like a clip, not shrunk into blurred padding.

2026-10-05: the first story in eleven days ("Cinna Crew Ditched Her
Mid-Chase") shipped with every beat a 1080x607 strip of the whole stream —
facecam, HUD, sub counter — in two thirds of blurred padding. 31.6% of the
screen. The clip arm stopped doing that weeks ago: `shot_plan.build` stacks
a facecam over full-width gameplay, crops to a face, or crops to the
motion, and its own docstring calls the whole-frame look "the single
loudest 'reposted clip' signal a Short can carry". The story renderer never
called it. Run against those two real Cinna clips, the plan picks
`facecam_gameplay` for one and an action crop for the other.

Real ffmpeg on synthesized sources; the shot plan's detector is stubbed so
the tests do not depend on a face being found in test footage.
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

from third_capture import shot_plan, story                    # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def _make(path: Path, w: int, h: int, secs: float = 4.0) -> Path:
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                    "-t", f"{secs}", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                    str(path)], check=True)
    return path


def _wh(path: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", str(path)], text=True)
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class ABeatUsesTheClipArmsShotPlan(unittest.TestCase):
    def setUp(self):
        self.td = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.src = _make(self.td / "src.mp4", 1280, 720)
        story._AN_CACHE.clear()
        self.calls = {"analyze": 0, "build": 0}

    def _fake_build(self, framed: bool):
        def build(video, work, analyze_on=None, an=None):
            self.calls["build"] += 1
            self.assertEqual(Path(analyze_on), self.src,
                             "the plan is decided on the SOURCE")
            self.assertIsNotNone(an, "the source's analysis is passed in")
            if not framed:
                return None, {"layout": "wide"}
            out = Path(work) / "shotplan.mp4"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
                            "-vf", "scale=1080:1920", "-c:v", "libx264",
                            "-preset", "ultrafast", "-c:a", "copy", str(out)],
                           check=True)
            return out, {"layout": "facecam_gameplay"}
        return build

    def _analyze(self, video):
        self.calls["analyze"] += 1
        return {"sw": 1280, "sh": 720, "subjects": []}

    def _segment(self, tag, framed=True, cmds=None):
        real_run = story._run

        def run(cmd):
            if cmds is not None:
                cmds.append(cmd)
            return real_run(cmd)
        with mock.patch.object(shot_plan, "analyze", side_effect=self._analyze), \
                mock.patch.object(shot_plan, "build",
                                  side_effect=self._fake_build(framed)), \
                mock.patch.object(story, "_run", side_effect=run):
            out = self.td / f"seg_{tag}.mp4"
            layout = story._extract_segment(
                self.src, out, self.td, tag, start=0.5, end=3.0, words=[],
                hook="LEFT BEHIND", framing="wide")
        return out, layout

    def test_a_planned_beat_is_the_plans_shot_not_a_strip(self):
        cmds = []
        out, layout = self._segment("a", cmds=cmds)
        self.assertEqual(layout, "facecam_gameplay")
        self.assertEqual(_wh(out), (1080, 1920))
        final = " ".join(cmds[-1])
        self.assertNotIn("boxblur", final,
                         "a framed beat must not be blur-filled again")

    def test_no_plan_falls_back_to_blur_fill(self):
        cmds = []
        out, layout = self._segment("b", framed=False, cmds=cmds)
        self.assertEqual(layout, "blur_fill")
        self.assertEqual(_wh(out), (1080, 1920))
        self.assertIn("boxblur", " ".join(cmds[-1]))

    def test_beats_from_one_source_share_one_analysis(self):
        self._segment("c")
        self._segment("d")
        self.assertEqual(self.calls["analyze"], 1)
        self.assertEqual(self.calls["build"], 2)

    def test_the_render_records_each_beats_layout(self):
        srcinfo = {"S": {"path": str(self.src), "words": [],
                         "channel": "x", "duration_s": 4.0,
                         "source_url": "S"}}
        edl = {"structure": "chronological", "premise": "p",
               "hook_overlay": "HOOK HERE NOW",
               "beats": [{"source_id": "S", "start": 0.2, "end": 1.6,
                          "role": "setup", "purpose": "a"},
                         {"source_id": "S", "start": 1.8, "end": 3.2,
                          "role": "payoff", "purpose": "b"}],
               "ending": {"duration": 0.5}}
        with mock.patch.object(shot_plan, "analyze", side_effect=self._analyze), \
                mock.patch.object(shot_plan, "build",
                                  side_effect=self._fake_build(True)):
            led = story.render_story(edl, srcinfo, self.td / "story.mp4",
                                     self.td / "w")
        self.assertEqual([b["layout"] for b in led["beats"]],
                         ["facecam_gameplay", "facecam_gameplay"])
        self.assertEqual(_wh(self.td / "story.mp4"), (1080, 1920))


if __name__ == "__main__":
    unittest.main()
