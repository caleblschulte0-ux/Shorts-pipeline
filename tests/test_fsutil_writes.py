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

from shared.fsutil import write_json_if_changed, load_json   # noqa: E402


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
