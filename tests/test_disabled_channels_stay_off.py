"""A channel the operator turned OFF must not have a cron that publishes it.

Operator ruling 2026-08-05: explainer 4/day, trending 6/day, third 6/day,
and *"the long form video should not be posting right now."*

That ruling landed in `config/channel_registry.json` — which is the right
place, and is where every slate decision resolves from. But the registry
only governs REGISTERED channels, and two publishing paths are not
registered channels:

  * `curiosity.yml` — its own weekly cron, its own uploader.
  * `longform.yml`  — its own weekly cron, uploading an extra long-form
    format to the EXPLAINER channel. Explainer is enabled, so nothing about
    the registry looks wrong; the long-form format simply isn't in it.

`longform.yml` was found on 2026-08-06 still set to build AND upload on its
Sunday cron, three days before it would next have fired. The ruling was true
in the registry, true in the docs, and false in the one workflow that would
actually have published one.

So this file checks the thing the registry structurally cannot: that an
off-by-ruling publishing path cannot publish itself on a timer. Both
workflows keep working on manual dispatch — turning a channel back on stays
a deliberate act, which is the whole point.

    python -m unittest tests.test_disabled_channels_stay_off -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WF = ROOT / ".github" / "workflows"

#: Workflows that publish a channel/format the operator has switched off.
#: To re-enable one: turn it on in the registry (or add the format), then
#: take it out of this list in the SAME change — never one without the other.
OFF_BY_RULING = {
    "longform.yml": "long-form is not posting (2026-08-05 ruling); it is "
                    "also not a format in explainer's registry entry",
    "curiosity.yml": "curiosity is disabled in config/channel_registry.json",
}


def body(name: str) -> str:
    p = WF / name
    if not p.exists():
        raise unittest.SkipTest(f"{name} no longer exists")
    return p.read_text()


class TestAnOffChannelHasNoPublishingCron(unittest.TestCase):

    def test_each_off_workflow_neutralises_its_schedule(self):
        """A cron may still RUN (building is free and keeps the path warm).
        What it may not do is upload without a human saying so."""
        for name, why in OFF_BY_RULING.items():
            src = body(name)
            if "schedule:" not in src:
                continue                      # no cron at all — fine
            self.assertTrue(
                re.search(r"github\.event_name.*schedule", src)
                or "inputs.enable_publish" in src,
                f"{name} has a cron and no guard tying uploads to a manual "
                f"dispatch — {why}")

    def test_longform_cron_forces_dry_run(self):
        src = body("longform.yml")
        self.assertIn("--dry-run", src)
        guard = src[src.index("github.event_name"):]
        self.assertIn("--dry-run", guard[:400],
                      "the scheduled-run branch must add --dry-run; without "
                      "it a Sunday cron uploads a video the operator said "
                      "should not post")

    def test_curiosity_cron_cannot_set_the_publish_flag(self):
        src = body("curiosity.yml")
        self.assertIn("CURIOSITY_PUBLISH_ENABLED", src)
        self.assertIn("inputs.enable_publish", src,
                      "publishing must hang off a dispatch input a cron "
                      "cannot supply")


class TestTheRegistryAndTheWorkflowsAgree(unittest.TestCase):
    """The registry is the source of truth for WHICH channels ship. This
    checks nothing has quietly drifted back on."""

    def test_only_the_ruled_channels_are_enabled(self):
        from shared import channel_registry as reg
        self.assertEqual(sorted(reg.channel_ids()),
                         ["explainer", "third", "trending"])

    def test_the_daily_counts_match_the_ruling(self):
        from shared import channel_registry as reg
        self.assertEqual(
            {c: reg.channel(c).get("target_count") for c in reg.channel_ids()},
            {"explainer": 4, "third": 6, "trending": 6})

    def test_long_form_is_not_a_format_any_channel_ships(self):
        """If long-form ever becomes a registered format, this test failing
        is the reminder to take longform.yml out of OFF_BY_RULING too."""
        from shared import channel_registry as reg
        for cid in reg.channel_ids():
            fmts = set(reg.formats(cid, state=None))
            self.assertNotIn("long_form", fmts)
            self.assertNotIn("longform", fmts)


if __name__ == "__main__":
    unittest.main()
