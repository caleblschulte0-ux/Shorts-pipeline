"""A story that passes a backtest reaches the channel, judged again.

Search 31 (2026-10-13) passed Pikaboo and Payo at 88 and it had no way
onto the channel: a backtest uploads nothing and writes no repo state.
Operator, 2026-10-16, on posting what passes: *"Go"*.
`backtest_preview.promote` records a passing story's plan; the channel's
next run takes it first (`run_third._proven_clusters`) and starts from
that plan, which still goes through revalidate, render and the critic at
the same bar.
"""
from __future__ import annotations

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


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bp = _load("backtest_preview")


def _cut(label, score, passes, urls):
    return {"label": label, "passes": passes, "revision": 1,
            "files": {"mp4": f"{label}.mp4"},
            "review": {"story_score": score},
            "edl": {"title": label, "premise": "p",
                    "beats": [{"source_id": u, "start": 0, "end": 5}
                              for u in urls]},
            "sources": [{"url": u, "channel": f"ch{i}", "date": f"2026-10-0{i+1}",
                         "summary": "s"} for i, u in enumerate(urls)]}


class PromoteRecordsOnlyWhatPassed(unittest.TestCase):
    def test_a_pass_is_recorded_once_and_a_fail_never(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proven.json"
            report = {"cuts": [_cut("a", 88, True, ["u1", "u2"]),
                               _cut("b", 79, False, ["u3", "u4"])]}
            self.assertEqual(bp.promote(report, path, "31"), 1)
            self.assertEqual(bp.promote(report, path, "31"), 0)
            st = json.loads(path.read_text())["stories"]
            self.assertEqual([s["label"] for s in st], ["a"])
            self.assertEqual(st[0]["source_urls"], ["u1", "u2"])
            self.assertEqual(st[0]["score"], 88)

    def test_no_pass_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proven.json"
            bp.promote({"cuts": [_cut("b", 79, False, ["u3", "u4"])]},
                       path)
            self.assertFalse(path.exists())

    def test_a_story_the_operator_rejected_is_never_promoted_again(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proven.json"
            path.write_text(json.dumps({"stories": [], "rejected": [
                {"label": "a", "source_urls": ["u1", "u2"]}]}))
            report = {"cuts": [_cut("a", 95, True, ["u2", "u1"])]}
            self.assertEqual(bp.promote(report, path, "40"), 0)
            self.assertEqual(json.loads(path.read_text())["stories"], [])

    def test_pikaboo_vs_payo_is_rejected_and_off_the_list(self):
        data = json.loads((ROOT / "state" /
                           "third_proven_stories.json").read_text())
        self.assertFalse([s for s in data["stories"]
                          if "pikaboo" in s["label"]])
        self.assertTrue([s for s in data["rejected"]
                         if "pikaboo" in s["label"]])


class TheChannelTakesItFirst(unittest.TestCase):
    def setUp(self):
        self.rt = _load("run_third")

    def _clusters(self, data, backtest=False):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "proven.json"
            p.write_text(json.dumps(data))
            env = {"STORY_BACKTEST_DIR": td} if backtest else {}
            with mock.patch.object(self.rt, "PROVEN_STORIES", p), \
                    mock.patch.dict(os.environ, env, clear=False):
                if not backtest:
                    os.environ.pop("STORY_BACKTEST_DIR", None)
                return self.rt._proven_clusters()

    def test_a_proven_story_becomes_a_candidate_with_its_plan(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "proven.json"
            bp.promote({"cuts": [_cut("a", 88, True, ["u1", "u2"])]}, path)
            data = json.loads(path.read_text())
        out = self._clusters(data)
        self.assertEqual(len(out), 1)
        c = out[0]
        self.assertEqual([x["source_url"] for x in c["clips"]], ["u1", "u2"])
        self.assertEqual(c["kind"], "scouted")
        self.assertTrue(c["proven_edl"]["beats"])

    def test_a_backtest_does_not_rerender_what_passed(self):
        data = {"stories": [{"edl": {"beats": [{"source_id": "u1"}]},
                             "source_urls": ["u1", "u2"]}]}
        self.assertEqual(self._clusters(data, backtest=True), [])

    def test_the_plan_still_goes_through_revalidate(self):
        src = (ROOT / "scripts" / "run_third.py").read_text()
        i = src.index('cluster["proven_edl"]')
        self.assertIn("story_director.revalidate(_kept[\"edl\"], sub)",
                      src[i:i + 900])


if __name__ == "__main__":
    unittest.main()
