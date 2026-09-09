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
        """WIRING only — the behaviour is tested by running it.

        This assertion, and the status check that used to sit below it,
        searched this step's TEXT for `workflows/daily.yml/dispatches`, a
        `HTTP.*!=.*204` regex and an `exit 1` within 400 characters. None of
        that runs anything: a refactor could leave those tokens in a comment
        or an unreachable branch while a rejected dispatch exited zero, and
        every assertion still passed (doctor finding d486c2fbfdaf).

        The dispatch-and-verify is `scripts/dispatch_render.py` now, and
        `tests/test_dispatch_render.py` executes it against 204,
        401/403/404/422, a 500, a timeout, a reset, a malformed response and
        a missing token — asserting the process exit code, which is what
        this workflow actually reads."""
        body = HANDOFF["run"]
        self.assertIn("scripts/dispatch_render.py", body,
                      "the step must call the tested dispatcher, not just "
                      "print that workflow_run will fire")
        self.assertIn("--workflow daily.yml", body)
        self.assertIn("--ref main", body)
        self.assertIn("GH_TOKEN", str(HANDOFF.get("env", {})),
                      "the dispatcher needs a token or it refuses to send")

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
        # The pre-flight that requires phase_b_report.json for a
        # workflow_run trigger. Matched by its full name, not by position
        # and not by the "Pre-flight" prefix: daily.yml grew a second
        # pre-flight step (the judge-secret check) and a prefix match
        # silently started asserting against that one instead.
        preflight_step = next(
            s for s in daily["jobs"]["daily"]["steps"]
            if s.get("name", "") == "Pre-flight — kill switch + failure counter")
        self.assertIn("phase_b_report.json", preflight_step["run"])


if __name__ == "__main__":
    unittest.main()
