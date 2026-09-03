"""A real Phase B apply must produce a VERIFIED render handoff.

Doctor finding 2fc5cbb21cca (critical, 2026-08-25): exchange_phase_b.yml's
"Hand off to render" step used to only print that daily.yml's workflow_run
trigger would fire — it never dispatched anything and never checked that
GitHub actually scheduled a downstream run. On 2026-08-23 that assumption
broke live: run 32643778540 (the schedule backstop) completed successfully
and wrote exchange/bundles/20260823/phase_b_report.json — a genuine, real,
non-skipped apply — and a second candidate run also completed successfully,
yet the repository's Actions history shows ZERO daily.yml runs for that
date, not even a skipped one. Trending shipped zero, every check green.

This pins two things a plain read of the YAML can miss:

  1. WIRING: the job carries `actions: write` (required to call the
     workflow-dispatch API) and the "Hand off to render" step still only
     runs for a REAL apply (guarded by `steps.guard.outputs.skip != 'true'`,
     which distinguishes an applied candidate from the OTHER scheduled
     hour's no-op) and never on a dry run.
  2. CONTRACT: the step's body actually calls the workflows/daily.yml/
     dispatches endpoint and treats anything other than HTTP 204 as a
     failure (`exit 1`) rather than a printed notice — so a rejected
     dispatch fails the job loudly instead of completing green with
     nothing rendered downstream.

    python -m unittest tests.test_phase_b_render_handoff -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WF_PATH = ROOT / ".github" / "workflows" / "exchange_phase_b.yml"
WF = yaml.safe_load(WF_PATH.read_text())
JOB = WF["jobs"]["phase-b"]
STEPS = {s["name"]: s for s in JOB["steps"]}
HANDOFF = STEPS["Hand off to render"]


class TestTheHandoffIsVerifiedNotAssumed(unittest.TestCase):

    def test_job_can_call_the_dispatch_api(self):
        self.assertEqual(
            JOB.get("permissions", WF.get("permissions", {})).get("actions"),
            "write",
            "the workflow-dispatch API call in 'Hand off to render' needs "
            "actions: write — without it the dispatch below 403s")

    def test_handoff_only_runs_on_a_real_non_skipped_apply(self):
        guard = str(HANDOFF.get("if", ""))
        self.assertIn("steps.guard.outputs.skip != 'true'", guard,
                      "must not fire on the OTHER scheduled candidate's "
                      "no-op backstop hour")
        self.assertIn("dry_run != true", guard,
                      "must not fire on a --dry-run apply")

    def test_handoff_actually_dispatches_daily_yml(self):
        body = HANDOFF["run"]
        self.assertIn("workflows/daily.yml/dispatches", body,
                      "the step must call the real workflow-dispatch "
                      "endpoint, not just print that workflow_run will fire")
        self.assertIn('"ref":"main"', body.replace(" ", ""))

    def test_a_rejected_dispatch_fails_the_job(self):
        body = HANDOFF["run"]
        # The step must branch on the HTTP status and exit non-zero when
        # it is not 204 — a printed ::error with no exit is exactly the
        # "every check green, nothing rendered" shape this pins against.
        self.assertRegex(
            body, r'HTTP.*!=.*204',
            "must check the dispatch response status")
        status_check = body[body.index("204"):]
        self.assertIn("exit 1", status_check[:400],
                      "a non-204 response must fail the job, not just log")

    def test_workflow_run_fallback_is_still_wired(self):
        """Belt-and-suspenders: the explicit dispatch above is the fix, but
        daily.yml's workflow_run trigger must stay as a fallback route, and
        its own phase_b_report.json preflight must still gate it so neither
        route can render an unfinished day."""
        daily = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "daily.yml").read_text())
        on = daily.get(True, daily.get("on", {}))  # pyyaml parses bare `on:` as True
        self.assertIn("workflow_run", on)
        names = on["workflow_run"].get("workflows", [])
        self.assertIn(
            "Exchange Phase B (consume ChatGPT, self-fill, ready to render)",
            names)
        preflight = daily["jobs"]["daily"]["steps"][0]
        # First step after checkout should still be the pre-flight that
        # requires phase_b_report.json for a workflow_run trigger.
        preflight_step = next(
            s for s in daily["jobs"]["daily"]["steps"]
            if s.get("name", "").startswith("Pre-flight"))
        self.assertIn("phase_b_report.json", preflight_step["run"])


if __name__ == "__main__":
    unittest.main()
