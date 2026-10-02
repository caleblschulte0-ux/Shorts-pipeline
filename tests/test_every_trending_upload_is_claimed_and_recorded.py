"""Every trending upload is checked against MAIN, claimed, and recorded.

2026-09-29, from the Actions logs of runs 36562738283 and 36562746794:

1. Phase B dispatched daily.yml AND raised the workflow_run event it also
   listens on. The `daily-shorts` group queued the second run correctly —
   but actions/checkout fetched the event's SHA (11:35), so the second run
   started at 12:00:49 on a posted log that did not hold the first run's
   uploads (pushed 12:00:44) and uploaded "She Ordered Me To Stock Shelves"
   a second time.
2. The first run's three BACKFILL uploads (ZzmH5XnezTE, IDnQa373Z8A,
   6QNCNr2dDhw) never reached state/posted_log.json: main() appended only
   the pre-written results and then `save_log(load_log())` re-saved the
   file unchanged under a comment saying it recorded the backfill.
3. Four takeover-authored graph_race packages repeated AUGUST titles. The
   renderer dropped them silently ("using 2 pre-written packages") and then
   counted them as today's uploads — "uploaded 8/6"; a later run wrote
   uploaded=6 beside an empty URL list.

    python -m pytest tests/test_every_trending_upload_is_claimed_and_recorded.py -q
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import run_trending_daily as rtd                        # noqa: E402
from scripts import merge_posted_log as mpl             # noqa: E402

TITLE = "She Ordered Me To Stock Shelves. I Closed The Aisle."


class LogCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="trending-log-"))
        self.log_path = self.tmp / "posted_log.json"
        self.log_path.write_text(json.dumps({"posted": []}))
        self.persisted: list[dict] = []
        self.real_persist = rtd._persist_log_now
        p1 = mock.patch.object(rtd, "LOG_PATH", self.log_path)
        # the fake persist "reaches the remote" (True): a claim that does not
        # refuses its upload, which AClaimNobodyCanSeeProtectsNobody covers
        p2 = mock.patch.object(
            rtd, "_persist_log_now",
            lambda why: (self.persisted.append(
                {"why": why, "log": json.loads(self.log_path.read_text())}),
                True)[1])
        # Off CI by default: in Actions GITHUB_ACTIONS is set, and the
        # origin refresh would merge the REAL main ledger (381 entries) into
        # this test's empty log. A test that exercises the refresh sets it.
        env = {k: v for k, v in __import__("os").environ.items()
               if k != "GITHUB_ACTIONS"}
        p3 = mock.patch.dict("os.environ", env, clear=True)
        for p in (p1, p2, p3):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def log(self) -> dict:
        return json.loads(self.log_path.read_text())


class TheSecondRunSeesMain(LogCase):
    def test_a_stale_checkout_cannot_re_upload_what_main_already_holds(self):
        """The local ledger is empty (a checkout from before the first run
        pushed); main holds the upload. The upload must be refused, and the
        uploader must never be called."""
        remote = {"posted": [{"title": TITLE, "topic": TITLE,
                              "posted_at": "2026-09-29T11:44:39Z",
                              "video_url": "https://youtube.com/shorts/o9GniW71MIk"}]}

        def fake_run(cmd, **kw):
            if cmd[:2] == ["git", "show"]:
                return SimpleNamespace(returncode=0, stdout=json.dumps(remote),
                                       stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        called = []
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                mock.patch.object(subprocess, "run", fake_run):
            with self.assertRaises(rtd.DuplicateUpload):
                rtd._guarded_upload(title=TITLE, topic=TITLE, fmt="reddit",
                                    publish_at=None,
                                    do_upload=lambda: called.append(1))
        self.assertEqual(called, [], "the uploader ran on a duplicate")
        # and main's entry is now in the local ledger for everything after
        self.assertEqual(len(self.log()["posted"]), 1)

    def test_a_duplicate_is_its_own_failure_stage(self):
        self.assertEqual(rtd._failure_stage("DuplicateUpload: already posted"),
                         "duplicate_refused")


class TheUploadIsClaimedThenRecorded(LogCase):
    def test_claim_is_pushed_before_the_upload_and_the_entry_after(self):
        seen_at_upload = {}

        def do_upload():
            seen_at_upload.update(persisted=list(self.persisted))
            return "https://youtube.com/shorts/NEW"

        url = rtd._guarded_upload(title="T1", topic="topic one",
                                  fmt="reddit", publish_at=None,
                                  do_upload=do_upload)
        self.assertEqual(url, "https://youtube.com/shorts/NEW")
        # BEFORE the API call: a pushed claim, no posted entry yet.
        before = seen_at_upload["persisted"]
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0]["log"]["uploads"][0]["state"], "uploading")
        self.assertEqual(before[0]["log"]["posted"], [])
        # AFTER: the entry is in `posted`, the claim confirmed, both pushed.
        log = self.log()
        self.assertEqual([e["video_url"] for e in log["posted"]],
                         ["https://youtube.com/shorts/NEW"])
        self.assertEqual(log["uploads"][0]["state"], "posted")
        self.assertEqual(log["uploads"][0]["url"],
                         "https://youtube.com/shorts/NEW")
        self.assertEqual(len(self.persisted), 2)

    def test_an_error_that_may_have_uploaded_keeps_the_claim(self):
        def boom():
            raise TimeoutError("read timed out")
        with self.assertRaises(TimeoutError):
            rtd._guarded_upload(title="T2", topic="t2", fmt=None,
                                publish_at=None, do_upload=boom)
        self.assertEqual(self.log()["uploads"][0]["state"], "uploading")
        with self.assertRaises(rtd.DuplicateUpload):
            rtd._guarded_upload(title="T2", topic="t2", fmt=None,
                                publish_at=None, do_upload=lambda: "x")

    def test_an_error_that_cannot_have_uploaded_releases_the_claim(self):
        def quota():
            raise RuntimeError("quotaExceeded")
        with self.assertRaises(RuntimeError):
            rtd._guarded_upload(title="T3", topic="t3", fmt=None,
                                publish_at=None, do_upload=quota)
        self.assertEqual(self.log().get("uploads"), [])
        self.assertEqual(rtd._guarded_upload(
            title="T3", topic="t3", fmt=None, publish_at=None,
            do_upload=lambda: "https://youtube.com/shorts/ok"),
            "https://youtube.com/shorts/ok")


class AClaimNobodyCanSeeProtectsNobody(LogCase):
    """2026-10-02, operator: "why do we keep reposting the same videos?" The
    claim-then-post guard only works if the claim is ON MAIN before the API
    call. A claim whose push failed was a warning, and the upload went ahead
    on a ledger no queued run could see. Now it refuses."""

    def test_a_claim_that_did_not_reach_main_refuses_the_upload(self):
        uploaded = []
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                mock.patch.object(rtd, "_refresh_log_from_origin", lambda: None), \
                mock.patch.object(rtd, "_persist_log_now", lambda why: False):
            with self.assertRaises(rtd.ClaimNotDurable):
                rtd._guarded_upload(title="T1", topic="topic one", fmt="reddit",
                                    publish_at=None,
                                    do_upload=lambda: uploaded.append(1) or "u")
        self.assertEqual(uploaded, [])
        # released locally: nothing posted, no open claim left behind
        log = self.log()
        self.assertEqual(log["posted"], [])
        self.assertEqual([u for u in log.get("uploads", []) if not u.get("url")], [])

    def test_it_is_its_own_failure_stage_not_an_infra_error(self):
        self.assertEqual(rtd._failure_stage("ClaimNotDurable: x"), "duplicate_refused")

    def test_off_ci_there_is_no_remote_and_the_claim_counts(self):
        # the fixture clears GITHUB_ACTIONS; the real persist must say True
        self.assertTrue(self.real_persist("x"))

    def test_on_ci_a_failed_push_is_false_and_a_good_one_true(self):
        import subprocess as _sp
        real_path = rtd.REPO / "state" / "posted_log.json"   # the push is faked
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                mock.patch.object(rtd, "LOG_PATH", real_path), \
                mock.patch.object(_sp, "run", return_value=mock.Mock(returncode=1, stderr="x", stdout="")):
            self.assertFalse(self.real_persist("x"))
        with mock.patch.dict("os.environ", {"GITHUB_ACTIONS": "true"}), \
                mock.patch.object(rtd, "LOG_PATH", real_path), \
                mock.patch.object(_sp, "run", return_value=mock.Mock(returncode=0, stderr="", stdout="pushed")):
            self.assertTrue(self.real_persist("x"))


class ABackfillUploadReachesThePostedLog(LogCase):
    """run_one is the backfill's upload path. Stub everything around the
    upload and check the posted log — the old code never wrote it there."""

    def test_run_one_records_its_upload(self):
        pkg = {"title": "I Saved A Refill", "shots": []}
        topic = SimpleNamespace(query="some headline", angle=None,
                                headlines=[], snippets=[])
        uploader = mock.Mock()
        uploader.return_value.upload.return_value = SimpleNamespace(
            url="https://youtube.com/shorts/ZzmH5XnezTE")
        pkg_dir = self.tmp / "pk"
        out_dir = self.tmp / "out"
        out_dir.mkdir()
        with mock.patch.object(rtd, "_research", lambda t: None), \
                mock.patch.object(rtd.script_generator, "generate",
                                  lambda *a, **k: dict(pkg)), \
                mock.patch.object(rtd, "PACKAGE_DIR", pkg_dir), \
                mock.patch.object(rtd, "OUTPUT_DIR", out_dir), \
                mock.patch.object(rtd, "REPO", self.tmp), \
                mock.patch.object(rtd, "_backfill_illustrations", lambda p: None), \
                mock.patch.object(rtd, "_illustration_quarantine", lambda p: None), \
                mock.patch.object(rtd, "_render_package", lambda p, o: None), \
                mock.patch.object(rtd, "_qa_and_thumbnail",
                                  lambda p, o, r: (None, None)), \
                mock.patch.object(rtd, "_showrunner",
                                  lambda *a, **k: {"blocked": False}), \
                mock.patch("shared.uploaders.YouTubeUploader", uploader), \
                mock.patch("shared.crosspost.crosspost", lambda *a, **k: None):
            res = rtd.run_one(topic, None, dry_run=False, no_schedule=True)
        self.assertTrue(res["ok"], res.get("error"))
        self.assertTrue(res.get("logged"))
        self.assertIn("https://youtube.com/shorts/ZzmH5XnezTE",
                      [e["video_url"] for e in self.log()["posted"]])


class TheManifestSaysWhyAndCountsToday(unittest.TestCase):
    LOG = {"posted": [
        {"title": "A 2-Year-Old App Just Passed Etsy",
         "posted_at": "2026-08-17T09:53:19Z",
         "video_url": "https://youtube.com/shorts/U2J2nQdOo-c"},
        {"title": "Yesterday", "posted_at": "2026-09-28T21:24:10Z",
         "video_url": "https://youtube.com/shorts/y"},
        {"title": TITLE, "posted_at": "2026-09-29T11:44:39Z",
         "video_url": "https://youtube.com/shorts/o9GniW71MIk"},
    ]}

    def test_every_excluded_package_says_when_and_where(self):
        pkgs = [{"title": "A 2-Year-Old App Just Passed Etsy",
                 "format": "graph_race",
                 "_path": "state/trending_packages/20260929/01_graph-x.json"},
                {"title": "Fresh one", "format": "graph_race"}]
        keep, why = rtd.split_manifest(pkgs, self.LOG)
        self.assertEqual([p["title"] for p in keep], ["Fresh one"])
        self.assertEqual(len(why), 1)
        for needle in ("01_graph-x.json", "graph_race", "2026-08-17",
                       "U2J2nQdOo-c"):
            self.assertIn(needle, why[0])

    def test_only_todays_uploads_count_toward_today(self):
        """The old count was 'a package title appears anywhere in the log'
        — four August uploads counted as today's (8/6)."""
        today = rtd.uploaded_on(self.LOG, "20260929")
        self.assertEqual([e["title"] for e in today], [TITLE])

    def test_the_outcome_lists_every_url_behind_uploaded(self):
        outcome, complete = rtd.compute_production_outcome(
            [{"ok": True, "video_url": "https://youtu.be/new"}],
            prior_uploaded=5, expected=6, dry_run=False,
            prior_urls=[f"https://youtu.be/{i}" for i in range(5)])
        self.assertTrue(complete)
        self.assertEqual(len(outcome["video_urls"]), outcome["uploaded"])

    def test_an_over_filled_day_is_not_repair_required(self):
        results = [{"ok": True, "video_url": f"https://youtu.be/{i}"}
                   for i in range(4)]
        outcome, complete = rtd.compute_production_outcome(
            results, prior_uploaded=4, expected=6, dry_run=False)
        self.assertTrue(complete)
        self.assertEqual(outcome["status"], "production_complete")


class BackfillCreditsEarlierUploads(unittest.TestCase):
    def test_a_day_already_filled_by_an_earlier_run_backfills_nothing(self):
        args = SimpleNamespace(count=6, dry_run=False, no_schedule=True)
        with mock.patch.object(rtd, "discover_all",
                               side_effect=AssertionError("authored")):
            out = rtd._backfill([{"ok": True}], args, [None] * 8, None,
                                {"posted": []}, prior_uploaded=5)
        self.assertEqual(out, [])


class AConfirmedClaimSurvivesAPushRace(unittest.TestCase):
    def test_the_side_with_the_url_wins(self):
        claim = {"slug": "s", "claimed_at": "2026-09-29T11:44:30Z",
                 "state": "uploading", "url": None}
        done = dict(claim, state="posted", url="https://youtu.be/x")
        merged = mpl.merge({"posted": [], "uploads": [claim]},
                           {"posted": [], "uploads": [done]})
        self.assertEqual(merged["uploads"], [done])


class TheWorkflowChecksOutTheTip(unittest.TestCase):
    def test_checkout_names_a_ref_and_the_group_queues(self):
        import yaml
        wf = yaml.safe_load((ROOT / ".github/workflows/daily.yml").read_text())
        job = wf["jobs"]["daily"]
        self.assertEqual(job["concurrency"]["cancel-in-progress"], False)
        co = next(s for s in job["steps"]
                  if str(s.get("uses", "")).startswith("actions/checkout"))
        self.assertTrue((co.get("with") or {}).get("ref"),
                        "no ref: a queued run checks out the event's stale SHA")


if __name__ == "__main__":
    unittest.main()
