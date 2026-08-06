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


class TestNoSelfTriggerLoops(unittest.TestCase):
    """A workflow that commits to a path another workflow (or itself) treats
    as a push trigger must say [skip ci], or one day's run pokes the next
    stage back awake after the day is done. Found live on 2026-08-06:
    daily.yml's blanket `state/` commit includes any package `_backfill`
    authored, `state/trending_packages/**` is Phase A's push trigger, and the
    message had no [skip ci] — so every day with a re-authored slot would
    have re-run Phase A against an already-rendered day."""

    def _commit_messages(self, name: str) -> list[str]:
        src = body(name)
        return re.findall(r'ci_commit_state\.sh\s*\\\n\s*"([^"]+)"', src) + \
               re.findall(r'git commit[^\n]*-m\s*"([^"\n]+)"', src)

    def test_workflows_committing_trigger_paths_skip_ci(self):
        # (workflow, path fragment it commits that is somebody's push trigger)
        risky = {
            "daily.yml": "state/",              # trending_packages -> Phase A
            "doctor.yml": "doctor/",            # doctor/reports -> doctor.yml
            "exchange_phase_a.yml": "state/trending_packages",
            "exchange_phase_b.yml": "state/trending_packages",
            "retro.yml": "retro/",
            "third.yml": "state/third",         # third_packages -> third.yml
        }
        for name in risky:
            for msg in self._commit_messages(name):
                self.assertIn("[skip ci]", msg,
                              f"{name} commits with {msg!r} — a push-trigger "
                              f"path without [skip ci] is a self-poke loop")

    def test_explainer_has_exactly_one_automatic_trigger(self):
        """Two automatic triggers + a per-RUN cap = 8 posts against a 4/day
        ruling: the posted log dedupes slugs, not days, so a second same-day
        run posts the NEXT four stories."""
        import yaml
        d = yaml.safe_load(body("explainer.yml"))
        on = d.get("on") or d.get(True)
        self.assertNotIn("workflow_run", on)
        self.assertIn("schedule", on)

    def test_post_stories_carries_a_per_day_cap(self):
        src = (ROOT / "scripts" / "post_stories.py").read_text()
        self.assertIn("posted_today", src,
                      "the per-day cap is the backstop for ANY double-fire "
                      "(manual re-run included) — do not remove it")


class TestEveryWorkflowIsValidToGitHub(unittest.TestCase):
    """PyYAML is more forgiving than GitHub Actions, and the gap is fatal in
    a hands-off system: a file GitHub rejects still parses green locally,
    its CRON silently never fires, and the only symptom is a jobless
    'failure' run named by file path on every non-[skip ci] push — which
    nobody reads.

    That is not hypothetical. retro_decide.yml carried a duplicated
    `continue-on-error:` key on one step from the day it merged (#213) to
    2026-08-06. PyYAML kept the last copy without a word; Actions refused
    the whole file; the decide half of the retro improvement loop NEVER ran
    once, while 135 validation-failure runs piled up unnoticed. This class
    checks, for every workflow, the Actions strictnesses PyYAML forgives."""

    @staticmethod
    def _strict_load(text: str):
        import yaml

        class Strict(yaml.SafeLoader):
            pass

        def mapping(loader, node, deep=False):
            seen = []
            for k, _ in node.value:
                key = loader.construct_object(k, deep=deep)
                if key in seen:
                    raise AssertionError(f"duplicate key {key!r}")
                seen.append(key)
            return yaml.SafeLoader.construct_mapping(loader, node, deep)

        Strict.construct_mapping = mapping
        return yaml.load(text, Strict)

    def test_no_workflow_has_duplicate_keys(self):
        for p in sorted(WF.glob("*.yml")):
            try:
                self._strict_load(p.read_text())
            except AssertionError as e:
                self.fail(f"{p.name}: {e} — GitHub rejects the whole file, "
                          f"so its crons silently never fire")

    def test_no_step_declares_both_uses_and_run(self):
        import yaml
        for p in sorted(WF.glob("*.yml")):
            d = yaml.safe_load(p.read_text())
            for jname, j in (d.get("jobs") or {}).items():
                for i, s in enumerate(j.get("steps") or []):
                    self.assertFalse(
                        "uses" in s and "run" in s,
                        f"{p.name} {jname}[{i}] has both uses and run — "
                        f"PyYAML-fine, Actions-fatal")


class TestAutoPauseIsABackoffNotALatch(unittest.TestCase):
    """Two zero-upload days sit the channel out for ONE day, then it retries
    itself. The old behavior — skip forever until a human resets a counter
    over SSH — contradicted the standing ruling ("it goes through and tries
    again") and would have parked the channel on any two-day external
    outage."""

    def test_the_preflight_can_resume_itself(self):
        src = body("daily.yml")
        self.assertIn("auto_pause_day", src)
        self.assertIn("auto-resume", src.lower())
        self.assertNotIn("This CANNOT clear itself", src)

    def test_the_paused_day_is_still_loudly_alarmed(self):
        """Self-retry must not become self-silence — daily_alarm keeps its
        channel_auto_paused CRITICAL (tests/test_daily_alarm.py owns the
        behavior; this just pins the wiring)."""
        src = (ROOT / "scripts" / "daily_alarm.py").read_text()
        self.assertIn("channel_auto_paused", src)


if __name__ == "__main__":
    unittest.main()
