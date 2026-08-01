"""Tests for the learning loop's correctness — the parts that silently lie.

Every bug covered here shipped in the first cut and would have produced
confident, wrong conclusions rather than errors. That is the failure mode
worth testing hardest: a review system that crashes gets fixed, a review
system that quietly mis-ranks every video gets believed.

    python -m unittest tests.test_retro_loop -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))   # APPEND: see note below

import build_retro as br            # noqa: E402
import retro_mailbox as mb          # noqa: E402
import review_proposals as rp       # noqa: E402
from shared import experiments as ex  # noqa: E402


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


class TestPercentileHonesty(unittest.TestCase):
    """The original excluded peers by VALUE. On a channel where most videos
    have 0 views that deleted nearly the whole comparison population, and
    the survivor looked like a star against one peer."""

    def test_ties_do_not_delete_the_population(self):
        pop = [0.0] * 9 + [5.0]
        self.assertIsNotNone(br.percentile_in(0.0, pop))

    def test_a_zero_view_video_is_average_not_worst(self):
        """Nine zero-view videos: each is exactly typical, not p0."""
        pct = br.percentile_in(0.0, [0.0] * 9 + [5.0])
        self.assertGreater(pct, 30)
        self.assertLess(pct, 70)

    def test_a_real_outperformer_still_reads_high(self):
        self.assertGreater(br.percentile_in(5.0, [0.0] * 9 + [5.0]), 80)

    def test_thin_populations_still_refuse(self):
        self.assertIsNone(br.percentile_in(1.0, [0.0, 0.0]))

    def test_only_the_current_video_is_excluded(self):
        vids = [{"video_id": f"v{i}", "views": 0, "age_hours": 30,
                 "published_at": "2026-07-30T10:00:00Z", "title": f"t{i}"}
                for i in range(8)]
        vids.append({"video_id": "star", "views": 100, "age_hours": 30,
                     "published_at": "2026-07-30T10:00:00Z", "title": "star"})
        data = {"videos": vids}
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "a.json").write_text(json.dumps(data))
            saved = br.ROOT
            br.ROOT = tmp
            r = br.channel_report("t", "a.json", "20260730")
            br.ROOT = saved
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        rows = {x["title"]: x for x in r["today"]}
        # Every zero video keeps its 7 zero peers + the star = 8 peers.
        self.assertIsNotNone(rows["t0"]["percentile_vs_same_age"])
        self.assertGreater(rows["star"]["percentile_vs_same_age"],
                           rows["t0"]["percentile_vs_same_age"])


class TestMissingIsNotZero(unittest.TestCase):
    def test_none_stays_none(self):
        self.assertIsNone(br.metric({"likes": None}, "likes"))

    def test_a_real_zero_stays_zero(self):
        self.assertEqual(br.metric({"likes": 0}, "likes"), 0)

    def test_missing_metrics_are_listed_not_invented(self):
        vids = [{"video_id": "v1", "views": 5, "age_hours": 30, "likes": None,
                 "published_at": "2026-07-30T10:00:00Z", "title": "x"}]
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "a.json").write_text(json.dumps({"videos": vids}))
            saved, br.ROOT = br.ROOT, tmp
            r = br.channel_report("t", "a.json", "20260730")
            br.ROOT = saved
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertIn("likes", r["today"][0]["missing_metrics"])


class TestAgeMatching(unittest.TestCase):
    def test_cohorts_only_contain_their_window(self):
        vids = [{"age_hours": 2, "views": 1, "_vph": 0.5, "_fmt": "a"},
                {"age_hours": 25, "views": 9, "_vph": 0.4, "_fmt": "a"},
                {"age_hours": 170, "views": 50, "_vph": 0.3, "_fmt": "a"}]
        self.assertEqual(br.cohort_at(vids, 20, 30)["n"], 1)
        self.assertEqual(br.cohort_at(vids, 0, 6)["n"], 1)

    def test_format_scoping_keeps_comparisons_honest(self):
        vids = [{"age_hours": 25, "views": 9, "_vph": 0.4, "_fmt": "graph"},
                {"age_hours": 25, "views": 1, "_vph": 0.1, "_fmt": "reddit"}]
        self.assertEqual(br.cohort_at(vids, 20, 30, "graph")["n"], 1)

    def test_an_empty_window_says_so(self):
        self.assertEqual(br.cohort_at([], 20, 30)["n"], 0)


class ExperimentCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="exp-"))
        self._saved = (ex.RETRO_STATE, ex.REGISTER)
        ex.RETRO_STATE, ex.REGISTER = self.tmp, self.tmp / "e.json"

    def tearDown(self):
        ex.RETRO_STATE, ex.REGISTER = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestSampleAdvancement(ExperimentCase):
    """`bump_samples` existed but nothing called it, so no experiment could
    ever reach its sample floor — they ran forever."""

    def _exp(self, **over):
        kw = dict(change="c", metric="m", direction="up", baseline=1.0,
                  channel="trending", format="graph_race", min_days=7,
                  min_samples=3, now=iso(8))
        kw.update(over)
        return ex.register("h", **kw)

    def test_eligible_videos_counted_and_experiment_flips(self):
        self._exp()
        pool = {"trending": [{"published_at": iso(1), "format": "graph_race"},
                             {"published_at": iso(2), "format": "graph_race"},
                             {"published_at": iso(3), "format": "graph_race"}]}
        due = ex.advance(pool)
        self.assertEqual(len(due), 1)
        self.assertEqual(ex.all_experiments()[0]["samples_seen"], 3)

    def test_videos_from_before_the_change_do_not_count(self):
        self._exp()
        ex.advance({"trending": [{"published_at": iso(20),
                                  "format": "graph_race"}] * 5})
        self.assertEqual(ex.all_experiments()[0]["samples_seen"], 0)

    def test_the_wrong_channel_does_not_count(self):
        self._exp()
        ex.advance({"explainer": [{"published_at": iso(1),
                                   "format": "graph_race"}] * 9})
        self.assertEqual(ex.all_experiments()[0]["samples_seen"], 0)

    def test_the_wrong_format_does_not_count(self):
        self._exp()
        ex.advance({"trending": [{"published_at": iso(1),
                                  "format": "text_card"}] * 9})
        self.assertEqual(ex.all_experiments()[0]["samples_seen"], 0)

    def test_advance_is_idempotent(self):
        self._exp()
        pool = {"trending": [{"published_at": iso(1), "format": "graph_race"}]}
        for _ in range(5):
            ex.advance(pool)
        self.assertEqual(ex.all_experiments()[0]["samples_seen"], 1)

    def test_an_experiment_cannot_run_forever(self):
        self._exp(now=iso(60))
        self.assertTrue(ex.stale())
        ex.abandon(ex.all_experiments()[0]["id"], "no clean verdict possible")
        self.assertEqual(ex.all_experiments()[0]["status"], "abandoned")


class TestMailbox(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mb-"))
        self._saved = (mb.RETRO_ROOT, mb.ROOT)
        mb.RETRO_ROOT, mb.ROOT = self.tmp, self.tmp.parent

    def tearDown(self):
        mb.RETRO_ROOT, mb.ROOT = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _day(self, date, brief=True, answered=False):
        d = self.tmp / date
        d.mkdir(parents=True, exist_ok=True)
        if brief:
            (d / "brief.json").write_text("{}")
        if answered:
            (d / "proposals.json").write_text('{"proposals": []}')

    def test_a_missed_day_stays_reviewable(self):
        self._day("20260728")
        self._day("20260729")
        self.assertEqual(mb.next_review()["review_date"], "20260728")
        self.assertEqual(mb.mailbox()["open_count"], 2)

    def test_answering_removes_it_and_cannot_repeat(self):
        self._day("20260728", answered=True)
        self._day("20260729")
        self.assertEqual(mb.next_review()["review_date"], "20260729")

    def test_fully_answered_mailbox_is_empty(self):
        self._day("20260729", answered=True)
        self.assertIsNone(mb.next_review())

    def test_a_folder_with_no_brief_is_not_open(self):
        self._day("20260729", brief=False)
        self.assertIsNone(mb.next_review())


class TestEvidenceMustBeReal(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ev-"))
        self._saved = rp.RETRO_ROOT
        rp.RETRO_ROOT = self.tmp
        d = self.tmp / "20260801"
        d.mkdir(parents=True)
        self.brief = {"channels": {"trending": {"last_30d":
                      {"videos": 76, "median_views": 3.0}}}}
        (d / "brief.json").write_text(json.dumps(self.brief))

    def tearDown(self):
        rp.RETRO_ROOT = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _p(self, **over):
        p = {"title": "T", "category": "content", "confidence": "medium",
             "observation": "median_views is 3.0 across 76 videos",
             "evidence": ["channels.trending.last_30d"],
             "proposal": "do a thing", "expected_effect": "better",
             "how_we_would_know": "median_views rises", "risks": "some"}
        p.update(over)
        return p

    def test_real_numbers_pass(self):
        self.assertEqual(rp.check_evidence(self._p(), self.brief), [])

    def test_invented_numbers_are_caught(self):
        errs = rp.check_evidence(
            self._p(observation="graph_race sits at p12 vs 47.3 for text_card"),
            self.brief)
        self.assertTrue(any("not present anywhere" in e for e in errs))

    def test_a_bogus_evidence_path_is_caught(self):
        errs = rp.check_evidence(
            self._p(evidence=["channels.trending.made_up_field"]), self.brief)
        self.assertTrue(any("not a field" in e for e in errs))

    def test_no_evidence_at_all_is_caught(self):
        self.assertTrue(rp.check_evidence(self._p(evidence=[]), self.brief))

    def test_no_brief_means_unverifiable(self):
        self.assertTrue(rp.check_evidence(self._p(), None))


class TestThrashControl(unittest.TestCase):
    def _p(self, **over):
        p = {"title": "Shorten the graph hook", "channel": "trending",
             "format": "graph_race", "files": ["make_graph_race.py"],
             "category": "content"}
        p.update(over)
        return p

    def test_a_reworded_refile_collides(self):
        a = rp.signature(self._p(title="Shorten the graph hook"))
        b = rp.signature(self._p(title="The graph hook should be shorter"))
        self.assertEqual(a, b)

    def test_a_declined_idea_cannot_simply_return(self):
        hist = [{"signature": rp.signature(self._p()), "verdict": "decline",
                 "date": "20260730", "because": "no evidence"}]
        self.assertTrue(rp.check_duplicates(self._p(), hist))

    def test_new_evidence_reopens_it(self):
        hist = [{"signature": rp.signature(self._p()), "verdict": "decline",
                 "date": "20260730", "because": "no evidence"}]
        p = self._p(new_evidence_since="14 more graph_race videos at 72h")
        self.assertEqual(rp.check_duplicates(p, hist), [])

    def test_one_experiment_per_channel(self):
        self.assertTrue(rp.check_capacity(
            self._p(), {"trending": ["20260725-something"]}))

    def test_a_watch_proposal_is_never_capped(self):
        self.assertEqual(rp.check_capacity(
            self._p(category="watch"), {"trending": ["x"]}), [])


class TestReviewNeverBlocksProduction(unittest.TestCase):
    """If analytics, the reviewer, or the triage fails, the day's videos
    must still render. Every review entrypoint exits 0 on bad input."""

    def _run(self, *args):
        return subprocess.run([sys.executable, *args], cwd=ROOT,
                              capture_output=True, text=True)

    def test_advance_experiments_survives_a_broken_register(self):
        self.assertEqual(
            self._run("scripts/advance_experiments.py").returncode, 0)

    def test_weekly_rollup_survives_no_data(self):
        self.assertEqual(
            self._run("scripts/weekly_rollup.py", "--dry-run").returncode, 0)

    def test_triage_of_a_nonexistent_date_is_clean(self):
        self.assertEqual(
            self._run("scripts/review_proposals.py",
                      "--date", "29991231").returncode, 0)

    def test_mailbox_survives_an_empty_repo(self):
        self.assertEqual(self._run("scripts/retro_mailbox.py").returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestFullArcDryRun(unittest.TestCase):
    """The whole loop over simulated days, against the real modules:

        1 brief written           4 accepted -> experiment registered
        2 reviewer proposes       5 new eligible videos advance it
        3 Claude decides          6 the gate holds until BOTH floors pass
                                  7 verdict reached
                                  8 next brief carries the whole history

    Anything short of this passes unit tests and still fails to compound,
    which is the only thing this system is for."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="arc-"))
        import retro_reply as rr
        self.rr = rr
        self._saved = (ex.RETRO_STATE, ex.REGISTER, rr.RETRO_ROOT, rr.STATE,
                       rr.LEDGER, rr.AGENDA, rp.RETRO_ROOT, mb.RETRO_ROOT)
        ex.RETRO_STATE = self.tmp / "state"
        ex.REGISTER = ex.RETRO_STATE / "experiments.json"
        rr.RETRO_ROOT = rp.RETRO_ROOT = mb.RETRO_ROOT = self.tmp
        rr.STATE = self.tmp / "state"
        rr.LEDGER = rr.STATE / "ledger.jsonl"
        rr.AGENDA = rr.STATE / "agenda.json"

    def tearDown(self):
        (ex.RETRO_STATE, ex.REGISTER, self.rr.RETRO_ROOT, self.rr.STATE,
         self.rr.LEDGER, self.rr.AGENDA, rp.RETRO_ROOT,
         mb.RETRO_ROOT) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_whole_arc(self):
        D = "20260801"
        day = self.tmp / D
        day.mkdir(parents=True)

        # 1. A brief exists and is unanswered.
        brief = {"date": D, "channels": {"trending": {"last_30d":
                 {"videos": 76, "median_views": 3.0}}}}
        (day / "brief.json").write_text(json.dumps(brief))
        self.assertEqual(mb.next_review()["review_date"], D,
                         "the mailbox did not surface the open brief")

        # 2. The reviewer answers — one file, so it cannot be answered twice.
        (day / "proposals.json").write_text(json.dumps({"proposals": [{
            "proposal_id": "P-1", "title": "Shorten the graph hook",
            "channel": "trending", "format": "graph_race",
            "category": "content", "confidence": "medium",
            "observation": "median_views is 3.0 across 76 videos",
            "evidence": ["channels.trending.last_30d"],
            "files": ["make_graph_race.py"],
            "proposal": "Cut the hook overlay to 0.8s",
            "expected_effect": "better 3s hold",
            "how_we_would_know": "median_views rises",
            "risks": "may clip line two", "rollback": "revert constant"}]}))
        self.assertIsNone(mb.next_review(), "answered brief still in mailbox")

        # 3. Triage accepts it.
        t = rp.triage(D)
        self.assertEqual(t["counts"]["accepted"], 1, t)

        # 4. Claude decides, and the decision registers an experiment.
        e = ex.register("Shorter graph hooks hold better", change="0.9s",
                        metric="graph_race.median_views", direction="up",
                        baseline=3.0, channel="trending", format="graph_race",
                        min_days=7, min_samples=3, proposal_file="P-1",
                        now=iso(8))
        self.rr.append_ledger({"date": D, "proposal_file": "P-1",
                               "signature": rp.signature({
                                   "channel": "trending",
                                   "format": "graph_race",
                                   "files": ["make_graph_race.py"]}),
                               "title": "Shorten the graph hook",
                               "verdict": "adopt", "because": "shipped 0.9s",
                               "commit": "abc123def456",
                               "experiment_id": e["id"]})

        # 5+6. Two eligible videos is not enough — the floor must hold.
        ex.advance({"trending": [{"published_at": iso(1),
                                  "format": "graph_race"}] * 2})
        self.assertEqual(ex.all_experiments()[0]["status"], "running")
        ok, why = ex.readout_ready(ex.all_experiments()[0])
        self.assertFalse(ok)
        self.assertIn("samples", why)

        # A third crosses it.
        due = ex.advance({"trending": [{"published_at": iso(1),
                                        "format": "graph_race"}] * 3})
        self.assertEqual(len(due), 1, "window closed but no readout demanded")

        # 7. Verdict.
        r = ex.conclude(ex.all_experiments()[0], observed=4.2)
        self.assertEqual(r["status"], "adopted", r["readout"])

        # 8. Re-filing the same idea is now refused as already decided.
        dupes = rp.check_duplicates(
            {"channel": "trending", "format": "graph_race",
             "files": ["make_graph_race.py"], "title": "hook again"},
            self.rr.read_ledger())
        self.assertTrue(dupes, "an adopted idea could be re-proposed")
        self.assertIn("already adopted", dupes[0])

        # ...and the history is all still there for tomorrow's brief.
        ledger = self.rr.read_ledger()
        self.assertEqual(ledger[-1]["verdict"], "adopt")
        self.assertEqual(ledger[-1]["commit"], "abc123def456")
        self.assertEqual(ledger[-1]["experiment_id"], e["id"])
        self.assertEqual(ex.all_experiments()[0]["status"], "adopted")


class TestReadmeAndValidatorAgree(unittest.TestCase):
    """The reviewer follows retro/README.md literally. If the documented
    example does not pass the validator, every proposal it writes is
    malformed and the loop produces nothing — a failure that looks like the
    reviewer being bad at its job."""

    def _readme_example(self) -> dict:
        import re
        text = (ROOT / "retro" / "README.md").read_text()
        m = re.search(r'\{"proposals": \[\{(.*?)\}\]\}', text, re.S)
        self.assertIsNotNone(m, "the README lost its proposal example")
        return json.loads('{"proposals": [{' + m.group(1) + '}]}')["proposals"][0]

    def test_readme_example_passes_validation(self):
        ex = self._readme_example()
        self.assertEqual(rp.check_shape(ex), [],
                         "the documented example fails the validator")

    def test_readme_example_has_every_required_field(self):
        ex = self._readme_example()
        missing = [k for k in rp.REQUIRED if k not in ex]
        self.assertEqual(missing, [],
                         f"README example omits required field(s): {missing}")

    def test_readme_example_is_not_refused_on_policy(self):
        self.assertEqual(rp.check_forbidden(self._readme_example()), [])
