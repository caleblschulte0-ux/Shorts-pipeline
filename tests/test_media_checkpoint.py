"""Tests for the split-worker checkpoint contract (`shared/media_checkpoint`).

Fully offline — no Drive, no network, no ChatGPT. Everything that touches the
filesystem runs against a temp `BUNDLE_ROOT`.

The point of most of these is not that the happy path works; it is that each
specific way the 06:00 / 07:00 split can silently produce a wrong video is
mechanically refused:

  * two different requests collapsing onto one filename
  * a checkpoint from yesterday's bundle being reused today
  * an image adopted on the strength of its filename alone
  * a crashed worker's claim blocking a shot forever
  * the media worker writing DONE and rendering half a day
  * an authored shot's image landing on the wrong package

    python -m unittest tests.test_media_checkpoint -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from funnel import media_judge                       # noqa: E402
from shared import authoring_brief as brief          # noqa: E402
from shared import exchange_bundle as xb             # noqa: E402
from shared import media_checkpoint as mc            # noqa: E402

DATE = "20260731"
SHA_A = "a" * 64
SHA_B = "b" * 64

PKG = {
    "slug": "spacex-catch",
    "title": "SpaceX Caught Starship Again",
    "script": ("SpaceX just caught Starship again. The booster came down at "
               "1,200 mph and stopped dead."),
    "shots": [
        {"phrase": "SpaceX just caught Starship again",
         "query": "SpaceX Starship rocket launch"},
        {"phrase": "The booster came down at 1,200 mph",
         "query": "rocket booster descent"},
    ],
}


def good_image(sha=SHA_A, **kw):
    img = {"sha256": sha, "bytes": 1554380, "format": "png",
           "width": 1080, "height": 1080}
    img.update(kw)
    return img


def good_drive(file_id="1AbCdEf", *, request_id="r1", date=DATE, fmt="png",
               **kw):
    """A COMPLETE Drive record. Every field here is compared against the
    checkpoint, so a helper that quietly omitted one would hide the very
    checks these tests exist to prove."""
    d = {"file_id": file_id, "folder_id": "1FolderX",
         "filename": mc.deterministic_filename(date, request_id, fmt),
         "download_url": f"https://drive.google.com/uc?export=download&id={file_id}",
         "sharing": "anyone_with_link"}
    d.update(kw)
    return d


class _TempBundles(unittest.TestCase):
    """Redirect every module that resolves a bundle path at call time."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self._saved = (mc.BUNDLE_ROOT, xb.BUNDLE_ROOT)
        mc.BUNDLE_ROOT = self.root
        xb.BUNDLE_ROOT = self.root
        (self.root / DATE).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        mc.BUNDLE_ROOT, xb.BUNDLE_ROOT = self._saved
        self._td.cleanup()

    def write_bundle(self, obj):
        p = self.root / DATE / "bundle.json"
        p.write_text(json.dumps(obj, indent=2) + "\n")
        return p


# --------------------------------------------------------------------------
# ids and filenames
# --------------------------------------------------------------------------
class TestSafeRequestId(unittest.TestCase):
    def test_already_safe_ids_are_untouched(self):
        self.assertEqual(mc.safe_request_id("spacex-catch-s2-9f1c4a"),
                         "spacex-catch-s2-9f1c4a")
        self.assertEqual(mc.safe_request_id("a_b.c-1"), "a_b.c-1")

    def test_sanitizing_never_collapses_two_requests(self):
        """`a/b` and `a:b` both sanitize to `a-b`. If that were the answer,
        two different prompts would share one Drive file and one checkpoint."""
        ids = ["a/b", "a:b", "a b", "a-b", "a|b", "a\\b"]
        safe = [mc.safe_request_id(i) for i in ids]
        self.assertEqual(len(set(safe)), len(ids), dict(zip(ids, safe)))

    def test_truncation_still_distinguishes(self):
        a = mc.safe_request_id("x" * 200 + "-one")
        b = mc.safe_request_id("x" * 200 + "-two")
        self.assertNotEqual(a, b)
        self.assertLessEqual(len(a), mc._MAX_SAFE + 9)

    def test_path_traversal_cannot_escape(self):
        for hostile in ("../../etc/passwd", "..", "./.././x", "/abs/path"):
            s = mc.safe_request_id(hostile)
            self.assertNotIn("/", s)
            self.assertFalse(s.startswith("."), s)
            p = mc.checkpoint_path(DATE, hostile)
            self.assertIn("media-progress", str(p))
            self.assertNotIn("..", str(p))

    def test_empty_id_still_yields_a_filename(self):
        self.assertTrue(mc.safe_request_id(""))
        self.assertTrue(mc.deterministic_filename(DATE, ""))


class TestDeterministicFilename(unittest.TestCase):
    def test_shape_and_roundtrip(self):
        name = mc.deterministic_filename("2026-07-31", "spacex-s2-abc")
        self.assertEqual(name, "20260731__spacex-s2-abc.png")
        parsed = mc.parse_filename(name)
        self.assertEqual(parsed["date"], "20260731")
        self.assertEqual(parsed["safe_request_id"], "spacex-s2-abc")
        self.assertEqual(parsed["ext"], "png")

    def test_dashed_and_bare_dates_agree(self):
        self.assertEqual(mc.deterministic_filename("2026-07-31", "r"),
                         mc.deterministic_filename("20260731", "r"))

    def test_jpeg_normalizes_so_one_image_has_one_name(self):
        self.assertEqual(mc.deterministic_filename(DATE, "r", "jpeg"),
                         mc.deterministic_filename(DATE, "r", "JPG"))

    def test_unknown_extension_falls_back_to_png(self):
        self.assertTrue(mc.deterministic_filename(DATE, "r", "exe")
                        .endswith(".png"))

    def test_parse_rejects_a_non_deterministic_name(self):
        for bad in ("image.png", "20260731-foo.png", "foo__bar.png", ""):
            self.assertIsNone(mc.parse_filename(bad), bad)


class TestAuthoredShotIds(unittest.TestCase):
    def test_stable_and_derived_only_from_package_and_index(self):
        a = mc.authored_shot_request_id("kangaroo-court", 3)
        b = mc.authored_shot_request_id("kangaroo-court", 3)
        self.assertEqual(a, b)
        self.assertEqual(a, "authored-kangaroo-court-s3")
        self.assertNotEqual(a, mc.authored_shot_request_id("kangaroo-court", 4))

    def test_normalization_matches_promotion(self):
        """`ingest_authored` rewrites every slug through `safe_slug` before
        the package lands on disk. If these two disagreed, every authored-shot
        checkpoint would be orphaned the moment its package was promoted."""
        for raw in ("Kangaroo Court!", "  weird__slug  ", "ALLCAPS",
                    "emoji-🦘-slug", "a/b/c", "-leading-dash-"):
            self.assertEqual(mc._norm_package_id(raw), brief.safe_slug(raw),
                             raw)

    def test_roundtrip_and_detection(self):
        rid = mc.authored_shot_request_id("some-pkg", 0)
        self.assertEqual(mc.parse_authored_shot_request_id(rid),
                         ("some-pkg", 0))
        self.assertTrue(mc.is_authored_shot_request(rid))
        self.assertFalse(mc.is_authored_shot_request("spacex-s2-abc"))
        self.assertIsNone(mc.parse_authored_shot_request_id("authored-x"))

    def test_bad_index_does_not_raise(self):
        self.assertTrue(mc.authored_shot_request_id("p", None))
        self.assertTrue(mc.authored_shot_request_id("p", -4))


# --------------------------------------------------------------------------
# the bundle publishes the filename BEFORE anyone starts
# --------------------------------------------------------------------------
class TestBundleCarriesTheContract(_TempBundles):
    def test_every_request_carries_its_filename_and_prompt_hash(self):
        rep = media_judge.judge_package(PKG, None)
        b = xb.build_bundle(DATE, [PKG], [rep])
        self.assertTrue(b["requests"])
        for req in b["requests"]:
            rid = req["request_id"]
            self.assertEqual(req["safe_request_id"], mc.safe_request_id(rid))
            self.assertEqual(req["drive_filename"],
                             mc.deterministic_filename(DATE, rid, "png"))
            self.assertEqual(req["prompt_sha256"],
                             mc.prompt_sha256(req["prompt_verbatim"]))
            self.assertIn("media-progress", req["checkpoint_path"])

    def test_protocol_block_is_present_and_names_both_workers(self):
        rep = media_judge.judge_package(PKG, None)
        b = xb.build_bundle(DATE, [PKG], [rep])
        proto = b["media_protocol"]
        self.assertEqual(proto["schema"], mc.SCHEMA)
        self.assertIn("media", proto["workers"])
        self.assertIn("finalizer", proto["workers"])
        self.assertEqual(len(proto["recovery_order"]), 5)
        who = b["instructions"]["who_runs_what"]
        self.assertIn("NEVER write DONE", who["media_worker_0600"])
        self.assertIn("DONE", who["only_done_renders"])

    def test_animation_requests_ask_for_an_mp4_filename(self):
        import os
        os.environ[xb.ANIM_BUDGET_ENV] = "1"
        try:
            rep = media_judge.judge_package(PKG, None)
            b = xb.build_bundle(DATE, [PKG], [rep])
            anim = [r for r in b["requests"] if r["kind"] == "animation"][0]
            self.assertTrue(anim["drive_filename"].endswith(".mp4"))
        finally:
            os.environ.pop(xb.ANIM_BUDGET_ENV, None)


# --------------------------------------------------------------------------
# bundle identity
# --------------------------------------------------------------------------
class TestBundleIdentity(_TempBundles):
    """Identity tracks THE ASK, not the file that carries it.

    It used to be the sha256 of bundle.json's bytes. Phase A runs on every
    auto-merge and re-judges media each time — six rewrites on 2026-08-01,
    the last five hours AFTER the 06:00 worker finished. Every one silently
    invalidated the checkpoints written before it, and because a DONE run now
    requires checkpoints, all 17 verified images would have been refused."""

    def _bundle(self, *reqs, registry_sha="reg-a"):
        return {"date": DATE, "contract": {"registry_sha256": registry_sha,
                                           "registry_revision": 1},
                "requests": [{"request_id": r, "prompt_sha256": f"p-{r}",
                              "drive_filename": f"{DATE}__{r}.png",
                              "kind": "image", "slug": "s", "shot_index": 0}
                             for r in reqs]}

    def test_a_cosmetic_rewrite_does_NOT_move_the_identity(self):
        """The 2026-08-01 bug, pinned. Phase A re-judging media changes the
        file without changing anything a worker acts on."""
        b = self._bundle("r1", "r2")
        first = mc.write_bundle_identity(DATE, b)
        noisy = dict(b, packages=[{"media_health": {"strong": 3}}],
                     generated_at="later", status="open")
        self.assertEqual(mc.ask_fingerprint(noisy), first)
        self.assertEqual(mc.write_bundle_identity(DATE, noisy), first)
        self.assertEqual(mc.bundle_identity(DATE), first)

    def test_request_order_does_not_move_it(self):
        a = mc.ask_fingerprint(self._bundle("r1", "r2"))
        b = mc.ask_fingerprint(self._bundle("r2", "r1"))
        self.assertEqual(a, b)

    def test_a_CHANGED_ASK_does_move_it(self):
        base = mc.ask_fingerprint(self._bundle("r1"))
        self.assertNotEqual(base, mc.ask_fingerprint(self._bundle("r1", "r2")))
        self.assertNotEqual(base, mc.ask_fingerprint(
            self._bundle("r1", registry_sha="reg-b")))
        changed = self._bundle("r1")
        changed["requests"][0]["prompt_sha256"] = "different"
        self.assertNotEqual(base, mc.ask_fingerprint(changed))

    def test_the_sidecar_is_what_readers_get(self):
        b = self._bundle("r1")
        ident = mc.write_bundle_identity(DATE, b)
        self.assertEqual(mc.bundle_identity(DATE), ident)
        self.assertTrue((mc.bundle_dir(DATE) / mc.IDENTITY_FILE).exists())

    def test_chatgpt_takeover_identity_survives_a_late_phase_a_bundle(self):
        """A late bundle is useful as a work order, but cannot invalidate
        media made after ChatGPT already claimed the production date."""
        late = self._bundle("late-request")
        mc.write_bundle_identity(DATE, late)
        (mc.bundle_dir(DATE) / "takeover.json").write_text(json.dumps({
            "owner": "chatgpt",
            "mode": "takeover",
            "checkpoint_identity": "takeover-claim-abc123",
        }))
        self.assertEqual(mc.bundle_identity(DATE), "takeover-claim-abc123")

    def test_old_bundles_without_a_sidecar_still_resolve(self):
        self.write_bundle({"a": 1})
        self.assertTrue(mc.bundle_identity(DATE))

    def test_a_corrupt_sidecar_falls_back_rather_than_lying(self):
        self.write_bundle({"a": 1})
        (mc.bundle_dir(DATE) / mc.IDENTITY_FILE).write_text("not-a-hash")
        self.assertTrue(mc.bundle_identity(DATE))

    def test_missing_bundle_is_none_not_a_crash(self):
        self.assertIsNone(mc.bundle_identity("20991231"))

    def test_garbage_never_raises(self):
        for junk in (None, [], "x", {}):
            self.assertIsInstance(mc.ask_fingerprint(junk), str)


# --------------------------------------------------------------------------
# checkpoints
# --------------------------------------------------------------------------
class TestCheckpoints(_TempBundles):
    def _cp(self, **kw):
        base = dict(date=DATE, request_id="r1", bundle_id="bid",
                    prompt="a prompt", drive=good_drive(), image=good_image())
        base.update(kw)
        return mc.build_checkpoint(**base)

    def test_roundtrip(self):
        cp = self._cp()
        path = mc.write_checkpoint(DATE, cp)
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "r1.json")
        back = mc.read_checkpoint(DATE, "r1")
        self.assertEqual(back["request_id"], "r1")
        self.assertEqual(back["drive"]["filename"],
                         mc.deterministic_filename(DATE, "r1", "png"))
        self.assertEqual(mc.all_checkpoints(DATE)["r1"]["bundle"]["identity"],
                         "bid")

    def test_clean_checkpoint_is_reusable(self):
        cp = self._cp()
        self.assertTrue(mc.checkpoint_reusable(
            cp, date=DATE, bundle_id="bid", request_id="r1",
            prompt="a prompt"))

    def test_a_changed_prompt_invalidates_it(self):
        cp = self._cp()
        problems = mc.checkpoint_problems(cp, date=DATE, bundle_id="bid",
                                          request_id="r1",
                                          prompt="a DIFFERENT prompt")
        self.assertTrue(any("prompt changed" in p for p in problems), problems)

    def test_a_different_bundle_invalidates_it(self):
        cp = self._cp()
        problems = mc.checkpoint_problems(cp, date=DATE, bundle_id="OTHER",
                                          request_id="r1", prompt="a prompt")
        self.assertTrue(any("DIFFERENT bundle" in p for p in problems),
                        problems)

    def test_yesterdays_checkpoint_is_refused(self):
        cp = self._cp(date="20260730")
        problems = mc.checkpoint_problems(cp, date=DATE, bundle_id="bid",
                                          request_id="r1", prompt="a prompt")
        self.assertTrue(any("not '20260731'" in p for p in problems), problems)

    def test_wrong_request_id_is_refused(self):
        cp = self._cp()
        problems = mc.checkpoint_problems(cp, date=DATE, bundle_id="bid",
                                          request_id="r2", prompt="a prompt")
        self.assertTrue(any("request_id" in p for p in problems), problems)

    def test_unverified_status_is_not_reusable(self):
        for status in ("in_progress", "failed", "skipped"):
            cp = self._cp(status=status)
            self.assertFalse(mc.checkpoint_reusable(
                cp, date=DATE, bundle_id="bid", request_id="r1",
                prompt="a prompt"), status)

    def test_thin_records_are_refused(self):
        cases = {
            "no drive.file_id": dict(
                drive={"sharing": "anyone_with_link", "folder_id": "1F",
                       "filename": mc.deterministic_filename(DATE, "r1")}),
            "no drive.folder_id": dict(
                drive={"sharing": "anyone_with_link", "file_id": "1A",
                       "filename": mc.deterministic_filename(DATE, "r1")}),
            "not 64 hex": dict(image=good_image(sha="nope")),
            "image.bytes missing or zero": dict(image=good_image(bytes=0)),
            "image.width missing or zero": dict(image=good_image(width=0)),
            # sharing and filename are new agreement fields — a checkpoint
            # that omits either is a claim we cannot act on.
            "not 'anyone_with_link'": dict(
                drive=good_drive(sharing="private")),
            "no drive.filename": dict(drive=good_drive(filename="")),
            "not the deterministic": dict(
                drive=good_drive(filename="whatever.png")),
            "drive.filename names request": dict(
                drive=good_drive(
                    filename=mc.deterministic_filename(DATE, "SOMEONE-ELSE"))),
            "drive.filename is dated": dict(
                drive=good_drive(
                    filename=mc.deterministic_filename("20260101", "r1"))),
        }
        for expect, kw in cases.items():
            problems = mc.checkpoint_problems(self._cp(**kw), date=DATE,
                                              bundle_id="bid",
                                              request_id="r1")
            self.assertTrue(any(expect in p for p in problems),
                            (expect, problems))

    def test_garbage_never_raises(self):
        for junk in (None, [], "x", {}, {"schema": "other"}):
            self.assertTrue(mc.checkpoint_problems(junk, date=DATE))
        self.assertIsNone(mc.read_checkpoint(DATE, "nope"))
        self.assertEqual(mc.all_checkpoints("20991231"), {})

    def test_unreadable_checkpoint_file_is_skipped_not_fatal(self):
        mc.write_checkpoint(DATE, self._cp())
        (mc.progress_dir(DATE) / "broken.json").write_text("{not json")
        self.assertEqual(list(mc.all_checkpoints(DATE)), ["r1"])


# --------------------------------------------------------------------------
# orphan reconciliation
# --------------------------------------------------------------------------
class TestPlanRecovery(_TempBundles):
    def _cp(self, **kw):
        base = dict(date=DATE, request_id="r1", bundle_id="bid",
                    prompt="a prompt", drive=good_drive(), image=good_image())
        base.update(kw)
        return mc.build_checkpoint(**base)

    def test_valid_checkpoint_wins(self):
        mc.write_checkpoint(DATE, self._cp())
        plan = mc.plan_recovery(date=DATE, request_id="r1", bundle_id="bid",
                                prompt="a prompt")
        self.assertEqual(plan["action"], "reuse_checkpoint")

    def test_valid_checkpoint_beats_even_a_live_claim(self):
        mc.write_checkpoint(DATE, self._cp())
        mc.create_claim(DATE, "r1", worker="media", worker_run_id="someone")
        plan = mc.plan_recovery(date=DATE, request_id="r1", bundle_id="bid",
                                prompt="a prompt", worker_run_id="me")
        self.assertEqual(plan["action"], "reuse_checkpoint")

    def test_single_orphan_is_adopted_not_trusted(self):
        name = mc.deterministic_filename(DATE, "r1")
        plan = mc.plan_recovery(date=DATE, request_id="r1", bundle_id="bid",
                                prompt="a prompt",
                                drive_listing=[{"name": name, "id": "1XYZ"}])
        self.assertEqual(plan["action"], "adopt_orphan")
        self.assertEqual(plan["drive_file_id"], "1XYZ")
        self.assertIn("hash the BYTES", plan["reason"])

    def test_duplicate_names_are_conflicted_never_guessed(self):
        name = mc.deterministic_filename(DATE, "r1")
        plan = mc.plan_recovery(date=DATE, request_id="r1", bundle_id="bid",
                                prompt="a prompt",
                                drive_listing=[{"name": name, "id": "1A"},
                                               {"name": name, "id": "1B"}])
        self.assertEqual(plan["action"], "conflicted")
        self.assertEqual(len(plan["candidates"]), 2)
        self.assertNotIn("drive_file_id", plan)

    def test_a_similar_filename_is_not_a_match(self):
        plan = mc.plan_recovery(
            date=DATE, request_id="r1", bundle_id="bid", prompt="p",
            drive_listing=[{"name": "20260731__r1.PNG", "id": "1A"},
                           {"name": "r1.png", "id": "1B"},
                           {"name": mc.deterministic_filename(DATE, "r2"),
                            "id": "1C"}])
        self.assertEqual(plan["action"], "generate")

    def test_stale_checkpoint_plus_orphan_adopts_rather_than_reusing(self):
        """The image on Drive was made for a prompt that has since changed.
        Adoption re-verifies and re-checkpoints it; reuse would have pinned a
        picture of the wrong thing."""
        mc.write_checkpoint(DATE, self._cp(prompt="OLD prompt"))
        name = mc.deterministic_filename(DATE, "r1")
        plan = mc.plan_recovery(date=DATE, request_id="r1", bundle_id="bid",
                                prompt="NEW prompt",
                                drive_listing=[{"name": name, "id": "1XYZ"}])
        self.assertEqual(plan["action"], "adopt_orphan")
        self.assertTrue(any("prompt changed" in p
                            for p in plan["checkpoint_problems"]))

    def test_nothing_anywhere_means_generate(self):
        plan = mc.plan_recovery(date=DATE, request_id="r1", bundle_id="bid",
                                prompt="p", drive_listing=[])
        self.assertEqual(plan["action"], "generate")

    def test_live_claim_by_another_run_defers(self):
        mc.create_claim(DATE, "r1", worker="media", worker_run_id="them")
        plan = mc.plan_recovery(date=DATE, request_id="r1", bundle_id="bid",
                                prompt="p", drive_listing=[],
                                worker_run_id="me")
        self.assertEqual(plan["action"], "claimed")

    def test_our_own_claim_does_not_block_us(self):
        mc.create_claim(DATE, "r1", worker="media", worker_run_id="me")
        plan = mc.plan_recovery(date=DATE, request_id="r1", bundle_id="bid",
                                prompt="p", drive_listing=[],
                                worker_run_id="me")
        self.assertEqual(plan["action"], "generate")


# --------------------------------------------------------------------------
# claims
# --------------------------------------------------------------------------
class TestClaims(_TempBundles):
    def test_first_writer_wins_second_is_told_who_holds_it(self):
        a = mc.create_claim(DATE, "r1", worker="media", worker_run_id="A")
        b = mc.create_claim(DATE, "r1", worker="finalizer", worker_run_id="B")
        self.assertTrue(a["granted"])
        self.assertFalse(b["granted"])
        self.assertIn("media", b["reason"])

    def test_reentry_by_the_same_run_is_idempotent(self):
        mc.create_claim(DATE, "r1", worker="media", worker_run_id="A")
        again = mc.create_claim(DATE, "r1", worker="media", worker_run_id="A")
        self.assertTrue(again["granted"])
        self.assertFalse(again["reclaimed"])

    def test_an_expired_claim_never_blocks_forever(self):
        """A worker that dies mid-image must not leave a tombstone that
        silently costs one shot per crash, permanently."""
        past = mc._utcnow() - timedelta(hours=3)
        mc.create_claim(DATE, "r1", worker="media", worker_run_id="dead",
                        lease_seconds=60, now=past)
        self.assertFalse(mc.claim_active(mc.read_claim(DATE, "r1")))
        got = mc.create_claim(DATE, "r1", worker="finalizer",
                              worker_run_id="alive")
        self.assertTrue(got["granted"])
        self.assertTrue(got["reclaimed"])
        self.assertEqual(mc.read_claim(DATE, "r1")["worker"], "finalizer")

    def test_expired_claims_are_listable(self):
        past = mc._utcnow() - timedelta(hours=3)
        mc.create_claim(DATE, "r1", worker="media", worker_run_id="dead",
                        lease_seconds=60, now=past)
        mc.create_claim(DATE, "r2", worker="media", worker_run_id="live")
        stale = [c["request_id"] for c in mc.expired_claims(DATE)]
        self.assertEqual(stale, ["r1"])

    def test_release_then_reclaim(self):
        mc.create_claim(DATE, "r1", worker="media", worker_run_id="A")
        self.assertTrue(mc.release_claim(DATE, "r1"))
        self.assertTrue(mc.create_claim(DATE, "r1", worker="media",
                                        worker_run_id="B")["granted"])

    def test_corrupt_claim_file_is_taken_over_not_honoured(self):
        p = mc.claim_path(DATE, "r1")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json")
        got = mc.create_claim(DATE, "r1", worker="media", worker_run_id="A")
        self.assertTrue(got["granted"])

    def test_claim_lives_under_the_claims_dir(self):
        mc.create_claim(DATE, "r1", worker="media")
        self.assertTrue(mc.claim_path(DATE, "r1").parent.name ==
                        mc.CLAIMS_DIRNAME)


# --------------------------------------------------------------------------
# worker boundaries
# --------------------------------------------------------------------------
class TestWorkerBoundaries(unittest.TestCase):
    def test_media_worker_may_checkpoint(self):
        for p in (f"exchange/bundles/{DATE}/media-progress/r1.json",
                  f"exchange/bundles/{DATE}/media-progress/claims/r1.json"):
            ok, why = mc.worker_may_write("media", p)
            self.assertTrue(ok, (p, why))

    def test_media_worker_may_not_fire_the_render(self):
        """The whole reason the split can go wrong: DONE at 06:00 renders an
        hour before anything is authored or punched up, all checks green."""
        for p in (f"exchange/bundles/{DATE}/DONE",
                  f"exchange/bundles/{DATE}/response.json",
                  f"exchange/bundles/{DATE}/authored/01_x.json"):
            ok, why = mc.worker_may_write("media", p)
            self.assertFalse(ok, p)
            self.assertIn("never write", why)

    def test_finalizer_may_write_the_lot(self):
        for p in (f"exchange/bundles/{DATE}/DONE",
                  f"exchange/bundles/{DATE}/response.json",
                  f"exchange/bundles/{DATE}/authored/01_x.json",
                  f"exchange/bundles/{DATE}/media-progress/r1.json",
                  "retro/20260731/proposals/p.json"):
            ok, why = mc.worker_may_write("finalizer", p)
            self.assertTrue(ok, (p, why))

    def test_neither_worker_may_touch_pipeline_code(self):
        for w in ("media", "finalizer"):
            for p in ("scripts/exchange_phase_b.py", "shared/levity.py",
                      ".github/workflows/daily.yml", "tests/test_levity.py",
                      "exchange/README.md", "docs/FALLBACKS.md",
                      "state/trending_packages/20260731/01_x.json",
                      "CLAUDE.md"):
                ok, why = mc.worker_may_write(w, p)
                self.assertFalse(ok, (w, p))
                self.assertTrue(why)

    def test_unknown_worker_is_refused(self):
        ok, why = mc.worker_may_write("chatgpt", "anything")
        self.assertFalse(ok)
        self.assertIn("unknown worker", why)


# --------------------------------------------------------------------------
# Phase B response validation
# --------------------------------------------------------------------------
class TestResponseValidation(_TempBundles):
    def setUp(self):
        super().setUp()
        rep = media_judge.judge_package(PKG, None)
        self.bundle = xb.build_bundle(DATE, [PKG], [rep])
        self.write_bundle(self.bundle)
        self.bid = mc.bundle_identity(DATE)
        self.req = self.bundle["requests"][0]
        self.rid = self.req["request_id"]

    def _checkpoint(self, **kw):
        base = dict(date=DATE, request_id=self.rid, bundle_id=self.bid,
                    prompt=self.req["prompt_verbatim"],
                    drive=good_drive(request_id=self.rid), image=good_image())
        base.update(kw)
        cp = mc.build_checkpoint(**base)
        mc.write_checkpoint(DATE, cp)
        return cp

    def _entry(self, **kw):
        e = {"request_id": self.rid, "status": "fulfilled",
             "drive": good_drive(request_id=self.rid), "image": good_image()}
        e.update(kw)
        return e

    def _validate(self, response, **kw):
        return mc.validate_response_media(response, self.bundle, date=DATE,
                                          bundle_id=self.bid, **kw)

    def test_a_matching_pair_passes(self):
        self._checkpoint()
        out = self._validate({"media": [self._entry()]})
        self.assertEqual(out["rejected"], [])
        self.assertEqual(out["ok"], [self.rid])

    def test_hash_disagreeing_with_the_checkpoint_is_refused(self):
        self._checkpoint()
        out = self._validate({"media": [self._entry(image=good_image(SHA_B))]})
        self.assertTrue(any("image.sha256 disagrees" in p
                            for p in out["rejected"][0]["problems"]))

    def test_byte_count_disagreeing_is_refused(self):
        self._checkpoint()
        out = self._validate(
            {"media": [self._entry(image=good_image(bytes=99))]})
        self.assertTrue(any("image.bytes disagrees" in p
                            for p in out["rejected"][0]["problems"]))

    def test_fabricated_hash_is_refused(self):
        self._checkpoint()
        out = self._validate(
            {"media": [self._entry(image=good_image(sha="deadbeef"))]})
        self.assertTrue(any("not 64 hex" in p
                            for p in out["rejected"][0]["problems"]))

    def test_missing_hash_is_refused(self):
        self._checkpoint()
        img = good_image()
        img.pop("sha256")
        out = self._validate({"media": [self._entry(image=img)]})
        self.assertTrue(any("sha256 missing" in p
                            for p in out["rejected"][0]["problems"]))

    def test_missing_dimensions_or_format_is_refused(self):
        self._checkpoint()
        for field in ("width", "height", "format"):
            img = good_image()
            img.pop(field)
            out = self._validate({"media": [self._entry(image=img)]})
            self.assertTrue(any(field in p
                                for p in out["rejected"][0]["problems"]),
                            field)

    def test_wrong_request_id_is_refused(self):
        self._checkpoint()
        out = self._validate({"media": [self._entry(request_id="not-a-request")]})
        self.assertTrue(any("no such request_id" in p
                            for p in out["rejected"][0]["problems"]))

    def test_duplicate_request_ids_are_refused(self):
        self._checkpoint()
        out = self._validate({"media": [self._entry(), self._entry()]})
        self.assertEqual(len(out["rejected"]), 1)
        self.assertTrue(any("duplicate request_id" in p
                            for p in out["rejected"][0]["problems"]))

    def test_a_checkpoint_from_another_bundle_is_refused(self):
        self._checkpoint(bundle_id="a-different-bundle")
        out = self._validate({"media": [self._entry()]})
        self.assertTrue(any("DIFFERENT bundle" in p
                            for p in out["rejected"][0]["problems"]))

    def test_a_checkpoint_whose_prompt_moved_is_refused(self):
        self._checkpoint(prompt="something else entirely")
        out = self._validate({"media": [self._entry()]})
        self.assertTrue(any("prompt changed" in p
                            for p in out["rejected"][0]["problems"]))

    def test_one_drive_file_under_two_requests_refuses_BOTH(self):
        """Even when the bytes are IDENTICAL and both pointers agree with
        their own checkpoints perfectly.

        Matching hashes are not a licence to share a file: two requests are
        two different lines of script, and one image answering both is a shot
        doing double duty — which is how a slate ends up visually repeating.
        Both sides go, because nothing here can say which request legitimately
        owns the file, and guessing is the same coin flip `plan_recovery`
        refuses on duplicate filenames."""
        r2 = self.bundle["requests"][1]
        rid2 = r2["request_id"]
        for req in (self.req, r2):
            rid = req["request_id"]
            mc.write_checkpoint(DATE, mc.build_checkpoint(
                date=DATE, request_id=rid, bundle_id=self.bid,
                prompt=req["prompt_verbatim"],
                drive=good_drive("SAME", request_id=rid),
                image=good_image(SHA_A)))
        out = self._validate({"media": [
            self._entry(drive=good_drive("SAME", request_id=self.rid)),
            {"request_id": rid2, "status": "fulfilled",
             "drive": good_drive("SAME", request_id=rid2),
             "image": good_image(SHA_A)}]})
        self.assertEqual(out["ok"], [], "a shared file survived validation")
        self.assertEqual({r["request_id"] for r in out["rejected"]},
                         {self.rid, rid2})
        for r in out["rejected"]:
            self.assertTrue(any("claimed by TWO requests" in p
                                for p in r["problems"]), r)

    def test_missing_checkpoint_warns_by_default_and_fails_when_required(self):
        soft = self._validate({"media": [self._entry()]})
        self.assertEqual(soft["rejected"], [])
        self.assertEqual(len(soft["warnings"]), 1)
        hard = self._validate({"media": [self._entry()]},
                              require_checkpoint=True)
        self.assertEqual(len(hard["rejected"]), 1)

    def test_an_honest_failure_is_not_a_defect(self):
        out = self._validate({"media": [self._entry(status="failed")]})
        self.assertEqual(out["ok"], [])
        self.assertIn("not a delivered asset",
                      out["rejected"][0]["problems"][0])

    def test_authored_shot_media_in_the_top_level_array_is_refused(self):
        rid = mc.authored_shot_request_id("some-pkg", 1)
        out = self._validate({"media": [self._entry(request_id=rid)]})
        self.assertTrue(any("must ride ON THE SHOT" in p
                            for p in out["rejected"][0]["problems"]))

    def test_authored_shot_on_its_own_shot_passes(self):
        rid = mc.authored_shot_request_id("kangaroo-court", 1)
        mc.write_checkpoint(DATE, mc.build_checkpoint(
            date=DATE, request_id=rid, bundle_id=self.bid,
            request_kind="authored_shot", package_id="kangaroo-court",
            shot_index=1, prompt="anything",
            drive=good_drive(request_id=rid), image=good_image()))
        out = self._validate({"authored": [{
            "slug": "kangaroo-court",
            "shots": [{"phrase": "a"},
                      {"phrase": "b", "media": {
                          "status": "fulfilled",
                          "drive": good_drive(request_id=rid),
                          "image": good_image()}}]}]})
        self.assertEqual(out["rejected"], [])
        self.assertEqual(out["ok"], [rid])

    def test_authored_shot_explicit_wrong_request_id_is_refused(self):
        rid = mc.authored_shot_request_id("kangaroo-court", 1)
        mc.write_checkpoint(DATE, mc.build_checkpoint(
            date=DATE, request_id=rid, bundle_id=self.bid,
            request_kind="authored_shot", package_id="kangaroo-court",
            shot_index=1, prompt="anything",
            drive=good_drive(request_id=rid), image=good_image()))
        out = self._validate({"authored": [{
            "slug": "kangaroo-court",
            "shots": [{}, {"media": {
                "request_id": "authored-someone-else-s1",
                "status": "fulfilled",
                "drive": good_drive(request_id=rid),
                "image": good_image()}}]}]})
        self.assertTrue(any("does not match" in p
                            for p in out["rejected"][0]["problems"]))

    def test_authored_media_on_the_wrong_package_is_refused(self):
        rid = mc.authored_shot_request_id("kangaroo-court", 1)
        mc.write_checkpoint(DATE, mc.build_checkpoint(
            date=DATE, request_id=rid, bundle_id=self.bid,
            request_kind="authored_shot", package_id="A DIFFERENT PACKAGE",
            shot_index=1, prompt="anything",
            drive=good_drive(request_id=rid), image=good_image()))
        out = self._validate({"authored": [{
            "slug": "kangaroo-court",
            "shots": [{}, {"media": {"status": "fulfilled",
                                     "drive": good_drive(request_id=rid),
                                     "image": good_image()}}]}]})
        self.assertTrue(any("wrong" in p or "belongs to package" in p
                            for p in out["rejected"][0]["problems"]),
                        out["rejected"])

    def test_authored_media_on_the_wrong_shot_is_refused(self):
        rid = mc.authored_shot_request_id("kangaroo-court", 1)
        mc.write_checkpoint(DATE, mc.build_checkpoint(
            date=DATE, request_id=rid, bundle_id=self.bid,
            request_kind="authored_shot", package_id="kangaroo-court",
            shot_index=4, prompt="anything",
            drive=good_drive(request_id=rid), image=good_image()))
        out = self._validate({"authored": [{
            "slug": "kangaroo-court",
            "shots": [{}, {"media": {"status": "fulfilled",
                                     "drive": good_drive(request_id=rid),
                                     "image": good_image()}}]}]})
        self.assertTrue(any("shot 4" in p
                            for p in out["rejected"][0]["problems"]),
                        out["rejected"])

    def test_a_bundle_request_checkpoint_cannot_back_an_authored_shot(self):
        rid = mc.authored_shot_request_id("kangaroo-court", 0)
        mc.write_checkpoint(DATE, mc.build_checkpoint(
            date=DATE, request_id=rid, bundle_id=self.bid,
            request_kind="bundle_request", package_id="kangaroo-court",
            shot_index=0, prompt="anything",
            drive=good_drive(request_id=rid), image=good_image()))
        out = self._validate({"authored": [{
            "slug": "kangaroo-court",
            "shots": [{"media": {"status": "fulfilled",
                                 "drive": good_drive(request_id=rid),
                                 "image": good_image()}}]}]})
        self.assertTrue(any("request_kind" in p
                            for p in out["rejected"][0]["problems"]))

    # -- correction 4: agreement is field by field, not just the hash -----
    def test_every_agreement_field_is_compared(self):
        """Hash and byte count only say the CONTENT matches. An image can
        verify byte-for-byte and still be under a name nobody can recover, in
        the wrong folder, or private — so every field is checked, and this
        test walks all of them so none can be quietly dropped later."""
        cases = {
            ("drive", "file_id"): "SOMETHING-ELSE",
            ("drive", "folder_id"): "1WrongFolder",
            ("image", "sha256"): SHA_B,
            ("image", "bytes"): 999,
            ("image", "format"): "webp",
            ("image", "width"): 640,
            ("image", "height"): 480,
        }
        for (section, field), wrong in cases.items():
            self._checkpoint()
            entry = self._entry()
            entry[section] = dict(entry[section])
            entry[section][field] = wrong
            out = self._validate({"media": [entry]})
            self.assertTrue(out["rejected"], (section, field))
            self.assertTrue(
                any(f"{section}.{field} disagrees" in p or
                    f"{section}.{field}" in p
                    for p in out["rejected"][0]["problems"]),
                (section, field, out["rejected"][0]["problems"]))

    def test_a_field_present_on_the_checkpoint_but_missing_here_is_refused(self):
        for section, field in (("drive", "folder_id"), ("drive", "filename"),
                               ("image", "width"), ("image", "format")):
            self._checkpoint()
            entry = self._entry()
            entry[section] = {k: v for k, v in entry[section].items()
                              if k != field}
            out = self._validate({"media": [entry]})
            self.assertTrue(out["rejected"], (section, field))

    def test_the_deterministic_filename_is_compared(self):
        self._checkpoint()
        out = self._validate({"media": [self._entry(
            drive=good_drive(request_id="a-different-request"))]})
        self.assertTrue(any("drive.filename" in p
                            for p in out["rejected"][0]["problems"]),
                        out["rejected"])

    def test_a_private_drive_file_is_refused_even_when_it_matches(self):
        """Drive serves an HTML permission page instead of bytes for anything
        not link-visible. 'I uploaded it' and 'you can fetch it' are separate
        claims and only one of them puts a picture in the video."""
        self._checkpoint(drive=good_drive(request_id=self.rid,
                                          sharing="private"))
        out = self._validate({"media": [self._entry(
            drive=good_drive(request_id=self.rid, sharing="private"))]})
        self.assertTrue(any("anyone_with_link" in p
                            for p in out["rejected"][0]["problems"]),
                        out["rejected"])

    def test_sharing_disagreement_is_refused(self):
        self._checkpoint()
        out = self._validate({"media": [self._entry(
            drive=good_drive(request_id=self.rid, sharing="private"))]})
        self.assertTrue(any("sharing disagrees" in p
                            for p in out["rejected"][0]["problems"]),
                        out["rejected"])

    def test_legacy_public_true_still_reads_as_link_visible(self):
        """Older pointers said `public: true` rather than naming a state.
        That is the same assertion and must keep working."""
        self.assertEqual(mc.sharing_of({"public": True}), mc.PUBLIC_SHARING)
        self.assertEqual(mc.sharing_of({"public": False}), "private")
        self.assertEqual(mc.sharing_of({}), "unknown")
        self.assertEqual(mc.sharing_of(None), "unknown")
        drive = good_drive(request_id=self.rid)
        drive.pop("sharing")
        drive["public"] = True
        self._checkpoint(drive=dict(drive))
        out = self._validate({"media": [self._entry(drive=dict(drive))]})
        self.assertEqual(out["rejected"], [])

    # -- the response must answer THIS bundle's contract ------------------
    def test_a_response_answering_another_contract_is_refused(self):
        """A worker that read a newer registry, or yesterday's bundle, is
        answering a different question — its counts and formats will be wrong
        in ways nothing downstream can see."""
        self.bundle["contract"] = {"registry_revision": 1,
                                   "registry_sha256": "a" * 64,
                                   "source_commit": "abc123",
                                   "production_date": DATE}
        self._checkpoint()
        out = self._validate({"contract": {"registry_revision": 2,
                                           "registry_sha256": "b" * 64},
                              "media": [self._entry()]})
        self.assertEqual(len(out["contract_problems"]), 2, out)
        self.assertTrue(any("registry_revision" in p
                            for p in out["contract_problems"]))

    def test_a_matching_contract_declaration_passes(self):
        self.bundle["contract"] = {"registry_revision": 3,
                                   "registry_sha256": "c" * 64,
                                   "production_date": DATE}
        self._checkpoint()
        out = self._validate({"contract": {"registry_revision": 3,
                                           "registry_sha256": "c" * 64,
                                           "production_date": DATE},
                              "media": [self._entry()]})
        self.assertEqual(out["contract_problems"], [])
        self.assertEqual(out["rejected"], [])

    def test_a_silent_response_is_tolerated(self):
        """An older worker simply does not declare a contract. Silence is
        not evidence of a mismatch; a WRONG declaration is."""
        self.bundle["contract"] = {"registry_revision": 3}
        self._checkpoint()
        out = self._validate({"media": [self._entry()]})
        self.assertEqual(out["contract_problems"], [])

    def test_garbage_response_never_raises(self):
        for junk in (None, [], "x", {}, {"media": "not a list"},
                     {"media": [None, 3, {"request_id": None}]}):
            out = mc.validate_response_media(junk, self.bundle, date=DATE,
                                             bundle_id=self.bid)
            self.assertIn("counts", out)


if __name__ == "__main__":
    unittest.main()
