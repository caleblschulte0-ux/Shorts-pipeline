"""A backtest shows its FINISHED cuts, where the operator reads.

Operator, 2026-10-09, handed a 570MB artifact zip: *"i need to see the
finished producs and i need to seem them here"*. `backtest_preview` picks
each story's best cut, phone-sized, and `backtest-preview.yml` publishes it
to `preview-renders` after every backtest, where a session can fetch it.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "scripts"))

import backtest_preview as bp                       # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def _cut(label, rev, score, passes=False, mp4="x.mp4"):
    return {"label": label, "revision": rev, "passes": passes,
            "review": {"story_score": score, "stranger_summary": "s"},
            "edl": {"title": "t", "hook_overlay": "h"},
            "files": {"mp4": mp4}}


class EachStorysBestCut(unittest.TestCase):
    def test_one_per_story_best_story_first(self):
        got = bp.best_cuts({"cuts": [
            _cut("a", 0, 58), _cut("a", 1, 66), _cut("a", 2, 62),
            _cut("b", 0, 72), _cut("b", 1, 72), _cut("c", 0, 40)]})
        self.assertEqual([(c["label"], c["revision"]) for c in got],
                         [("b", 1), ("a", 1), ("c", 0)])

    def test_a_pass_outranks_a_higher_fail(self):
        got = bp.best_cuts({"cuts": [_cut("a", 0, 85),
                                      _cut("b", 0, 80, passes=True)]})
        self.assertEqual(got[0]["label"], "b")

    def test_a_cut_with_no_video_is_not_shown(self):
        self.assertEqual(bp.best_cuts({"cuts": [_cut("a", 0, 70, mp4=None)]}),
                         [])


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg unavailable")
class ItProducesPhoneSizedVideo(unittest.TestCase):
    def test_end_to_end(self):
        td = Path(self.enterContext(tempfile.TemporaryDirectory()))
        art = td / "dl" / "backtest"
        art.mkdir(parents=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=1080x1920:rate=30", "-f", "lavfi",
                        "-i", "sine", "-t", "2", "-shortest",
                        str(art / "k__r1.mp4")], check=True)
        (art / "report.json").write_text(json.dumps(
            {"floor": 80, "cuts": [_cut("kai story", 1, 66, mp4="k__r1.mp4")]}))
        self.assertEqual(bp.main(str(td / "dl"), str(td / "out")), 0)
        idx = json.loads((td / "out" / "index.json").read_text())
        f = td / "out" / idx["cuts"][0]["file"]
        self.assertTrue(f.exists())
        self.assertTrue(f.name.startswith("01_66_kai-story"))
        dims = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             str(f)], capture_output=True, text=True).stdout.strip()
        self.assertEqual(dims, "540,960")


class ABacktestDoesNotRetellTheLastOnes(unittest.TestCase):
    """Operator, 2026-10-09: "are we just doing the same sotires over and
    over again?" Backtests 3-12 re-cut Kai's "call" story six times."""

    def setUp(self):
        sys.path.insert(1, str(ROOT))
        import story_backtest
        from third_capture import clip_memory
        self.sb, self.cm = story_backtest, clip_memory
        self.td = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_what_earlier_runs_refused_is_skipped(self):
        mem_p = self.td / "mem.json"
        mem_p.write_text(json.dumps({"clips": {}, "stories_tried": []}))
        carry = self.td / "carry.json"
        carry.write_text(json.dumps({"stories_tried": [
            {"members": ["a", "b"], "why": "not a story",
             "d": "2026-10-08"}], "kept_edits": [
            {"sources": ["a", "c"], "score": 72, "edl": {},
             "d": "2026-10-08"}]}))
        self.assertEqual(self.sb.carry(self.cm, mem_p, str(carry)), 1)
        mem = self.cm.load(mem_p)
        self.assertIsNotNone(self.cm.already_tried(mem, ["a", "b"]))
        self.assertEqual(self.cm.kept_edit(mem, ["a", "c"])["score"], 72)
        # carried twice, counted once
        self.assertEqual(self.sb.carry(self.cm, mem_p, str(carry)), 0)

    def test_no_carry_is_a_fresh_start(self):
        self.assertEqual(self.sb.carry(self.cm, self.td / "m.json", ""), 0)

    def test_the_workflows_pass_it_along(self):
        wf = (ROOT / ".github" / "workflows").joinpath
        self.assertIn('--carry "$RUNNER_TEMP/carry.json"',
                      wf("story-backtest.yml").read_text())
        self.assertIn("backtests/carry.json",
                      wf("backtest-preview.yml").read_text())


class AKeptEditSurvivesTheSave(unittest.TestCase):
    def test_prune_keeps_kept_edits(self):
        from third_capture import clip_memory as cm
        mem = {"clips": {}, "stories_tried": [], "kept_edits": [
            {"sources": ["a", "b"], "score": 76, "edl": {},
             "d": "2026-10-08"}]}
        from datetime import date
        out = cm.prune(mem, date(2026, 10, 9))
        self.assertEqual(out["kept_edits"][0]["score"], 76)


class ItRunsAfterEveryBacktest(unittest.TestCase):
    def test_the_workflow_follows_the_backtest(self):
        wf = (ROOT / ".github" / "workflows" /
              "backtest-preview.yml").read_text()
        self.assertIn('workflows: ["Story backtest"]', wf)
        self.assertIn("scripts/backtest_preview.py", wf)
        self.assertIn("preview-renders", wf)
        name = (ROOT / ".github" / "workflows" /
                "story-backtest.yml").read_text().splitlines()[0]
        self.assertEqual(name, "name: Story backtest")


if __name__ == "__main__":
    unittest.main()
