"""The doctor: ChatGPT diagnoses, Claude decides, nothing is automatic.

Three properties keep this useful rather than becoming a file nobody opens:

  1. **It cannot apply anything.** No workflow reads a finding and edits
     code. Same safety model as `retro/`.
  2. **A settled finding cannot come back.** The reviewer re-reads the whole
     repo daily; without durable verdicts keyed on WHAT a finding touches,
     it would re-file the thing you killed last week, in new words, forever.
     Rewording must not defeat it — that is the test that matters most.
  3. **The refusal list still applies.** "Make the numbers go up by lowering
     the bar" is refused here exactly as it is in the retro triage, because
     it is the SAME list, imported — not a second copy that can drift.

    python -m unittest tests.test_doctor -v
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import doctor                                            # noqa: E402


def finding(**kw):
    base = {
        "title": "the reddit renderer drops verified shot images",
        "horizon": "bug", "severity": "high", "area": "trending/render",
        "files": ["make_reddit_story.py"],
        "observation": "The renderer ignores shot.image_url.",
        "proposal": "Consume the verified per-shot images in the top half.",
        "evidence": "make_reddit_story.py has no reader for shot.image_url; "
                    "vision QA judges a composite that never existed.",
    }
    base.update(kw)
    return base


def report(*findings, schema=doctor.SCHEMA, date="20260806"):
    return {"schema": schema, "date": date, "findings": list(findings)}


class DoctorCase(unittest.TestCase):
    """Redirect the doctor's whole state tree into a scratch dir."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="doctor-"))
        self._saved = (doctor.DOCTOR_DIR, doctor.VERDICTS, doctor.BACKLOG,
                       doctor.EVIDENCE, doctor.REPORTS_DIR)
        doctor.DOCTOR_DIR = self.tmp
        doctor.VERDICTS = self.tmp / "verdicts.json"
        doctor.BACKLOG = self.tmp / "backlog.json"
        doctor.EVIDENCE = self.tmp / "evidence.json"
        doctor.REPORTS_DIR = self.tmp / "reports"

    def tearDown(self):
        (doctor.DOCTOR_DIR, doctor.VERDICTS, doctor.BACKLOG,
         doctor.EVIDENCE, doctor.REPORTS_DIR) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sig_of(self, f):
        return doctor.signature(f)


class TestASettledFindingStaysSettled(DoctorCase):
    """The property the whole thing rests on."""

    def test_rewording_does_NOT_get_it_past_the_gate(self):
        f = finding()
        doctor.ingest(report(f))
        doctor.rule(self.sig_of(f), "not_doing", because="already fixed")
        reworded = finding(
            title="shot illustrations are ignored by make_reddit_story",
            observation="Totally different sentence.",
            proposal="Have the renderer read the verified images.",
            evidence="Nothing in make_reddit_story.py consumes image_url.")
        res = doctor.validate_report(report(reworded))
        self.assertEqual(res["counts"]["accepted"], 0)
        self.assertIn("already ruled `not_doing`",
                      " ".join(res["rejected"][0]["problems"]))

    def test_the_refusal_reason_is_shown_back_to_the_reviewer(self):
        """"No" with a reason teaches; "no" alone gets re-argued."""
        f = finding()
        doctor.ingest(report(f))
        doctor.rule(self.sig_of(f), "not_doing",
                    because="the 08-02 rescue already did this")
        res = doctor.validate_report(report(finding()))
        self.assertIn("08-02 rescue", " ".join(res["rejected"][0]["problems"]))

    def test_genuine_new_evidence_DOES_reopen_it(self):
        f = finding()
        doctor.ingest(report(f))
        doctor.rule(self.sig_of(f), "not_doing", because="fixed")
        again = finding(new_evidence_since="regressed in 4783b7c3 — the "
                                           "panel builder returns [] now")
        self.assertEqual(
            doctor.validate_report(report(again))["counts"]["accepted"], 1)

    def test_later_parks_it_then_lets_it_back(self):
        f = finding()
        doctor.ingest(report(f))
        doctor.rule(self.sig_of(f), "later", because="after the migration",
                    revisit_after="29991231")
        self.assertEqual(
            doctor.validate_report(report(finding()))["counts"]["accepted"], 0)
        doctor.rule(self.sig_of(f), "later", because="ok",
                    revisit_after="20200101")          # window has passed
        self.assertEqual(
            doctor.validate_report(report(finding()))["counts"]["accepted"], 1)

    def test_later_gets_a_revisit_date_even_when_none_is_given(self):
        e = doctor.rule("abc123", "later", because="not yet")
        self.assertRegex(e["revisit_after"], r"^\d{8}$")

    def test_a_shipped_finding_is_not_refiled_as_new(self):
        f = finding()
        doctor.ingest(report(f))
        doctor.rule(self.sig_of(f), "done", commit="deadbeef")
        res = doctor.validate_report(report(finding()))
        self.assertIn("already shipped",
                      " ".join(res["rejected"][0]["problems"]))

    def test_doing_and_in_progress_do_NOT_block_a_refresh(self):
        """A finding being worked on may legitimately be re-described."""
        f = finding()
        doctor.ingest(report(f))
        for verdict in ("doing", "in_progress"):
            doctor.rule(self.sig_of(f), verdict, because="picked up")
            self.assertEqual(
                doctor.validate_report(report(finding()))["counts"]["accepted"],
                1, verdict)


class TestSignatureIdentity(unittest.TestCase):
    def test_the_same_files_and_area_are_the_same_finding(self):
        self.assertEqual(doctor.signature(finding()),
                         doctor.signature(finding(title="totally different",
                                                  observation="x" * 40)))

    def test_a_different_file_is_a_different_finding(self):
        self.assertNotEqual(
            doctor.signature(finding()),
            doctor.signature(finding(files=["make_graph_race.py"])))

    def test_a_different_area_is_a_different_finding(self):
        self.assertNotEqual(doctor.signature(finding()),
                            doctor.signature(finding(area="explainer")))

    def test_fileless_findings_fall_back_to_title_words(self):
        a = finding(files=[], title="split the monolithic niche config")
        b = finding(files=[], title="the niche config monolithic split")
        self.assertEqual(doctor.signature(a), doctor.signature(b))

    def test_two_unrelated_fileless_findings_differ(self):
        a = finding(files=[], title="split the niche config")
        b = finding(files=[], title="add retention analytics per format")
        self.assertNotEqual(doctor.signature(a), doctor.signature(b))

    def test_signatures_are_short_and_stable_across_runs(self):
        s = doctor.signature(finding())
        self.assertRegex(s, r"^[0-9a-f]{12}$")
        self.assertEqual(s, doctor.signature(finding()))


class TestTheRefusalListIsInherited(DoctorCase):
    """Same list as the retro triage — imported, never re-implemented."""

    def refuse(self, **kw):
        res = doctor.validate_report(report(finding(**kw)))
        self.assertEqual(res["counts"]["accepted"], 0,
                         "a bar-lowering finding was accepted")
        return " ".join(res["rejected"][0]["problems"]).lower()

    def test_weakening_the_showrunner(self):
        self.assertIn("showrunner", self.refuse(
            title="lower the showrunner threshold",
            files=["scripts/showrunner_review.py"],
            proposal="Lower the min score so more videos pass the gate."))

    def test_deleting_a_test(self):
        self.assertIn("test", self.refuse(
            title="drop the flaky suite",
            files=["tests/test_captions.py"],
            proposal="Delete this test, it keeps failing."))

    def test_more_volume_through_a_lower_bar(self):
        self.assertTrue(self.refuse(
            title="ship more per day",
            files=[],
            proposal="Increase videos per day by relaxing the quality gate."))

    def test_fabricating_data(self):
        self.assertTrue(self.refuse(
            title="fill the gaps",
            files=[],
            proposal="Invent plausible statistics when the source is thin."))

    def test_a_STRONGER_gate_is_always_welcome(self):
        res = doctor.validate_report(report(finding(
            title="add a loudness floor to technical QA",
            files=["shared/video_qa.py"],
            proposal="Add a check that blocks a render whose audio is "
                     "silent, on top of the existing gates.",
            evidence="shared/video_qa.py measures loudness but never "
                     "blocks on it; three uploads this week were silent.")))
        self.assertEqual(res["counts"]["accepted"], 1)


class TestReportShape(DoctorCase):
    def bad(self, **kw):
        res = doctor.validate_report(report(finding(**kw)))
        self.assertEqual(res["counts"]["accepted"], 0)
        return " ".join(res["rejected"][0]["problems"])

    def test_the_schema_must_match(self):
        res = doctor.validate_report(report(finding(), schema="something/v9"))
        self.assertFalse(res["ok"])
        self.assertIn("schema", " ".join(res["rejected"][0]["problems"]))

    def test_a_missing_field_is_refused(self):
        self.assertIn("proposal", self.bad(proposal=""))

    def test_an_unknown_horizon_is_refused(self):
        self.assertIn("horizon", self.bad(horizon="someday"))

    def test_an_unknown_severity_is_refused(self):
        self.assertIn("severity", self.bad(severity="catastrophic"))

    def test_thin_evidence_is_refused(self):
        self.assertIn("evidence", self.bad(evidence="it's bad"))

    def test_a_file_that_does_not_exist_is_refused(self):
        """A finding about an imaginary file is a hallucination, and it is
        the cheapest possible thing to check."""
        self.assertIn("does not exist",
                      self.bad(files=["scripts/not_a_real_file.py"]))

    def test_a_duplicate_inside_one_report_is_refused(self):
        res = doctor.validate_report(report(finding(), finding()))
        self.assertEqual(res["counts"]["accepted"], 1)
        self.assertIn("duplicate", " ".join(res["rejected"][0]["problems"]))

    def test_junk_does_not_crash_it(self):
        for junk in (None, [], "string", {"schema": doctor.SCHEMA,
                                          "findings": [None, 7, "x"]}):
            res = doctor.validate_report(junk)
            self.assertIn("rejected", res)


class TestTheBacklog(DoctorCase):
    def test_ingest_lands_it_awaiting_a_ruling(self):
        res = doctor.ingest(report(finding()))
        self.assertEqual(len(res["added"]), 1)
        self.assertEqual(doctor.ruling_of(res["added"][0]), doctor.UNRULED)

    def test_a_refresh_keeps_the_ruling_and_the_first_seen_date(self):
        """ChatGPT may sharpen a description; it may not launder a new
        decision through a rewrite."""
        f = finding()
        doctor.ingest(report(f), date="20260801")
        sig = self.sig_of(f)
        doctor.rule(sig, "doing", because="picked up")
        doctor.ingest(report(finding(observation="sharper wording")),
                      date="20260806")
        self.assertEqual(doctor.ruling_of(sig), "doing",
                         "a rewrite must not clear the ruling")
        item = doctor.load_backlog()[sig]
        self.assertEqual(item["first_seen"], "20260801")
        self.assertEqual(item["last_seen"], "20260806")
        self.assertEqual(item["observation"], "sharper wording")

    def test_a_PARKED_finding_is_not_even_refreshed(self):
        """`later` and `not_doing` stop the item at validation, so a parked
        finding's text stays frozen too — there is nothing to refresh
        because the re-file never got in."""
        f = finding()
        doctor.ingest(report(f), date="20260801")
        sig = self.sig_of(f)
        doctor.rule(sig, "later", because="after the migration")
        res = doctor.ingest(report(finding(observation="sharper wording")),
                            date="20260806")
        self.assertEqual(res["refreshed"], [])
        self.assertEqual(doctor.load_backlog()[sig]["last_seen"], "20260801")

    def test_next_puts_doing_ahead_of_unruled(self):
        a = finding(files=["make_reddit_story.py"], severity="low")
        b = finding(files=["make_graph_race.py"], severity="low")
        doctor.ingest(report(a, b))
        doctor.rule(self.sig_of(b), "doing", because="picked")
        self.assertEqual(doctor.next_up()[0]["signature"], self.sig_of(b))

    def test_the_backlog_ranks_critical_bugs_first(self):
        doctor.ingest(report(
            finding(files=["make_graph_race.py"], severity="low",
                    horizon="long_term"),
            finding(files=["make_reddit_story.py"], severity="critical",
                    horizon="bug")))
        self.assertEqual(doctor.backlog_view()[0]["severity"], "critical")

    def test_not_doing_items_drop_out_of_next(self):
        f = finding()
        doctor.ingest(report(f))
        doctor.rule(self.sig_of(f), "not_doing", because="no")
        self.assertEqual(doctor.next_up(), [])

    def test_a_ruling_keeps_its_history(self):
        doctor.rule("sig1", "later", because="not yet")
        e = doctor.rule("sig1", "doing", because="now it matters")
        self.assertEqual(e["verdict"], "doing")
        self.assertEqual(e["history"][0]["verdict"], "later")

    def test_an_illegal_verdict_is_refused(self):
        with self.assertRaises(ValueError):
            doctor.rule("sig1", "maybe")

    def test_the_vocabulary_is_the_operators_own(self):
        self.assertEqual(set(doctor.VERDICTS_ALLOWED),
                         {"doing", "not_doing", "later", "in_progress",
                          "done"})


class TestTheEvidencePackTellsChatGPTWhatIsSettled(DoctorCase):
    def test_settled_rulings_are_published_to_the_reviewer(self):
        f = finding()
        doctor.ingest(report(f))
        doctor.rule(self.sig_of(f), "not_doing", because="already fixed")
        pack = doctor.evidence_pack()
        sigs = {s["signature"] for s in pack["settled"]}
        self.assertIn(self.sig_of(f), sigs,
                      "the reviewer cannot avoid re-filing what it is never "
                      "shown")

    def test_open_work_is_published_too(self):
        doctor.ingest(report(finding()))
        pack = doctor.evidence_pack()
        self.assertTrue(pack["open_backlog"])

    def test_the_pack_carries_runtime_truth_not_just_code(self):
        """Source alone yields plausible findings; source plus what actually
        broke yields checkable ones."""
        pack = doctor.evidence_pack()
        for key in ("alarm", "production_runs", "showrunner_recent",
                    "recent_commits"):
            self.assertIn(key, pack)

    def test_it_never_raises_on_a_bare_repo(self):
        self.assertIn("schema", doctor.evidence_pack())


class TestThePromptsMatchTheCode(DoctorCase):
    """`doctor/PROMPTS.md` is pasted verbatim into two scheduled tasks that
    run unattended. A prompt promising a flag that does not exist fails at
    3am in someone else's app, where nobody is watching — so the promises
    are checked here."""

    TEXT = (ROOT / "doctor" / "PROMPTS.md").read_text()

    def test_every_verdict_it_names_is_a_real_verdict(self):
        named = set(re.findall(r"rule <sig> ([a-z_]+)", self.TEXT))
        self.assertTrue(named)
        self.assertEqual(named - set(doctor.VERDICTS_ALLOWED), set())

    def test_every_subcommand_it_names_exists(self):
        named = set(re.findall(r"scripts/doctor\.py ([a-z-]+)", self.TEXT))
        self.assertTrue(named)
        self.assertEqual(named - {"backlog", "next", "rule", "show",
                                  "validate", "ingest", "evidence"}, set())

    def test_the_example_report_it_shows_actually_validates(self):
        """If the schema in the prompt is wrong, every report is rejected
        on arrival and the loop produces nothing, daily."""
        res = doctor.validate_report(report(finding(
            title="short and specific",
            observation="what is true right now",
            proposal="what to do about it",
            evidence="the file and line, the log, the run — something a "
                     "reader can open and check")))
        self.assertEqual(res["counts"]["accepted"], 1)

    def test_the_empty_report_it_mandates_is_accepted(self):
        """The prompt tells ChatGPT to file a report even with no findings,
        because a missing report is ambiguous. That must not be an error."""
        res = doctor.validate_report(
            {"schema": doctor.SCHEMA, "date": "20260806",
             "summary": "nothing new", "findings": []})
        self.assertEqual(res["rejected"], [])

    def test_the_report_path_it_names_is_the_one_the_workflow_watches(self):
        self.assertIn("doctor/reports/<YYYYMMDD>.json", self.TEXT)
        wf = (ROOT / ".github" / "workflows" / "doctor.yml").read_text()
        self.assertIn("doctor/reports/**", wf)

    def test_it_tells_chatgpt_the_two_things_that_stop_repetition(self):
        self.assertIn("new_evidence_since", self.TEXT)
        self.assertIn("settled", self.TEXT)

    def test_it_forbids_editing_code(self):
        self.assertIn("NEVER edit", self.TEXT)


class TestNothingIsEverApplied(unittest.TestCase):
    """The safety model, stated as a test — same as retro's."""

    def test_no_workflow_edits_code_from_a_finding(self):
        pat = re.compile(r"doctor\.py\s+(apply|fix|author)|apply_finding")
        for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
            self.assertIsNone(pat.search(wf.read_text()),
                              f"{wf.name} looks like it applies a doctor "
                              f"finding automatically")

    def test_the_doctor_script_has_no_apply_path(self):
        src = (ROOT / "scripts" / "doctor.py").read_text()
        for banned in ("subprocess.run([\"git\", \"commit\"",
                       "git push", "claude -p"):
            self.assertNotIn(banned, src,
                             "the doctor must not author or ship anything — "
                             "it diagnoses, Claude decides")

    def test_the_readme_states_the_rule(self):
        text = (ROOT / "doctor" / "README.md").read_text().lower()
        self.assertIn("ever applied automatically", text)
        self.assertIn("never edits code", text)

    def test_the_doctor_does_not_touch_the_retro_proposal_machinery(self):
        """retro's two-workflow contract is separately enforced; the doctor
        must not become a third party to it."""
        src = (ROOT / "scripts" / "doctor.py").read_text()
        self.assertNotIn("proposals/", src)
        self.assertNotIn("retro_reply", src)


if __name__ == "__main__":
    unittest.main()
