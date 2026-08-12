"""A scheduled task that fires and commits nothing must READ as a failure.

2026-08-12. All three ChatGPT scheduled tasks fired on time — media ~06:03
CT, finalizer ~07:03, doctor overnight — and left nothing in the repo: no
`media-progress/STARTED.json`, no `response.json`, no `DONE`, no
`doctor/reports/20260812.json`.

The bundle was not the problem. Today's bundle is structurally identical to
yesterday's (same schema, mode "author", 13 well-formed requests present when
the media worker fired), and yesterday the very same task committed a
STARTED.json heartbeat, sixteen checkpoints, a response and a DONE.

The decisive observation is STEP 0. The heartbeat is one small JSON commit
made before any real work: no Drive, no image generation, no bundle parsing.
It depends on exactly ONE capability — the ability to write to the repo — and
it did not land, on the same day, for all three tasks. That capability is not
something the repo can grant. What the repo CAN stop doing is depending on it
silently:

  * `daily_alarm` runs at 01:15 UTC, so a 06:03 CT failure went unreported
    for ~20 hours — long past the point where re-firing could save the day;
  * an empty `media-progress/` reads identically whether the worker failed or
    the day genuinely had no media requests;
  * a missing watchdog record would have been silent in exactly the same way,
    which is why the alarm evaluates live when no record exists.

    python -m unittest tests.test_chatgpt_watchdog -v
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
# APPEND, never insert: scripts/ has its own test_*.py and putting it first
# shadows the real tests package during discovery.
sys.path.append(str(ROOT / "scripts"))

AFTER = datetime(2026, 8, 12, 13, 0, tzinfo=timezone.utc)    # 08:00 CT
BEFORE = datetime(2026, 8, 12, 10, 30, tzinfo=timezone.utc)  # 05:30 CT


class WatchdogCase(unittest.TestCase):
    DATE = "20260812"

    def setUp(self):
        import chatgpt_watchdog as w
        self.w = w
        self.tmp = Path(tempfile.mkdtemp(prefix="watchdog-"))
        self._root = w.ROOT
        w.ROOT = self.tmp
        self.bundle_dir = self.tmp / "exchange" / "bundles" / self.DATE
        self.bundle_dir.mkdir(parents=True)
        (self.tmp / "doctor" / "reports").mkdir(parents=True)

    def tearDown(self):
        self.w.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def bundle(self, n_requests=12):
        (self.bundle_dir / "bundle.json").write_text(json.dumps({
            "date": self.DATE, "mode": "author",
            "requests": [{"request_id": f"r{i}"} for i in range(n_requests)]}))

    def progress(self, *names):
        d = self.bundle_dir / "media-progress"
        d.mkdir(exist_ok=True)
        for n in names:
            (d / n).write_text("{}")


class TestTodaysActualFailure(WatchdogCase):
    """The exact 2026-08-12 state: a real bundle, zero artifacts."""

    def test_media_reads_as_failed_not_idle(self):
        self.bundle()
        r = self.w.evaluate("media", self.DATE, now=AFTER)
        self.assertEqual(r["status"], "FAILED_NO_ARTIFACT")
        self.assertIn("CHATGPT TASK FAILED", r["headline"])

    def test_finalizer_reads_as_failed(self):
        self.bundle()
        self.assertEqual(
            self.w.evaluate("finalizer", self.DATE, now=AFTER)["status"],
            "FAILED_NO_ARTIFACT")

    def test_doctor_is_only_judged_after_its_NIGHTLY_deadline(self):
        """The doctor files around 23:00 CT, so at 08:00 CT it is not late —
        it has not been asked yet. Judging it in the morning would report a
        failure every single day, including days it works."""
        self.assertEqual(
            self.w.evaluate("doctor", self.DATE, now=AFTER)["status"],
            "pending")
        nextday = datetime(2026, 8, 13, 6, 0, tzinfo=timezone.utc)
        self.assertEqual(
            self.w.evaluate("doctor", self.DATE, now=nextday)["status"],
            "FAILED_NO_ARTIFACT")

    def test_the_headline_names_the_task_and_the_date(self):
        self.bundle()
        h = self.w.evaluate("media", self.DATE, now=AFTER)["headline"]
        self.assertIn("media", h)
        self.assertIn(self.DATE, h)


class TestTheDayThatWorkedStaysGreen(WatchdogCase):
    """2026-08-11 really did land its artifacts. An alarm that also fires on
    the good day is worth nothing."""

    def test_a_heartbeat_alone_is_enough_to_pass(self):
        """STEP 0 is the contract's own definition of showing up."""
        self.bundle()
        self.progress("STARTED.json")
        self.assertEqual(
            self.w.evaluate("media", self.DATE, now=AFTER)["status"], "ok")

    def test_checkpoints_pass(self):
        self.bundle()
        self.progress("STARTED.json", "reddit-a-s0-abc.json")
        self.assertEqual(
            self.w.evaluate("media", self.DATE, now=AFTER)["status"], "ok")

    def test_a_FAILED_note_is_a_SUCCESSFUL_heartbeat(self):
        """The worker showed up and said what blocked it. That is the
        contract working — 'silence is the one output never acceptable'."""
        self.bundle()
        self.progress("FAILED-reddit-a-s0.json")
        self.assertEqual(
            self.w.evaluate("media", self.DATE, now=AFTER)["status"], "ok")

    def test_response_plus_done_passes(self):
        self.bundle()
        (self.bundle_dir / "response.json").write_text("{}")
        (self.bundle_dir / "DONE").write_text("")
        self.assertEqual(
            self.w.evaluate("finalizer", self.DATE, now=AFTER)["status"], "ok")

    def test_a_filed_doctor_report_passes(self):
        (self.tmp / "doctor" / "reports" / f"{self.DATE}.json").write_text("{}")
        self.assertEqual(
            self.w.evaluate("doctor", self.DATE, now=AFTER)["status"], "ok")


class TestItDoesNotCryWolf(WatchdogCase):

    def test_a_day_with_no_media_requests_is_not_a_failure(self):
        self.bundle(n_requests=0)
        r = self.w.evaluate("media", self.DATE, now=AFTER)
        self.assertEqual(r["status"], "not_required")

    def test_no_bundle_at_all_is_not_a_worker_failure(self):
        """Phase A has not run — that is Phase A's problem, not ChatGPT's."""
        (self.bundle_dir / "bundle.json").unlink(missing_ok=True)
        for t in ("media", "finalizer"):
            self.assertEqual(
                self.w.evaluate(t, self.DATE, now=AFTER)["status"],
                "not_required")

    def test_before_the_deadline_it_is_pending_not_failed(self):
        """Calling a task failed before its deadline is how an alarm earns a
        reputation for lying."""
        self.bundle()
        self.assertEqual(
            self.w.evaluate("media", self.DATE, now=BEFORE)["status"],
            "pending")

    def test_the_deadline_is_judged_in_CENTRAL_time(self):
        """The crons fire at fixed UTC hours and drift an hour at DST; the
        tasks are scheduled in local time. Judging in UTC is the bug that put
        Phase B's backstop before the finalizer for half of every year."""
        self.bundle()
        # 12:30 UTC is 07:30 CDT — past the 07:00 media deadline
        late = datetime(2026, 8, 12, 12, 30, tzinfo=timezone.utc)
        self.assertEqual(
            self.w.evaluate("media", self.DATE, now=late)["status"],
            "FAILED_NO_ARTIFACT")

    def test_a_past_date_is_always_judged(self):
        self.bundle()
        nextday = datetime(2026, 8, 13, 3, 0, tzinfo=timezone.utc)
        self.assertEqual(
            self.w.evaluate("media", self.DATE, now=nextday)["status"],
            "FAILED_NO_ARTIFACT")


class TestPartialClosureIsItsOwnState(WatchdogCase):
    """response.json without DONE is authored work that will never render —
    distinct from both success and a no-show."""

    def test_response_without_done_is_not_ok(self):
        self.bundle()
        (self.bundle_dir / "response.json").write_text("{}")
        r = self.w.evaluate("finalizer", self.DATE, now=AFTER)
        self.assertTrue(r["partial"])
        self.assertNotEqual(r["status"], "ok")

    def test_done_without_response_is_not_ok_either(self):
        self.bundle()
        (self.bundle_dir / "DONE").write_text("")
        self.assertNotEqual(
            self.w.evaluate("finalizer", self.DATE, now=AFTER)["status"], "ok")


class TestTheRecordAndTheExitCode(WatchdogCase):

    def test_it_records_a_machine_readable_verdict(self):
        self.bundle()
        p = self.w.record(self.w.evaluate("media", self.DATE, now=AFTER))
        obj = json.loads(p.read_text())
        self.assertEqual(obj["schema"], "chatgpt-task-outcome/v1")
        self.assertEqual(obj["status"], "FAILED_NO_ARTIFACT")
        self.assertIn("checked_at", obj)

    def test_outcomes_reads_back_what_it_wrote(self):
        self.bundle()
        self.w.record(self.w.evaluate("media", self.DATE, now=AFTER))
        self.assertIn("media", self.w.outcomes(self.DATE))

    def test_outcomes_of_an_unjudged_date_is_empty_not_an_error(self):
        self.assertEqual(self.w.outcomes("29991231"), {})


class TestTheAlarmReportsIt(unittest.TestCase):
    """The verdict has to reach the thing that shouts."""

    def setUp(self):
        import chatgpt_watchdog as w
        import daily_alarm as alarm
        self.w, self.alarm = w, alarm
        self.tmp = Path(tempfile.mkdtemp(prefix="wdalarm-"))
        self._wr, self._ar = w.ROOT, alarm.ROOT
        w.ROOT = alarm.ROOT = self.tmp
        (self.tmp / "exchange" / "bundles" / "20260812").mkdir(parents=True)
        (self.tmp / "exchange" / "bundles" / "20260812"
         / "bundle.json").write_text(json.dumps(
             {"requests": [{"request_id": "r0"}]}))
        (self.tmp / "doctor" / "reports").mkdir(parents=True)
        (self.tmp / "state").mkdir(exist_ok=True)

    def tearDown(self):
        self.w.ROOT, self.alarm.ROOT = self._wr, self._ar
        shutil.rmtree(self.tmp, ignore_errors=True)

    def codes(self):
        r = self.alarm.check("20260812", now=AFTER)
        return {a["code"]: a["severity"] for a in r["alarms"]}, r

    def test_each_failed_task_is_a_named_critical(self):
        codes, r = self.codes()
        for t in ("media", "finalizer"):
            self.assertEqual(codes.get(f"chatgpt_task_failed_{t}"), "critical",
                             f"{t} not reported critical")
        self.assertFalse(r["ok"])

    def test_a_missing_watchdog_record_is_NOT_silent(self):
        """If the watchdog itself never ran, the alarm must still answer —
        otherwise this fix just moves the blind spot up one level."""
        self.assertEqual(self.w.outcomes("20260812"), {})
        codes, _r = self.codes()
        self.assertIn("chatgpt_task_failed_media", codes)

    def test_it_says_when_the_verdict_was_computed_live(self):
        r = self.alarm.check("20260812", now=AFTER)
        a = next(x for x in r["alarms"]
                 if x["code"] == "chatgpt_task_failed_media")
        self.assertIn("watchdog record", a["fix"])

    def test_a_recorded_verdict_is_used_as_is(self):
        self.w.record(self.w.evaluate("media", "20260812", now=AFTER))
        codes, _r = self.codes()
        self.assertEqual(codes.get("chatgpt_task_failed_media"), "critical")

    def test_the_old_heuristic_stops_double_reporting(self):
        """One outage, reported once. Saying it twice in different words
        makes the report harder to read, not louder."""
        codes, _r = self.codes()
        self.assertNotEqual(codes.get("chatgpt_exchange_silent"), "critical")


if __name__ == "__main__":
    unittest.main()
