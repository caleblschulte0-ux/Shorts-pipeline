"""Phase A must be able to run on a day nobody authored anything.

Doctor finding f7633072ef78. Nothing under `tests/` referenced
`exchange_phase_a.yml`, its backstop, or its trigger topology — the
workflow's own comments were the entire specification. Those comments record
two outages that this file now holds shut:

  * 2026-07-30 — the `workflow_run` trigger carried `branches: [main]`, which
    for workflow_run matches the TRIGGERING run's head branch. auto-merge.yml
    runs in the pull request's context, so its head_branch is the PR branch,
    never `main`. The filter excluded the only event it was meant to catch,
    and Phase A never fired.
  * the backstop cron was 04:30 UTC, a guess at the Routine's time and wrong
    by five hours: Phase A ran before the packages existed, found nothing,
    exited clean in ten seconds, and never ran again.

`tests/test_authoring_takeover.py` starts at the already-authored bundle, so
a day where the whole authoring chain is missing was covered nowhere. And
this bug class is invisible in the Actions tab: a Phase A that finds no
packages exits 0.

The rule: **at least one trigger must be independent of upstream authoring
having already happened**, and the date the bundle is written under must be
the same date the run computes.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WF_PATH = ROOT / ".github" / "workflows" / "exchange_phase_a.yml"
WF = yaml.safe_load(WF_PATH.read_text())
RAW = WF_PATH.read_text()
# pyyaml parses a bare `on:` key as the boolean True
ON = WF.get(True, WF.get("on", {}))
JOB = WF["jobs"]["phase-a"]
STEPS = {s.get("name"): s for s in JOB["steps"]}


class SomethingRunsEvenIfNothingUpstreamDid(unittest.TestCase):
    def test_there_is_a_trigger_that_needs_no_upstream_run(self):
        """workflow_run and push both require the authoring chain to have
        worked. If those are the only triggers, a day where the Routine
        never ran produces no bundle and no signal."""
        independent = {"schedule", "workflow_dispatch"} & set(ON)
        self.assertTrue(
            independent,
            "every Phase A trigger depends on upstream authoring — a day the "
            "Routine missed would produce no bundle and nothing would notice")

    def test_the_backstop_is_scheduled_after_the_routine_authors(self):
        """04:30 was a guess at the Routine's time and was wrong by five
        hours. The Routine is observed at ~09:19 UTC."""
        crons = [c["cron"] for c in ON["schedule"]]
        self.assertTrue(crons)
        for cron in crons:
            minute, hour = cron.split()[0], cron.split()[1]
            with self.subTest(cron=cron):
                self.assertRegex(hour, r"^\d+$", "no wildcard backstop hour")
                total = int(hour) * 60 + int(minute)
                self.assertGreater(
                    total, 9 * 60 + 19,
                    f"{cron} fires at or before the Routine's observed 09:19 "
                    "UTC — Phase A would find no packages and exit 0")

    def test_the_workflow_run_trigger_has_no_branch_filter(self):
        """The 2026-07-30 outage, exactly. For workflow_run, `branches`
        matches the TRIGGERING run's head branch — auto-merge runs in the
        PR's context, so it is never `main`."""
        wr = ON["workflow_run"]
        self.assertNotIn("branches", wr,
                         "a branches filter here excludes the only event "
                         "this trigger exists to catch (see the workflow's "
                         "own comment)")
        self.assertIn("Auto-merge claude PRs", wr["workflows"])
        self.assertIn("completed", wr["types"])

    def test_the_push_path_covers_every_channel_phase_a_prepares(self):
        paths = ON["push"]["paths"]
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "exchange_phase_a", ROOT / "scripts" / "exchange_phase_a.py")
        pa = importlib.util.module_from_spec(spec)
        sys.modules["exchange_phase_a"] = pa
        spec.loader.exec_module(pa)
        for channel, rel in pa.PACKAGE_DIRS.items():
            with self.subTest(channel=channel):
                self.assertTrue(
                    any(str(rel) in p for p in paths),
                    f"a push of {channel} packages ({rel}) does not start "
                    "Phase A")


class TheDateIsResolvedOnceAndUsedTwice(unittest.TestCase):
    """The bundle is written under a date and committed under a date. If
    those are computed differently the run commits an empty path and exits
    clean."""

    def _date_expr(self, step_name: str) -> str:
        run = STEPS[step_name]["run"]
        m = re.search(r'DATE=\$\(date -u \+(\S+)\)', run)
        self.assertIsNotNone(m, f"{step_name} does not compute a date")
        return m.group(1)

    def test_both_steps_compute_the_same_date(self):
        self.assertEqual(self._date_expr("Find media, judge, write bundle"),
                         self._date_expr("Commit the ask"))

    def test_both_steps_honour_the_dispatch_input(self):
        for name in ("Find media, judge, write bundle", "Commit the ask"):
            with self.subTest(step=name):
                self.assertIn('DATE="${{ inputs.date }}"', STEPS[name]["run"])

    def test_the_bundle_path_is_what_everything_downstream_reads(self):
        """`exchange/bundles/<date>/bundle.json` is the file the watchdog,
        the media worker and Phase B all look for."""
        commit = STEPS["Commit the ask"]["run"]
        self.assertIn('exchange/bundles/$DATE', commit)
        from shared import media_checkpoint as mc
        self.assertIn("exchange/bundles",
                      str(mc.BUNDLE_ROOT).replace("\\", "/"))

    def test_the_commit_is_marked_skip_ci(self):
        """Phase A commits packages and the bundle; without [skip ci] the
        push trigger above would start Phase A again from its own commit."""
        self.assertIn("[skip ci]", STEPS["Commit the ask"]["run"])


class TheWatchdogCoversTheGapAnyway(unittest.TestCase):
    """Triggers can all be right and GitHub can still not fire them — the
    2026-08-29/30 case. `phase_a_watchdog` is the independent check, and it
    must stay pointed at this workflow."""

    def test_the_watchdog_workflow_dispatches_phase_a(self):
        wd = (ROOT / ".github" / "workflows" / "phase_a_watchdog.yml")
        self.assertTrue(wd.exists(), "the readiness watchdog is gone")
        self.assertIn("exchange_phase_a.yml", wd.read_text())

    def test_the_watchdog_judges_before_the_media_worker_starts(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "phase_a_watchdog", ROOT / "scripts" / "phase_a_watchdog.py")
        w = importlib.util.module_from_spec(spec)
        sys.modules["phase_a_watchdog"] = w
        spec.loader.exec_module(w)
        self.assertLess(w.DEADLINE_CENTRAL, w.MEDIA_WORKER_CENTRAL,
                        "a watchdog that judges after the worker has already "
                        "needed the bundle reports a fact, not a warning")


class TheKillSwitchStillComesFirst(unittest.TestCase):
    def test_the_first_real_step_is_the_kill_switch(self):
        names = [s.get("name") for s in JOB["steps"]]
        self.assertEqual(names[0], "Checkout")
        self.assertEqual(names[1], "Pre-flight — kill switch")

    def test_a_paused_pipeline_stops_the_job(self):
        self.assertIn("exit 1", STEPS["Pre-flight — kill switch"]["run"])
        self.assertIn("PAUSED", STEPS["Pre-flight — kill switch"]["run"])


if __name__ == "__main__":
    unittest.main()
