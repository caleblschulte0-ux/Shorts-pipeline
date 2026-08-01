"""The alarm must fire on the failures that were previously silent.

Every one of these is a real incident this pipeline had while every workflow
stayed green. If any of these tests stops failing-when-it-should, the alarm
has gone deaf and we are back to finding out days later.

    python -m unittest tests.test_daily_alarm -v
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

import daily_alarm as alarm                          # noqa: E402
from shared import channel_registry as reg           # noqa: E402

DATE = "29991215"
LATE = datetime(2999, 12, 16, 12, 0, tzinfo=timezone.utc)   # the day after


class AlarmCase(unittest.TestCase):
    """Redirect the repo paths the alarm reads into a scratch tree."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="alarm-"))
        self._root = alarm.ROOT
        alarm.ROOT = self.tmp
        (self.tmp / "state").mkdir(parents=True)
        (self.tmp / "exchange" / "bundles" / DATE).mkdir(parents=True)
        # A full slate for every channel, so a clean day really is clean.
        for cid in reg.channel_ids():
            log = reg.paths(cid).get("posted_log")
            if not log:
                continue
            n = reg.target_count(cid)
            self._write_log(log, n)

    def tearDown(self):
        alarm.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_log(self, rel, n):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        stamp = f"{DATE[:4]}-{DATE[4:6]}-{DATE[6:8]}T12:00:00Z"
        p.write_text(json.dumps(
            {"posted": [{"title": f"v{i}", "posted_at": stamp}
                        for i in range(n)]}))

    def _bundle(self, **files):
        d = self.tmp / "exchange" / "bundles" / DATE
        for name, obj in files.items():
            name = {"bundle": "bundle.json", "response": "response.json",
                    "report": "phase_b_report.json", "done": "DONE"}[name]
            (d / name).write_text(obj if isinstance(obj, str)
                                  else json.dumps(obj))

    def codes(self, result):
        return {a["code"] for a in result["alarms"]}

    def criticals(self, result):
        return {a["code"] for a in result["alarms"]
                if a["severity"] == "critical"}


class TestSilentOutage(AlarmCase):
    """2026-07-26..28: three days, zero videos, nothing alerted."""

    def test_a_day_that_shipped_nothing_is_CRITICAL(self):
        for cid in reg.channel_ids():
            log = reg.paths(cid).get("posted_log")
            if log:
                self._write_log(log, 0)
        r = alarm.check(DATE, now=LATE)
        self.assertFalse(r["ok"])
        self.assertIn("no_posts_trending", self.criticals(r))
        self.assertIn("no_posts_explainer", self.criticals(r))

    def test_a_short_slate_is_a_warning_not_a_crisis(self):
        self._write_log(reg.paths("trending")["posted_log"], 2)
        r = alarm.check(DATE, now=LATE)
        self.assertIn("short_slate_trending", self.codes(r))
        self.assertNotIn("short_slate_trending", self.criticals(r))

    def test_a_full_day_raises_nothing_about_posting(self):
        r = alarm.check(DATE, now=LATE)
        self.assertFalse({c for c in self.codes(r)
                          if c.startswith(("no_posts", "short_slate"))})


class TestTheWrongBundleBug(AlarmCase):
    """2026-08-01: ChatGPT finished, Phase B applied a two-day-old bundle,
    the run went green, 16 verified images were discarded."""

    def test_DONE_without_a_report_for_that_date_is_CRITICAL(self):
        self._bundle(bundle={"date": DATE}, done='{"date": "%s"}' % DATE,
                     response={"media": [{"request_id": "r1"}]})
        r = alarm.check(DATE, now=LATE)
        self.assertIn("done_but_no_report", self.criticals(r))

    def test_chatgpt_media_delivered_but_none_pinned_is_CRITICAL(self):
        self._bundle(bundle={"date": DATE}, done='{"date": "%s"}' % DATE,
                     response={"media": [{"request_id": f"r{i}"}
                                         for i in range(16)]},
                     report={"date": DATE,
                             "media": {"fulfilled": 0, "self_filled": 16}})
        r = alarm.check(DATE, now=LATE)
        self.assertIn("chatgpt_media_dropped", self.criticals(r))

    def test_a_partial_pin_is_only_a_warning(self):
        self._bundle(bundle={"date": DATE}, done='{"date": "%s"}' % DATE,
                     response={"media": [{"request_id": f"r{i}"}
                                         for i in range(16)]},
                     report={"date": DATE,
                             "media": {"fulfilled": 12, "refused": 4}})
        r = alarm.check(DATE, now=LATE)
        self.assertIn("chatgpt_media_partial", self.codes(r))
        self.assertNotIn("chatgpt_media_partial", self.criticals(r))

    def test_a_report_filed_under_the_wrong_date_is_CRITICAL(self):
        self._bundle(bundle={"date": DATE}, done='{"date": "%s"}' % DATE,
                     response={"media": []},
                     report={"date": "20260730", "media": {"fulfilled": 0}})
        r = alarm.check(DATE, now=LATE)
        self.assertIn("report_wrong_date", self.criticals(r))

    def test_a_healthy_exchange_says_nothing(self):
        self._bundle(bundle={"date": DATE}, done='{"date": "%s"}' % DATE,
                     response={"media": [{"request_id": f"r{i}"}
                                         for i in range(16)]},
                     report={"date": DATE, "media": {"fulfilled": 16}})
        r = alarm.check(DATE, now=LATE)
        self.assertFalse({c for c in self.codes(r) if "chatgpt" in c
                          or "report" in c or "done_but" in c})


class TestItDoesNotCryWolf(AlarmCase):
    """A false alarm teaches people to ignore the real one."""

    def test_mid_day_defers_the_publishing_checks(self):
        for cid in reg.channel_ids():
            log = reg.paths(cid).get("posted_log")
            if log:
                self._write_log(log, 0)
        noon = datetime(2999, 12, 15, 15, 0, tzinfo=timezone.utc)  # 9am CST
        r = alarm.check(DATE, now=noon)
        self.assertTrue(r["deferred"])
        self.assertFalse({c for c in self.codes(r)
                          if c.startswith("no_posts")})

    def test_a_clean_finished_day_exits_zero(self):
        self._bundle(bundle={"date": DATE}, done='{"date": "%s"}' % DATE,
                     response={"media": []}, report={"date": DATE,
                                                     "media": {}})
        r = alarm.check(DATE, now=LATE)
        self.assertTrue(r["ok"], [a["code"] for a in r["alarms"]])

    def test_it_never_raises_on_missing_or_junk_state(self):
        shutil.rmtree(self.tmp / "state", ignore_errors=True)
        (self.tmp / "exchange" / "bundles" / DATE / "bundle.json").write_text(
            "{not json")
        r = alarm.check(DATE, now=LATE)
        self.assertIn("alarms", r)

    def test_markdown_renders_without_blowing_up(self):
        r = alarm.check(DATE, now=LATE)
        self.assertIn(DATE, alarm.render(r))


class TestAnUnusableRegistryIsTheLoudestThing(AlarmCase):
    def test_it_reports_and_stops(self):
        from tests.registry_fixture import broken_registry
        with broken_registry():
            r = alarm.check(DATE, now=LATE)
        self.assertFalse(r["ok"])
        self.assertEqual(self.criticals(r), {"registry_unusable"})


class TestTheAlarmIsActuallyScheduled(unittest.TestCase):
    def test_a_workflow_runs_it_and_goes_red(self):
        wf = (ROOT / ".github" / "workflows" / "alarm.yml")
        self.assertTrue(wf.exists(), "the alarm is not wired to anything")
        text = wf.read_text()
        self.assertIn("scripts/daily_alarm.py", text)
        self.assertIn("gh issue comment", text)
        self.assertIn("exit 1", text)
        import yaml
        on = yaml.safe_load(text)[True]     # PyYAML parses bare `on:` as True
        self.assertIn("schedule", on)


if __name__ == "__main__":
    unittest.main()
