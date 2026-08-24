"""A blocked story makes PROGRESS between runs instead of looping.

08-22 and 08-23 the same four slugs were rendered and blocked three times
each, both days, ~18 renders/day, zero ships — and the machinery built to
prevent exactly that was installed but disconnected at four separate
joints. Each test pins one joint:

  1. the rotate-to-back window was 20h against a ~24h cron, so a block
     always EXPIRED before the run that would have acted on it;
  2. `state/scene_plans/` (the repair loop's output, the thing that made a
     slug's score climb 39->43->48 within a run) was never in the persist
     list, so every day restarted from the identical baseline;
  3. the judge's `problems`/`fixes` were dropped from the durable ledger,
     leaving nothing for a cross-run re-planner to act on;
  4. no alarm distinguished "the runs are broken" from "the runs work and
     every video fails the bar" — opposite fixes, one symptom.

    python -m unittest tests.test_blocked_slug_churn -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))


class TestTheRotationWindowOutlivesTheCron(unittest.TestCase):

    def test_a_30h_old_block_still_rotates(self):
        """30h is yesterday's same-slot run: the case the 20h window lost."""
        import post_stories as ps
        with tempfile.TemporaryDirectory() as td:
            saved = ps.STATE_DIR
            ps.STATE_DIR = Path(td)
            try:
                led = Path(td) / "showrunner_verdicts.jsonl"
                old = (datetime.now(timezone.utc) - timedelta(hours=30))
                fresh = (datetime.now(timezone.utc) - timedelta(hours=2))
                led.write_text(
                    json.dumps({"ts": old.isoformat(timespec="seconds"),
                                "slug": "yesterday-block",
                                "verdict": "block"}) + "\n" +
                    json.dumps({"ts": fresh.isoformat(timespec="seconds"),
                                "slug": "today-block",
                                "verdict": "block"}) + "\n")
                got = ps._recent_gate_blocks()
                self.assertIn("yesterday-block", got,
                              "the window is shorter than the cron gap "
                              "again — the rotation can never fire")
                self.assertIn("today-block", got)
            finally:
                ps.STATE_DIR = saved

    def test_a_three_day_old_block_has_served_its_time(self):
        import post_stories as ps
        with tempfile.TemporaryDirectory() as td:
            saved = ps.STATE_DIR
            ps.STATE_DIR = Path(td)
            try:
                led = Path(td) / "showrunner_verdicts.jsonl"
                stale = (datetime.now(timezone.utc) - timedelta(hours=80))
                led.write_text(json.dumps(
                    {"ts": stale.isoformat(timespec="seconds"),
                     "slug": "ancient", "verdict": "block"}) + "\n")
                self.assertNotIn("ancient", ps._recent_gate_blocks())
            finally:
                ps.STATE_DIR = saved


class TestRepairProgressSurvivesTheRunner(unittest.TestCase):

    def test_scene_plans_are_in_the_persist_list(self):
        src = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        persist = src.split("Persist posted log + analytics", 1)[1]
        self.assertIn("state/scene_plans", persist)


class TestTheLedgerKeepsTheDiagnosis(unittest.TestCase):

    def test_problems_and_fixes_are_in_the_record(self):
        import showrunner_review as sr
        with tempfile.TemporaryDirectory() as td:
            saved = sr.LEDGER
            sr.LEDGER = Path(td) / "verdicts.jsonl"
            try:
                sr.append_ledger("slug-x", {
                    "score": 39, "verdict": "block",
                    "problems": ["seg1 is a bare number column"],
                    "fixes": ["place the markers on the countries"]})
                rec = json.loads(sr.LEDGER.read_text().splitlines()[0])
                self.assertEqual(rec["problems"],
                                 ["seg1 is a bare number column"])
                self.assertEqual(rec["fixes"],
                                 ["place the markers on the countries"])
            finally:
                sr.LEDGER = saved

    def test_a_chatty_verdict_is_bounded(self):
        import showrunner_review as sr
        with tempfile.TemporaryDirectory() as td:
            saved = sr.LEDGER
            sr.LEDGER = Path(td) / "verdicts.jsonl"
            try:
                sr.append_ledger("slug-x", {
                    "score": 39, "verdict": "block",
                    "problems": ["p" * 900] * 20, "fixes": []})
                rec = json.loads(sr.LEDGER.read_text().splitlines()[0])
                self.assertLessEqual(len(rec["problems"]), 6)
                self.assertLessEqual(len(rec["problems"][0]), 300)
            finally:
                sr.LEDGER = saved


class TestChurnRaisesItsOwnAlarm(unittest.TestCase):
    """Six-plus judged renders and zero ships is a QUALITY crisis and gets
    its own critical — no_posts_* alone cannot tell it apart from a broken
    workflow, and the two have opposite fixes."""

    def _run(self, rows):
        import daily_alarm as da
        with tempfile.TemporaryDirectory() as td:
            saved = da.ROOT
            da.ROOT = Path(td)
            try:
                (Path(td) / "state").mkdir()
                (Path(td) / "state" / "showrunner_verdicts.jsonl").write_text(
                    "\n".join(json.dumps(r) for r in rows) + "\n")
                # a mid-afternoon check, well past the deferral hour
                now = datetime(2026, 8, 22, 23, 0, tzinfo=timezone.utc)
                return da.check("20260822", now=now)
            finally:
                da.ROOT = saved

    @staticmethod
    def _rows(n_blocks, slugs, ships=0):
        rows = []
        for i in range(n_blocks):
            rows.append({"ts": f"2026-08-22T19:{i:02d}:00+00:00",
                         "slug": slugs[i % len(slugs)], "verdict": "block"})
        for i in range(ships):
            rows.append({"ts": f"2026-08-22T21:{i:02d}:00+00:00",
                         "slug": "winner", "verdict": "ship"})
        return rows

    def test_the_0822_shape_fires_critical(self):
        out = self._run(self._rows(12, ["a", "b", "c", "d"]))
        hit = [a for a in out["alarms"]
               if a["code"] == "showrunner_starving_the_slate"]
        self.assertTrue(hit, "the churn day raised no alarm again")
        self.assertEqual(hit[0]["severity"], "critical")
        self.assertIn("x3", hit[0]["detail"])

    def test_one_ship_stands_the_alarm_down(self):
        out = self._run(self._rows(12, ["a", "b"], ships=1))
        self.assertFalse([a for a in out["alarms"]
                          if a["code"] == "showrunner_starving_the_slate"])

    def test_a_normal_day_with_few_blocks_is_quiet(self):
        out = self._run(self._rows(3, ["a", "b", "c"]))
        self.assertFalse([a for a in out["alarms"]
                          if a["code"] == "showrunner_starving_the_slate"])

    def test_the_fix_text_defends_the_gate(self):
        """The alarm must never read as 'loosen the showrunner'."""
        out = self._run(self._rows(12, ["a"]))
        hit = [a for a in out["alarms"]
               if a["code"] == "showrunner_starving_the_slate"][0]
        self.assertIn("Weakening the gate is not on the table", hit["fix"])


class TestRetroCountsRealBlocks(unittest.TestCase):

    def test_the_count_is_case_insensitive(self):
        """The ledger writes lowercase "block"; the uppercase-only match
        reported 0 blocks on every real day since the ledger existed."""
        src = (ROOT / "scripts" / "build_retro.py").read_text()
        self.assertNotIn('v.get("verdict") == "BLOCK"', src)
        self.assertIn('.lower() == "block"', src)


if __name__ == "__main__":
    unittest.main()
