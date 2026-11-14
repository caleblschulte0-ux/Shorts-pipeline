"""The run goes red when cut-ins and montages stop reaching the channel or
a render crashes (operator, 2026-11-14: "what can we double check to make
sure isn't going to be wrong again?"). Each case is a pattern the live
reports showed for days before anyone saw it on the channel."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import sports_health as h

REPO = Path(__file__).resolve().parents[1]


def _slot(cut_in=0, outro=False, skipped=None):
    s = {"ledger": {"cut_in": ["x@1"] * cut_in, "outro": outro or None}}
    if skipped:
        s["skipped"] = skipped
    return s


class HealthCheck(unittest.TestCase):
    def test_a_crash_is_always_a_failure(self):
        got = h.problems([{"slots": [
            {"skipped": "render failed: JSONDecodeError: Extra data"}]}])
        self.assertTrue(any("crashed" in p for p in got))

    def test_bare_posts_only_is_a_failure(self):
        got = h.problems([{"slots": [_slot() for _ in range(5)]}])
        self.assertTrue(any("not one had" in p for p in got))

    def test_montages_all_held_is_a_failure(self):
        held = [_slot(outro=True, skipped="showrunner_block: tiny")
                for _ in range(3)]
        got = h.problems([{"slots": held + [_slot(cut_in=1)]}])
        self.assertTrue(any("were held" in p for p in got))

    def test_a_healthy_run_passes(self):
        slots = [_slot(cut_in=1), _slot(outro=True), _slot(),
                 _slot(), _slot(skipped="too short: 12.1s"),
                 {"skipped": "download failed"}]
        self.assertEqual(h.problems([{"slots": slots}]), [])

    def test_it_runs_in_the_posting_workflow(self):
        wf = (REPO / ".github" / "workflows" / "sports.yml").read_text()
        self.assertIn("python3 scripts/sports_health.py", wf)
        # before the step that checks out preview-renders over the repo
        self.assertLess(wf.index("scripts/sports_health.py"),
                        wf.index("Publish them to the preview-renders"))


if __name__ == "__main__":
    unittest.main()
