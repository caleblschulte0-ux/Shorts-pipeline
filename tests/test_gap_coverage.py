"""Tests for surviving a RECURRING authoring gap (the Claude weekly limit).

The reserve bank and the ChatGPT takeover exist for a gap that lasts a day
or three and happens several times a month — not for a one-off catastrophe.
That frequency changes what matters:

  * the stale-slate fallback becomes dangerous. `most_recent_package_dir()`
    serves yesterday's dir when today's is empty, and the only upload guard
    was a 6-HOUR window — so on day two of a gap it re-uploads day one's
    videos, 24h later, straight past that window.
  * a fallback brain stops being an incident and becomes a normal Tuesday,
    so it has to be visible in the daily report and the phone push.

    python -m unittest tests.test_gap_coverage -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_trending_daily as rtd                     # noqa: E402


class GapTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gap-"))
        self._saved = (rtd.PACKAGE_DIR, rtd.LOG_PATH)
        rtd.PACKAGE_DIR = self.tmp / "trending_packages"
        rtd.LOG_PATH = self.tmp / "posted_log.json"
        rtd.PACKAGE_DIR.mkdir(parents=True)

    def tearDown(self):
        rtd.PACKAGE_DIR, rtd.LOG_PATH = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_day(self, date: str, titles: list[str]) -> None:
        d = rtd.PACKAGE_DIR / date
        d.mkdir(parents=True, exist_ok=True)
        for i, t in enumerate(titles, 1):
            (d / f"0{i}_pkg.json").write_text(json.dumps(
                {"slug": f"slug-{i}", "title": t, "subreddit": "pettyrevenge",
                 "script": "x", "shots": []}))

    def mark_posted(self, titles: list[str]) -> None:
        rtd.LOG_PATH.write_text(json.dumps(
            {"posted": [{"title": t, "topic": t,
                         "posted_at": "2026-07-29T12:00:00Z"} for t in titles]}))

    def today(self) -> str:
        return rtd.todays_package_dir().name


class TestNoDuplicateUploads(GapTestCase):
    def test_stale_dir_already_posted_is_refused_entirely(self):
        """Day two of a gap: yesterday's slate is the most recent dir and
        every one of its videos is already on YouTube. Serving it again is
        the single worst outcome the posted log exists to prevent."""
        self.write_day("20260729", ["Story A", "Story B"])
        self.mark_posted(["Story A", "Story B"])
        d, pkgs = rtd.load_prewritten_packages()
        self.assertIsNone(d)
        self.assertEqual(pkgs, [])

    def test_stale_dir_keeps_only_the_unposted_packages(self):
        """A partial gap — some of yesterday's slate failed to upload. Those
        are still legitimately servable; the posted ones are not."""
        self.write_day("20260729", ["Story A", "Story B", "Story C"])
        self.mark_posted(["Story A"])
        d, pkgs = rtd.load_prewritten_packages()
        self.assertEqual(d.name, "20260729")
        self.assertEqual([p["title"] for p in pkgs], ["Story B", "Story C"])

    def test_todays_packages_win_and_are_untouched(self):
        self.write_day(self.today(), ["Fresh One", "Fresh Two"])
        self.write_day("20260729", ["Story A"])
        d, pkgs = rtd.load_prewritten_packages()
        self.assertEqual(d.name, self.today())
        self.assertEqual(len(pkgs), 2)

    def test_matching_is_case_and_whitespace_insensitive(self):
        self.write_day("20260729", ["  Story A  "])
        self.mark_posted(["story a"])
        self.assertEqual(rtd.load_prewritten_packages(), (None, []))

    def test_empty_posted_log_does_not_block_anything(self):
        self.write_day("20260729", ["Story A"])
        d, pkgs = rtd.load_prewritten_packages()
        self.assertEqual(len(pkgs), 1)

    def test_corrupt_posted_log_fails_open_not_shut(self):
        """A broken log must not wedge the channel — but it also must not
        pretend the log is empty when it can be read."""
        rtd.LOG_PATH.write_text("{not json")
        self.assertEqual(rtd.posted_titles(), set())


class TestFallbackBrainIsVisible(unittest.TestCase):
    """ntfy sends the first ~20 lines of daily_report.md to the phone, so a
    takeover has to appear at the very top or it may as well not be logged."""

    def _report(self, sources: list[str]) -> str:
        results = [{"ok": True, "topic": f"t{i}", "title": f"T{i}",
                    "video_url": "u", "elapsed_seconds": 1.0,
                    "source": s} for i, s in enumerate(sources)]
        return rtd.format_report("2026-08-01", results)

    def test_chatgpt_takeover_is_announced_in_the_first_lines(self):
        head = "\n".join(self._report(["chatgpt"] * 6).splitlines()[:20])
        self.assertIn("ChatGPT wrote 6", head)
        self.assertIn("weekly limit", head)

    def test_reserve_draw_is_announced_with_the_top_up_command(self):
        head = "\n".join(self._report(["reserve"] * 2 + ["brain"] * 4
                                      ).splitlines()[:20])
        self.assertIn("reserve bank", head)
        self.assertIn("package_reserve.py status", head)

    def test_a_mixed_day_reports_both(self):
        head = "\n".join(self._report(
            ["chatgpt", "chatgpt", "reserve", "brain"]).splitlines()[:20])
        self.assertIn("ChatGPT wrote 2", head)
        self.assertIn("1 package(s) came from the reserve", head)

    def test_a_normal_day_has_no_banner(self):
        report = self._report(["brain"] * 6)
        self.assertNotIn("ChatGPT wrote", report)
        self.assertNotIn("reserve bank", report)

    def test_missing_source_is_treated_as_the_brain(self):
        """Older report rows have no `source` key; they must not read as a
        fallback day."""
        results = [{"ok": True, "topic": "t", "title": "T", "video_url": "u",
                    "elapsed_seconds": 1.0}]
        self.assertNotIn("ChatGPT wrote",
                         rtd.format_report("2026-08-01", results))


if __name__ == "__main__":
    unittest.main(verbosity=2)
