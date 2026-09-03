"""A no-op write is not free — `write_json_if_changed`.

`data_learning/niche.config.json` is 719 KB and was rewritten in full on
every explainer run whether or not anything in it had changed. Two runs that
both changed nothing still produced two conflicting 719 KB diffs, which is
why `explainer.yml` carries a `--autostash -X ours` retry loop around its
push.

The file is also the second-largest in the repo, so every no-op write is a
719 KB commit, a push, and a permanent line in `git log -p`.

    python -m unittest tests.test_fsutil_writes -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from shared.fsutil import (write_json_if_changed, load_json,   # noqa: E402
                           load_state_json, CorruptStateError)


class TestWriteJsonIfChanged(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fsutil-"))
        self.p = self.tmp / "cfg.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_it_creates_a_missing_file(self):
        self.assertTrue(write_json_if_changed(self.p, {"a": 1}))
        self.assertEqual(load_json(self.p, None), {"a": 1})

    def test_rewriting_identical_content_does_NOT_touch_the_file(self):
        write_json_if_changed(self.p, {"a": 1})
        before = self.p.stat().st_mtime_ns
        self.assertFalse(write_json_if_changed(self.p, {"a": 1}))
        self.assertEqual(self.p.stat().st_mtime_ns, before,
                         "a no-op write still rewrote the file — that is the "
                         "719 KB conflict magnet")

    def test_a_real_change_is_written(self):
        write_json_if_changed(self.p, {"a": 1})
        self.assertTrue(write_json_if_changed(self.p, {"a": 2}))
        self.assertEqual(load_json(self.p, None), {"a": 2})

    def test_a_change_deep_inside_a_big_document_is_detected(self):
        big = {"stories": [{"slug": f"s{i}", "segments": [{"n": i}]}
                           for i in range(200)]}
        write_json_if_changed(self.p, big)
        self.assertFalse(write_json_if_changed(self.p, big))
        big["stories"][137]["segments"][0]["n"] = 999
        self.assertTrue(write_json_if_changed(self.p, big),
                        "a real edit was skipped — worse than churn")

    def test_appending_a_story_is_written(self):
        cfg = {"stories": [{"slug": "a"}]}
        write_json_if_changed(self.p, cfg)
        cfg["stories"].append({"slug": "b"})
        self.assertTrue(write_json_if_changed(self.p, cfg))
        self.assertEqual(len(load_json(self.p, {})["stories"]), 2)

    def test_it_honours_ensure_ascii_when_comparing(self):
        """author_stories writes with ensure_ascii=False. If the comparison
        used a different encoding the file would rewrite every single run."""
        obj = {"title": "café — naïve"}
        write_json_if_changed(self.p, obj, ensure_ascii=False)
        self.assertFalse(write_json_if_changed(self.p, obj,
                                               ensure_ascii=False))
        self.assertIn("café", self.p.read_text(encoding="utf-8"))

    def test_an_unreadable_file_is_simply_overwritten(self):
        self.p.write_bytes(b"\xff\xfe not utf8 at all")
        self.assertTrue(write_json_if_changed(self.p, {"a": 1}))
        self.assertEqual(load_json(self.p, None), {"a": 1})

    def test_corrupt_json_is_replaced_rather_than_trusted(self):
        self.p.write_text("{ this is not json")
        self.assertTrue(write_json_if_changed(self.p, {"a": 1}))

    def test_the_write_is_atomic_and_leaves_no_temp_files(self):
        write_json_if_changed(self.p, {"a": 1})
        self.assertEqual([q.name for q in self.tmp.iterdir()], ["cfg.json"])

    def test_it_ends_with_a_newline_like_the_old_writers_did(self):
        write_json_if_changed(self.p, {"a": 1})
        self.assertTrue(self.p.read_text().endswith("\n"))


class TestLoadStateJsonFailsClosed(unittest.TestCase):
    """Doctor finding d65eddf69fba: authoritative state must distinguish
    corruption from absence. `load_json` returns the empty default for BOTH,
    so a truncated posted log read as "nothing ever posted" — a duplicate
    upload plus, on the next write, the loss of the real history.
    `load_state_json` keeps default-on-missing (first runs work) and raises
    on corruption (a run without its dedupe state must not run)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fsutil-state-"))
        self.p = self.tmp / "posted_log.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_missing_file_returns_default_first_run_ok(self):
        self.assertEqual(load_state_json(self.p, {"posted": {}}),
                         {"posted": {}})
        self.assertFalse(self.p.exists(), "reading must not create the file")

    def test_valid_file_is_returned(self):
        self.p.write_text('{"posted": {"a": 1}}')
        self.assertEqual(load_state_json(self.p, {}), {"posted": {"a": 1}})

    def test_corrupt_file_refuses_and_names_the_file(self):
        self.p.write_text('{"posted": {"a"')     # a torn write
        with self.assertRaises(CorruptStateError) as ctx:
            load_state_json(self.p, {"posted": {}})
        self.assertIn(str(self.p), str(ctx.exception))

    def test_corrupt_bytes_are_preserved_in_a_sidecar(self):
        bad = b'{"posted": {"a"'
        self.p.write_bytes(bad)
        with self.assertRaises(CorruptStateError):
            load_state_json(self.p, {})
        sidecar = self.p.with_name(self.p.name + ".corrupt")
        self.assertEqual(sidecar.read_bytes(), bad,
                         "the evidence must survive for the repair")
        # ...and the original is untouched — the loader repairs nothing.
        self.assertEqual(self.p.read_bytes(), bad)

    def test_undecodable_bytes_refuse_too(self):
        self.p.write_bytes(b"\xff\xfe not utf8 at all")
        with self.assertRaises(CorruptStateError):
            load_state_json(self.p, {})

    def test_wrong_top_level_shape_refuses_when_declared(self):
        """A log that parses as a bare list where a dict is required is as
        unusable as garbage — log.get() would explode later, or worse,
        quietly iterate the wrong thing."""
        self.p.write_text('["not", "a", "dict"]')
        with self.assertRaises(CorruptStateError):
            load_state_json(self.p, {}, expect_type=dict)

    def test_valid_null_is_data_not_corruption(self):
        """Without expect_type, `null` is a legitimate parse result — the
        strict loader must not confuse a parsed None with a failure."""
        self.p.write_text("null\n")
        self.assertIsNone(load_state_json(self.p, {"posted": {}}))

    def test_the_tolerant_loader_is_unchanged_for_caches(self):
        """load_json keeps default-on-corrupt: expendable caches must never
        be able to fail a run."""
        self.p.write_text("{not json")
        self.assertEqual(load_json(self.p, {"cache": True}), {"cache": True})


class TestAuthoritativeReadersUseTheStrictLoader(unittest.TestCase):
    """The mechanism is worthless unless the posted-log/ledger readers are
    actually wired to it — same pattern as TestTheConfigWritersUseIt.
    (scripts/run_third.py keeps its own earlier fail-closed loader with the
    full incident narrative; it already refuses corruption.)"""

    READERS = ["scripts/run_trending_daily.py", "scripts/post_stories.py",
               "scripts/post_curiosity.py", "scripts/render_cinematic.py",
               "scripts/build_longform.py", "scripts/request_permission.py"]

    def test_they_all_go_through_load_state_json(self):
        for rel in self.READERS:
            self.assertIn("load_state_json", (ROOT / rel).read_text(),
                          f"{rel} no longer uses the fail-closed state "
                          f"loader — a corrupt posted log would read as "
                          f"empty again (doctor finding d65eddf69fba)")

    def test_merge_posted_log_refuses_a_corrupt_side(self):
        """The union-merge is the other way a corrupt log silently drops
        entries: one side read as {} makes the 'union' a mass-delete of
        that side. Missing stays empty (fresh checkout); corrupt is fatal."""
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import merge_posted_log as mpl
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        tmp = Path(tempfile.mkdtemp(prefix="merge-"))
        try:
            bad = tmp / "theirs.json"
            bad.write_text('{"posted"')
            with self.assertRaises(SystemExit) as ctx:
                mpl._load(str(bad))
            self.assertIn(str(bad), str(ctx.exception))
            self.assertEqual(mpl._load(str(tmp / "missing.json")), {})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestTheConfigWritersUseIt(unittest.TestCase):
    """Every writer of the explainer config, not just one of them."""

    WRITERS = ["scripts/author_stories.py", "scripts/story_forge.py",
               "scripts/normalize_charts.py"]

    def test_none_of_them_blind_writes_the_config(self):
        for rel in self.WRITERS:
            src = (ROOT / rel).read_text()
            self.assertNotIn("CONFIG.write_text(", src,
                             f"{rel} still rewrites niche.config.json "
                             f"unconditionally")

    def test_they_all_go_through_the_helper(self):
        for rel in self.WRITERS:
            self.assertIn("write_json_if_changed", (ROOT / rel).read_text(),
                          f"{rel} does not use write_json_if_changed")


if __name__ == "__main__":
    unittest.main()
