"""GITHUB'S CRON IS NOT A CLOCK, AND THE PIPELINE NO LONGER PRETENDS IT IS.

2026-09-22: every scheduled run landed two to five hours late or never
came. The explainer's 13:40 slot, Phase B's 13:30 backstop and the dead-
man's 11:05 and 13:05 slots did not fire at all; the hourly claim cron ran
at 00:12, 05:12 and 10:09. `clock.yml` is a workflow_dispatch chain that
fires what the crons missed. Held here:

  1. the cron reader understands every cron in the repo (or the cron is
     listed as cron-only, with a reason);
  2. `due` fires a missed slot after GitHub's grace, once, and never a slot
     that a run already covered, is still inside the grace, or is stale;
  3. every dispatch carries the inputs the cron path needs;
  4. the workflow is a chain: dispatchable, one at a time, self-spawning
     after every tick, with a bootstrap cron and an off switch.
"""
from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import clock as C                                # noqa: E402
from scripts import deadman as DM                             # noqa: E402

UTC = timezone.utc


def _t(h, m, day=22):
    return datetime(2026, 9, day, h, m, tzinfo=UTC)     # a Tuesday


class TheReaderCoversEveryCron(unittest.TestCase):
    def test_every_cron_in_the_repo_parses_or_is_listed_cron_only(self):
        wf_dir = ROOT / ".github" / "workflows"
        unread = {}
        for p in sorted(wf_dir.glob("*.yml")):
            for expr in C.crons_of(p):
                try:
                    C.parse_cron(expr)
                except ValueError as e:
                    if p.name not in C.CRON_ONLY:
                        unread[f"{p.name}: {expr}"] = str(e)
        self.assertEqual(unread, {})

    def test_every_cron_workflow_is_covered_or_excused(self):
        wf_dir = ROOT / ".github" / "workflows"
        sched = C.schedule(wf_dir)
        for p in sorted(wf_dir.glob("*.yml")):
            if C.crons_of(p):
                self.assertTrue(p.name in sched or p.name in C.CRON_ONLY,
                                f"{p.name} has a cron the clock neither covers nor excuses")
        for name, why in C.CRON_ONLY.items():
            self.assertTrue(why.strip(), f"{name} is cron-only without a reason")

    def test_the_field_forms_in_use(self):
        self.assertEqual(C.parse_cron("40 13 * * *")["hours"], [13])
        self.assertEqual(C.parse_cron("20 5,17 * * *")["hours"], [5, 17])
        self.assertEqual(len(C.parse_cron("25 * * * *")["hours"]), 24)
        self.assertEqual(C.parse_cron("*/20 * * * *")["minutes"], [0, 20, 40])
        self.assertEqual(C.parse_cron("0 15 * * 6")["dow"], {6})
        with self.assertRaises(ValueError):
            C.parse_cron("0 0 1 * *")            # a calendar, not a day

    def test_weekday_crons_only_name_slots_on_their_day(self):
        tue = _t(16, 0)
        self.assertEqual(C.slots_today("0 15 * * 6", tue), [])          # Saturday
        self.assertEqual(C.slots_today("0 15 * * 2", tue), [_t(15, 0)])  # Tuesday
        self.assertEqual(C.slots_today("20 5,17 * * *", tue), [_t(5, 20)])


class DueFiresWhatWasMissedAndOnlyThat(unittest.TestCase):
    SCHED = {"explainer.yml": ["40 13 * * *", "10 17 * * *"],
             "claim_reviews.yml": ["25 * * * *"]}

    def test_the_real_2026_09_22_afternoon(self):
        now = _t(13, 55)
        runs = {"explainer.yml": [_t(11, 51)],               # the dead-man's re-fire
                "claim_reviews.yml": [_t(0, 12), _t(5, 12), _t(10, 9)]}
        plan = C.due(now, self.SCHED, runs)
        self.assertEqual(plan["fire"]["explainer.yml"], _t(13, 40))
        self.assertEqual(plan["fire"]["claim_reviews.yml"], _t(13, 25))
        # 09:25 was covered by the 10:09 run; 10:25 onward had nothing after
        # them, and the newest missed slot is the one fired.
        self.assertIn(_t(9, 25), plan["covered"]["claim_reviews.yml"])
        self.assertNotIn(_t(10, 25), plan["covered"]["claim_reviews.yml"])
        self.assertNotIn("claim_reviews.yml", plan["abandoned"])

    def test_a_run_after_the_slot_covers_it_whatever_raised_it(self):
        plan = C.due(_t(14, 30), self.SCHED, {"explainer.yml": [_t(13, 47)]})
        self.assertNotIn("explainer.yml", plan["fire"])
        self.assertEqual(plan["covered"]["explainer.yml"], [_t(13, 40)])

    def test_github_gets_its_grace_first(self):
        plan = C.due(_t(13, 45), self.SCHED, {})
        self.assertNotIn("explainer.yml", plan["fire"])
        plan = C.due(_t(13, 40) + timedelta(minutes=C.GRACE_MIN), self.SCHED, {})
        self.assertEqual(plan["fire"]["explainer.yml"], _t(13, 40))

    def test_a_stale_slot_is_abandoned_not_fired_at_midnight(self):
        plan = C.due(_t(23, 50), {"exchange_phase_a.yml": ["45 9 * * *"]}, {})
        self.assertEqual(plan["fire"], {})
        self.assertEqual(plan["abandoned"]["exchange_phase_a.yml"], [_t(9, 45)])

    def test_one_dispatch_per_workflow_the_latest_missed_slot(self):
        plan = C.due(_t(14, 0), {"deadman.yml": ["5 11 * * *", "5 13 * * *"]}, {})
        self.assertEqual(plan["fire"]["deadman.yml"], _t(13, 5))
        self.assertEqual(plan["abandoned"], {})

    def test_a_future_slot_is_not_due(self):
        plan = C.due(_t(13, 0), self.SCHED, {})
        self.assertNotIn("explainer.yml", plan["fire"])


class ADispatchReachesTheCronsPath(unittest.TestCase):
    def test_the_explainer_is_dispatched_as_the_deadman_dispatches_it(self):
        self.assertEqual(C.DISPATCH_INPUTS["explainer.yml"], DM.DISPATCH_INPUTS["explainer"])

    def test_phase_b_is_told_it_is_the_backstop(self):
        self.assertEqual(C.DISPATCH_INPUTS["exchange_phase_b.yml"], {"backstop": "true"})
        src = (ROOT / ".github" / "workflows" / "exchange_phase_b.yml").read_text()
        self.assertIn("inputs.backstop }}\" = \"true\" ]; } && FLAGS=\"$FLAGS --backstop\"", src)
        self.assertIn("backstop:", src[src.index("workflow_dispatch"):src.index("schedule:")])
        # the already-applied guard honours it too
        i = src.index("Skip backstop when Phase B already ran")
        self.assertIn("inputs.backstop", src[i:i + 500])

    def test_every_dispatch_input_names_a_real_workflow_input(self):
        import yaml
        for wf, inputs in C.DISPATCH_INPUTS.items():
            doc = yaml.safe_load((ROOT / ".github" / "workflows" / wf).read_text())
            on = doc.get(True, doc.get("on"))
            declared = (on.get("workflow_dispatch") or {}).get("inputs") or {}
            for k in inputs:
                self.assertIn(k, declared, f"{wf} has no input {k!r}")


class TheWorkflowIsAChain(unittest.TestCase):
    def setUp(self):
        import yaml
        self.src = (ROOT / ".github" / "workflows" / "clock.yml").read_text()
        self.doc = yaml.safe_load(self.src)
        self.on = self.doc.get(True, self.doc.get("on"))

    def test_it_can_be_dispatched_and_has_a_bootstrap_cron(self):
        self.assertIn("workflow_dispatch", self.on)
        self.assertTrue(self.on.get("schedule"))

    def test_one_clock_at_a_time_and_the_tick_survives_a_failed_fire(self):
        self.assertEqual(self.doc["concurrency"]["group"], "clock")
        self.assertFalse(self.doc["concurrency"]["cancel-in-progress"])
        steps = self.doc["jobs"]["tick"]["steps"]
        tick = [s for s in steps if "clock.py --tick" in str(s.get("run", ""))]
        self.assertEqual(len(tick), 1)
        self.assertEqual(str(tick[0].get("if")), "always()")
        self.assertLessEqual(self.doc["jobs"]["tick"]["timeout-minutes"], 30)
        self.assertEqual(self.doc["permissions"]["actions"], "write")

    def test_the_tick_is_bounded_and_switchable(self):
        self.assertGreaterEqual(C.TICK_MIN, 10)
        self.assertLess(C.seconds_to_next_tick(_t(13, 57, 22)), 4 * 60)
        self.assertIn("state/clock/OFF", C.OFF_FILES)
        self.assertIn("PAUSED", C.OFF_FILES)

    def test_it_lifts_no_gate(self):
        """The clock dispatches workflows; it never touches SHOWRUNNER, the
        editorial gate or a posted log."""
        src = (ROOT / "scripts" / "clock.py").read_text()
        for bad in ("SHOWRUNNER", "posted_log", "editorial_gate", "PUBLISH_ENABLED"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
