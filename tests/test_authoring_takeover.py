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
        self.assertIn("not bankable",
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
