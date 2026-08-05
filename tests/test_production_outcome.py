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

    python -m unittest tests.test_production_outcome -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
sys.path.append(str(ROOT / "scripts"))

DAILY = (ROOT / ".github" / "workflows" / "daily.yml").read_text()


class TestRedVersusPaused(unittest.TestCase):
    """The workflow's counter step IS the policy — pin its shape."""

    def counter_step(self) -> str:
        return DAILY.split("Update failure counter", 1)[1].split(
            "- name:", 1)[0]

    def test_the_run_still_goes_red_on_any_shortfall(self):
        """ChatGPT's visibility rule survives the repair: the orchestrator
        exits non-zero whenever production is incomplete."""
        src = (ROOT / "scripts" / "run_trending_daily.py").read_text()
        self.assertIn("if not complete:", src)
        self.assertIn("repair/retry required", src)

    def test_the_counter_reads_the_production_outcome(self):
        step = self.counter_step()
        self.assertIn("production_runs", step)
        self.assertIn("uploaded", step)

    def test_a_partial_day_does_NOT_bump_the_counter(self):
        step = self.counter_step()
        self.assertIn('"$UPLOADED" -gt 0', step)
        self.assertIn("Counter NOT bumped", step)

    def test_a_zero_upload_day_still_bumps_it(self):
        step = self.counter_step()
        self.assertIn("Zero uploads", step)
        self.assertIn("auto-pause at 2", step)

    def test_a_green_run_still_resets_it(self):
        self.assertIn('echo "0" > state/failure_count.txt',
                      self.counter_step())

    def test_the_policy_says_why_out_loud(self):
        """The comment is load-bearing: the next person to touch this step
        must meet the argument, not just the bash."""
        step = self.counter_step()
        self.assertIn("punishes the gate", step)
        self.assertIn("lower bar", step)


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
