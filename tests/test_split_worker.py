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
sys.path.insert(0, str(ROOT / "scripts"))

from funnel import media_judge                       # noqa: E402
from shared import authoring_brief as brief          # noqa: E402
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

    def _bundle(self, packages, *, target=6, channel_requests=None):
        req = None
        if len(packages) < target:
            req = brief.build_request(DATE, "trending",
                                      have_packages=packages, target=target)
        reports = [media_judge.judge_package(p, None) for p in packages]
        return xb.build_bundle(DATE, packages, reports, req,
                               channel_requests or ({"trending": req} if req
                                                    else None))

    def test_zero_packages_asks_for_the_full_slate(self):
        b = self._bundle([])
        self.assertEqual(b["mode"], "author")
        self.assertEqual(b["authoring_request"]["write"], 6)
        self.assertEqual(b["authoring_request"]["mix"],
                         {"reddit_story": 2, "text_card": 2, "graph_race": 2})

    def test_partial_days_ask_only_for_the_shortfall(self):
        cases = {
            1: ([reddit_pkg(slug="a")], {"reddit_story": 1, "text_card": 2,
                                    "graph_race": 2}),
            3: ([reddit_pkg(slug="a"), reddit_pkg(slug="b"), text_card_pkg(slug="c")],
                {"reddit_story": 0, "text_card": 1, "graph_race": 2}),
            5: ([reddit_pkg(slug="a"), reddit_pkg(slug="b"), text_card_pkg(slug="c"),
                 text_card_pkg(slug="d"), graph_pkg(slug="e")],
                {"reddit_story": 0, "text_card": 0, "graph_race": 1}),
        }
        for have, (pkgs, want) in cases.items():
            b = self._bundle(pkgs)
            self.assertEqual(b["authoring_request"]["mix"], want, have)
            self.assertEqual(b["authoring_request"]["write"], 6 - have, have)

    def test_a_full_slate_is_punch_up_mode(self):
        pkgs = [reddit_pkg(slug="a"), reddit_pkg(slug="b"), text_card_pkg(slug="c"),
                text_card_pkg(slug="d"), graph_pkg(slug="e"), graph_pkg(slug="f")]
        b = self._bundle(pkgs)
        self.assertEqual(b["mode"], "punch_up")
        self.assertNotIn("authoring_request", b)

    def test_a_full_trending_slate_does_not_hide_the_other_channels(self):
        """The trap the split makes easier to fall into: six packages exist,
        so 'nothing to author' — and the explainer rewrite silently never
        happens. Explainer and curiosity are separate channels with separate
        asks."""
        pkgs = [reddit_pkg(slug="a"), reddit_pkg(slug="b"), text_card_pkg(slug="c"),
                text_card_pkg(slug="d"), graph_pkg(slug="e"), graph_pkg(slug="f")]
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
        saved = mc.BUNDLE_ROOT
        try:
            mc.BUNDLE_ROOT = ROOT / "exchange" / "bundles"
            bid = mc.bundle_identity(self.DATE)
            mc.write_checkpoint(self.DATE, mc.build_checkpoint(
                date=self.DATE, request_id=rid, bundle_id=bid,
                prompt=req["prompt_verbatim"],
                drive={"file_id": "REAL", "download_url": url,
                       "filename": req["drive_filename"],
                       "sharing": "anyone_with_link"},
                image={"sha256": sha, "bytes": nbytes, "format": "png",
                       "width": 64, "height": 64}))
        finally:
            mc.BUNDLE_ROOT = saved
        (self.bundle / "response.json").write_text(json.dumps({"media": [{
            "request_id": rid, "status": "fulfilled",
            "drive": {"file_id": "REAL", "download_url": url},
            "image": {"sha256": sha, "bytes": nbytes, "format": "png",
                      "width": 64, "height": 64}}]}))
        out = self._run()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        report = json.loads((self.bundle / "phase_b_report.json").read_text())
        self.assertEqual(report["media"]["refused"], 0, out.stdout)
        self.assertEqual(report["media"]["fulfilled"], 1, out.stdout)
        self.assertEqual(report["checkpoints"]["ok"], 1)

    def test_no_checkpoints_at_all_still_ships_the_day(self):
        """Policy A. A worker that skipped its checkpoints must lose its
        images to a warning, not to stock self-fill — the byte verification
        below it is independent and strong on its own."""
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

    def test_require_checkpoints_turns_that_warning_into_a_refusal(self):
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
