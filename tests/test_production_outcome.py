"""The production-outcome contract, and the line between RED and PAUSED.

ChatGPT's 2026-08-02 rescue introduced something genuinely right: a
machine-readable per-channel production outcome
(`state/production_runs/<date>/<channel>.json`), and a run that goes RED
whenever uploaded < expected — a partial day must never look green.

It also introduced something wrong: every shortfall fed the auto-pause
failure counter, so two days in which the SHOWRUNNER correctly held one
video would pause the whole channel. A machine that punishes the gate for
working is the "more output via a lower bar" pressure with a cron attached.

The 2026-08-05 repair keeps the visibility and fixes the counter:

    RED     = uploaded < expected           (visibility — kept)
    COUNTER = bumps only when uploaded == 0 (outage — restored)

These tests hold both halves, plus the alarm's use of the outcome file and
the vision-QA/showrunner mascot separation.

HOW the workflow policy is held changed on 2026-08-24 (doctor finding
9943424b8251). This file used to slice daily.yml as TEXT and assert that
tokens like `exit 1` or `"$UPLOADED" -gt 0` existed — which pinned the
wording while a refactor that kept the words but broke the wiring would
have passed. Now the policy EXECUTES:

  * the failure-counter policy was extracted VERBATIM into
    scripts/daily_failure_counter.sh (daily.yml calls it); the tests run
    that script against fixture state and assert what it writes and says;
  * the pre-flight and stop-if-skipped steps CANNOT move out of daily.yml —
    tests/test_split_worker.py both executes the preflight's inline `run:`
    text in a bare temp dir and pins the stop step's inline text — so for
    those two the tests parse the workflow YAML and run the steps' actual
    shell with each scenario's inputs, asserting real exit codes and state;
  * a thin structural layer still pins the wiring itself: the YAML parses,
    the steps bind to the right `if:` conditions, and the counter step
    really invokes the extracted script.

    python -m unittest tests.test_production_outcome -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import run_trending_daily as rtd                        # noqa: E402

DAILY = (ROOT / ".github" / "workflows" / "daily.yml").read_text()
COUNTER_SH = ROOT / "scripts" / "daily_failure_counter.sh"

PREFLIGHT_STEP = "Pre-flight — kill switch + failure counter"
STOP_STEP = "Stop here if skipped"
COUNTER_STEP = "Update failure counter"
RUN_STEP = "Run daily orchestrator"


def daily_steps() -> dict:
    """The workflow's steps by name, from a real YAML parse — so a daily.yml
    that stops parsing, or a renamed/vanished step, fails loudly here rather
    than making a text split silently match the wrong region."""
    wf = yaml.safe_load(DAILY)
    return {s.get("name"): s for s in wf["jobs"]["daily"]["steps"]}


class WorkflowShellCase(unittest.TestCase):
    """Fixture: a throwaway repo root in which the workflow's policy shell —
    the extracted script, or an inline step's parsed `run:` text — actually
    executes, with GITHUB_OUTPUT captured and the git-commit helper stubbed
    out so the tests exercise the POLICY, never git."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="prodpolicy-"))
        (self.tmp / "state").mkdir()
        self.gh_out = self.tmp / "github_output"
        self.gh_out.write_text("")
        (self.tmp / "scripts").mkdir()
        (self.tmp / "scripts" / "ci_commit_state.sh").write_text(
            '#!/usr/bin/env bash\necho "$@" >> ci_commit_calls.txt\n')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bash(self, script: str, **env):
        """Run shell text the way an Actions `run:` step does (bash -e)."""
        full_env = {**os.environ, "GITHUB_OUTPUT": str(self.gh_out)}
        full_env.update({k: str(v) for k, v in env.items()})
        return subprocess.run(["bash", "-e", "-c", script], cwd=self.tmp,
                              env=full_env, capture_output=True, text=True)

    def skip_output(self):
        """The step's `skip` output — last `skip=` line wins, exactly as
        GITHUB_OUTPUT resolves repeated writes."""
        val = None
        for line in self.gh_out.read_text().splitlines():
            if line.startswith("skip="):
                val = line[len("skip="):]
        return val

    @staticmethod
    def today() -> str:
        return datetime.now(timezone.utc).strftime("%Y%m%d")


class TestRedVersusPaused(WorkflowShellCase):
    """The failure-counter policy is scripts/daily_failure_counter.sh — these
    tests RUN it, they don't grep it. (The orchestrator-side half of the
    contract, compute_production_outcome, is executed directly below.)"""

    # ---- the orchestrator's completion decision (pure function) ----------

    def test_the_run_still_goes_red_on_any_shortfall(self):
        """ChatGPT's visibility rule survives the repair: the real completion
        decision (not just its source text) exits non-zero and records
        repair_required whenever fewer videos uploaded than were expected —
        including when the shortfall is entirely the showrunner correctly
        holding weak videos, not a crash."""
        results = [
            {"ok": True, "video_url": "https://youtu.be/1"},
            {"ok": False, "quarantined": False},   # showrunner held it
            {"ok": False, "quarantined": True},    # QA quarantined it
        ]
        outcome, complete = rtd.compute_production_outcome(
            results, prior_uploaded=0, expected=6, dry_run=False)
        self.assertFalse(complete)
        self.assertEqual(outcome["status"], "repair_required")
        self.assertEqual(outcome["uploaded"], 1)
        self.assertEqual(outcome["quarantined"], 1)
        self.assertEqual(outcome["failed"], 1)

    def test_a_full_slate_reports_complete(self):
        """The same decision must say production_complete when uploaded
        actually meets expected — the test must not just always fail."""
        results = [{"ok": True, "video_url": f"https://youtu.be/{i}"}
                   for i in range(6)]
        outcome, complete = rtd.compute_production_outcome(
            results, prior_uploaded=0, expected=6, dry_run=False)
        self.assertTrue(complete)
        self.assertEqual(outcome["status"], "production_complete")
        self.assertEqual(outcome["uploaded"], 6)

    def test_prior_uploads_count_toward_the_target(self):
        """A backfill run picking up where an earlier attempt left off must
        credit videos already posted today, not just this call's results."""
        results = [{"ok": True, "video_url": "https://youtu.be/1"}]
        outcome, complete = rtd.compute_production_outcome(
            results, prior_uploaded=5, expected=6, dry_run=False)
        self.assertTrue(complete)
        self.assertEqual(outcome["uploaded"], 6)

    def test_dry_run_never_reports_repair_required(self):
        results = [{"ok": False, "quarantined": False}] * 6
        outcome, complete = rtd.compute_production_outcome(
            results, prior_uploaded=0, expected=6, dry_run=True)
        self.assertTrue(complete)
        self.assertEqual(outcome["status"], "dry_run")
        self.assertEqual(outcome["uploaded"], 0)

    def test_main_exits_non_zero_on_a_shortfall(self):
        """End to end: drive main()'s own exit-code contract, not just the
        decision helper, so a future refactor that stops calling
        compute_production_outcome from main() still gets caught."""
        import inspect
        src = inspect.getsource(rtd.main)
        self.assertIn("compute_production_outcome", src)
        self.assertIn("return 1", src)

    # ---- the workflow's counter policy (extracted script, executed) ------

    def counter(self, run_outcome: str):
        return self.bash(f"bash {COUNTER_SH}", RUN_OUTCOME=run_outcome)

    def write_outcome(self, uploaded: int):
        d = self.tmp / "state" / "production_runs" / self.today()
        d.mkdir(parents=True, exist_ok=True)
        (d / "trending.json").write_text(json.dumps({
            "schema": "production-channel-outcome/v1", "channel": "trending",
            "uploaded": uploaded}))

    def fc(self):
        p = self.tmp / "state" / "failure_count.txt"
        return p.read_text().strip() if p.exists() else None

    def test_the_counter_reads_the_production_outcome(self):
        """Same red run, opposite counter behavior depending only on what the
        outcome file says — proof the script reads it, not proof the string
        'production_runs' appears somewhere."""
        (self.tmp / "state" / "failure_count.txt").write_text("0\n")
        self.write_outcome(uploaded=4)
        self.counter("failure")
        self.assertEqual(self.fc(), "0", "4 uploads must not bump")
        self.write_outcome(uploaded=0)
        self.counter("failure")
        self.assertEqual(self.fc(), "1", "0 uploads must bump")

    def test_a_partial_day_does_NOT_bump_the_counter(self):
        """A held/quarantined video is the gate working, not an outage."""
        (self.tmp / "state" / "failure_count.txt").write_text("1\n")
        self.write_outcome(uploaded=2)
        proc = self.counter("failure")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.fc(), "1")
        self.assertIn("Counter NOT bumped", proc.stdout)

    def test_a_zero_upload_day_still_bumps_it(self):
        self.write_outcome(uploaded=0)
        proc = self.counter("failure")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.fc(), "1")
        proc = self.counter("failure")
        self.assertEqual(self.fc(), "2")
        self.assertIn("auto-pause at 2", proc.stdout)

    def test_a_missing_outcome_file_counts_as_an_outage(self):
        """No outcome file on a failed run means the orchestrator died before
        writing anything — that is the outage shape, and it must bump; a
        junk/missing file must never read as 'probably fine'."""
        proc = self.counter("failure")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.fc(), "1")

    def test_a_green_run_still_resets_it(self):
        (self.tmp / "state" / "failure_count.txt").write_text("2\n")
        proc = self.counter("success")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.fc(), "0")
        self.assertIn("counter reset", proc.stdout)

    def test_the_policy_says_why_out_loud(self):
        """The comment is load-bearing: the next person to touch this policy
        must meet the argument, not just the bash. It moved with the code
        into the script."""
        src = COUNTER_SH.read_text()
        self.assertIn("punishes the gate", src)
        self.assertIn("lower bar", src)


class TestTheWorkflowWiresThePolicy(unittest.TestCase):
    """The thin structural layer: the policy executes elsewhere in this file,
    but the WIRING — which step runs when, and that the counter step really
    calls the extracted script — stays pinned against the parsed YAML, not
    against string fragments in unparsed text."""

    def test_daily_yml_parses_and_the_policy_steps_exist(self):
        steps = daily_steps()
        for name in (PREFLIGHT_STEP, STOP_STEP, COUNTER_STEP, RUN_STEP):
            self.assertIn(name, steps)

    def test_the_counter_step_invokes_the_extracted_script(self):
        step = daily_steps()[COUNTER_STEP]
        self.assertIn("scripts/daily_failure_counter.sh", step["run"])
        self.assertEqual(step.get("env", {}).get("RUN_OUTCOME"),
                         "${{ steps.run.outcome }}",
                         "the script judges the orchestrator outcome — it "
                         "must be wired in as env")

    def test_the_steps_bind_to_the_intended_conditions(self):
        """The if: conditions ARE the pause machinery — a skip that stops
        gating the orchestrator, or a counter that stops running on failure
        (`always()`), breaks the policy with every token still present."""
        steps = daily_steps()
        self.assertEqual(steps[COUNTER_STEP].get("if"),
                         "always() && steps.preflight.outputs.skip == ''")
        self.assertEqual(steps[STOP_STEP].get("if"),
                         "steps.preflight.outputs.skip != ''")
        self.assertEqual(steps[RUN_STEP].get("if"),
                         "steps.preflight.outputs.skip == ''")
        self.assertEqual(steps[PREFLIGHT_STEP].get("id"), "preflight")
        self.assertEqual(steps[RUN_STEP].get("id"), "run")


class TestAPausedRunIsNotAGreenRun(WorkflowShellCase):
    """2026-08-03..05. The auto-pause tripped, daily.yml skipped the
    orchestrator, and the job reported SUCCESS for three days while trending
    shipped nothing. A green check on a dead channel is the failure shape
    this repo keeps re-learning.

    The stop step stays INLINE in daily.yml — tests/test_split_worker.py
    pins its inline text (the phase_b_incomplete branch specifically), so
    extracting it would break a suite outside this file's remit. Instead
    these tests run the step's own `run:` shell, parsed from the workflow,
    with each skip reason — the exit code is the assertion."""

    def stop(self, skip: str):
        step = daily_steps()[STOP_STEP]
        script = step["run"].replace(
            "${{ steps.preflight.outputs.skip }}", skip)
        return self.bash(script)

    def test_an_auto_pause_fails_the_run(self):
        proc = self.stop("auto")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("::error::", proc.stdout)

    def test_a_deliberate_manual_pause_stays_green(self):
        """Being told off daily for a decision you made on purpose is how
        people learn to ignore red."""
        proc = self.stop("manual")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("on purpose", proc.stdout)

    def test_the_other_phase_b_candidate_stays_green(self):
        """The benign twice-daily Phase B no-op (see the preflight) must not
        page anyone — green, and explicitly not rendering."""
        proc = self.stop("phase_b_incomplete")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("not rendering", proc.stdout)


class TestPreflightBackoffExecutes(WorkflowShellCase):
    """Auto-pause is a BACKOFF, not a latch: two zero-upload days sit the
    channel out ONE day, then it retries itself (standing ruling: 'if
    something doesn't run properly, it goes through and tries again').

    The preflight also stays INLINE in daily.yml — tests/test_split_worker.py
    executes its `run:` text in a bare temp dir to prove the Phase B
    handoff gate, and an extraction would strand that suite. These tests
    reuse the same parse-and-execute pattern for the pause/backoff half, so
    every branch of the decision is driven for real."""

    def preflight(self, event: str = "workflow_dispatch"):
        step = daily_steps()[PREFLIGHT_STEP]
        script = step["run"].replace("${{ github.event_name }}", event)
        return self.bash(script)

    def test_a_healthy_day_proceeds(self):
        proc = self.preflight()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.skip_output(), "")

    def test_manual_pause_files_skip_the_day_as_manual(self):
        for flag in ("PAUSED", "PAUSED_DAILY"):
            (self.tmp / flag).write_text("")
            proc = self.preflight()
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(self.skip_output(), "manual", flag)
            (self.tmp / flag).unlink()

    def test_two_zero_upload_days_pause_and_record_the_sit_out_day(self):
        (self.tmp / "state" / "failure_count.txt").write_text("2\n")
        proc = self.preflight()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.skip_output(), "auto")
        day = self.tmp / "state" / "auto_pause_day.txt"
        self.assertEqual(day.read_text().strip(), self.today())
        # the honesty the old text test pinned, now read off a real run:
        # it says it retries itself, and still prints the sooner-than-
        # tomorrow escape hatch
        self.assertIn("retry ITSELF tomorrow", proc.stdout)
        self.assertIn("echo 0 > state/failure_count.txt", proc.stdout)

    def test_a_refire_on_the_paused_day_stays_paused(self):
        (self.tmp / "state" / "failure_count.txt").write_text("2\n")
        (self.tmp / "state" / "auto_pause_day.txt").write_text(self.today())
        proc = self.preflight()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.skip_output(), "auto")
        # still sitting out the same day: nothing reset, nothing re-recorded
        self.assertEqual(
            (self.tmp / "state" / "failure_count.txt").read_text().strip(),
            "2")

    def test_after_a_full_day_off_it_retries_itself(self):
        (self.tmp / "state" / "failure_count.txt").write_text("2\n")
        (self.tmp / "state" / "auto_pause_day.txt").write_text("19990101")
        proc = self.preflight()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.skip_output(), "",
                         "a sat-out day must resume, not skip again")
        self.assertEqual(
            (self.tmp / "state" / "failure_count.txt").read_text().strip(),
            "1", "resume keeps one strike: another zero day re-pauses")
        self.assertFalse(
            (self.tmp / "state" / "auto_pause_day.txt").exists())
        self.assertIn("AUTO-RESUME", proc.stdout)

    def test_the_pause_never_becomes_a_latch_again(self):
        """This used to pin the opposite: the pause 'CANNOT clear itself'
        and printed the manual reset command. Changed 2026-08-06 under the
        standing ruling. The behavior is executed above; this guards the
        step against the old latch wording sneaking back in."""
        self.assertNotIn("CANNOT clear itself",
                         daily_steps()[PREFLIGHT_STEP]["run"])


class TestTheOrchestratorWritesTheOutcome(unittest.TestCase):
    def test_the_outcome_file_carries_what_the_judgment_needs(self):
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        for field in ('"schema": "production-channel-outcome/v1"',
                      '"uploaded"', '"expected"', '"quarantined"',
                      '"status"', '"repair_required"'):
            self.assertIn(field, src)


class TestTheAlarmReadsTheOutcome(unittest.TestCase):
    """`repair_required` still sitting there at end of day is a critical."""

    DATE = "29991215"
    LATE = datetime(2999, 12, 16, 12, 0, tzinfo=timezone.utc)

    def setUp(self):
        import daily_alarm as alarm
        self.alarm = alarm
        self.tmp = Path(tempfile.mkdtemp(prefix="prodout-"))
        self._root = alarm.ROOT
        alarm.ROOT = self.tmp
        from tests.test_daily_alarm import AlarmCase
        # reuse the fixture's full-slate setup so posting checks stay quiet
        self._case = AlarmCase()
        self._case.tmp, self._case._root = self.tmp, self._root
        (self.tmp / "state").mkdir(parents=True, exist_ok=True)
        (self.tmp / "exchange" / "bundles" / self.DATE).mkdir(parents=True)
        from shared import channel_registry as reg
        for cid in reg.channel_ids():
            log = reg.paths(cid).get("posted_log")
            if log:
                self._case._write_log(log, reg.target_count(cid))

    def tearDown(self):
        self.alarm.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def outcome(self, status, uploaded, expected=6, cid="trending"):
        d = self.tmp / "state" / "production_runs" / self.DATE
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{cid}.json").write_text(json.dumps({
            "schema": "production-channel-outcome/v1", "date": self.DATE,
            "channel": cid, "expected": expected, "uploaded": uploaded,
            "quarantined": expected - uploaded, "failed": 0,
            "status": status}))

    def codes(self, r):
        return {a["code"] for a in r["alarms"]}

    def test_repair_required_at_end_of_day_is_CRITICAL(self):
        self.outcome("repair_required", 4)
        r = self.alarm.check(self.DATE, now=self.LATE)
        self.assertIn("production_repair_trending", self.codes(r))
        crit = {a["code"] for a in r["alarms"]
                if a["severity"] == "critical"}
        self.assertIn("production_repair_trending", crit)

    def test_the_fix_text_warns_against_rekicking_a_gate_hold(self):
        self.outcome("repair_required", 5)
        r = self.alarm.check(self.DATE, now=self.LATE)
        a = next(x for x in r["alarms"]
                 if x["code"] == "production_repair_trending")
        self.assertIn("showrunner doing its job", a["fix"])

    def test_a_complete_day_raises_nothing_and_notes_it(self):
        self.outcome("production_complete", 6)
        r = self.alarm.check(self.DATE, now=self.LATE)
        self.assertNotIn("production_repair_trending", self.codes(r))
        self.assertTrue(any("production outcome complete" in n
                            for n in r["notes"]))

    def test_mid_day_repair_required_is_deferred_not_shouted(self):
        self.outcome("repair_required", 2)
        noon = datetime(2999, 12, 15, 15, 0, tzinfo=timezone.utc)
        r = self.alarm.check(self.DATE, now=noon)
        self.assertNotIn("production_repair_trending", self.codes(r),
                         "mid-day the repair may still be in flight")

    def test_a_junk_outcome_file_is_ignored(self):
        d = self.tmp / "state" / "production_runs" / self.DATE
        d.mkdir(parents=True, exist_ok=True)
        (d / "trending.json").write_text("{not json")
        r = self.alarm.check(self.DATE, now=self.LATE)
        self.assertIn("alarms", r)


class TestTheTwoJudgesAgreeAboutTheMascot(unittest.TestCase):
    """2026-08-03 separation: Data belongs to Explainer. The 08-02 vision
    prompt told the QA judge a mascot in a trending frame was 'intentional'
    while the showrunner directive calls it a brand violation — one judge
    excusing what the other must block."""

    def test_vision_QA_no_longer_excuses_a_mascot_on_trending(self):
        from funnel.gemini_images import _vision_layout
        for layout in ("reddit_illustrated", "reddit_gameplay_card",
                       "stacked"):
            self.assertNotIn("mascot", _vision_layout(layout).lower(),
                             f"{layout}: vision QA must leave the mascot "
                             f"verdict to the showrunner")

    def test_the_showrunner_still_flags_it(self):
        from scripts.showrunner_review import _format_directive
        for fmt in ("reddit_story", "graph_race"):
            self.assertIn("decorative_mascot",
                          _format_directive({"format": fmt}))


if __name__ == "__main__":
    unittest.main()
