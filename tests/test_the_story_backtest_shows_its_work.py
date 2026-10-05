"""The story backtest shows what the story arm makes — and touches nothing.

Operator, 2026-10-05: "to test it you need to be back testing and showing
me what it's coming up with." `scripts/story_backtest.py` drives the real
`_story_attempt` and keeps every cut the critic sees
(`run_third._backtest_keep`). These tests hold the two things that make it
safe to run any time: production is unaffected (the hook is a no-op without
STORY_BACKTEST_DIR), and a backtest writes no repo state.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


RT = _load("rt_backtest_test", ROOT / "scripts" / "run_third.py")
BT = _load("story_backtest_test", ROOT / "scripts" / "story_backtest.py")

REVIEW = {"publish": True, "story_score": 84, "payoff_at": 30.0,
          "stranger_summary": "She gets ditched, then caught.",
          "problems": []}
EDL = {"title": "T", "premise": "P", "hook_overlay": "H",
       "beats": [{"source_id": "a"}], "structure": "chronological"}


class TheHookIsInvisibleInProduction(unittest.TestCase):
    def test_without_the_env_var_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STORY_BACKTEST_DIR", None)
            mp4 = Path(td) / "x.mp4"
            mp4.write_bytes(b"v")
            RT._backtest_keep("lbl", 0, mp4, EDL, REVIEW, [])
            self.assertEqual(sorted(p.name for p in Path(td).iterdir()),
                             ["x.mp4"])

    def test_with_it_every_cut_is_kept_with_its_verdict(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "bt"
            mp4 = Path(td) / "x.mp4"
            mp4.write_bytes(b"v")
            with mock.patch.dict(os.environ, {"STORY_BACKTEST_DIR": str(out)}):
                RT._backtest_keep("Cinna@vod1/ev", 0, mp4, EDL, REVIEW,
                                  [{"source_id": "u", "channel": "cinna"}])
                RT._backtest_keep("Cinna@vod1/ev", 1, mp4, EDL, REVIEW, [])
            names = sorted(p.name for p in out.iterdir())
            self.assertEqual(names, ["cinna-vod1-ev__r0.json",
                                     "cinna-vod1-ev__r0.mp4",
                                     "cinna-vod1-ev__r1.json",
                                     "cinna-vod1-ev__r1.mp4"])
            rec = json.loads((out / "cinna-vod1-ev__r0.json").read_text())
            self.assertEqual(rec["review"]["story_score"], 84)
            self.assertEqual(rec["edl"]["title"], "T")

    def test_both_review_sites_keep_the_cut(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        self.assertEqual(src.count("_backtest_keep(elbl"), 2,
                         "the first render AND every repair are kept")


def _digest(paths):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.exists()}


class ABacktestWritesNoRepoState(unittest.TestCase):
    def test_a_run_reports_and_leaves_state_alone(self):
        state = [ROOT / "state" / n for n in
                 ("third_posted_log.json", "third_clip_memory.json",
                  "third_events.json", "third_qa_stats.json")]
        before = _digest(state)
        seen_logs = []

        class Stub:
            _JUDGES: dict = {}
            EVENTS_FILE = None
            _CLIP_MEMORY = None

            @staticmethod
            def _deadline_passed():
                return False

            @classmethod
            def _story_attempt(cls, pkg, log, work, out_mp4, slug):
                seen_logs.append(set(log["posted"]))
                cls._JUDGES["story_director"] = {
                    "supply": {"scouted": [{"premise": "p", "shape": "x",
                                            "n": 2}]},
                    "clusters": [{"outcome": "not_a_story",
                                  "cluster": "c", "why": "no change"}]}
                if slug.endswith("-1"):
                    mp4 = Path(work) / "s.mp4"
                    mp4.write_bytes(b"v")
                    RT._backtest_keep("soda@vod/ev", 0, mp4, EDL, REVIEW, [])
                    return {"authored_title": "Soda Loses",
                            "narrative_score": 84, "story_key": "story-x",
                            "member_keys": ["a", "b"], "revision_count": 0}
                return None

        from third_capture import clip_memory
        old_path = clip_memory.PATH
        try:
            with tempfile.TemporaryDirectory() as td, \
                    mock.patch.object(BT, "_load_run_third",
                                      return_value=Stub), \
                    mock.patch.object(BT, "_sheet", return_value=None), \
                    mock.patch.dict(os.environ, {}):
                rc = BT.main(["--attempts", "2", "--out", td])
                self.assertEqual(rc, 0)
                report = (Path(td) / "report.md").read_text()
                self.assertIn("WOULD SHIP", report)
                self.assertIn("Soda Loses", report)
                self.assertIn("not_a_story", report)
                self.assertIn("PASSES (score 84", report)
        finally:
            clip_memory.PATH = old_path
        self.assertIn("backtest-1", seen_logs[1],
                      "a passing story is shipped IN MEMORY so the next "
                      "attempt looks elsewhere")
        self.assertEqual(_digest(state), before, "repo state was written")


if __name__ == "__main__":
    unittest.main()
