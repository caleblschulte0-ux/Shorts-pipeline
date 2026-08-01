"""Tests for the placement gate — the hard enforcement of the funnel rule.

Docs said "shared capability goes up the funnel, never into a channel";
the gate makes auto-merge refuse PRs that break it. These tests simulate
each violation class with real files in the working tree (restored after),
plus prove the current tree is clean so the gate can't block legitimate work.

    python -m unittest tests.test_placement_gate -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))   # APPEND: see note below

import placement_gate as pg  # noqa: E402


class TestChannelMapping(unittest.TestCase):
    def test_channel_groups(self):
        self.assertEqual(pg.channel_of("make_reddit_story.py"), "daily")
        self.assertEqual(pg.channel_of("reddit_card.py"), "daily")
        self.assertEqual(pg.channel_of("data_learning/studio_render.py"),
                         "data_learning")
        self.assertEqual(pg.channel_of("third_capture/auto_edit.py"), "third")

    def test_out_of_scope(self):
        for f in ("scripts/run_third.py", "funnel/media_funnel.py",
                  "shared/fsutil.py", "engines/parallax.py",
                  "tests/test_exchange.py", "docs/PIPELINE_LAYOUT.md"):
            self.assertIsNone(pg.channel_of(f), f)

    def test_import_target_channels(self):
        self.assertEqual(pg._module_channel("data_learning.story"),
                         "data_learning")
        self.assertEqual(pg._module_channel("third_capture"), "third")
        self.assertEqual(pg._module_channel("make_text_card"), "daily")
        self.assertIsNone(pg._module_channel("funnel.media_funnel"))
        self.assertIsNone(pg._module_channel("shared.fsutil"))
        self.assertIsNone(pg._module_channel("os"))


class TestViolations(unittest.TestCase):
    """Plant real violation files, assert the gate catches them, clean up."""

    def setUp(self):
        self._planted: list[Path] = []

    def tearDown(self):
        for p in self._planted:
            p.unlink(missing_ok=True)

    def _plant(self, rel: str, content: str) -> str:
        p = ROOT / rel
        p.write_text(content)
        self._planted.append(p)
        return rel

    def test_shadow_caught(self):
        f = self._plant("third_capture/fsutil.py", "def x():\n    pass\n")
        errs = pg.check_shadow([f])
        self.assertEqual(len(errs), 1)
        self.assertIn("SHADOWS shared/fsutil.py", errs[0])

    def test_init_py_exempt(self):
        errs = pg.check_shadow(["third_capture/__init__.py"])
        self.assertEqual(errs, [])

    def test_copy_from_shared_caught(self):
        src = (ROOT / "shared" / "punchup_guard.py").read_text()
        # steal a real chunk of a shared module into a channel file
        chunk = "\n".join(l for l in src.splitlines()
                          if len(l.strip()) >= 20)[:4000]
        f = self._plant("data_learning/my_guard.py", chunk)
        errs = pg.check_copy([f])
        self.assertEqual(len(errs), 1)
        self.assertIn("COPIES", errs[0])
        self.assertIn("moves UP the funnel", errs[0])

    def test_copy_across_channels_caught(self):
        src = (ROOT / "data_learning" / "charts.py").read_text()
        chunk = "\n".join(l for l in src.splitlines()
                          if len(l.strip()) >= 20)[:4000]
        f = self._plant("third_capture/charts_local.py", chunk)
        errs = pg.check_copy([f])
        self.assertEqual(len(errs), 1)
        self.assertIn("channel 'data_learning'", errs[0])

    def test_small_original_file_not_flagged(self):
        f = self._plant("third_capture/tiny_helper.py",
                        "def third_only_thing(clip):\n"
                        "    return clip.duration_for_this_channel_only * 2\n")
        self.assertEqual(pg.check_copy([f]), [])

    def test_cross_channel_import_caught(self):
        f = self._plant("third_capture/sneaky.py",
                        "from data_learning import charts\n")
        errs = pg.check_ximport([f])
        self.assertEqual(len(errs), 1)
        self.assertIn("channels never import each other", errs[0])

    def test_daily_import_from_channel_dir_caught(self):
        f = self._plant("data_learning/wants_daily.py",
                        "import make_text_card\n")
        errs = pg.check_ximport([f])
        self.assertEqual(len(errs), 1)

    def test_same_group_import_allowed(self):
        f = self._plant("data_learning/uses_sibling.py",
                        "from data_learning import charts\n")
        self.assertEqual(pg.check_ximport([f]), [])

    def test_shared_layer_import_allowed(self):
        f = self._plant("third_capture/fine.py",
                        "from shared import fsutil\n"
                        "from funnel import media_funnel\n"
                        "from engines.still_motion import maybe_kenburns\n")
        self.assertEqual(pg.check_ximport([f]), [])


class TestCurrentTreeIsClean(unittest.TestCase):
    """The gate must pass on main as it stands, or auto-merge is bricked."""

    def test_tree_audit_passes(self):
        everything = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py")
                      if ".git" not in p.parts and "cache" not in p.parts]
        channel_files = [f for f in everything if pg.channel_of(f)]
        self.assertGreater(len(channel_files), 10)   # sanity: scope is real
        self.assertEqual(pg.check_shadow(channel_files), [])
        self.assertEqual(pg.check_ximport(channel_files), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
