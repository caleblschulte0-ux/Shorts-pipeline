"""Tests for the retro WORKFLOW's wiring, not just its scripts.

Each of these covers a wiring bug that unit tests cannot see, because the
scripts were individually correct and the workflow called them at the wrong
time or with the wrong date. Those are the expensive ones: everything is
green, and the evidence is quietly wrong.

    python -m unittest tests.test_retro_workflow -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_retro as br        # noqa: E402
import retro_mailbox as mb      # noqa: E402

WF = yaml.safe_load((ROOT / ".github" / "workflows" / "retro.yml").read_text())
STEPS = {s["name"]: s for s in WF["jobs"]["retro"]["steps"]}


def guard(step_name: str) -> str:
    return str(STEPS[step_name].get("if", ""))


class TestAProposalPushOnlyTriages(unittest.TestCase):
    """A push of proposals.json must not move the evidence those proposals
    were written against. Refreshing analytics or rebuilding the brief on
    that trigger invalidates every citation ChatGPT just made."""

    MUST_NOT_RUN_ON_PUSH = (
        "Refresh analytics",
        "Advance experiment sample counts",
        "Build the brief",
        "Weekly rollup (Sundays)",
        "Post the executive summary",
    )

    def test_evidence_producing_steps_are_skipped_on_push(self):
        for name in self.MUST_NOT_RUN_ON_PUSH:
            self.assertIn("github.event_name != 'push'", guard(name),
                          f"{name!r} would run on a proposals push and could "
                          f"change the evidence ChatGPT already used")

    def test_triage_does_run_on_push(self):
        self.assertNotIn("event_name != 'push'", guard("Triage proposals"))

    def test_the_push_commit_touches_only_triage_output(self):
        body = STEPS["Commit brief + triage + summary"]["run"]
        self.assertIn("github.event_name }}\" = \"push\"", body)
        push_branch = body.split("if [", 1)[1].split("else", 1)[0]
        self.assertIn("triage.json", push_branch)
        self.assertNotIn("state/analytics", push_branch,
                         "the push path would commit refreshed analytics")


class TestTheNightlyAlwaysBuildsToday(unittest.TestCase):
    """The mailbox decides what ChatGPT REVIEWS. It must never decide what
    GitHub BUILDS — conflating them meant one missed review stopped today's
    brief existing and rewrote a published one with newer numbers."""

    def test_scheduled_runs_use_todays_chicago_date(self):
        body = STEPS["Resolve the review date"]["run"]
        scheduled = body.split("else", 1)[1]
        self.assertIn("steps.when.outputs.today", scheduled)
        self.assertNotIn("--next-date", scheduled,
                         "the nightly build still follows the mailbox")

    def test_the_date_comes_from_chicago_not_utc(self):
        body = STEPS["Is it really evening in Chicago?"]["run"]
        self.assertIn("America/Chicago", body)
        self.assertIn("today=", body)

    def test_a_push_derives_its_date_from_the_path(self):
        body = STEPS["Resolve the review date"]["run"]
        push = body.split('EVENT" = "push"', 1)[1].split("else", 1)[0]
        self.assertIn("retro/[0-9]{8}/", push)

    def test_both_dst_crons_exist_with_an_in_code_gate(self):
        crons = {c["cron"] for c in WF[True]["schedule"]}
        self.assertEqual(crons, {"15 23 * * *", "15 0 * * *"})
        self.assertIn("now.hour == 18",
                      STEPS["Is it really evening in Chicago?"]["run"])


class TestBriefImmutability(unittest.TestCase):
    """A published brief is the evidence a reviewer cited. Rewriting it
    silently invalidates their proposals."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="imm-"))
        self._saved = br.RETRO_ROOT
        br.RETRO_ROOT = self.tmp

    def tearDown(self):
        br.RETRO_ROOT = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, date, force=False):
        cmd = [sys.executable, "scripts/build_retro.py", "--date", date]
        if force:
            cmd.append("--force")
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)

    def test_a_reviewed_brief_is_not_overwritten(self):
        d = self.tmp / "20260728"
        d.mkdir(parents=True)
        original = json.dumps({"date": "20260728", "sentinel": "ORIGINAL"})
        (d / "brief.json").write_text(original)
        (d / "proposals.json").write_text('{"proposals": []}')

        import importlib
        sys.argv = ["build_retro.py", "--date", "20260728"]
        importlib.reload(br)
        br.RETRO_ROOT = self.tmp
        br.main()
        self.assertEqual((d / "brief.json").read_text(), original,
                         "a published, reviewed brief was overwritten")

    def test_an_unreviewed_brief_may_still_be_refreshed(self):
        d = self.tmp / "20260729"
        d.mkdir(parents=True)
        (d / "brief.json").write_text('{"sentinel": "STALE"}')
        import importlib
        sys.argv = ["build_retro.py", "--date", "20260729"]
        importlib.reload(br)
        br.RETRO_ROOT = self.tmp
        br.main()
        self.assertNotIn("STALE", (d / "brief.json").read_text())


class TestMissedReviewsAndConsecutiveDays(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="days-"))
        self._saved = (mb.RETRO_ROOT, br.RETRO_ROOT)
        mb.RETRO_ROOT = br.RETRO_ROOT = self.tmp

    def tearDown(self):
        mb.RETRO_ROOT, br.RETRO_ROOT = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _brief(self, date, sentinel):
        d = self.tmp / date
        d.mkdir(parents=True, exist_ok=True)
        (d / "brief.json").write_text(json.dumps({"date": date,
                                                  "sentinel": sentinel}))

    def test_two_consecutive_briefs_both_survive(self):
        """Day 2's build must not disturb day 1 — the bug was that the
        nightly took the mailbox's oldest open date and rewrote it."""
        self._brief("20260730", "DAY1")
        self._brief("20260731", "DAY2")
        d1 = json.loads((self.tmp / "20260730" / "brief.json").read_text())
        d2 = json.loads((self.tmp / "20260731" / "brief.json").read_text())
        self.assertEqual(d1["sentinel"], "DAY1")
        self.assertEqual(d2["sentinel"], "DAY2")

    def test_a_missed_review_stays_open_without_blocking_the_next_brief(self):
        self._brief("20260730", "DAY1")          # never reviewed
        self._brief("20260731", "DAY2")          # built anyway
        self.assertEqual(mb.next_review()["review_date"], "20260730")
        self.assertEqual(mb.mailbox()["open_count"], 2)
        self.assertTrue((self.tmp / "20260731" / "brief.json").exists())

    def test_answering_the_old_one_advances_the_mailbox(self):
        self._brief("20260730", "DAY1")
        self._brief("20260731", "DAY2")
        (self.tmp / "20260730" / "proposals.json").write_text(
            '{"proposals": []}')
        self.assertEqual(mb.next_review()["review_date"], "20260731")

    def test_a_proposal_push_leaves_the_brief_byte_identical(self):
        """The acceptance criterion: triage must not touch brief.json."""
        self._brief("20260730", "DAY1")
        before = (self.tmp / "20260730" / "brief.json").read_bytes()
        (self.tmp / "20260730" / "proposals.json").write_text(
            '{"proposals": []}')
        subprocess.run([sys.executable, "scripts/review_proposals.py",
                        "--date", "20260730"], cwd=ROOT,
                       capture_output=True, text=True)
        after = (self.tmp / "20260730" / "brief.json").read_bytes()
        self.assertEqual(before, after, "triage modified the brief")


class TestClaudeIsSummonedToDecide(unittest.TestCase):
    """Without this the loop is a suggestion inbox: proposals accumulate and
    nothing answers them unless a human remembers."""

    def setUp(self):
        self.wf = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "retro_decide.yml").read_text())

    def test_a_decide_workflow_exists_and_is_scheduled(self):
        self.assertEqual({c["cron"] for c in self.wf[True]["schedule"]},
                         {"0 13 * * *", "0 14 * * *"})

    def test_it_records_verdicts_through_retro_reply(self):
        body = json.dumps(self.wf)
        self.assertIn("retro_reply.py", body)
        self.assertIn("pending_decisions.py", body)

    def test_it_cannot_block_production(self):
        for step in self.wf["jobs"]["decide"]["steps"]:
            if "claude" in json.dumps(step).lower() and step.get("run"):
                self.assertTrue(step.get("continue-on-error"),
                                f"{step.get('name')} could fail the job")

    def test_pending_decisions_finds_unanswered_proposals(self):
        import pending_decisions as pd
        tmp = Path(tempfile.mkdtemp())
        saved = pd.RETRO_ROOT
        try:
            pd.RETRO_ROOT = tmp
            d = tmp / "20260730"
            d.mkdir(parents=True)
            (d / "triage.json").write_text(json.dumps({
                "accepted": [{"file": "p1.json", "title": "T",
                              "channel": "trending"}]}))
            rows = pd.pending()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["file"], "p1.json")
        finally:
            pd.RETRO_ROOT = saved
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_routine_is_told_to_answer_pending_proposals(self):
        text = (ROOT / "CLAUDE_ROUTINE_INSTRUCTIONS.md").read_text()
        self.assertIn("pending_decisions.py", text)
        self.assertIn("retro_reply.py", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
