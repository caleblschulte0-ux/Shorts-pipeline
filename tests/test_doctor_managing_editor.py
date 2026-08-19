"""The doctor is the channels' MANAGING EDITOR, and the plumbing agrees.

Operator ruling 2026-08-16, verbatim intent: "it's supposed to take over
me ... it's like the manager, editor ... the whole overview guy of the
channel." The doctor loop was already reading code and shipping fixes
(#275, #278); what it could NOT do was manage — its evidence pack carried
alarms, production outcomes and verdicts, but no analytics, no posting
cadence, no retro briefs. A manager who cannot see performance is a code
reviewer with a grander title.

These tests pin the three pieces that make the mandate real:

  1. `strategy` is a first-class finding horizon — accepted by intake,
     ranked in the backlog between quick wins and long-term work;
  2. the evidence pack carries the manager's desk: per-channel posting
     cadence, top videos by views-per-hour, and pointers to the full
     analytics and retro briefs;
  3. both halves of the contract say it out loud — the reviewer is told to
     file strategy findings from performance data, and the triage is told
     to BUILD accepted ones as registry/doctrine changes, with the refusal
     list governing strategy exactly as it governs code.

    python -m unittest tests.test_doctor_managing_editor -v
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
# APPEND, never insert: scripts/ has its own test_*.py and putting it first
# shadows the real tests package during discovery.
sys.path.append(str(ROOT / "scripts"))

import doctor  # noqa: E402
import daily_alarm  # noqa: E402

PROMPTS = (ROOT / "doctor" / "PROMPTS.md").read_text()


class TestStrategyIsAFirstClassHorizon(unittest.TestCase):

    def test_intake_accepts_it(self):
        self.assertIn("strategy", doctor.HORIZONS)

    def test_it_ranks_between_quick_wins_and_long_term(self):
        r = doctor._HOR_RANK
        self.assertLess(r["small_fix"], r["strategy"])
        self.assertLess(r["strategy"], r["long_term"])
        self.assertLess(r["bug"], r["strategy"],
                        "a live bug always outranks a direction call")

    def test_every_horizon_is_ranked(self):
        """A horizon missing from the rank map silently sorts last — that is
        how a bucket becomes a place findings go to be ignored."""
        for h in doctor.HORIZONS:
            self.assertIn(h, doctor._HOR_RANK, h)


class TestTheEvidencePackCarriesTheDesk(unittest.TestCase):
    """Built against a fake ROOT so the test owns every file it reads."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mgr-"))
        self._root = doctor.ROOT
        doctor.ROOT = self.tmp
        (self.tmp / "state").mkdir()
        (self.tmp / "state" / "explainer_posted_log.json").write_text(
            json.dumps({"posted": {
                "a": {"at": "2026-08-14T10:00:00+00:00", "url": "u1"},
                "b": {"at": "2026-08-14T12:00:00+00:00", "url": "u2"},
                "old": {"at": "2026-01-01T00:00:00+00:00", "url": "u3"},
            }}))
        (self.tmp / "state" / "posted_log.json").write_text(
            json.dumps({"posted": [
                {"posted_at": "2026-08-15T09:00:00Z", "video_url": "v"}]}))
        adir = self.tmp / "state" / "analytics_explainer"
        adir.mkdir()
        (adir / "latest.json").write_text(json.dumps({"videos": [
            {"title": "Macao density", "vph": 1.25, "views": 210},
            {"title": "Hottest Planets", "vph": 0.48, "views": 900},
            {"title": "junk row without vph"},
        ]}))
        (self.tmp / "retro" / "20260814").mkdir(parents=True)
        (self.tmp / "retro" / "20260815").mkdir()

    def tearDown(self):
        doctor.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pack(self):
        return doctor.evidence_pack().get("channel_performance", {})

    def test_posting_cadence_is_in_the_pack(self):
        perf = self.pack()
        self.assertEqual(
            perf["explainer"]["posted_by_day_14d"].get("2026-08-14"), 2)
        self.assertEqual(perf["explainer"]["total_posted"], 3)

    def test_old_posts_do_not_pollute_the_window(self):
        self.assertNotIn("2026-01-01",
                         self.pack()["explainer"]["posted_by_day_14d"])

    def test_the_list_shaped_trending_log_reads_too(self):
        self.assertEqual(
            self.pack()["trending"]["posted_by_day_14d"].get("2026-08-15"), 1)

    def test_analytics_top_videos_by_vph(self):
        a = self.pack()["analytics_explainer"]
        self.assertEqual(a["videos"], 3)
        self.assertEqual(a["top_by_vph"][0]["vph"], 1.25)
        self.assertIn("full_data", a)

    def test_retro_briefs_are_pointed_at(self):
        self.assertEqual(self.pack()["retro_briefs"],
                         ["retro/20260814/brief.json",
                          "retro/20260815/brief.json"])

    def test_a_bare_repo_does_not_crash_the_pack(self):
        shutil.rmtree(self.tmp / "state")
        (self.tmp / "state").mkdir()
        self.assertIsInstance(self.pack(), dict)


class TestCadenceMatchesTheAlarmNotRawRows(unittest.TestCase):
    """The 2026-08-15 bug, pinned: third's log carries QA refusals and
    pending claims beside real uploads, and the desk used to count every
    row. This is the production-shaped fixture the doctor finding asked
    for — two real uploads, four refusals, and a pending claim, all with
    the mixed timestamp fields third's log actually uses — and it requires
    the desk to land on the exact same count the alarm already gets right."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mgr-cadence-"))
        self._root = doctor.ROOT
        doctor.ROOT = self.tmp
        (self.tmp / "state").mkdir()
        (self.tmp / "state" / "third_posted_log.json").write_text(
            json.dumps({"posted": {
                "clip-20260815-1": {"ts": "2026-08-15T09:00:00Z",
                                    "url": "https://youtu.be/a"},
                "clip-20260815-2": {"posted_at": "2026-08-15T11:00:00Z",
                                    "url": "https://youtu.be/b"},
                "rejected-clip-20260815-3": {"ts": "2026-08-15T08:00:00Z",
                                             "qa_rejected": True},
                "clip-20260815-4": {"ts": "2026-08-15T08:30:00Z",
                                    "qa_rejected": True},
                "clip-20260815-5": {"ts": "2026-08-15T08:45:00Z",
                                    "status": "rejected: low quality"},
                "clip-20260815-6": {"ts": "2026-08-15T08:50:00Z"},  # pending
            }}))
        (self.tmp / "state" / "posted_log.json").write_text(
            json.dumps({"posted": []}))
        (self.tmp / "state" / "explainer_posted_log.json").write_text(
            json.dumps({"posted": {}}))

    def tearDown(self):
        doctor.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_desk_and_the_alarm_agree_on_2_of_6(self):
        perf = doctor.evidence_pack()["channel_performance"]["third"]
        self.assertEqual(perf["posted_by_day_14d"].get("2026-08-15"), 2)
        self.assertEqual(perf["total_posted"], 2)

        alarm_count = len(daily_alarm._posted_on(
            self.tmp / "state" / "third_posted_log.json", "20260815"))
        self.assertEqual(alarm_count, 2)
        self.assertEqual(perf["posted_by_day_14d"]["2026-08-15"],
                         alarm_count)

    def test_attempted_and_excluded_are_preserved_not_laundered(self):
        """The fix must not just DROP the refusals — it must say how many
        there were, so a manager can still see a day with a rough shoot."""
        perf = doctor.evidence_pack()["channel_performance"]["third"]
        self.assertEqual(perf["attempted"], 6)
        self.assertEqual(perf["rejected_or_pending"], 4)


class TestTopByVphReadsTheProducersRealField(unittest.TestCase):
    """scripts/fetch_analytics.py writes `views_per_hour`; the desk used to
    read only `vph`, which the producer never emits, so every leaderboard
    was 0.0 ranked in source order."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mgr-vph-"))
        self._root = doctor.ROOT
        doctor.ROOT = self.tmp
        (self.tmp / "state").mkdir()
        for name in ("posted_log.json", "explainer_posted_log.json",
                    "third_posted_log.json"):
            (self.tmp / "state" / name).write_text(json.dumps({"posted": []}))
        adir = self.tmp / "state" / "analytics_explainer"
        adir.mkdir()
        (adir / "latest.json").write_text(json.dumps({"videos": [
            {"title": "Low", "views_per_hour": 0.5, "views": 34},
            {"title": "High", "views_per_hour": 2.1, "views": 412},
        ]}))

    def tearDown(self):
        doctor.ROOT = self._root
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ranking_uses_the_real_producer_field(self):
        a = doctor.evidence_pack()["channel_performance"]["analytics_explainer"]
        self.assertEqual(a["top_by_vph"][0]["title"], "High")
        self.assertEqual(a["top_by_vph"][0]["vph"], 2.1)


class TestTheContractSaysItOutLoud(unittest.TestCase):
    """The mandate has to live in the pointer target, or a future session
    trims it as prompt bloat and the doctor quietly demotes itself back to
    code reviewer."""

    def test_the_reviewer_is_told_it_is_the_manager(self):
        self.assertIn("MANAGING EDITOR", PROMPTS)
        self.assertIn('horizon: "strategy"', PROMPTS)
        self.assertIn("channel_performance", PROMPTS)

    def test_the_triage_is_told_to_build_strategy(self):
        sec2 = PROMPTS.split("## 2.", 1)[1].split("## 3.", 1)[0]
        self.assertIn("strategy", sec2)
        self.assertIn("channel_registry.json", sec2)

    def test_the_refusal_list_still_governs_strategy(self):
        """"Post more by weakening a gate" is refused from ANY bucket — the
        manager mandate must never read as a licence the retro loop was
        explicitly denied."""
        self.assertIn("refused", PROMPTS.split("STEP 2b", 1)[1]
                      .split("STEP 3", 1)[0].lower())

    def test_honesty_about_thin_data_is_part_of_the_job(self):
        """The operator said it plainly: it might not have much to work
        with yet. The contract makes "not enough data yet" a legitimate
        finding rather than a silence."""
        self.assertIn("not enough data yet", PROMPTS)


if __name__ == "__main__":
    unittest.main()
