"""The split-worker day, end to end — plus every takeover path it must not break.

`tests/test_media_checkpoint.py` covers the contract unit by unit. This covers
the two things that only show up when the pieces run together:

  * the 8-step dry-run fixture (`scripts/exchange_dry_run.py`), which stands
    in for the 06:00 media worker and the 07:00 finalizer;
  * the takeover matrix — the split added a second worker, and the thing most
    likely to break quietly is one of the fallback paths that existed to keep
    the channel posting when Claude is dark.

    python -m unittest tests.test_split_worker -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))   # APPEND: see note below

from funnel import media_judge                       # noqa: E402
from shared import authoring_brief as brief          # noqa: E402
from shared import channel_registry as reg           # noqa: E402
from shared import exchange_bundle as xb             # noqa: E402
from shared import media_checkpoint as mc            # noqa: E402
from tests.test_package_buffer import (               # noqa: E402
    graph_pkg, reddit_pkg, text_card_pkg)

DATE = "29991230"


# --------------------------------------------------------------------------
# the fixture
# --------------------------------------------------------------------------
class TestDryRunFixture(unittest.TestCase):
    def test_all_eight_steps_pass(self):
        out = subprocess.run(
            [sys.executable, "scripts/exchange_dry_run.py", "--json"],
            cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        report = json.loads(out.stdout)
        self.assertEqual(report["passed"], report["total"])
        self.assertEqual(report["total"], 8)
        for step in report["steps"]:
            self.assertTrue(step["checks"], f"step {step['step']} asserts "
                                            f"nothing")
            self.assertTrue(step["ok"], step)


# --------------------------------------------------------------------------
# the takeover matrix — the split must not quietly break any of these
# --------------------------------------------------------------------------
class TestTakeoverMatrix(unittest.TestCase):
    """Every shape of short day, and what the bundle must say about it."""

    def _bundle(self, packages, *, target=None, channel_requests=None):
        req = None
        if len(packages) < (target or reg.target_count("trending")):
            req = brief.build_request(DATE, "trending",
                                      have_packages=packages, target=target)
        reports = [media_judge.judge_package(p, None) for p in packages]
        return xb.build_bundle(DATE, packages, reports, req,
                               channel_requests or ({"trending": req} if req
                                                    else None))

    def test_zero_packages_asks_for_the_whole_registered_slate(self):
        """Expectations DERIVED from the registry, never restated. A test
        that repeats the mix is just a ninth copy of the ruling."""
        b = self._bundle([])
        self.assertEqual(b["mode"], "author")
        self.assertEqual(b["authoring_request"]["mix"],
                         reg.target_mix("trending"))
        self.assertEqual(b["authoring_request"]["write"],
                         reg.target_count("trending"))

    def test_partial_days_ask_only_for_the_shortfall(self):
        """Build a partial day out of whatever the registry currently wants,
        so this keeps working through any future mix change."""
        mix = reg.target_mix("trending")
        makers = {"reddit_story": reddit_pkg, "text_card": text_card_pkg,
                  "graph_race": graph_pkg}
        have, i = [], 0
        for fid, n in mix.items():
            maker = makers.get(fid)
            if not maker:
                continue
            for _ in range(max(0, n - 1)):      # one short of each
                have.append(maker(slug=f"partial-{i}"))
                i += 1
        b = self._bundle(have)
        want = {fid: mix[fid] - sum(1 for p in have
                                    if reg.classify(p, "trending") == fid)
                for fid in mix}
        self.assertEqual(b["authoring_request"]["mix"], want)
        self.assertEqual(b["authoring_request"]["write"], sum(want.values()))

    @staticmethod
    def _full_slate():
        """A complete slate for whatever the registry currently asks for."""
        makers = {"reddit_story": reddit_pkg, "text_card": text_card_pkg,
                  "graph_race": graph_pkg}
        out, i = [], 0
        for fid, n in reg.target_mix("trending").items():
            for _ in range(n):
                out.append(makers[fid](slug=f"full-{i}"))
                i += 1
        return out

    def test_a_full_slate_is_punch_up_mode(self):
        pkgs = self._full_slate()
        b = self._bundle(pkgs)
        self.assertEqual(b["mode"], "punch_up")
        self.assertNotIn("authoring_request", b)

    def test_a_full_trending_slate_does_not_hide_the_other_channels(self):
        """The trap the split makes easier to fall into: six packages exist,
        so 'nothing to author' — and the explainer rewrite silently never
        happens. Explainer and curiosity are separate channels with separate
        asks."""
        pkgs = self._full_slate()
        b = self._bundle(pkgs, channel_requests={
            "explainer": {"channel": "explainer", "job": "rewrite_words",
                          "write": 2},
            "curiosity": {"channel": "curiosity", "job": "stock_queue",
                          "write": 3}})
        self.assertEqual(b["mode"], "author")
        self.assertIsNone(b["authoring_request"])
        job0 = b["instructions"]["two_jobs"][0]
        self.assertIn("OTHER CHANNELS", job0)
        self.assertIn("curiosity", job0)
        self.assertIn("explainer", job0)
        self.assertNotIn("there is no slate", job0,
                         "the bundle is telling ChatGPT trending is empty "
                         "when it is full")
        self.assertEqual(b["counts"]["channels_needing_a_brain"], 2)

    def test_a_short_day_still_leads_with_the_trending_authoring_job(self):
        b = self._bundle([reddit_pkg(slug="a")])
        job0 = b["instructions"]["two_jobs"][0]
        self.assertIn("AUTHOR THE DAY", job0)
        self.assertIn("authoring_request", job0)

    def test_the_brief_still_forbids_writing_into_the_slate(self):
        b = self._bundle([])
        self.assertIn("Do NOT write into state/trending_packages/",
                      b["authoring_request"]["where"]["never"])

    def test_the_media_contract_now_asks_for_checkpoints_too(self):
        b = self._bundle([])
        contract = b["authoring_request"]["media_contract"]
        self.assertIn("checkpoint_every_shot", contract)
        self.assertIn("authored-<slug>-s<shot_index>",
                      contract["checkpoint_every_shot"])


# --------------------------------------------------------------------------
# Phase B, run for real
# --------------------------------------------------------------------------
class TestPhaseBHonoursTheCheckpoints(unittest.TestCase):
    """Runs the real script as a subprocess against a scratch date."""

    DATE = "29991229"

    def setUp(self):
        self.bundle = ROOT / "exchange" / "bundles" / self.DATE
        self.day = ROOT / "state" / "trending_packages" / self.DATE
        self._clean()
        self.bundle.mkdir(parents=True)

    def tearDown(self):
        self._clean()

    def _clean(self):
        shutil.rmtree(self.bundle, ignore_errors=True)
        shutil.rmtree(self.day, ignore_errors=True)

    def _run(self, *extra):
        return subprocess.run(
            [sys.executable, "scripts/exchange_phase_b.py", "--date",
             self.DATE, "--no-self-fill", "--no-punchup", *extra],
            cwd=ROOT, capture_output=True, text=True)

    def _write_bundle(self, pkgs):
        reports = [media_judge.judge_package(p, None) for p in pkgs]
        b = xb.build_bundle(self.DATE, pkgs, reports)
        (self.bundle / "bundle.json").write_text(json.dumps(b, indent=2) + "\n")
        return b

    def _png(self, name):
        import hashlib
        from PIL import Image
        im = Image.new("RGB", (64, 64))
        im.putdata([(x * 3 % 256, y * 5 % 256, (x + y) % 256)
                    for y in range(64) for x in range(64)])
        path = self.bundle / name
        im.save(path)
        blob = path.read_bytes()
        return f"file://{path}", hashlib.sha256(blob).hexdigest(), len(blob)

    def test_a_pointer_that_contradicts_its_checkpoint_is_refused(self):
        pkg = reddit_pkg(slug="checkpoint-liar")
        self.day.mkdir(parents=True, exist_ok=True)
        (self.day / "01_checkpoint-liar.json").write_text(json.dumps(pkg))
        b = self._write_bundle([pkg])
        rid = b["requests"][0]["request_id"]
        url, sha, nbytes = self._png(b["requests"][0]["drive_filename"])

        # The media worker verified ONE image; the response points at another.
        saved = mc.BUNDLE_ROOT
        try:
            mc.BUNDLE_ROOT = ROOT / "exchange" / "bundles"
            bid = mc.bundle_identity(self.DATE)
            mc.write_checkpoint(self.DATE, mc.build_checkpoint(
                date=self.DATE, request_id=rid, bundle_id=bid,
                prompt=b["requests"][0]["prompt_verbatim"],
                drive={"file_id": "REAL", "filename": "x.png",
                       "sharing": "anyone_with_link"},
                image={"sha256": "a" * 64, "bytes": nbytes, "format": "png",
                       "width": 64, "height": 64}))
        finally:
            mc.BUNDLE_ROOT = saved

        (self.bundle / "response.json").write_text(json.dumps({"media": [{
            "request_id": rid, "status": "fulfilled",
            "drive": {"file_id": "SOMETHING-ELSE", "download_url": url},
            "image": {"sha256": sha, "bytes": nbytes, "format": "png",
                      "width": 64, "height": 64}}]}))

        out = self._run()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("REFUSED media", out.stdout)
        report = json.loads((self.bundle / "phase_b_report.json").read_text())
        self.assertEqual(report["media"]["fulfilled"], 0)
        self.assertEqual(report["media"]["refused"], 1)

    def test_a_matching_pair_is_pinned(self):
        pkg = reddit_pkg(slug="checkpoint-honest")
        self.day.mkdir(parents=True, exist_ok=True)
        (self.day / "01_checkpoint-honest.json").write_text(json.dumps(pkg))
        b = self._write_bundle([pkg])
        req = b["requests"][0]
        rid = req["request_id"]
        url, sha, nbytes = self._png(req["drive_filename"])
        # A COMPLETE Drive record — every field is compared against the
        # checkpoint, so an incomplete one is refused on its own merits and
        # would hide what this test is actually about.
        drive = {"file_id": "REAL", "folder_id": "1FolderX",
                 "download_url": url, "filename": req["drive_filename"],
                 "sharing": "anyone_with_link"}
        saved = mc.BUNDLE_ROOT
        try:
            mc.BUNDLE_ROOT = ROOT / "exchange" / "bundles"
            bid = mc.bundle_identity(self.DATE)
            mc.write_checkpoint(self.DATE, mc.build_checkpoint(
                date=self.DATE, request_id=rid, bundle_id=bid,
                prompt=req["prompt_verbatim"], drive=drive,
                image={"sha256": sha, "bytes": nbytes, "format": "png",
                       "width": 64, "height": 64}))
        finally:
            mc.BUNDLE_ROOT = saved
        (self.bundle / "response.json").write_text(json.dumps({"media": [{
            "request_id": rid, "status": "fulfilled", "drive": drive,
            "image": {"sha256": sha, "bytes": nbytes, "format": "png",
                      "width": 64, "height": 64}}]}))
        out = self._run()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        report = json.loads((self.bundle / "phase_b_report.json").read_text())
        self.assertEqual(report["media"]["refused"], 0, out.stdout)
        self.assertEqual(report["media"]["fulfilled"], 1, out.stdout)
        self.assertEqual(report["checkpoints"]["ok"], 1)

    def test_no_done_backstop_still_accepts_uncheckpointed_media(self):
        """Policy A, and ONLY on this path. With no DONE, ChatGPT never
        finished — often never started — so there are no checkpoints to
        require, and demanding them would turn 'ChatGPT was late' into 'the
        channel posts nothing'."""
        pkg = reddit_pkg(slug="no-checkpoints")
        self.day.mkdir(parents=True, exist_ok=True)
        (self.day / "01_no-checkpoints.json").write_text(json.dumps(pkg))
        b = self._write_bundle([pkg])
        req = b["requests"][0]
        url, sha, nbytes = self._png(req["drive_filename"])
        (self.bundle / "response.json").write_text(json.dumps({"media": [{
            "request_id": req["request_id"], "status": "fulfilled",
            "drive": {"file_id": "REAL", "download_url": url},
            "image": {"sha256": sha, "bytes": nbytes, "format": "png",
                      "width": 64, "height": 64}}]}))
        out = self._run()
        report = json.loads((self.bundle / "phase_b_report.json").read_text())
        self.assertEqual(report["media"]["fulfilled"], 1, out.stdout)
        self.assertEqual(report["checkpoints"]["warnings"], 1)

    def test_DONE_makes_checkpoints_mandatory(self):
        """DONE is ChatGPT's assertion that both workers ran to completion.
        If they did, every image has a checkpoint — writing one is the media
        worker's whole job. So an uncheckpointed pointer on a DONE run is not
        a skipped step, it is media nobody recorded verifying, and accepting
        it with a warning is the exact failure shape this contract ends."""
        pkg = reddit_pkg(slug="done-is-strict")
        self.day.mkdir(parents=True, exist_ok=True)
        (self.day / "01_done-is-strict.json").write_text(json.dumps(pkg))
        b = self._write_bundle([pkg])
        req = b["requests"][0]
        url, sha, nbytes = self._png(req["drive_filename"])
        (self.bundle / "response.json").write_text(json.dumps({"media": [{
            "request_id": req["request_id"], "status": "fulfilled",
            "drive": {"file_id": "REAL", "download_url": url},
            "image": {"sha256": sha, "bytes": nbytes, "format": "png",
                      "width": 64, "height": 64}}]}))
        (self.bundle / "DONE").write_text(json.dumps({"date": self.DATE}))

        out = self._run()                       # no --require-checkpoints
        self.assertIn("checkpoints are REQUIRED", out.stdout)
        report = json.loads((self.bundle / "phase_b_report.json").read_text())
        self.assertTrue(report["checkpoints"]["required"])
        self.assertEqual(report["media"]["fulfilled"], 0, out.stdout)
        self.assertEqual(report["media"]["refused"], 1)
        self.assertEqual(report["checkpoints"]["warnings"], 0,
                         "a missing checkpoint downgraded to a warning on a "
                         "DONE run")

    def test_a_refused_pointer_self_fills_rather_than_rendering_bare(self):
        """Refusing is only half the job — the shot still needs a picture."""
        pkg = reddit_pkg(slug="refused-then-filled")
        self.day.mkdir(parents=True, exist_ok=True)
        (self.day / "01_refused-then-filled.json").write_text(json.dumps(pkg))
        b = self._write_bundle([pkg])
        req = b["requests"][0]
        url, sha, nbytes = self._png(req["drive_filename"])
        (self.bundle / "response.json").write_text(json.dumps({"media": [{
            "request_id": req["request_id"], "status": "fulfilled",
            "drive": {"file_id": "REAL", "download_url": url},
            "image": {"sha256": sha, "bytes": nbytes, "format": "png",
                      "width": 64, "height": 64}}]}))
        (self.bundle / "DONE").write_text(json.dumps({"date": self.DATE}))
        out = subprocess.run(
            [sys.executable, "scripts/exchange_phase_b.py", "--date",
             self.DATE, "--no-punchup"], cwd=ROOT, capture_output=True,
            text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        report = json.loads((self.bundle / "phase_b_report.json").read_text())
        detail = [d for d in report["details"]
                  if d.get("request_id") == req["request_id"]]
        self.assertTrue(detail)
        self.assertEqual(report["media"]["fulfilled"], 0)
        self.assertEqual(report["media"]["refused"], 1)
        # It went on to try self-fill; offline that finds nothing, which is
        # still the correct PATH — what matters is it did not pin the
        # unverified pointer and did not stop there.
        self.assertIn(detail[-1]["outcome"], ("self_fill", "unfilled"))

    def test_require_checkpoints_forces_it_on_a_no_done_run(self):
        pkg = reddit_pkg(slug="strict-mode")
        self.day.mkdir(parents=True, exist_ok=True)
        (self.day / "01_strict-mode.json").write_text(json.dumps(pkg))
        b = self._write_bundle([pkg])
        req = b["requests"][0]
        url, sha, nbytes = self._png(req["drive_filename"])
        (self.bundle / "response.json").write_text(json.dumps({"media": [{
            "request_id": req["request_id"], "status": "fulfilled",
            "drive": {"file_id": "REAL", "download_url": url},
            "image": {"sha256": sha, "bytes": nbytes, "format": "png",
                      "width": 64, "height": 64}}]}))
        out = self._run("--require-checkpoints")
        report = json.loads((self.bundle / "phase_b_report.json").read_text())
        self.assertEqual(report["media"]["fulfilled"], 0, out.stdout)
        self.assertEqual(report["media"]["refused"], 1)

    def test_a_response_without_done_still_runs(self):
        """Policy A again: a finalizer that wrote its work but never got to
        DONE must not cost the day when the backstop cron picks it up."""
        pkg = reddit_pkg(slug="no-done-marker")
        self.day.mkdir(parents=True, exist_ok=True)
        (self.day / "01_no-done-marker.json").write_text(json.dumps(pkg))
        self._write_bundle([pkg])
        (self.bundle / "response.json").write_text(json.dumps({"media": []}))
        out = self._run()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("ABSENT (proceeding", out.stdout)

    def test_require_done_defers_when_the_finalizer_has_not_finished(self):
        pkg = reddit_pkg(slug="deferred")
        self.day.mkdir(parents=True, exist_ok=True)
        (self.day / "01_deferred.json").write_text(json.dumps(pkg))
        self._write_bundle([pkg])
        out = self._run("--require-done")
        self.assertEqual(out.returncode, 2, out.stdout)

    def test_chatgpt_packages_are_promoted_never_written_straight_in(self):
        """The promotion gate is the only way into the slate, and it runs the
        same structural validator the reserve bank uses."""
        self._write_bundle([])
        bad = graph_pkg(slug="split-broken")
        bad["series"][0]["values"] = bad["series"][0]["values"][:2]
        (self.bundle / "response.json").write_text(json.dumps(
            {"authored": [reddit_pkg(slug="split-good"), bad]}))
        out = self._run()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        names = sorted(p.name for p in self.day.glob("*.json"))
        self.assertEqual(len(names), 1, names)
        self.assertIn("split-good", names[0])
        quarantine = json.loads(
            (self.bundle / "authored_report.json").read_text())
        self.assertEqual(len(quarantine["rejected"]), 1)


# --------------------------------------------------------------------------
# the backstop window — the DST trap, both halves of the year
# --------------------------------------------------------------------------
class TestBackstopWindow(unittest.TestCase):
    """The finalizer runs 7:00 AM America/Chicago, a LOCAL-time task. GitHub
    crons are UTC. The old 12:45 UTC backstop was 7:45 Central in summer (45
    minutes into the finalizer) and 6:45 Central in WINTER — fifteen minutes
    BEFORE the finalizer started. For half the year it would have rendered a
    day with no punch-up and no authored packages, all green.

    Every case here is a real wall-clock moment in one of the two seasons."""

    DATE = "29991228"

    def _at(self, iso_utc):
        import exchange_phase_b as pb
        from datetime import datetime, timezone
        when = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)
        return pb.backstop_status(self.DATE, now_utc=when)

    # -- summer (CDT, UTC-5): finalizer 12:00 UTC, window closes 13:30 UTC --
    def test_summer_the_old_1245_cron_would_now_be_refused(self):
        st = self._at("2026-07-31T12:45:00")
        self.assertFalse(st["ready"], st)
        self.assertIn("07:45", st["local"])

    def test_summer_before_the_finalizer_even_starts(self):
        self.assertFalse(self._at("2026-07-31T11:00:00")["ready"])

    def test_summer_first_cron_runs(self):
        st = self._at("2026-07-31T13:30:00")
        self.assertTrue(st["ready"], st)
        self.assertIn("08:30", st["local"])

    def test_summer_second_cron_also_past_the_window(self):
        self.assertTrue(self._at("2026-07-31T14:30:00")["ready"])

    # -- winter (CST, UTC-6): finalizer 13:00 UTC, window closes 14:30 UTC --
    def test_winter_the_old_1245_cron_fired_BEFORE_the_finalizer(self):
        """The reported bug, pinned. 12:45 UTC in January is 6:45 Central —
        fifteen minutes before the 7:00 finalizer starts."""
        st = self._at("2026-01-15T12:45:00")
        self.assertFalse(st["ready"], st)
        self.assertIn("06:45", st["local"])

    def test_winter_first_cron_is_too_early_and_no_ops(self):
        st = self._at("2026-01-15T13:30:00")
        self.assertFalse(st["ready"], st)
        self.assertIn("07:30", st["local"])

    def test_winter_second_cron_runs(self):
        st = self._at("2026-01-15T14:30:00")
        self.assertTrue(st["ready"], st)
        self.assertIn("08:30", st["local"])

    def test_both_seasons_land_at_the_same_central_time(self):
        """The whole point: the backstop is 08:30 Central in July and 08:30
        Central in January, from two fixed UTC crons."""
        for iso in ("2026-07-31T13:30:00", "2026-01-15T14:30:00"):
            st = self._at(iso)
            self.assertTrue(st["ready"], iso)
            self.assertIn("08:30", st["local"], iso)

    def test_the_dst_changeover_days_are_covered(self):
        # Spring forward 2026-03-08, fall back 2026-11-01.
        self.assertTrue(self._at("2026-03-09T13:30:00")["ready"])   # CDT
        self.assertTrue(self._at("2026-11-02T14:30:00")["ready"])   # CST
        self.assertFalse(self._at("2026-11-02T13:30:00")["ready"])  # CST early

    def test_the_window_is_ninety_minutes_after_seven_central(self):
        import exchange_phase_b as pb
        self.assertEqual(pb.FINALIZER_HOUR_CENTRAL, 7)
        self.assertEqual(pb.FINALIZER_WINDOW_MINUTES, 90)


class TestBackstopDoesNotOverlapALiveFinalizer(unittest.TestCase):
    """The finalizer commits response.json, reads it back, THEN commits DONE.
    A backstop landing between those two commits reads a half-finished day."""

    DATE = "29991227"

    def setUp(self):
        self.bundle = ROOT / "exchange" / "bundles" / self.DATE
        shutil.rmtree(self.bundle, ignore_errors=True)
        self.bundle.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.bundle, ignore_errors=True)

    def _status(self):
        import exchange_phase_b as pb
        from datetime import datetime, timezone
        # 09:00 Central in summer — comfortably past the window, so only the
        # mid-commit check can hold it back.
        return pb.backstop_status(self.DATE, now_utc=datetime.fromisoformat(
            "2026-07-31T14:00:00").replace(tzinfo=timezone.utc))

    def test_a_fresh_response_without_done_defers(self):
        import os
        p = self.bundle / "response.json"
        p.write_text("{}")
        os.utime(p, (1785500000, 1785500000))   # mtime irrelevant; reset below
        import time
        os.utime(p, None)                        # now
        st = self._status()
        self.assertFalse(st["ready"], st)
        self.assertIn("mid-commit", st["reason"])

    def test_an_old_response_without_done_does_not_block_forever(self):
        """A finalizer that died before writing DONE must not wedge the
        backstop shut — that trades a weak day for no day."""
        import os
        p = self.bundle / "response.json"
        p.write_text("{}")
        os.utime(p, (1735689600, 1735689600))    # 2025-01-01, ancient
        self.assertTrue(self._status()["ready"])

    def test_done_present_never_defers(self):
        import os
        (self.bundle / "response.json").write_text("{}")
        (self.bundle / "DONE").write_text("{}")
        os.utime(self.bundle / "response.json", None)
        self.assertTrue(self._status()["ready"])


# --------------------------------------------------------------------------
# the trigger invariant
# --------------------------------------------------------------------------
class TestOnlyDoneTriggersPhaseB(unittest.TestCase):
    def test_phase_b_push_paths_are_done_and_nothing_else(self):
        """A media-progress push must never start a render. If it did, Phase B
        would run at 06:05 with no punch-up, no authored packages and most
        images still missing — with every check green."""
        wf = (ROOT / ".github" / "workflows" / "exchange_phase_b.yml").read_text()
        head = wf.split("workflow_dispatch:")[0]
        paths = [ln.strip().lstrip("- ").strip("'\"")
                 for ln in head.splitlines()
                 if ln.strip().startswith("- 'exchange")
                 or ln.strip().startswith('- "exchange')]
        self.assertEqual(paths, ["exchange/bundles/*/DONE"], paths)

    def test_the_backstop_crons_bracket_the_finalizer_in_both_seasons(self):
        """Two candidate UTC hours, one of which is 08:30 Central in each DST
        half. A single cron cannot do this — that is what put the old backstop
        15 minutes ahead of the winter finalizer."""
        import exchange_phase_b as pb
        wf = (ROOT / ".github" / "workflows" / "exchange_phase_b.yml").read_text()
        crons = [ln.split("cron:")[1].strip().strip("'\"")
                 for ln in wf.splitlines() if "cron:" in ln
                 and not ln.strip().startswith("#")]
        self.assertEqual(sorted(crons), ["30 13 * * *", "30 14 * * *"], crons)
        self.assertNotIn("45 12 * * *", crons,
                         "the 12:45 UTC cron is 6:45 Central in winter — "
                         "before the finalizer starts")
        self.assertIn("--backstop", wf,
                      "the scheduled run must go through the Central-time "
                      "gate, not just fire")
        # And the two crons genuinely straddle the window in both seasons.
        from datetime import datetime, timezone
        for date, ready_utc, early_utc in (("2026-07-31", 13, 14),
                                           ("2026-01-15", 14, 13)):
            def at(h):
                return pb.backstop_status("29991228", now_utc=datetime
                                          .fromisoformat(f"{date}T{h:02d}:30:00")
                                          .replace(tzinfo=timezone.utc))
            self.assertTrue(at(ready_utc)["ready"], (date, ready_utc))
            if date == "2026-01-15":
                self.assertFalse(at(early_utc)["ready"], (date, early_utc))

    def test_no_other_workflow_fires_on_a_checkpoint_push(self):
        for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
            text = wf.read_text()
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped.startswith("- "):
                    continue          # only path-list entries can be triggers
                self.assertNotIn("media-progress", stripped,
                                 f"{wf.name} references media-progress in a "
                                 f"trigger path")


if __name__ == "__main__":
    unittest.main()
