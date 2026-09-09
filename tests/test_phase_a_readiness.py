"""Phase A must be GUARANTEED to have run before ChatGPT needs its bundle.

Doctor finding 5187e34e11f3. exchange_phase_a.yml has three triggers and
only one — a single cron with hours of documented drift — is independent of
upstream authoring having already happened. On 2026-08-29 and 2026-08-30 the
06:00 Central media worker reached the handoff with no bundle, and nothing
went red: chatgpt_watchdog read the missing bundle as "0 images requested"
and reported not_required, so the one check aimed at that morning excused
the failure it existed to catch.

    python -m unittest tests.test_phase_a_readiness -v
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
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import phase_a_watchdog as paw                          # noqa: E402
import chatgpt_watchdog as cw                           # noqa: E402
from shared import centraltime                          # noqa: E402

CDT_0300 = datetime(2026, 9, 9, 8, 0, tzinfo=timezone.utc)   # 03:00 Central
CDT_0700 = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)  # 07:00 Central


class TestTheClockIsJudgedLocally(unittest.TestCase):
    """Everything scheduled for humans is Central; crons are UTC and slip an
    hour at DST. A UTC-anchored deadline is right for half the year."""

    def test_before_the_hour_is_not_past_it(self):
        self.assertFalse(
            centraltime.deadline_passed("20260909", 5, CDT_0300))

    def test_after_the_hour_is_past_it(self):
        self.assertTrue(centraltime.deadline_passed("20260909", 5, CDT_0700))

    def test_an_earlier_date_is_always_judgeable(self):
        self.assertTrue(centraltime.deadline_passed("20260908", 23, CDT_0300))

    def test_a_later_date_is_never_judged_early(self):
        self.assertFalse(centraltime.deadline_passed("20260910", 0, CDT_0700))

    def test_an_unparseable_date_is_judged_not_skipped(self):
        self.assertTrue(centraltime.deadline_passed("nonsense", 5, CDT_0700))

    def test_the_timezone_is_defined_once(self):
        """Four modules had grown their own copy of this string, and the
        docs had grown two stale copies of the derived UTC hours."""
        self.assertEqual(centraltime.TZ, "America/Chicago")


class TestTheVerdict(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="paw-"))
        self._root = paw.ROOT
        paw.ROOT = self.tmp
        (self.tmp / "exchange" / "bundles").mkdir(parents=True)

    def tearDown(self):
        paw.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _bundle(self, date: str, **over):
        d = self.tmp / "exchange" / "bundles" / date
        d.mkdir(parents=True, exist_ok=True)
        body = {"bundle_id": f"b-{date}", "requests": [{"id": "x"}]}
        body.update(over)
        (d / "bundle.json").write_text(json.dumps(body))

    def test_a_present_bundle_is_ready(self):
        self._bundle("20260909")
        r = paw.evaluate("20260909", CDT_0700)
        self.assertEqual(r["status"], "ready")
        self.assertTrue(r["ok"])
        self.assertEqual(r["n_requests"], 1)

    def test_no_bundle_before_the_deadline_is_PENDING_not_a_failure(self):
        """Calling it missing before the deadline is how an alarm earns a
        reputation for lying."""
        r = paw.evaluate("20260909", CDT_0300)
        self.assertEqual(r["status"], "pending")
        self.assertTrue(r["ok"])

    def test_no_bundle_past_the_deadline_FAILS_CLOSED(self):
        r = paw.evaluate("20260909", CDT_0700)
        self.assertEqual(r["status"], "MISSING")
        self.assertFalse(r["ok"])
        self.assertIn("PHASE A HAS NOT RUN", r["headline"])

    def test_an_unreadable_bundle_counts_as_absent(self):
        d = self.tmp / "exchange" / "bundles" / "20260909"
        d.mkdir(parents=True)
        (d / "bundle.json").write_text("{not json")
        self.assertEqual(paw.evaluate("20260909", CDT_0700)["status"],
                         "MISSING")

    def test_the_verdict_round_trips_to_disk(self):
        self._bundle("20260909")
        paw.record(paw.evaluate("20260909", CDT_0700))
        self.assertEqual(paw.verdict("20260909")["status"], "ready")

    def test_no_verdict_on_disk_reads_as_None_not_a_crash(self):
        self.assertIsNone(paw.verdict("20991231"))


class TestTheMediaCheckStopsExcusingIt(unittest.TestCase):
    """The regression that let 08-29 and 08-30 pass green."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cw-"))
        self._cwroot, self._pawroot = cw.ROOT, paw.ROOT
        cw.ROOT = paw.ROOT = self.tmp
        (self.tmp / "exchange" / "bundles").mkdir(parents=True)

    def tearDown(self):
        cw.ROOT, paw.ROOT = self._cwroot, self._pawroot
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _verdict(self, date: str, status: str):
        d = self.tmp / "state" / "phase_a_readiness"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{date}.json").write_text(
            json.dumps({"date": date, "status": status}))

    def test_a_missing_bundle_with_a_MISSING_verdict_is_REQUIRED(self):
        """It used to return not_required -> ok -> green."""
        self._verdict("20260909", "MISSING")
        required, why = cw.media_expectation("20260909")
        self.assertTrue(required)
        self.assertIn("PHASE A NEVER RAN", why)

    def test_the_reason_points_at_the_readiness_record(self):
        self._verdict("20260909", "MISSING")
        self.assertIn("phase_a_readiness",
                      cw.media_expectation("20260909")[1])

    def test_it_still_does_not_blame_the_worker_before_a_verdict_exists(self):
        """The media worker cannot invent a bundle. With no readiness
        verdict yet we say so, rather than inventing blame."""
        required, why = cw.media_expectation("20260909")
        self.assertFalse(required)
        self.assertIn("not recorded", why)

    def test_a_real_bundle_with_no_requests_is_still_not_required(self):
        d = self.tmp / "exchange" / "bundles" / "20260909"
        d.mkdir(parents=True)
        (d / "bundle.json").write_text(json.dumps({"requests": []}))
        self.assertFalse(cw.media_expectation("20260909")[0])


class TestTheWorkflowHoldsItsShape(unittest.TestCase):
    WF = ROOT / ".github" / "workflows" / "phase_a_watchdog.yml"

    def setUp(self):
        import yaml
        self.y = yaml.safe_load(self.WF.read_text())
        self.body = self.WF.read_text()

    def test_the_crons_are_PAIRED_never_a_single_utc_hour(self):
        """05:00 Central is 10:00 UTC in summer and 11:00 in winter. A single
        UTC cron is correct for half the year — the trap that put Phase B's
        backstop before the finalizer."""
        crons = [c["cron"] for c in self.y[True]["schedule"]]
        self.assertEqual(sorted(crons), ["0 10 * * *", "0 11 * * *"])

    def test_it_judges_before_the_media_worker_starts(self):
        self.assertLess(paw.DEADLINE_CENTRAL, paw.MEDIA_WORKER_CENTRAL)

    def test_it_can_dispatch_phase_a(self):
        self.assertIn("actions", self.y["permissions"])
        self.assertIn("gh workflow run exchange_phase_a.yml", self.body)

    def test_it_judges_main_not_the_triggering_commit(self):
        """Phase A commits the bundle; a stale checkout is exactly how this
        reports a false MISSING and dispatches a duplicate."""
        self.assertIn("git fetch origin main", self.body)

    def test_the_verdict_is_persisted_even_on_failure(self):
        step = [s for s in self.y["jobs"]["readiness"]["steps"]
                if s.get("name") == "Persist the verdict"][0]
        self.assertEqual(step.get("if"), "always()")
        self.assertIn("state/phase_a_readiness", step["run"])

    def test_a_missing_bundle_fails_the_run(self):
        self.assertIn("exit 1", self.body)


class TestTheAlarmSaysIt(unittest.TestCase):
    def test_the_alarm_reads_the_readiness_verdict(self):
        """A verdict nothing surfaces is a capability nobody calls."""
        src = (ROOT / "scripts" / "daily_alarm.py").read_text()
        self.assertIn("phase_a_watchdog", src)
        self.assertIn("phase_a_never_ran", src)

    def test_it_evaluates_live_when_no_record_exists(self):
        """A watchdog that did not fire must not read as a clean day."""
        src = (ROOT / "scripts" / "daily_alarm.py").read_text()
        self.assertIn("_paw.evaluate(date)", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
