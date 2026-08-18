"""Third's fallback slate must be sized from the registry, never a template.

Doctor finding, signature 5ac409690185, ruled `doing` 2026-08-15:
`state/third_packages/default_clip.json`
carried its own `count` field (4) while `config/channel_registry.json` set
`target_count("third")` to 6. `run_third.main` read the template's count
with no registry lookup at all, so a flawless fallback day topped out at
4/6 — one quality rejection produced the 3/6 shape the 2026-08-13 alarm
actually recorded. The registry is supposed to be the ONLY place channel
policy lives (CLAUDE.md); a template field that silently wins is a second
source of truth.

    python -m unittest tests.test_third_fallback_count -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))   # APPEND: see note below

from shared import channel_registry  # noqa: E402
import run_third  # noqa: E402

# A minimal fallback template shaped like the real default_clip.json, but
# with a `count` deliberately different from the live registry's
# target_count("third") so the test proves the template loses.
_FIXTURE_TEMPLATE = {
    "count": 999,
    "story_count": 1,
    "channel": "third",
    "title": "{clip_title}",
    "capture": {"kind": "twitch_clip", "sources": {"twitch": ["kaicenat"]},
                "core": ["kaicenat"], "range": "24hr", "top": 8,
                "min_views": 1500, "min_pool": 8, "min_banger": 0.5,
                "min_banger_content": 0.7, "max_per_streamer": 2,
                "content_hard_floor": 0.35},
    "hashtags": ["shorts"],
}


class ThirdFallbackSlateSizeTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._orig_package_dir = run_third.PACKAGE_DIR
        self._tmpdir_ctx = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir_ctx.cleanup)
        tmp_path = Path(self._tmpdir_ctx.name)
        run_third.PACKAGE_DIR = tmp_path
        (tmp_path / "default_clip.json").write_text(
            json.dumps(_FIXTURE_TEMPLATE))

    def tearDown(self):
        run_third.PACKAGE_DIR = self._orig_package_dir

    def test_slate_size_comes_from_the_live_registry_not_the_template(self):
        registry_target = channel_registry.target_count("third")
        self.assertGreater(registry_target, 0)
        self.assertNotEqual(
            _FIXTURE_TEMPLATE["count"], registry_target,
            "fixture must disagree with the registry or this test cannot "
            "distinguish the fix from the bug")

        packages = run_third._synthesize_fallback_packages("20260819")

        self.assertEqual(len(packages), registry_target)
        slugs = [pkg["slug"] for pkg, _ in packages]
        self.assertEqual(len(slugs), len(set(slugs)),
                         "synthesized slugs must be unique")
        self.assertEqual(
            slugs, [f"clip-20260819-{i}" for i in range(1, registry_target + 1)])

    def test_synthesis_is_deterministic_for_the_same_date(self):
        first = run_third._synthesize_fallback_packages("20260819")
        second = run_third._synthesize_fallback_packages("20260819")
        self.assertEqual([p["story_mode"] for p, _ in first],
                         [p["story_mode"] for p, _ in second])

    def test_no_template_synthesizes_nothing(self):
        (run_third.PACKAGE_DIR / "default_clip.json").unlink()
        self.assertEqual(run_third._synthesize_fallback_packages("20260819"),
                         [])

    def test_unresolvable_registry_refuses_to_guess_a_count(self):
        with mock.patch.object(
                channel_registry, "target_count",
                side_effect=channel_registry.RegistryError("boom")):
            with self.assertRaises(channel_registry.RegistryError):
                run_third._synthesize_fallback_packages("20260819")


if __name__ == "__main__":
    unittest.main()
