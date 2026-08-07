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


class TestChatGPTSilenceIsPaged(AlarmCase):
    """The 08-04..08-07 hole: Phase A published 10-12 image requests every
    morning, ChatGPT returned nothing, and every exchange alarm stayed
    quiet because they all key off a response that exists. Four days of
    weak self-fill stock — the exact media the showrunner kept blocking —
    with no page. Silence must page."""

    def _requests_bundle(self, n=10):
        self._bundle(bundle={"media_requests": [{"request_id": f"r{i}"}
                                                for i in range(n)]})

    def test_requests_out_nothing_back_is_an_alarm(self):
        self._requests_bundle()
        r = alarm.check(DATE, now=LATE)
        self.assertIn("chatgpt_exchange_silent", self.codes(r))

    def test_two_silent_days_escalate_to_critical(self):
        self._requests_bundle()
        import json as _json
        prev = self.tmp / "exchange" / "bundles" / "29991214"
        prev.mkdir(parents=True)
        (prev / "bundle.json").write_text(_json.dumps(
            {"media_requests": [{"request_id": "x"}]}))
        r = alarm.check(DATE, now=LATE)
        self.assertIn("chatgpt_exchange_silent", self.criticals(r))

    def test_a_single_checkpoint_counts_as_alive(self):
        """The STARTED/checkpoint heartbeat is exactly what distinguishes
        'ran and died' (visible, debuggable) from 'never ran' (this
        alarm)."""
        self._requests_bundle()
        mp = self.tmp / "exchange" / "bundles" / DATE / "media-progress"
        mp.mkdir()
        (mp / "STARTED.json").write_text("{}")
        r = alarm.check(DATE, now=LATE)
        self.assertNotIn("chatgpt_exchange_silent", self.codes(r))

    def test_a_response_counts_as_alive(self):
        self._requests_bundle()
        self._bundle(response={"media": []})
        r = alarm.check(DATE, now=LATE)
        self.assertNotIn("chatgpt_exchange_silent", self.codes(r))

    def test_a_day_with_no_requests_stays_quiet(self):
        self._bundle(bundle={"media_requests": []})
        r = alarm.check(DATE, now=LATE)
        self.assertNotIn("chatgpt_exchange_silent", self.codes(r))


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


class TestItCanActuallyREADEveryChannelsLog(AlarmCase):
    """The posted logs are not all the same shape, and assuming they were
    made the alarm blind to a whole channel.

        trending / explainer   {"posted": [ {...} ]}                 LIST
        third                  {"posted": {"clip-...": {...}}}       DICT

    Iterating a dict yields KEYS — strings — which the old loop skipped, so
    `no_posts_third` fired as CRITICAL on days third had posted its full
    slate. A false critical every morning is how people learn to ignore the
    real one, which is the exact failure this alarm exists to avoid."""

    def test_a_DICT_keyed_log_is_counted(self):
        p = self.tmp / "state" / "third_posted_log.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"posted": {
            f"clip-{DATE}-{i}": {"url": f"https://y/{i}", "title": f"t{i}",
                                 "ts": f"{DATE[:4]}-{DATE[4:6]}-"
                                       f"{DATE[6:8]}T12:00:00Z"}
            for i in range(3)}}))
        self.assertEqual(len(alarm._posted_on(p, DATE)), 3)

    def test_a_LIST_log_still_works(self):
        p = self.tmp / "state" / "posted_log.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        stamp = f"{DATE[:4]}-{DATE[4:6]}-{DATE[6:8]}T12:00:00Z"
        p.write_text(json.dumps({"posted": [{"title": "a",
                                             "posted_at": stamp}]}))
        self.assertEqual(len(alarm._posted_on(p, DATE)), 1)

    def test_refusals_and_claims_are_not_counted_as_posts(self):
        """third's log records what it REFUSED and slots it CLAIMED as well
        as what it shipped. On 2026-08-05 that was 5 refusals against 3 real
        uploads — counting rows would report a full slate on a short day.
        Overcounting hides an outage as effectively as undercounting
        invents one."""
        p = self.tmp / "state" / "third_posted_log.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        stamp = f"{DATE[:4]}-{DATE[4:6]}-{DATE[6:8]}T12:00:00Z"
        p.write_text(json.dumps({"posted": {
            "clip-1": {"url": "https://y/1", "ts": stamp},
            # a refusal, marked the way the real log marks them: by key
            # prefix and `qa_rejected` — there is no `status` field
            "rejected-abc": {"source_url": "https://t/x", "ts": stamp,
                             "qa_rejected": True, "streamer": "x"},
            # a claimed slot whose upload never completed
            "clip-2": {"ts": stamp, "title": "claimed but never uploaded"}}}))
        self.assertEqual(len(alarm._posted_on(p, DATE)), 1)

    def test_the_real_log_gives_the_number_a_human_would_count(self):
        real = ROOT / "state" / "third_posted_log.json"
        if not real.exists():
            self.skipTest("no third log in this checkout")
        posted = json.loads(real.read_text()).get("posted") or {}
        by_hand = sum(
            1 for k, v in posted.items()
            if isinstance(v, dict) and v.get("url")
            and str(v.get("ts", "")).startswith("2026-08-05"))
        self.assertEqual(len(alarm._posted_on(real, "20260805")), by_hand)

    def test_another_days_entries_are_excluded(self):
        p = self.tmp / "state" / "third_posted_log.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"posted": {
            "clip-1": {"url": "https://y/1", "ts": "2020-01-01T00:00:00Z"}}}))
        self.assertEqual(alarm._posted_on(p, DATE), [])

    def test_the_real_third_log_shape_parses(self):
        """Against the actual file on disk, not a fixture — the fixture is
        what was wrong last time."""
        real = ROOT / "state" / "third_posted_log.json"
        if not real.exists():
            self.skipTest("no third log in this checkout")
        entries = json.loads(real.read_text()).get("posted")
        self.assertIsInstance(entries, dict,
                              "third's log changed shape — re-check the "
                              "alarm's reader")


class TestAPausedChannelSaysSo(AlarmCase):
    """2026-08-03..05: trending posted nothing for three days because the
    auto-pause counter was stuck at 2, and every run reported success. The
    alarm said `no_posts_trending` each morning — true, and useless. It named
    the symptom while the cause sat in a one-byte file.

    A pause explains every other symptom; nothing else explains a pause. So
    it is checked first and it names the exact command that clears it."""

    def _counter(self, n):
        p = self.tmp / "state" / "failure_count.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{n}\n")

    def test_the_auto_pause_is_CRITICAL_and_names_itself(self):
        self._counter(2)
        r = alarm.check(DATE, now=LATE)
        self.assertIn("channel_auto_paused", self.criticals(r))

    def test_it_says_the_counter_cannot_clear_itself(self):
        self._counter(3)
        r = alarm.check(DATE, now=LATE)
        a = next(x for x in r["alarms"] if x["code"] == "channel_auto_paused")
        self.assertIn("CANNOT clear itself", a["fix"])
        self.assertIn("failure_count.txt", a["fix"])

    def test_one_failure_is_a_warning_not_a_pause(self):
        self._counter(1)
        r = alarm.check(DATE, now=LATE)
        self.assertNotIn("channel_auto_paused", self.codes(r))
        self.assertTrue(any("one more failing day" in n for n in r["notes"]))

    def test_a_healthy_counter_says_nothing(self):
        self._counter(0)
        r = alarm.check(DATE, now=LATE)
        self.assertNotIn("channel_auto_paused", self.codes(r))

    def test_a_missing_counter_is_not_a_pause(self):
        r = alarm.check(DATE, now=LATE)
        self.assertNotIn("channel_auto_paused", self.codes(r))

    def test_a_corrupt_counter_is_not_a_pause(self):
        p = self.tmp / "state" / "failure_count.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("not a number")
        r = alarm.check(DATE, now=LATE)
        self.assertNotIn("channel_auto_paused", self.codes(r))

    def test_the_kill_switch_files_are_reported_too(self):
        for switch, code in (("PAUSED", "paused_paused"),
                             ("PAUSED_DAILY", "paused_paused_daily")):
            (self.tmp / switch).write_text("")
            r = alarm.check(DATE, now=LATE)
            self.assertIn(code, self.criticals(r))
            (self.tmp / switch).unlink()

    def test_a_pause_is_shouted_even_mid_day(self):
        """Publishing checks defer until evening, but a pause is knowable at
        any hour and wastes the whole day if you learn it at 18:00."""
        self._counter(2)
        noon = datetime(2999, 12, 15, 15, 0, tzinfo=timezone.utc)
        r = alarm.check(DATE, now=noon)
        self.assertIn("channel_auto_paused", self.criticals(r))


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
