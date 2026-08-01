"""The pipeline doctor's constitution, held to its word.

The doctor is an autonomous daily maintainer whose fixes merge through the
auto-merge gate with no human review. That is only tolerable because of what
it structurally CANNOT do — and this file is where "cannot" is made true.

Every refusal class gets its own test, phrased as the attack it prevents.
If one of these starts failing, the doctor has more power than the operator
granted it, and that is a worse bug than anything it might be fixing.

    python -m unittest tests.test_doctor -v
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import pipeline_doctor as doc                            # noqa: E402


def diff_for(path: str, removed: list[str] = (), added: list[str] = (),
             deleted: bool = False) -> str:
    lines = [f"diff --git a/{path} b/{path}"]
    if deleted:
        lines += ["deleted file mode 100644", f"--- a/{path}",
                  "+++ /dev/null"]
    else:
        lines += [f"--- a/{path}", f"+++ b/{path}", "@@ -1,9 +1,9 @@"]
    lines += [f"-{ln}" for ln in removed]
    lines += [f"+{ln}" for ln in added]
    return "\n".join(lines) + "\n"


class TestTheConstitutionRefuses(unittest.TestCase):
    """One test per attack. The refusal message must NAME the rule — a
    refusal the brain cannot understand is a refusal it routes around."""

    def refuse(self, diff, expect_word):
        problems = doc.review_diff(diff)
        self.assertTrue(problems, "diff was ALLOWED — the constitution has "
                                  "a hole")
        blob = " ".join(problems).lower()
        self.assertIn(expect_word.lower(), blob, problems)

    def test_weakening_the_showrunner(self):
        self.refuse(diff_for("scripts/showrunner_review.py",
                             removed=["MIN_SCORE = 70"],
                             added=["MIN_SCORE = 40"]), "protected")

    def test_weakening_the_shared_gate(self):
        self.refuse(diff_for("shared/showrunner_gate.py",
                             removed=["return {'blocked': True"],
                             added=["return {'blocked': False"]), "protected")

    def test_silencing_its_own_alarm(self):
        self.refuse(diff_for("scripts/daily_alarm.py",
                             removed=["alarm(f\"no_posts_{cid}\", "
                                      "\"critical\","]), "alarm")

    def test_rewriting_its_own_constitution(self):
        self.refuse(diff_for("scripts/pipeline_doctor.py",
                             removed=["MAX_DIFF_FILES = 8"],
                             added=["MAX_DIFF_FILES = 800"]), "constitution")

    def test_editing_the_refusal_list_it_inherits(self):
        self.refuse(diff_for("scripts/review_proposals.py",
                             removed=["FORBIDDEN_INTENT = ("]), "operator")

    def test_deleting_a_test_file(self):
        self.refuse(diff_for("tests/test_showrunner_gate.py", deleted=True),
                    "deletes a test")

    def test_removing_a_test_function(self):
        self.refuse(diff_for("tests/test_capabilities.py",
                             removed=["def test_captions_build(self):"]),
                    "test")

    def test_net_removing_assertions_inside_a_kept_test(self):
        self.refuse(diff_for("tests/test_exchange.py",
                             removed=["self.assertEqual(a, b)",
                                      "self.assertTrue(ok)"],
                             added=["pass"]), "assert")

    def test_touching_a_posted_log(self):
        self.refuse(diff_for("shared/some_module.py",
                             removed=["entries = load(posted_log_path)"]),
                    "posted")

    def test_editing_a_workflow(self):
        self.refuse(diff_for(".github/workflows/daily.yml",
                             added=["      - run: echo hi"]), "operator")

    def test_editing_channel_policy(self):
        self.refuse(diff_for("config/channel_registry.json",
                             removed=['"count": 6'], added=['"count": 12']),
                    "operator")

    def test_editing_doctrine(self):
        self.refuse(diff_for("CLAUDE.md", added=["- new rule"]), "doctrine")

    def test_writing_into_exchange_or_retro(self):
        self.refuse(diff_for("exchange/bundles/20260801/DONE",
                             added=["{}"]), "operator")
        self.refuse(diff_for("retro/20260801/triage.json", added=["{}"]),
                    "operator")

    def test_writing_run_state_that_is_not_its_own(self):
        self.refuse(diff_for("state/posted_log.json", added=['{"posted":[]}']),
                    "state")

    def test_removing_a_fail_closed_line_anywhere(self):
        self.refuse(diff_for("scripts/run_trending_daily.py",
                             removed=["gate = _showrunner(pkg, out_path, "
                                      "result, will_upload=not dry_run)"]),
                    "showrunner")

    def test_an_oversized_diff(self):
        big = "".join(diff_for(f"shared/mod_{i}.py", added=["x = 1"])
                      for i in range(doc.MAX_DIFF_FILES + 1))
        self.refuse(big, "files")

    def test_too_many_changed_lines(self):
        many = diff_for("shared/mod.py",
                        added=[f"line_{i} = {i}"
                               for i in range(doc.MAX_DIFF_LINES + 1)])
        self.refuse(many, "lines")

    def test_an_empty_diff_is_not_silently_fine(self):
        self.assertTrue(doc.review_diff(""))


class TestTheConstitutionAllows(unittest.TestCase):
    """A doctor that can fix nothing is theater. The allowed surface must
    stay real: renderers, scenes, funnel, engines, non-protected shared."""

    def allow(self, diff):
        problems = doc.review_diff(diff)
        self.assertEqual(problems, [], "a legitimate fix was refused")

    def test_a_bounded_renderer_fix(self):
        self.allow(diff_for("make_reddit_story.py",
                            removed=["CAP_MAX_CHARS = 22"],
                            added=["CAP_MAX_CHARS = 24"]))

    def test_adding_a_new_test_file(self):
        self.allow(diff_for("tests/test_new_thing.py",
                            added=["def test_it_works(self):",
                                   "    self.assertTrue(True)"]))

    def test_strengthening_checks_by_adding_showrunner_lines(self):
        """Adding gate code is the allowed direction — only removal is
        forbidden."""
        self.allow(diff_for("scripts/run_third.py",
                            added=["gate = showrunner_gate.run(out, "
                                   "slug=slug, will_upload=True)"]))

    def test_a_scene_fix_in_data_learning(self):
        self.allow(diff_for("data_learning/scenes.py",
                            removed=["stride = dd['stride'] * 3"],
                            added=["stride = dd['stride'] * 30"]))

    def test_writing_its_own_state(self):
        self.allow(diff_for("state/doctor/journal.jsonl",
                            added=['{"ts": "..."}']))

    def test_a_refactor_that_moves_asserts_but_keeps_the_count(self):
        self.allow(diff_for("tests/test_levity.py",
                            removed=["self.assertTrue(a)"],
                            added=["self.assertTrue(a, 'better message')"]))


class DoctorCase(unittest.TestCase):
    """Fixture: a scratch state dir so journal tests touch nothing real."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="doctor-"))
        self._state, self._journal = doc.STATE_DIR, doc.JOURNAL
        doc.STATE_DIR = self.tmp
        doc.JOURNAL = self.tmp / "journal.jsonl"

    def tearDown(self):
        doc.STATE_DIR, doc.JOURNAL = self._state, self._journal
        shutil.rmtree(self.tmp, ignore_errors=True)

    def alarm_ev(self, codes, date="29991216", severity="critical"):
        return {"date": date,
                "alarm": {"alarms": [{"code": c, "severity": severity,
                                      "detail": f"detail {c}", "fix": ""}
                                     for c in codes]},
                "ledger": [], "exchange": {}, "triage_accepted": [],
                "bank_low": [], "journal": doc.load_journal()}


class TestDiagnosis(DoctorCase):
    def test_the_wrong_bundle_bug_gets_the_mechanical_remedy(self):
        ev = self.alarm_ev(["done_but_no_report"])
        ev["exchange"] = {"done": True, "report": None, "bundle": True}
        f = doc.diagnose(ev)
        me = [x for x in f if x["playbook"] == "redispatch_phase_b"]
        self.assertEqual(len(me), 1)
        self.assertEqual(me[0]["kind"], "mechanical")

    def test_the_mechanical_remedy_needs_its_preconditions(self):
        """A redispatch when the report already exists would double-run
        Phase B for no reason."""
        ev = self.alarm_ev(["done_but_no_report"])
        ev["exchange"] = {"done": True, "report": {"date": "x"},
                          "bundle": True}
        f = doc.diagnose(ev)
        self.assertFalse([x for x in f
                          if x["playbook"] == "redispatch_phase_b"])

    def test_a_zero_post_day_is_an_authored_finding(self):
        f = doc.diagnose(self.alarm_ev(["no_posts_trending"]))
        self.assertEqual(f[0]["kind"], "authored")
        self.assertEqual(f[0]["severity"], "critical")

    def test_registry_unusable_goes_straight_to_the_operator(self):
        f = doc.diagnose(self.alarm_ev(["registry_unusable"]))
        self.assertEqual(f[0]["kind"], "report")

    def test_repeated_showrunner_blocks_become_ONE_finding(self):
        ev = self.alarm_ev([])
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        ev["ledger"] = [{"ts": now, "verdict": "block",
                        "auto_fails": ["junk_imagery"]}] * 4
        f = doc.diagnose(ev)
        srs = [x for x in f if x["signature"].startswith("showrunner:")]
        self.assertEqual(len(srs), 1)
        self.assertIn("gate", srs[0]["brief"] or "")
        self.assertIn("never the gate", srs[0]["brief"])

    def test_two_blocks_is_noise_not_a_finding(self):
        ev = self.alarm_ev([])
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        ev["ledger"] = [{"ts": now, "verdict": "block",
                        "auto_fails": ["junk_imagery"]}] * 2
        self.assertFalse([x for x in doc.diagnose(ev)
                          if x["signature"].startswith("showrunner:")])

    def test_accepted_triage_items_enter_the_queue(self):
        ev = self.alarm_ev([])
        ev["triage_accepted"] = [{"signature": "abc", "title": "tighter hook",
                                  "proposal": "do X", "files": []}]
        f = doc.diagnose(ev)
        self.assertTrue([x for x in f if x["signature"] == "triage:abc"])

    def test_an_unknown_alarm_code_is_watched_not_dropped(self):
        f = doc.diagnose(self.alarm_ev(["some_future_code"]))
        self.assertEqual(f[0]["kind"], "watch")

    def test_signatures_are_stable_across_days(self):
        a = doc.diagnose(self.alarm_ev(["no_posts_trending"],
                                       date="29991216"))
        b = doc.diagnose(self.alarm_ev(["no_posts_trending"],
                                       date="29991217"))
        self.assertEqual(a[0]["signature"], b[0]["signature"])


class TestPlanningBounds(DoctorCase):
    def findings(self, n, kind="authored", sev="warn"):
        return [{"signature": f"s{i}", "severity": sev, "title": f"t{i}",
                 "detail": "d", "kind": kind, "playbook": None,
                 "brief": "b"} for i in range(n)]

    def test_one_authored_fix_a_day_and_only_one(self):
        p = doc.plan(self.findings(5), [], "29991216")
        self.assertEqual(len(p["authored"]), doc.MAX_AUTHORED_PER_DAY)

    def test_an_overflowing_CRITICAL_lands_in_front_of_the_operator(self):
        p = doc.plan(self.findings(3, sev="critical"), [], "29991216")
        self.assertEqual(len(p["authored"]), 1)
        self.assertEqual(len(p["report"]), 2,
                         "criticals must never fall into 'watch' silently")

    def test_mechanical_is_capped_too(self):
        p = doc.plan(self.findings(9, kind="mechanical"), [], "29991216")
        self.assertEqual(len(p["mechanical"]), doc.MAX_MECHANICAL_PER_DAY)

    def test_twice_failed_signatures_escalate_and_STOP(self):
        journal = [{"signature": "s0", "outcome": "failed"},
                   {"signature": "s0", "outcome": "failed"}]
        p = doc.plan(self.findings(1), journal, "29991216")
        self.assertFalse(p["authored"], "the doctor retried a fix that has "
                                        "already failed twice")
        self.assertTrue(p["report"])
        self.assertIn("needs you", p["report"][0]["escalated"].lower())

    def test_one_shot_per_signature_per_day(self):
        journal = [{"signature": "s0", "date": "29991216",
                    "kind": "authored", "outcome": "pending"}]
        p = doc.plan(self.findings(1), journal, "29991216")
        self.assertFalse(p["authored"])


class TestTheClosedLoop(DoctorCase):
    def test_a_cleared_alarm_marks_the_action_resolved(self):
        doc.append_journal({"date": "29991215", "signature": "alarm:x",
                            "action_id": "29991215:alarm:x",
                            "kind": "authored", "action": "fixed it",
                            "expect_absent": "x", "outcome": "pending"})
        ev = self.alarm_ev([], date="29991216")
        ev["journal"] = doc.load_journal()
        res = doc.close_the_loop(ev)
        self.assertEqual(res[0]["outcome"], "resolved")

    def test_a_still_firing_alarm_marks_it_failed(self):
        doc.append_journal({"date": "29991215", "signature": "alarm:x",
                            "action_id": "29991215:alarm:x",
                            "kind": "authored", "action": "fixed it",
                            "expect_absent": "x", "outcome": "pending"})
        ev = self.alarm_ev(["x"], date="29991216")
        ev["journal"] = doc.load_journal()
        res = doc.close_the_loop(ev)
        self.assertEqual(res[0]["outcome"], "failed")
        # and that failure now counts toward escalation
        self.assertEqual(doc.failed_attempts(doc.load_journal()), {"alarm:x": 1})

    def test_same_day_actions_are_not_judged_early(self):
        doc.append_journal({"date": "29991216", "signature": "alarm:x",
                            "action_id": "29991216:alarm:x",
                            "kind": "authored", "action": "fixed it",
                            "expect_absent": "x", "outcome": "pending"})
        ev = self.alarm_ev([], date="29991216")
        ev["journal"] = doc.load_journal()
        self.assertEqual(doc.close_the_loop(ev), [])

    def test_the_brief_carries_the_constitution(self):
        p = doc.plan([{"signature": "s", "severity": "warn", "title": "t",
                       "detail": "d", "kind": "authored", "playbook": None,
                       "brief": "fix the thing"}], [], "29991216")
        path = doc.write_brief(p)
        text = path.read_text()
        self.assertIn("NEVER edit scripts/showrunner_review.py", text)
        self.assertIn("test that fails before your fix", text)
        self.assertIn("fix the thing", text)

    def test_render_says_quiet_when_there_is_nothing(self):
        p = {"date": "29991216", "mechanical": [], "authored": [],
             "report": [], "watch": []}
        self.assertIn("quiet", doc.render(p, []).lower())


class TestTheDoctorRespectsTheRetroContract(unittest.TestCase):
    """`tests/test_retro.py` allows exactly two workflows to touch retro
    proposals. The doctor must never become a third — it consumes the
    TRIAGE OUTPUT only, inside the script, not the workflow."""

    def test_the_script_reads_triage_not_proposals(self):
        src = (ROOT / "scripts" / "pipeline_doctor.py").read_text()
        self.assertIn("triage.json", src)
        self.assertNotIn('"proposals"', src)
        self.assertNotIn("proposals/", src)

    def test_the_workflow_if_present_stays_clear_of_the_proposal_regex(self):
        import re as _re
        wf = ROOT / ".github" / "workflows" / "doctor.yml"
        if not wf.exists():
            self.skipTest("doctor.yml not landed yet")
        body = wf.read_text()
        touches = _re.compile(
            r"retro[/\w.-]*proposals|proposals/|review_proposals|"
            r"pending_decisions|retro_reply|apply_proposal")
        self.assertIsNone(touches.search(body),
                          "doctor.yml touches the retro proposal machinery — "
                          "that contract belongs to retro.yml/retro_decide.yml")

    def test_the_workflow_if_present_never_pushes_main(self):
        wf = ROOT / ".github" / "workflows" / "doctor.yml"
        if not wf.exists():
            self.skipTest("doctor.yml not landed yet")
        body = wf.read_text()
        self.assertNotIn("push origin main", body)
        self.assertNotIn("HEAD:main", body)
        self.assertIn("claude/doctor-", body,
                      "authored fixes must ride a claude/doctor-* branch "
                      "through the PR gate")
        self.assertIn("review-diff", body,
                      "the workflow must run the constitution on the diff")


if __name__ == "__main__":
    unittest.main()
