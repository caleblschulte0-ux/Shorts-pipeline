"""Tests for the authoring takeover — ChatGPT as the brain for a dead day.

The takeover is only safe if three things hold: the brief asks for the right
thing (2+2+2, not six of one), the gate that accepts ChatGPT's work is the
same gate the renderers enforce, and a malformed package is quarantined
rather than promoted. Anything that reaches `state/trending_packages/` gets
rendered and uploaded, so "trust but verify" is the whole design.

    python -m unittest tests.test_authoring_takeover -v
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

from shared import authoring_brief as brief          # noqa: E402
from shared import exchange_bundle as xb             # noqa: E402
from tests.test_package_buffer import (               # noqa: E402
    graph_pkg, reddit_pkg, text_card_pkg)

import ingest_authored as ing                        # noqa: E402


# --------------------------------------------------------------------------
# These tests are about MECHANISM, not about today's operator ruling. They run
# against a fixture registry carrying the mix they were written for, so a
# future mix change in config/channel_registry.json breaks only the tests that
# are ABOUT the ruling (tests/test_channel_registry.py) instead of these.
# --------------------------------------------------------------------------
from tests.registry_fixture import LEGACY_MIX, registry   # noqa: E402

_FIXTURE = None


def setUpModule():
    global _FIXTURE
    _FIXTURE = registry(LEGACY_MIX)
    _FIXTURE.__enter__()


def tearDownModule():
    if _FIXTURE is not None:
        _FIXTURE.__exit__(None, None, None)


class TestBrief(unittest.TestCase):
    def test_empty_day_asks_for_the_full_222_slate(self):
        req = brief.build_request("20260801", "trending", have_packages=[],
                                  target=6)
        self.assertEqual(req["write"], 6)
        self.assertEqual(req["mix"], {"reddit_story": 2, "text_card": 2,
                                      "graph_race": 2})

    def test_partial_day_asks_only_for_the_shortfall(self):
        have = [reddit_pkg(slug="alpha-tale"), reddit_pkg(slug="bravo-tale"),
                text_card_pkg(slug="charlie-card")]
        req = brief.build_request("20260801", "trending", have_packages=have,
                                  target=6)
        self.assertEqual(req["write"], 3)
        self.assertEqual(req["mix"],
                         {"reddit_story": 0, "text_card": 1, "graph_race": 2})

    def test_brief_carries_the_full_spec_for_every_format(self):
        req = brief.build_request("20260801", "trending")
        for fmt in ("reddit_story", "text_card", "graph_race"):
            spec = req["formats"][fmt]
            self.assertTrue(spec["required"])
            self.assertTrue(spec["rules"])
            self.assertIn("renderer", spec)

    def test_brief_forbids_writing_straight_into_the_slate(self):
        req = brief.build_request("20260801", "trending")
        self.assertIn("state/trending_packages", req["where"]["never"])

    def test_brief_names_the_graph_drama_gate(self):
        """The renderer hard-refuses small numbers. If the brief doesn't say
        so, ChatGPT writes charts that are silently dropped."""
        rules = " ".join(brief.FORMAT_SPECS["graph_race"]["rules"]).lower()
        self.assertIn("1,000", rules)
        self.assertIn("3x", rules)

    def test_do_not_repeat_reads_real_recent_titles(self):
        req = brief.build_request("20260801", "trending")
        self.assertIsInstance(req["do_not_repeat"], list)


class TestBundleMode(unittest.TestCase):
    def test_normal_day_is_punch_up_mode(self):
        b = xb.build_bundle("20260801", [], [])
        self.assertEqual(b["mode"], "punch_up")
        self.assertNotIn("authoring_request", b)

    def test_takeover_flips_mode_and_leads_with_the_authoring_job(self):
        req = brief.build_request("20260801", "trending")
        b = xb.build_bundle("20260801", [], [], req)
        self.assertEqual(b["mode"], "author")
        self.assertEqual(b["counts"]["to_author"], 6)
        first = b["instructions"]["two_jobs"][0]
        self.assertTrue(first.startswith("0. AUTHOR THE DAY"))

    def test_takeover_keeps_the_media_and_punchup_jobs(self):
        """A partial day still wants its existing packages punched up."""
        req = brief.build_request("20260801", "trending")
        b = xb.build_bundle("20260801", [], [], req)
        joined = " ".join(b["instructions"]["two_jobs"])
        self.assertIn("MEDIA", joined)
        self.assertIn("PUNCH-UP", joined)


class IngestTestCase(unittest.TestCase):
    """Redirect the bundle root and the package dir into a temp tree."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="takeover-"))
        self._saved_root = xb.BUNDLE_ROOT
        self._saved_dirs = dict(ing.PACKAGE_DIRS)
        self._saved_ing_root = ing.ROOT
        xb.BUNDLE_ROOT = self.tmp / "exchange" / "bundles"
        ing.ROOT = self.tmp
        ing.PACKAGE_DIRS["trending"] = "state/trending_packages"
        (self.tmp / "state" / "trending_packages").mkdir(parents=True)
        xb.bundle_dir("20260801").mkdir(parents=True)

    def tearDown(self):
        xb.BUNDLE_ROOT = self._saved_root
        ing.ROOT = self._saved_ing_root
        ing.PACKAGE_DIRS.clear()
        ing.PACKAGE_DIRS.update(self._saved_dirs)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_response(self, authored: list[dict], **extra) -> None:
        body = {"schema": "x", "authored": authored}
        body.update(extra)
        (xb.bundle_dir("20260801") / "response.json").write_text(
            json.dumps(body))

    def day_files(self) -> list[Path]:
        d = self.tmp / "state" / "trending_packages" / "20260801"
        return sorted(d.glob("*.json")) if d.is_dir() else []


class TestIngest(IngestTestCase):
    def test_promotes_a_clean_slate_from_response_json(self):
        self.write_response([reddit_pkg(slug="alpha-tale"), reddit_pkg(slug="bravo-tale"),
                             text_card_pkg(slug="charlie-card"), text_card_pkg(slug="delta-card"),
                             graph_pkg(slug="echo-chart"), graph_pkg(slug="foxtrot-chart")])
        report = ing.ingest("20260801", "trending", target=6)
        self.assertEqual(len(report["promoted"]), 6)
        self.assertEqual(report["rejected"], [])
        self.assertEqual(len(self.day_files()), 6)

    def test_promoted_packages_are_marked_as_chatgpt_authored(self):
        self.write_response([reddit_pkg(slug="alpha-tale")])
        ing.ingest("20260801", "trending", target=6)
        pkg = json.loads(self.day_files()[0].read_text())
        self.assertEqual(pkg["_authored_by"], "chatgpt-takeover")

    def test_loose_files_are_also_read(self):
        d = xb.bundle_dir("20260801") / "authored"
        d.mkdir(parents=True)
        (d / "01_loose.json").write_text(json.dumps(reddit_pkg(slug="loose")))
        report = ing.ingest("20260801", "trending", target=6)
        self.assertEqual(len(report["promoted"]), 1)

    def test_broken_substring_is_quarantined_not_promoted(self):
        bad = reddit_pkg(slug="bad")
        bad["shots"][0]["phrase"] = "this phrase is nowhere in the script"
        self.write_response([bad, reddit_pkg(slug="good")])
        report = ing.ingest("20260801", "trending", target=6)
        self.assertEqual(len(report["promoted"]), 1)
        self.assertEqual(len(report["rejected"]), 1)
        self.assertIn("shot.phrase",
                      " ".join(report["rejected"][0]["problems"]))
        self.assertEqual(len(self.day_files()), 1,
                         "a package that fails validation reached the slate")

    def test_graph_with_mismatched_series_is_quarantined(self):
        bad = graph_pkg(slug="bad-graph")
        bad["series"][0]["values"] = bad["series"][0]["values"][:-2]
        self.write_response([bad])
        report = ing.ingest("20260801", "trending", target=6)
        self.assertEqual(report["promoted"], [])
        self.assertIn("values for", " ".join(report["rejected"][0]["problems"]))

    def test_unknown_format_is_quarantined(self):
        self.write_response([{"slug": "mystery", "title": "T",
                              "script": "words " * 200, "shots": []}])
        report = ing.ingest("20260801", "trending", target=6)
        self.assertEqual(report["promoted"], [])
        self.assertIn("not registered",
                      " ".join(report["rejected"][0]["problems"]))

    def test_duplicate_slug_within_one_response_is_caught(self):
        self.write_response([reddit_pkg(slug="same-slug-twice"), reddit_pkg(slug="same-slug-twice")])
        report = ing.ingest("20260801", "trending", target=6)
        self.assertEqual(len(report["promoted"]), 1)
        self.assertEqual(len(report["rejected"]), 1)

    def test_does_not_overflow_the_slate(self):
        existing = self.tmp / "state" / "trending_packages" / "20260801"
        existing.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            (existing / f"0{i + 1}_have.json").write_text(
                json.dumps(reddit_pkg(slug=f"have-{i}")))
        self.write_response([reddit_pkg(slug=f"newcomer-{i}") for i in range(4)])
        report = ing.ingest("20260801", "trending", target=6)
        self.assertEqual(len(report["promoted"]), 1)
        self.assertEqual(len(report["rejected"]), 3)
        self.assertEqual(len(self.day_files()), 6)

    def test_promotion_never_clobbers_an_existing_package(self):
        existing = self.tmp / "state" / "trending_packages" / "20260801"
        existing.mkdir(parents=True, exist_ok=True)
        (existing / "01_have.json").write_text(json.dumps(
            reddit_pkg(slug="have")))
        self.write_response([reddit_pkg(slug="new-one")])
        ing.ingest("20260801", "trending", target=6)
        names = [p.name for p in self.day_files()]
        self.assertIn("01_have.json", names)
        self.assertEqual(len(names), 2)

    def test_path_traversal_slug_cannot_escape_the_day_directory(self):
        evil = reddit_pkg(slug="../../../../etc/passwd")
        self.write_response([evil])
        ing.ingest("20260801", "trending", target=6)
        for p in self.day_files():
            self.assertTrue(
                str(p).startswith(str(self.tmp)),
                f"authored package escaped the tree: {p}")

    def test_six_of_one_format_is_flagged(self):
        self.write_response([reddit_pkg(slug=f"revenge-story-{i}") for i in range(6)])
        report = ing.ingest("20260801", "trending", target=6)
        self.assertTrue(any("one format" in g
                            for g in report["slate_problems"]),
                        "the 6-of-one regression was not flagged")

    def test_no_authored_packages_is_a_clean_no_op(self):
        report = ing.ingest("20260801", "trending", target=6)
        self.assertEqual(report["offered"], 0)
        self.assertEqual(report["promoted"], [])
        self.assertEqual(self.day_files(), [])

    def test_dry_run_writes_nothing(self):
        self.write_response([reddit_pkg(slug="alpha-tale")])
        report = ing.ingest("20260801", "trending", target=6, dry_run=True)
        self.assertEqual(report["promoted"], ["alpha-tale"])
        self.assertEqual(self.day_files(), [])


class TestGateIsTheSameEverywhere(unittest.TestCase):
    """The brief, the reserve bank, and the ingest must agree on validity —
    if they drift, we ask for one thing and accept another."""

    def test_validate_authored_uses_the_shared_structural_gate(self):
        from shared import package_buffer as buf
        bad = text_card_pkg(slug="xray-card")
        bad["highlights"].append("not in the text")
        self.assertEqual(brief.validate_authored(bad),
                         buf.structural_problems(bad))

    def test_takeover_allows_todays_language_the_bank_refuses(self):
        """The bank needs evergreen; a takeover slate is FOR today, so
        'this morning' is correct there and must not be rejected."""
        from shared import package_buffer as buf
        pkg = text_card_pkg(slug="breaking-thing")
        pkg["text"] = "It happened this morning.\n\n" + pkg["text"]
        self.assertFalse(buf.eligible(pkg)[0])          # bank: refused
        self.assertEqual(brief.validate_authored(pkg), [])  # takeover: fine


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestSubscriptionIsFullyDead(unittest.TestCase):
    """The scenario the takeover actually exists for: no Claude Routine, no
    in-CI brain, an empty reserve bank — and, in the worst case, no Phase A
    either, so no bundle. ChatGPT is the only thing still running.

    Runs the REAL scripts as subprocesses against a scratch date, because
    what matters here is the process exit path, not a mocked function."""

    DATE = "29991228"

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

    def _phase_b(self):
        import subprocess
        return subprocess.run(
            [sys.executable, "scripts/exchange_phase_b.py", "--date",
             self.DATE, "--no-self-fill", "--no-punchup"],
            cwd=ROOT, capture_output=True, text=True)

    def test_no_bundle_and_nothing_authored_is_a_clean_refusal(self):
        """The rescue must not turn 'genuinely nothing happened' into a
        pretend success."""
        out = self._phase_b()
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("nothing to apply", out.stdout)
        self.assertFalse(self.day.exists())

    def test_no_bundle_but_chatgpt_authored_still_ships_the_day(self):
        """Phase A never ran, so there is no bundle. ChatGPT authored the
        slate anyway (its instructions say to). Phase B used to exit 2 here
        and throw the whole day away."""
        (self.bundle / "response.json").write_text(json.dumps(
            {"authored": [reddit_pkg(slug="rescued-lunch-thief"),
                          text_card_pkg(slug="rescued-shrinkflation"),
                          graph_pkg(slug="rescued-streaming")]}))
        out = self._phase_b()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("NO BUNDLE", out.stdout)
        self.assertIn("Rescuing:", out.stdout)
        promoted = sorted(p.name for p in self.day.glob("*.json"))
        self.assertEqual(len(promoted), 3, promoted)

    def test_claude_packages_with_no_bundle_are_still_covered(self):
        """The remaining edge: all six packages exist but Phase A died, so
        nothing ever searched for their media. Bailing would render a full
        Claude-authored slate on bare keyword stock. There is nothing for
        ChatGPT to author here — the day just needs its media pass."""
        self.day.mkdir(parents=True, exist_ok=True)
        for i in range(2):
            (self.day / f"0{i + 1}_claude.json").write_text(
                json.dumps(reddit_pkg(slug=f"claude-wrote-{i}")))
        out = self._phase_b()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("NO BUNDLE", out.stdout)
        self.assertIn("2 already on disk", out.stdout)
        self.assertIn("shots have media", out.stdout,
                      "the existing slate never went through the media pass")

    def test_the_rescue_still_validates(self):
        """Skipping Phase A must not also skip the gate."""
        bad = graph_pkg(slug="rescued-broken")
        bad["series"][0]["values"] = bad["series"][0]["values"][:2]
        (self.bundle / "response.json").write_text(json.dumps(
            {"authored": [reddit_pkg(slug="rescued-good"), bad]}))
        out = self._phase_b()
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(len(list(self.day.glob("*.json"))), 1,
                         "an invalid package survived the rescue path")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestChatGPTSuppliesItsOwnMedia(unittest.TestCase):
    """On a takeover day ChatGPT writes the script AND generates the
    pictures in the same pass — nothing downstream gets a second chance to
    ask it for anything. The bundle used to tell it the opposite."""

    def test_brief_carries_the_media_contract(self):
        req = brief.build_request("20260801", "trending")
        mc = req["media_contract"]
        self.assertIn("Every shot", mc["rule"])
        self.assertIn("media", mc["shape"]["shots"][0])
        self.assertTrue(any("SUPPLY THE MEDIA" in r for r in req["hard_rules"]))

    def test_takeover_note_asks_for_media_not_the_opposite(self):
        """Regression: the note used to read 'you do not need to source
        images for them', which is exactly the job we want done."""
        b = xb.build_bundle("20260801", [], [],
                            brief.build_request("20260801", "trending"))
        note = b["instructions"]["takeover_note"]
        self.assertNotIn("do not need to source", note)
        self.assertIn("supply the media", note.lower())

    def test_contract_exempts_the_formats_with_no_shots(self):
        mc = brief.MEDIA_CONTRACT
        self.assertIn("no `shots`", mc["text_card_and_graph_race"])

    def test_contract_is_honest_about_failing(self):
        self.assertIn("honest", brief.MEDIA_CONTRACT["if_you_cannot"])


class TestAuthoredMediaSurvivesIngest(IngestTestCase):
    def test_shot_media_pointers_reach_the_promoted_package(self):
        pkg = reddit_pkg(slug="with-pictures")
        pkg["shots"][0]["media"] = {
            "status": "fulfilled",
            "drive": {"file_id": "abc"},
            "image": {"sha256": "0" * 64, "format": "png"}}
        self.write_response([pkg])
        ing.ingest("20260801", "trending", target=6)
        on_disk = json.loads(self.day_files()[0].read_text())
        self.assertEqual(on_disk["shots"][0]["media"]["drive"]["file_id"],
                         "abc", "ChatGPT's own image pointer was dropped")


class TestAuthoredMediaVerification(unittest.TestCase):
    """Exercises the REAL download+verify path over file:// URLs, so the
    hash / decode / placeholder gates are genuinely run — no network, no
    mocks standing in for the thing under test."""

    def setUp(self):
        import exchange_phase_b as pb
        self.pb = pb
        self.tmp = Path(tempfile.mkdtemp(prefix="authmedia-"))
        self._saved_cache = pb.MEDIA_CACHE
        pb.MEDIA_CACHE = self.tmp / "cache"

    def tearDown(self):
        self.pb.MEDIA_CACHE = self._saved_cache
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _png(self, name: str, colorful: bool = True) -> tuple[str, str]:
        """Write a PNG, return (file:// url, sha256)."""
        import hashlib
        from PIL import Image
        im = Image.new("RGB", (64, 64))
        if colorful:
            im.putdata([(x * 3 % 256, y * 5 % 256, (x + y) % 256)
                        for y in range(64) for x in range(64)])
        path = self.tmp / name
        im.save(path)
        blob = path.read_bytes()
        return f"file://{path}", hashlib.sha256(blob).hexdigest()

    def _pointer(self, url: str, sha: str) -> dict:
        return {"status": "fulfilled", "drive": {"download_url": url},
                "image": {"sha256": sha, "format": "png"}}

    def _cover(self, pkg: dict) -> dict:
        report = {"media": {"fulfilled": 0, "self_filled": 0, "unfilled": 0}}
        self.pb.cover_authored(pkg, report, no_self_fill=True)
        return report

    def test_a_verified_pointer_is_pinned_to_the_shot(self):
        url, sha = self._png("good.png")
        pkg = reddit_pkg(slug="verified")
        pkg["shots"][0]["media"] = self._pointer(url, sha)
        report = self._cover(pkg)
        self.assertEqual(report["media"]["fulfilled"], 1)
        self.assertEqual(pkg["shots"][0]["media_origin"], "chatgpt_authored")
        self.assertTrue(Path(pkg["shots"][0]["image_url"]).exists())

    def test_a_wrong_hash_is_refused(self):
        url, _ = self._png("tampered.png")
        pkg = reddit_pkg(slug="tampered")
        pkg["shots"][0]["media"] = self._pointer(url, "f" * 64)
        report = self._cover(pkg)
        self.assertEqual(report["media"]["fulfilled"], 0)
        self.assertIsNone(pkg["shots"][0].get("image_url"))

    def test_a_flat_placeholder_is_refused(self):
        url, sha = self._png("flat.png", colorful=False)
        pkg = reddit_pkg(slug="flat")
        pkg["shots"][0]["media"] = self._pointer(url, sha)
        self.assertEqual(self._cover(pkg)["media"]["fulfilled"], 0)

    def test_the_pointer_is_consumed_not_left_on_the_package(self):
        """`media` is a transport field — it must not reach the renderer."""
        url, sha = self._png("consumed.png")
        pkg = reddit_pkg(slug="consumed")
        pkg["shots"][0]["media"] = self._pointer(url, sha)
        self._cover(pkg)
        self.assertNotIn("media", pkg["shots"][0])

    def test_shots_without_a_pointer_are_left_for_self_fill(self):
        url, sha = self._png("one.png")
        pkg = reddit_pkg(slug="partial")
        pkg["shots"][0]["media"] = self._pointer(url, sha)
        report = self._cover(pkg)
        self.assertEqual(report["media"]["fulfilled"], 1)
        self.assertEqual(report["media"]["unfilled"], len(pkg["shots"]) - 1)

    def test_entity_resolution_cannot_erase_chatgpt_media(self):
        """`enrich_package` writes `image_url: None` onto shots it cannot
        resolve. Run it AFTER pinning and it silently erases verified
        ChatGPT images — the 2026-07-30 failure shape, where 23 good images
        were discarded with every workflow green."""
        url, sha = self._png("order.png")
        pkg = reddit_pkg(slug="ordering")
        for shot in pkg["shots"]:
            shot["media"] = self._pointer(url, sha)
        report = self._cover(pkg)
        self.assertEqual(report["media"]["fulfilled"], len(pkg["shots"]))
        for shot in pkg["shots"]:
            self.assertTrue(shot.get("image_url"),
                            "a verified ChatGPT image was erased")
