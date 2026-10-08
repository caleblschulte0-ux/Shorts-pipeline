"""A story plan is judged and repaired ON PAPER before a frame is cut.

Story backtest 7 (2026-10-08) spent its whole render budget on six plans
that opened at 48-72 and never climbed: three renders and two vision
reviews each, for stories whose transcript already told the critic "who is
Reggie?" and "the payoff is never shown". The same critic now reads the
words the cut WOULD hold (`story.plan_ledger`), the director repairs what
it names, and only a plan that reads at `story_table_read_min` is
rendered. It can only add a block: the render is still judged with frames
at `story_min_score`.
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

from tests.test_a_story_is_repaired_before_it_is_dropped import (  # noqa
    _Harness, _review)
from third_capture import shot_plan, story                      # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None
READS = {"story_table_reads": 3, "story_table_read_min": 65}


class APlanIsReadFirst(_Harness):
    def outcomes(self):
        return [v.get("outcome") for v in self.verdicts()]

    def test_a_plan_that_reads_weak_is_not_rendered(self):
        led = self.run_attempt([_review(False, 50), _review(False, 52),
                                _review(False, 55)], spec_extra=READS)
        self.assertIsNone(led)
        self.assertEqual(self.revisions, 2, "repaired on paper twice")
        self.assertIn("table_read_failed", self.outcomes())

    def test_the_best_reading_plan_is_rendered_and_the_render_decides(self):
        led = self.run_attempt([_review(False, 66), _review(False, 70),
                                _review(False, 72), _review(True, 85)],
                               spec_extra=READS)
        self.assertIsNotNone(led, "the rendered cut passed at 85")

    def test_a_plan_that_reads_at_the_floor_is_rendered_at_once(self):
        led = self.run_attempt([_review(True, 82), _review(True, 85)],
                               spec_extra=READS)
        self.assertIsNotNone(led)
        self.assertEqual(self.revisions, 0)

    def test_a_good_table_read_never_ships_a_render_the_critic_fails(self):
        led = self.run_attempt([_review(True, 90), _review(False, 60),
                                _review(False, 61), _review(False, 62)],
                               spec_extra=READS)
        self.assertIsNone(led)

    def test_no_brain_at_the_table_leaves_it_to_the_render(self):
        led = self.run_attempt([{"publish": False, "story_score": -1,
                                 "problems": []}, _review(True, 85)],
                               spec_extra=READS)
        self.assertIsNotNone(led)

    def test_the_knobs_are_in_the_channel_config(self):
        import json
        cap = json.loads((ROOT / "state" / "third_packages"
                          / "default_clip.json").read_text())["capture"]
        self.assertIn("story_table_reads", cap)
        self.assertIn("story_table_read_min", cap)
        self.assertLess(cap["story_table_read_min"], 80,
                        "the table read screens; the render's 80 decides")


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class ThePaperLedgerIsTheRenderersLedger(unittest.TestCase):
    """What the critic reads at the table is what the render will hold."""

    def test_equivalent_to_render_story(self):
        td = Path(self.enterContext(tempfile.TemporaryDirectory()))
        src = td / "src.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error",
                        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440",
                        "-t", "6", "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        str(src)], check=True)
        story._AN_CACHE.clear()
        words = [{"w": f"w{i}", "s": i * 0.5, "e": i * 0.5 + 0.4}
                 for i in range(11)]
        edl = {"structure": "chronological", "premise": "p",
               "hook_overlay": "SODA BETS IT ALL",
               "beats": [{"source_id": "S", "start": 0.2, "end": 1.6,
                          "role": "setup", "purpose": "a",
                          "context_overlay": "LATER"},
                         {"source_id": "S", "start": 2.0, "end": 3.9,
                          "role": "payoff", "purpose": "b"}],
               "ending": {"duration": 1.0}}
        srcinfo = {"S": {"path": str(src), "words": words,
                         "duration_s": 6.0, "source_url": "S"}}
        with mock.patch.object(shot_plan, "analyze",
                               return_value={"sw": 1280, "sh": 720,
                                             "subjects": []}), \
                mock.patch.object(shot_plan, "build",
                                  return_value=(None, {"layout": "wide"})):
            led = story.render_story(edl, srcinfo, td / "s.mp4", td / "w")
        paper = story.plan_ledger(edl, srcinfo)
        keys = ("beat", "start", "end", "out_start", "out_end")
        self.assertEqual([{k: b[k] for k in keys} for b in paper["beats"]],
                         [{k: b[k] for k in keys} for b in led["beats"]])
        self.assertEqual(paper["final_words"], led["final_words"])
        self.assertEqual(paper["on_screen"], led["on_screen"])


if __name__ == "__main__":
    unittest.main()
