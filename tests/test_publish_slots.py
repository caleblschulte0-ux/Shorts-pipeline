"""Publish slots must be 8:00/9:30/11:00... CENTRAL, not drifting UTC.

Operator ruling 2026-07-30. The old list was hardcoded UTC hours, which would
silently shift the real posting time by an hour at every DST changeover, and
could not express half-hour slots at all.

    python -m unittest tests.test_publish_slots -v
"""
from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_trending_daily as rtd  # noqa: E402

CT = ZoneInfo("America/Chicago")


def central(iso: str) -> datetime:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc).astimezone(CT)


class TestPublishSlots(unittest.TestCase):
    def test_summer_slots_are_central_wall_clock(self):
        got = rtd.schedule_times(
            datetime(2026, 7, 30, 6, 30, tzinfo=timezone.utc), 6)
        self.assertEqual([f"{central(t):%H:%M}" for t in got],
                         ["08:00", "09:30", "11:00", "12:30", "14:00", "15:30"])

    def test_winter_slots_are_the_SAME_wall_clock(self):
        """The DST case a hardcoded UTC list gets wrong."""
        got = rtd.schedule_times(
            datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc), 6)
        self.assertEqual([f"{central(t):%H:%M}" for t in got],
                         ["08:00", "09:30", "11:00", "12:30", "14:00", "15:30"])

    def test_summer_and_winter_differ_in_UTC(self):
        """Same local time => different UTC. Proves it is not fixed-offset."""
        s = rtd.schedule_times(datetime(2026, 7, 30, 6, 30, tzinfo=timezone.utc), 1)[0]
        w = rtd.schedule_times(datetime(2026, 1, 15, 6, 30, tzinfo=timezone.utc), 1)[0]
        self.assertTrue(s.endswith("13:00:00Z"), s)   # CDT = UTC-5
        self.assertTrue(w.endswith("14:00:00Z"), w)   # CST = UTC-6

    def test_ninety_minute_spacing(self):
        got = rtd.schedule_times(
            datetime(2026, 7, 30, 6, 30, tzinfo=timezone.utc), 6)
        times = [central(t) for t in got]
        for a, b in zip(times, times[1:]):
            self.assertEqual((b - a).total_seconds(), 90 * 60)

    def test_late_run_rolls_into_tomorrow(self):
        got = rtd.schedule_times(
            datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc), 6)
        self.assertEqual(f"{central(got[0]):%H:%M}", "12:30")
        self.assertEqual(f"{central(got[-1]):%H:%M}", "11:00")
        self.assertGreater(central(got[-1]).day, central(got[0]).day)

    def test_all_slots_are_in_the_future(self):
        now = datetime(2026, 7, 30, 6, 30, tzinfo=timezone.utc)
        for t in rtd.schedule_times(now, 6):
            self.assertGreater(
                datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc), now)

    def test_env_override(self):
        os.environ["PUBLISH_SLOTS_CENTRAL"] = "7:00, 7:45 ,18:15"
        try:
            self.assertEqual(rtd._publish_slots(), [(7, 0), (7, 45), (18, 15)])
            got = rtd.schedule_times(
                datetime(2026, 7, 30, 6, 0, tzinfo=timezone.utc), 3)
            self.assertEqual([f"{central(t):%H:%M}" for t in got],
                             ["07:00", "07:45", "18:15"])
        finally:
            os.environ.pop("PUBLISH_SLOTS_CENTRAL", None)

    def test_bad_override_falls_back_to_default(self):
        os.environ["PUBLISH_SLOTS_CENTRAL"] = "garbage,,nope"
        try:
            self.assertEqual(rtd._publish_slots(),
                             list(rtd.DEFAULT_PUBLISH_SLOTS_CENTRAL))
        finally:
            os.environ.pop("PUBLISH_SLOTS_CENTRAL", None)

    def test_returns_utc_iso_for_the_youtube_api(self):
        for t in rtd.schedule_times(
                datetime(2026, 7, 30, 6, 30, tzinfo=timezone.utc), 6):
            self.assertRegex(t, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
