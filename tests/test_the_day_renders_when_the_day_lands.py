"""The explainer starts when the day's stories exist, not on a clock.

Operator, 2026-09-12: *"How come every day for the past five days I've had
to come in here and tell you to manually push videos?"*

Because a cron is not a schedule. The Routine authors the day's stories into
`niche.config.json` and they land on main around 09:30 UTC. The only
automatic trigger was `- cron: '40 13 * * *'`, and GitHub does not run a
cron at 13:40. Measured off the workflow's OWN run history:

    "13:40" actually fired   09-09 17:14   09-10 17:07
                             09-11 17:08   09-12 16:27

two and a half to three and a half hours late, every single day — GitHub
deprioritises scheduled workflows, and this repo runs a lot of Actions. So
finished stories sat unrendered for SEVEN HOURS, and the operator dispatched
the workflow by hand at 09:31, 09:23, 09:52, 09:35, 09:38, 09:40 and 09:37
on seven consecutive days to get the day out.

Nothing was broken. Everything was green. The videos did post — in the
evening, hours after they were ready, which for a channel posting on a
schedule is the same as not posting.

I ALSO GOT THIS WRONG WHEN ASKED DIRECTLY. On 09-10 the question was "so
tomorrow videos are going to post without me having to do anything?" and I
answered yes, citing the cron CONFIG — while this run history, which says
what the cron actually does, was one API call away. Verify the behaviour,
not the declaration.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WF = ROOT / ".github" / "workflows" / "explainer.yml"


def _on():
    import yaml
    d = yaml.safe_load(WF.read_text())
    # PyYAML parses a bare `on:` key as the boolean True.
    return d[True] if True in d else d["on"]


def _job():
    import yaml
    return yaml.safe_load(WF.read_text())["jobs"]["explainer"]


class TheContentLandingStartsTheDay(unittest.TestCase):
    def test_a_push_of_the_days_stories_fires_the_workflow(self):
        on = _on()
        self.assertIn("push", on, "nothing fires when the stories land")
        self.assertIn("data_learning/niche.config.json",
                      on["push"]["paths"])

    def test_it_only_watches_main(self):
        self.assertEqual(_on()["push"]["branches"], ["main"])

    def test_the_job_accepts_the_push_event(self):
        """The trigger is useless if the job's `if:` drops it — the
        condition listed only dispatch and schedule."""
        self.assertIn("push", _job()["if"])

    def test_it_does_NOT_watch_anything_ci_writes(self):
        """CI commits posted logs and analytics under `state/` on every run.
        Watching those would make the workflow trigger itself in a loop."""
        for p in _on()["push"]["paths"]:
            self.assertFalse(p.startswith("state/"), p)
            self.assertNotIn("**", p, f"{p} is broad enough to self-trigger")


class TheCronRemainsTheFloor(unittest.TestCase):
    """The cron is why this channel did not die when trending did (2026-08-03,
    three days of nothing from a fault in a different channel). It stays."""

    def test_both_crons_are_still_there(self):
        crons = [c["cron"] for c in _on()["schedule"]]
        self.assertIn("40 13 * * *", crons)
        self.assertIn("10 17 * * *", crons)

    def test_manual_dispatch_still_works(self):
        self.assertIn("workflow_dispatch", _on())


class TwoTriggersCannotDoubleThePost(unittest.TestCase):
    """The same argument the file already makes for why two CRONS are safe.

    This is NOT the chain the old comment warns about: that one hung off
    "Daily Shorts" — another channel's completion, which is both a coupling
    that already killed this channel once and a second daily budget nobody
    counted. This fires on THIS channel's own content landing, against the
    same budget.
    """

    def test_the_run_is_serialised(self):
        c = _job()["concurrency"]
        self.assertEqual(c["group"], "explainer-stories")
        self.assertFalse(c["cancel-in-progress"],
                         "a half-finished upload must not be cancelled")

    def test_the_poster_counts_what_today_already_posted(self):
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        self.assertIn("posted_today", src)
        self.assertIn("max_per_run", src)

    def test_a_day_already_finished_costs_nothing(self):
        """`budget = max(0, cap - posted_today)`, and budget 0 exits. That
        is what makes an extra trigger a no-op rather than a second slate."""
        import ast
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        tree = ast.parse(src)
        found = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if any(getattr(t, "id", "") == "budget" for t in node.targets):
                txt = ast.unparse(node.value)
                self.assertIn("max_per_run", txt)
                self.assertIn("posted_today", txt)
                found = True
        self.assertTrue(found, "the per-day budget is gone")


if __name__ == "__main__":
    unittest.main()
