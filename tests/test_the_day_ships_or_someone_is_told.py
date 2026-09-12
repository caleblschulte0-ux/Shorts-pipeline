"""The dead-man's switch: something ACTS when the day has not shipped.

Operator, 2026-09-12: *"I want you to add a million levels of redundancy and
fail safes ... there should be absolutely zero reason in any context why
video does not post."*

Three guards existed and all three were green through five days of a human
doing the job by hand:

  1. The explainer's only automatic trigger was `cron: '40 13 * * *'`, which
     GitHub fired at 17:14 / 17:07 / 17:08 / 16:27. Three hours late, daily.
  2. The run then went GREEN having posted ZERO videos, because the step
     named "Did the channel actually post today?" printed `::error` — an
     ANNOTATION, which fails nothing. 2026-09-12: two green runs, 0 posted.
     2026-09-11: 2 of 4.
  3. `alarm.yml` asks the right question at 01:15 UTC, after the day is over,
     and COMMENTS. It never fired, and it was right not to — videos HAD
     posted, because a human noticed at 09:30 and pushed the button.

That third one is the real lesson: a monitor a human silently repairs every
day reports a healthy system forever. Detection was never the gap. ACTING
was.

AND THE LINE THIS MUST NOT CROSS. "A video always posts" cannot mean "a
video posts anyway." `docs/EDITORIAL_RESET.md` and CLAUDE.md are explicit
that a fail-closed gate with a bypass is not a gate, and
`review_proposals.py` hard-refuses volume bought with a lower bar. So the
switch re-runs the channel — through the identical QA and showrunner path,
which is the operator's own ruling, "if something doesn't run properly, it
goes through and tries again" — and it never reaches for the gate. The last
class in this file is what holds that.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import deadman as dm                            # noqa: E402

WF = ROOT / ".github" / "workflows" / "deadman.yml"


def _wf():
    import yaml
    return yaml.safe_load(WF.read_text())


def _on():
    d = _wf()
    return d[True] if True in d else d["on"]


def _at(hour):
    return datetime(2026, 9, 12, hour, 0, tzinfo=timezone.utc)


REGISTRY = {"channels": {
    "explainer": {"enabled": True, "target_count": 4,
                  "paths": {"posted_log": "state/explainer_posted_log.json"}},
    "curiosity": {"enabled": False, "target_count": 1,
                  "paths": {"posted_log": "state/curiosity_posted_log.json"}},
}}


def _assess(posted, fires=0, hour=18):
    """`assess` with the world stubbed: N posted today, M repairs already."""
    led = {"explainer": [{"at": "x"}] * fires} if fires else {}
    with mock.patch.object(dm.al, "_posted_on",
                           return_value=[{}] * posted), \
         mock.patch.object(dm, "load_ledger", return_value=led):
        return dm.assess("20260912", now=_at(hour), registry=REGISTRY)


def _row(a, cid="explainer"):
    return next(r for r in a["channels"] if r["channel"] == cid)


class ItFiresWhenTheDayHasNotShipped(unittest.TestCase):
    def test_nothing_posted_means_fire(self):
        a = _assess(posted=0)
        self.assertEqual(_row(a)["action"], "fire")
        self.assertEqual(a["fire"], ["explainer"])

    def test_a_partial_day_also_fires(self):
        """2026-09-11 posted 2 of 4 and nothing anywhere called that a
        problem."""
        a = _assess(posted=2)
        self.assertEqual(_row(a)["action"], "fire")
        self.assertEqual(_row(a)["short"], 2)

    def test_a_delivered_day_is_left_alone(self):
        a = _assess(posted=4)
        self.assertEqual(_row(a)["action"], "ok")
        self.assertTrue(a["ok"])
        self.assertEqual(a["fire"], [])

    def test_more_than_the_target_is_still_fine(self):
        self.assertEqual(_row(_assess(posted=6))["action"], "ok")


class ItDoesNotJudgeADayBeforeItCouldHaveHappened(unittest.TestCase):
    def test_early_morning_waits(self):
        """The stories land at ~09:30. Firing at 06:00 would re-run a day
        whose content does not exist yet."""
        a = _assess(posted=0, hour=6)
        self.assertEqual(_row(a)["action"], "wait")
        self.assertEqual(a["fire"], [])

    def test_it_starts_judging_once_the_content_should_exist(self):
        self.assertEqual(_row(_assess(posted=0,
                                      hour=dm.FIRST_JUDGE_HOUR_UTC))["action"],
                         "fire")


class TheLoopTERMINATES(unittest.TestCase):
    """`deadman.yml` chains off the channel workflows COMPLETING and fires
    them again — a deliberate loop. The ledger is the only thing that stops
    it, so it is the most important assertion in this file."""

    def test_it_gives_up_at_the_bound(self):
        a = _assess(posted=0, fires=dm.MAX_FIRES)
        self.assertEqual(_row(a)["action"], "give_up")
        self.assertEqual(a["fire"], [])
        self.assertEqual(a["alarm"], ["explainer"])

    def test_it_keeps_trying_up_to_the_bound(self):
        for n in range(dm.MAX_FIRES):
            self.assertEqual(_row(_assess(posted=0, fires=n))["action"],
                             "fire", f"gave up after {n}")

    def test_the_bound_is_small_enough_to_notice(self):
        self.assertLessEqual(dm.MAX_FIRES, 5)
        self.assertGreaterEqual(dm.MAX_FIRES, 2)

    def test_giving_up_is_LOUD_not_quiet(self):
        """The whole failure mode being fixed is a guard that reports
        success. An exhausted switch must turn the check red."""
        steps = _wf()["jobs"]["switch"]["steps"]
        # BY NAME, not "the first step with an exit 1". It used to be the
        # latter and started passing for the wrong reason the moment a
        # FAILED DISPATCH also learned to exit 1 — a test that keeps passing
        # while measuring something else is the same class of fault as the
        # guards this file is about.
        red = [s for s in steps if "RED" in s.get("name", "")]
        self.assertEqual(len(red), 1, "the red-on-give-up step is gone")
        self.assertIn("exit 1", red[0]["run"])
        self.assertIn("alarm", red[0]["if"])

    def test_the_ledger_records_each_fire(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(dm, "STATE_DIR", Path(td)):
                dm.record_fire("20260912", "explainer", "first")
                dm.record_fire("20260912", "explainer", "second")
                led = json.loads((Path(td) / "20260912.json").read_text())
        self.assertEqual(len(led["explainer"]), 2)

    def test_it_records_BEFORE_it_dispatches(self):
        """If the dispatch succeeded and the record failed, the bound would
        be gone and this would loop forever. The other order costs one
        wasted attempt."""
        run = next(s["run"] for s in _wf()["jobs"]["switch"]["steps"]
                   if s.get("name", "").startswith("Fire the channels"))
        self.assertLess(run.index("--record-fire"), run.index("gh workflow run"))


class ADisabledChannelIsNotResurrected(unittest.TestCase):
    def test_it_is_skipped_entirely(self):
        a = _assess(posted=0)
        self.assertNotIn("curiosity", [r["channel"] for r in a["channels"]])

    def test_a_channel_with_no_delivery_workflow_is_reported_not_guessed(self):
        reg = {"channels": {"mystery": {
            "enabled": True, "target_count": 2,
            "paths": {"posted_log": "state/x.json"}}}}
        with mock.patch.object(dm.al, "_posted_on", return_value=[]), \
             mock.patch.object(dm, "load_ledger", return_value={}):
            a = dm.assess("20260912", now=_at(18), registry=reg)
        self.assertEqual(_row(a, "mystery")["action"], "report")


class ItDoesNotDependOnTheSchedulerAlone(unittest.TestCase):
    """The fault being worked around IS the scheduler running hours late, so
    leaning on one cron would rebuild the bug."""

    def test_it_chains_off_the_channel_runs_finishing(self):
        wr = _on()["workflow_run"]
        self.assertEqual(wr["types"], ["completed"])
        for name in ("Explainer Stories", "Daily Shorts"):
            self.assertIn(name, wr["workflows"])

    def test_there_are_many_crons_not_one(self):
        self.assertGreaterEqual(len(_on()["schedule"]), 5)

    def test_it_can_be_fired_by_hand(self):
        self.assertIn("workflow_dispatch", _on())

    def test_it_may_actually_dispatch(self):
        """`actions: write` is the difference between this and every guard
        that came before it."""
        self.assertEqual(_wf()["permissions"]["actions"], "write")

    def test_two_switches_cannot_race(self):
        self.assertEqual(_wf()["concurrency"]["group"], "deadman")


class TheCheckThatASKEDTheRightQuestionNowANSWERSIt(unittest.TestCase):
    def test_a_zero_post_day_fails_the_explainer_run(self):
        src = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        block = src.split("Did the channel actually post today?", 1)[1]
        block = block.split("- name:", 1)[0]
        self.assertIn("nothing-posted-today", block)
        self.assertIn("SystemExit(1)", block,
                      "it still only prints an annotation")


class ItNeverREACHESForTheGate(unittest.TestCase):
    """The same shape as `tests/test_backfill.py`, which fails if `_backfill`
    so much as mentions the showrunner. A repair path that can disable the
    judge is not a repair path, it is a bypass with a nice name."""

    FORBIDDEN = ("SHOWRUNNER", "showrunner", "--force", "force=true",
                 "bypass", "skip_gate", "no_gate")

    def test_the_script_does_not_mention_the_gate(self):
        src = (ROOT / "scripts" / "deadman.py").read_text()
        code = "\n".join(l for l in src.splitlines()
                         if not l.lstrip().startswith("#"))
        # the module docstring explains WHY it must not; strip it too
        code = code.split('"""', 2)[-1]
        for bad in self.FORBIDDEN:
            self.assertNotIn(bad, code, f"deadman.py reaches for {bad!r}")

    def test_the_workflow_does_not_disable_or_force_anything(self):
        txt = WF.read_text()
        code = "\n".join(l for l in txt.splitlines()
                         if not l.lstrip().startswith("#"))
        for bad in ("SHOWRUNNER=off", "--force", "force=true", "bypass"):
            self.assertNotIn(bad, code, f"deadman.yml reaches for {bad!r}")

    def test_it_re_runs_the_normal_path(self):
        """Repair means running the channel's own workflow in its own
        default mode — not a special back door."""
        run = next(s["run"] for s in _wf()["jobs"]["switch"]["steps"]
                   if s.get("name", "").startswith("Fire the channels"))
        self.assertIn("gh workflow run", run)
        self.assertIn("mode=auto", run)

    def test_every_workflow_it_fires_is_a_registered_channel_path(self):
        for cid, wf in dm.WORKFLOWS.items():
            self.assertTrue((ROOT / ".github" / "workflows" / wf).exists(),
                            f"{cid} -> {wf} does not exist")


class TheDispatCHActuallyREACHESTheWorkflow(unittest.TestCase):
    """Caught by RUNNING the switch, not by reading it.

    The first live repair passed `-f mode=auto` to all three channels and
    GitHub answered

        HTTP 422: Unexpected inputs provided: ["mode"]

    for `daily.yml` and `third.yml`, which declare no such input. Two of the
    three channels were never dispatched — and the step went GREEN, because
    the failure was written with `|| echo "::error ..."`, an ANNOTATION.
    That is the identical annotation-instead-of-failure bug this whole switch
    was built to end, reproduced inside the fix for it.

    `mode` cannot simply be dropped either: `explainer.yml` declares it with
    `default: 'verify'`, so a dispatch that omits it runs in VERIFY and posts
    nothing — a repair that reports success and delivers zero videos.

    So: per-channel inputs, and this test parses what each workflow actually
    ACCEPTS so the next wrong key fails here instead of in production.
    """

    def _declared_inputs(self, wf_name):
        import yaml
        d = yaml.safe_load(
            (ROOT / ".github" / "workflows" / wf_name).read_text())
        on = d[True] if True in d else d["on"]
        wd = on.get("workflow_dispatch") or {}
        return set((wd.get("inputs") or {}))

    def test_every_input_it_sends_is_one_the_workflow_declares(self):
        for cid, wf in dm.WORKFLOWS.items():
            sent = set(dm.DISPATCH_INPUTS.get(cid, {}))
            declared = self._declared_inputs(wf)
            self.assertTrue(
                sent <= declared,
                f"{cid} -> {wf}: sends {sorted(sent - declared)} which the "
                f"workflow does not accept (this is a 422 in production)")

    def test_every_channel_has_an_entry_even_if_empty(self):
        """A missing entry and an empty one must not be the same thing by
        accident — the empty ones are a decision."""
        self.assertEqual(set(dm.DISPATCH_INPUTS), set(dm.WORKFLOWS))

    def test_the_explainer_is_not_dispatched_into_VERIFY(self):
        """Its `mode` defaults to 'verify', which posts nothing. A repair
        that runs in verify mode is a repair that reports success and
        delivers zero videos."""
        import yaml
        d = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "explainer.yml").read_text())
        on = d[True] if True in d else d["on"]
        default = on["workflow_dispatch"]["inputs"]["mode"]["default"]
        self.assertEqual(default, "verify", "the premise changed — recheck")
        self.assertEqual(dm.DISPATCH_INPUTS["explainer"]["mode"], "auto")

    def test_a_failed_dispatch_FAILS_the_step(self):
        run = next(s["run"] for s in _wf()["jobs"]["switch"]["steps"]
                   if s.get("name", "").startswith("Fire the channels"))
        self.assertIn("exit 1", run,
                      "a dispatch that did not happen still goes green")
        self.assertNotIn('|| echo "::error title=deadman-dispatch-failed', run)

    def test_it_still_commits_the_ledger_before_failing(self):
        """Bailing out before the commit would lose the record of the
        attempts that DID fire, and the bound with it."""
        run = next(s["run"] for s in _wf()["jobs"]["switch"]["steps"]
                   if s.get("name", "").startswith("Fire the channels"))
        self.assertLess(run.index("ci_commit_state"), run.index("exit 1"))


if __name__ == "__main__":
    unittest.main()
