"""The explainer's run goes red on what sixteen logs showed and no record
kept (operator, 2026-11-14: "learn from this and expand 10 times in every
direction"): 2026-11-08..11, zero posts, the same stories held
`not_current` run after run, every run green.

    python -m pytest tests/test_explainer_health_check.py -q
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.append(str(REPO / "scripts"))

from scripts import explainer_health as h  # noqa: E402


def _run(posted=(), held=None, faults=(), dry=False):
    return {"ts": "2026-11-15T12:00:00+00:00", "dry_run": dry,
            "posted": list(posted), "held": held or {},
            "example": {k: f"why {k}" for k in (held or {})},
            "faults": list(faults)}


STUCK = {"not_current": ["earth-rotation", "naep-math"],
         "editorial_hold": ["helium"] * 60}


def _v(verdict="ship", fails=()):
    return {"ts": "2026-11-15T12:00:00", "slug": "s", "verdict": verdict,
            "one_line": "x", "auto_fails": list(fails)}


class TheCheck(unittest.TestCase):
    def test_the_week_of_2026_11_08_is_a_failure(self):
        got = h.problems([_run(held=STUCK) for _ in range(6)], [])
        self.assertTrue(any("not one story posted" in p for p in got))
        self.assertTrue(any("not_current in" in p and "earth-rotation" in p
                            for p in got))

    def test_a_fault_is_a_failure(self):
        got = h.problems([_run(posted=["a"], faults=[
            {"slug": "b", "error": "ClaimNotDurable: claim not pushed"}])],
            [])
        self.assertTrue(any("fault" in p for p in got))

    def test_a_gate_naming_one_defect_is_a_failure(self):
        vs = [_v(fails=["unreadable: tiny grey label"]) for _ in range(3)]
        vs += [_v()]
        got = h.problems([_run(posted=["a"])], vs)
        self.assertTrue(any("named unreadable" in p for p in got))

    def test_a_gate_blocking_most_cuts_is_a_failure(self):
        vs = [_v("block") for _ in range(3)] + [_v()]
        got = h.problems([_run(posted=["a"])], vs)
        self.assertTrue(any("blocked by the showrunner" in p for p in got))

    def test_a_healthy_day_passes(self):
        runs = [_run(held={"editorial_hold": ["x"] * 70,
                           "not_current": ["y"]}),
                _run(posted=["a", "b"], held={"not_current": ["y"]}),
                _run(posted=["c", "d"])]
        vs = [_v(), _v(fails=["unreadable: x"]), _v(), _v("block"), _v()]
        self.assertEqual(h.problems(runs, vs), [])

    def test_dry_runs_do_not_count(self):
        self.assertEqual(h.problems([_run(held=STUCK, dry=True)] * 6, []),
                         [])

    def test_it_runs_last_in_the_posting_workflow(self):
        wf = (REPO / ".github" / "workflows" / "explainer.yml").read_text()
        self.assertIn("python3 scripts/explainer_health.py", wf)
        self.assertGreater(wf.index("scripts/explainer_health.py"),
                           wf.index("Persist posted log + analytics"))
        # and the record it reads is persisted
        self.assertIn("state/explainer_runs.json", wf)


class TheRunIsRecorded(unittest.TestCase):
    def test_post_stories_keeps_a_small_record_of_each_run(self):
        import post_stories as ps
        results = [
            {"slug": "a", "ok": True, "url": "https://youtube.com/shorts/x"},
            {"slug": "b", "ok": False, "error": "not_current",
             "reasons": ["beat(s) [0] have no verified scene"]},
            {"slug": "c", "ok": False, "error": "editorial_hold",
             "reasons": ["data: illustrative"]},
            {"slug": "d", "ok": False, "error": "Boom: crashed"},
        ]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "runs.json"
            for _ in range(ps.RUNS_KEEP + 3):
                ps.record_run(ps.classify_results(results), path=p)
            runs = json.loads(p.read_text())["runs"]
            self.assertEqual(len(runs), ps.RUNS_KEEP)
            r = runs[-1]
            self.assertEqual(r["posted"], ["a"])
            self.assertEqual(r["held"]["not_current"], ["b"])
            self.assertIn("no verified scene", r["example"]["not_current"])
            self.assertEqual(r["faults"][0]["slug"], "d")
            # a run that tried nothing (the slate already posted) is skipped
            ps.record_run(ps.classify_results([]), path=p)
            self.assertEqual(len(json.loads(p.read_text())["runs"]),
                             ps.RUNS_KEEP)
            # and what it writes is what the check reads
            self.assertTrue(any("fault" in x for x in
                                h.problems(runs[-2:], [])))

    def test_post_stories_main_records_the_run(self):
        src = (REPO / "scripts" / "post_stories.py").read_text()
        main = src[src.index("def main("):]
        self.assertIn("record_run(_b", main)


if __name__ == "__main__":
    unittest.main()
