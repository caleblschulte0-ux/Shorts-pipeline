"""Regression test for `scripts/format_scoreboard.py`'s title-to-format join.

Found while triaging doctor finding 33ccbcdc479b ("hold the trending mix
until reliability and attribution are measurable"): the script's own
fallback bucketed reddit_story packages as `"reddit"`, a name that does not
exist in `config/channel_registry.json` (the format is `reddit_story`), so
`rows[fmt]` raised `KeyError` on every real reddit_story video and the whole
report — wired into `daily.yml` — silently died behind `|| exit 0`. Without
a working scoreboard nothing can argue a mix change from format-level
evidence, which is exactly what that strategy finding asked for.

    python -m unittest tests.test_format_scoreboard -v
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import format_scoreboard as sb            # noqa: E402


class TestFormatScoreboard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.pkg_root = root / "trending_packages"
        self.analytics = root / "analytics.json"
        self.pkg_root.mkdir()
        self._orig_pkg_root = sb.PKG_ROOT
        self._orig_analytics = sb.ANALYTICS
        sb.PKG_ROOT = self.pkg_root
        sb.ANALYTICS = self.analytics
        self.addCleanup(setattr, sb, "PKG_ROOT", self._orig_pkg_root)
        self.addCleanup(setattr, sb, "ANALYTICS", self._orig_analytics)

    def _write_pkg(self, name, data):
        d = self.pkg_root / "20260819"
        d.mkdir(exist_ok=True)
        (d / name).write_text(json.dumps(data))

    def _write_analytics(self, videos):
        self.analytics.write_text(json.dumps({"videos": videos}))

    def test_a_reddit_story_package_is_bucketed_as_reddit_story_not_KeyError(self):
        """The registry's actual format id, not the script's old made-up
        fallback name — this is the exact crash the doctor finding named."""
        self._write_pkg("r1.json", {"title": "A Reddit Story",
                                    "subreddit": "AskReddit"})
        self._write_analytics([{"title": "A Reddit Story", "views": 42}])
        result = sb.build()
        formats = {r["format"]: r for r in result["formats"]}
        self.assertIn("reddit_story", formats)
        self.assertEqual(formats["reddit_story"]["views"], 42)
        self.assertEqual(result["unmatched"], 0)

    def test_an_unknown_format_rolls_up_as_unmatched_rather_than_crashing(self):
        """A future/legacy format id the scoreboard does not know about must
        degrade to unmatched, not take the whole report down."""
        self._write_pkg("r2.json", {"title": "Mystery Format",
                                    "format": "totally_new_format"})
        self._write_analytics([{"title": "Mystery Format", "views": 9}])
        result = sb.build()
        self.assertEqual(result["unmatched"], 1)
        self.assertEqual(result["matched"], 0)

    def test_graph_race_and_explainer_still_bucket_correctly(self):
        self._write_pkg("g1.json", {"title": "A Graph Race",
                                    "format": "graph_race"})
        self._write_pkg("e1.json", {"title": "An Explainer"})
        self._write_analytics([{"title": "A Graph Race", "views": 10},
                               {"title": "An Explainer", "views": 5}])
        result = sb.build()
        formats = {r["format"]: r for r in result["formats"]}
        self.assertEqual(formats["graph_race"]["views"], 10)
        self.assertEqual(formats["explainer"]["views"], 5)


class TestTheRealInvocationImportsCleanly(unittest.TestCase):
    """daily.yml runs `python3 scripts/format_scoreboard.py` — a script
    invocation, not a module import — which puts scripts/ on sys.path[0]
    instead of the repo root. `from shared import channel_registry` used to
    fail there with a bare `except Exception` swallowing it, silently
    turning EVERY reddit_story package into 'explainer' (no crash, wrong
    data — worse than the KeyError it replaced). Runs the real subprocess,
    exactly as CI does, and checks the real registry-backed classification
    survives it."""

    def test_the_script_finds_reddit_story_when_run_directly(self):
        out = subprocess.run(
            [sys.executable, "scripts/format_scoreboard.py"],
            cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("reddit_story", out.stdout, out.stdout)


if __name__ == "__main__":
    unittest.main()
