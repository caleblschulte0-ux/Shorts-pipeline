"""A posting run says where it is, and when its next video should be up.

Operator, 2026-10-12, after a whole day of "ETA?" answered with "I can't
say": "You need to add something so we have a better guess on this shit."
The run's live log is unreadable until the job ends; now the run reports
each step to the `run-progress` branch, and `scripts/run_eta.py` turns the
last stories' timings into a time.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO))

from shared import run_progress as rp  # noqa: E402


def _tracker(history=None):
    store = {}
    if history is not None:
        store["explainer.json"] = {"history": history}
    t = rp.Tracker("explainer", push=True,
                   reader=lambda n: store.get(n, {}),
                   writer=lambda n, s: store.__setitem__(n, json.loads(json.dumps(s))))
    return t, store


class TheRunReportsEachStep(unittest.TestCase):
    def test_every_step_is_pushed_and_timed(self):
        t, store = _tracker()
        clock = [1000.0]
        real = rp._now
        rp._now = lambda: clock[0]
        try:
            t.mark("a", "prep")
            self.assertEqual(store["explainer.json"]["current"]["phase"], "prep")
            clock[0] += 120
            t.mark("a", "render")
            clock[0] += 1800
            t.mark("a", "review")
            clock[0] += 600
            t.mark("a", "upload")
            clock[0] += 60
            t.finish("a", "posted", "https://youtube.com/shorts/x")
        finally:
            rp._now = real
        s = store["explainer.json"]
        self.assertEqual(s["current"], {})
        rec = s["done"][0]
        self.assertEqual(rec["outcome"], "posted")
        self.assertEqual(rec["phases"],
                         {"prep": 2.0, "render": 30.0, "review": 10.0, "upload": 1.0})
        self.assertEqual(s["history"][-1]["slug"], "a")
        self.assertIn("eta", s)

    def test_a_story_skipped_before_render_teaches_nothing(self):
        t, store = _tracker()
        t.mark("b", "prep")
        t.finish("b", "editorial_hold")
        self.assertEqual(store["explainer.json"]["history"], [])
        self.assertEqual(store["explainer.json"]["done"][0]["outcome"],
                         "editorial_hold")

    def test_a_render_refused_at_the_start_teaches_nothing(self):
        # 2026-10-13: 60 stories refused 0.2 min into render (no drawn
        # scenes) filled the history and put a render's median at 0.3 min
        t, store = _tracker()
        t.mark("c", "prep")
        t.mark("c", "render")
        t.finish("c", "not_current")
        self.assertEqual(store["explainer.json"]["history"], [])
        junk = [{"outcome": "not_current", "phases": {"render": 0.2}}] * 10
        self.assertEqual(rp.typical(junk)["render"], rp.DEFAULT_MIN["render"])
        self.assertEqual(rp.post_rate(junk), rp.DEFAULT_POST_RATE)

    def test_history_survives_from_the_last_run(self):
        old = [{"slug": f"s{i}", "outcome": "posted",
                "phases": {"render": 40.0}} for i in range(5)]
        t, _ = _tracker(old)
        self.assertEqual(len(t.state["history"]), 5)

    def test_bookkeeping_never_breaks_a_run(self):
        def boom(*a):
            raise RuntimeError("push refused")
        t = rp.Tracker("explainer", push=True, reader=boom, writer=boom)
        t.mark("a", "prep")
        t.finish("a", "posted")
        t.end()


class TheGuessComesFromWhatRunsReallyTook(unittest.TestCase):
    def test_medians_replace_the_defaults(self):
        hist = [{"outcome": "posted",
                 "phases": {"prep": 3, "render": r, "review": 10, "upload": 1}}
                for r in (50, 60, 70)]
        self.assertEqual(rp.typical(hist)["render"], 60)
        self.assertEqual(rp.typical([])["render"], rp.DEFAULT_MIN["render"])

    def test_time_already_spent_comes_off(self):
        st = {"history": [], "current": {"slug": "a", "phase": "render",
                                         "phase_since": 0.0}}
        e = rp.estimate(st, now=10 * 60.0)
        want = (rp.DEFAULT_MIN["render"] - 10 + rp.DEFAULT_MIN["review"]
                + rp.DEFAULT_MIN["upload"])
        self.assertEqual(e["this_story_min"], round(want))

    def test_holds_push_the_next_post_out(self):
        passing = [{"outcome": "posted", "phases": {"render": 30, "review": 9}}] * 4
        failing = [{"outcome": "blocked", "phases": {"render": 30, "review": 9}}] * 4
        st = {"current": {}}
        a = rp.estimate({**st, "history": passing})
        b = rp.estimate({**st, "history": passing + failing})
        self.assertGreater(b["next_post_min"], a["next_post_min"])

    def test_it_says_a_time_in_words(self):
        sys.path.append(str(REPO / "scripts"))
        import run_eta
        st = {"run_started": "2026-10-13T00:00:00+00:00", "history": [],
              "done": [], "current": {"slug": "back-pain", "phase": "render",
                                      "phase_since": 0.0}}
        txt = run_eta.describe(st, now=60.0)
        self.assertIn("back-pain is drawing and rendering", txt)
        self.assertIn("Best guess for the next post", txt)


class TheBranchWriteLeavesTheRunAlone(unittest.TestCase):
    def test_it_pushes_one_file_and_touches_no_working_tree(self):
        with tempfile.TemporaryDirectory() as d:
            remote, work = Path(d) / "r.git", Path(d) / "w"
            g = lambda *a, cwd=None: subprocess.run(
                ["git", *a], cwd=cwd, check=True, capture_output=True, text=True)
            g("init", "-q", "--bare", str(remote))
            g("init", "-q", str(work))
            g("remote", "add", "origin", str(remote), cwd=work)
            (work / "f.txt").write_text("dirty\n")
            here = os.getcwd()
            os.chdir(work)
            try:
                rp._write_remote("explainer.json", {"channel": "explainer",
                                                    "updated": "now"})
                got = rp._read_remote("explainer.json")
            finally:
                os.chdir(here)
            self.assertEqual(got["channel"], "explainer")
            st = g("status", "--porcelain", cwd=work).stdout
            self.assertEqual(st.strip(), "?? f.txt")


class PostStoriesMarksEveryStep(unittest.TestCase):
    def test_each_phase_is_marked(self):
        tree = ast.parse((REPO / "scripts" / "post_stories.py").read_text())
        marked = {c.args[1].value for c in ast.walk(tree)
                  if isinstance(c, ast.Call)
                  and getattr(c.func, "attr", None) == "mark"
                  and len(c.args) == 2 and isinstance(c.args[1], ast.Constant)}
        self.assertEqual(marked, set(rp.PHASES))


if __name__ == "__main__":
    unittest.main()
