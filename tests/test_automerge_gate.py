"""The auto-merge unit gate must be able to FAIL.

Doctor finding 03ed6ae9f195 (critical, 2026-08-24): auto-merge.yml ran the
full suite as `python -m unittest ... 2>&1 | tail -40`. GitHub's default
`run:` shell on Linux is `bash -e {0}` — WITHOUT pipefail — so the step's
status was tail's zero even when unittest exited red, and `automerge`
would squash-merge a branch whose unit suite failed. The gate existed
because "a suite that never runs is decoration"; a suite whose failures
are discarded is the same decoration one file later.

Two pins:

  1. CONTRACT: the exact reporting wrapper the workflow uses (pipe to
     tail, run under the workflow's shell mode) must propagate a failing
     producer's status. This executes a real subprocess through the real
     pipe shape — a text assertion alone would miss a future shell-mode
     regression.
  2. WIRING: the workflow step actually enables pipefail before the pipe,
     so the contract proven in (1) is the contract CI runs under.

    python -m unittest tests.test_automerge_gate -v
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "auto-merge.yml"


class TestTheUnitGateCanFail(unittest.TestCase):

    def _pipe_status(self, script: str) -> int:
        """Run `script` the way the workflow's step runs its body: bash with
        errexit (GitHub's default `bash -e {0}`), body verbatim."""
        return subprocess.run(["bash", "-e", "-c", script]).returncode

    def test_a_failing_producer_survives_the_tail_pipe(self):
        """The doctor's reproduction, kept as the contract: exit 7 through
        the exact `producer 2>&1 | tail -40` shape must reach the step
        status once pipefail is on."""
        rc = self._pipe_status(
            "set -o pipefail\n(echo boom; exit 7) 2>&1 | tail -40")
        self.assertNotEqual(rc, 0, "a red producer was laundered to green")

    def test_without_pipefail_the_bug_is_real(self):
        """Sanity of the reproduction itself — under the plain default
        shell the failure IS discarded. If bash ever changes this, the
        wiring pin below is what keeps the gate honest."""
        rc = self._pipe_status("(echo boom; exit 7) 2>&1 | tail -40")
        self.assertEqual(rc, 0)

    def test_the_workflow_step_enables_pipefail(self):
        src = WF.read_text()
        body = src.split("name: Full unit suite", 1)[1].split("- name:", 1)[0]
        self.assertIn("set -o pipefail", body,
                      "the unit-suite step lost pipefail — its failures "
                      "no longer fail the gate")
        self.assertIn("python -m unittest discover -s tests", body)

    def test_no_other_unittest_pipe_in_the_gate_lacks_pipefail(self):
        """A future step that pipes a test run to tail/head without
        pipefail re-opens the same hole under a different name."""
        src = WF.read_text()
        for step in src.split("- name:")[1:]:
            code = "\n".join(l for l in step.splitlines()
                             if not l.strip().startswith("#"))
            piped = [l for l in code.splitlines()
                     if "unittest" in l and "| tail" in l]
            if piped:
                self.assertIn("set -o pipefail", code,
                              f"piped unittest without pipefail in step: "
                              f"{step.splitlines()[0].strip()}")


if __name__ == "__main__":
    unittest.main()
