"""Tests for the daily retro loop.

The loop has exactly one dangerous failure mode: the cheapest way to make
the numbers go up is to lower a bar, so a reviewer under pressure to
produce findings will eventually propose weakening the showrunner, pruning
the posted log, or deleting a test — and it will be well-argued. The
refusal has to be mechanical, which means it has to be tested like a
security control, not like a linter.

The second failure mode is quieter: a brief that lets a 9-view video look
like a trend. Age-matching and sample-size honesty are tested here too.

    python -m unittest tests.test_retro -v
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
sys.path.append(str(ROOT / "scripts"))   # APPEND: see note below

import build_retro as br                             # noqa: E402
import review_proposals as rp                        # noqa: E402


def proposal(**over) -> dict:
    p = {"schema": "shorts-retro-proposal/v1",
         "title": "Shorten the graph hook",
         "category": "content", "confidence": "medium",
         "observation": "8 graph_race videos average 0.16 vph vs 0.04 for "
                        "10 text_card.",
         "evidence": ["state/format_scoreboard.json"],
         "proposal": "Shorten the graph_race hook overlay to 0.8s.",
         "files": ["make_graph_race.py"],
         "expected_effect": "Higher 3s hold.",
         "how_we_would_know": "graph_race avg_view_pct after 10 more posts.",
         "risks": "Could hurt completion.", "rollback": "revert a constant"}
    p.update(over)
    return p


class TestRefusals(unittest.TestCase):
    """Every one of these has to be refused on policy, and refusal must not
    depend on the proposal being sloppy — a WELL-FORMED attack is the real
    case."""

    def _refused(self, **over) -> list[str]:
        return rp.check_forbidden(proposal(**over))

    def test_lowering_the_showrunner_floor(self):
        why = self._refused(
            title="Lower the showrunner score floor to ship more",
            proposal="Reduce SHOWRUNNER_MIN_SCORE from 70 to 55 so more "
                     "videos pass the gate.",
            files=["scripts/showrunner_review.py"])
        self.assertTrue(why)
        self.assertTrue(any("sovereign" in w or "lowering" in w for w in why))

    def test_disabling_the_showrunner_outright(self):
        self.assertTrue(self._refused(
            proposal="Set SHOWRUNNER=off when the queue is short.",
            files=["scripts/post_stories.py"]))

    def test_skipping_a_gate(self):
        self.assertTrue(self._refused(
            proposal="Skip the validation gate for packages we trust."))

    def test_pruning_the_posted_log(self):
        why = self._refused(
            title="Prune the posted log",
            proposal="Remove posted_log entries older than 60 days.",
            files=["state/posted_log.json"])
        self.assertTrue(any("dedupe" in w for w in why))

    def test_weakening_the_punchup_guard(self):
        self.assertTrue(self._refused(
            proposal="Relax the claim guard threshold so more punch-ups land.",
            files=["shared/punchup_guard.py"]))

    def test_deleting_a_test(self):
        self.assertTrue(self._refused(
            proposal="Delete the flaky placement gate test."))

    def test_more_volume_via_a_lower_bar(self):
        self.assertTrue(self._refused(
            proposal="Increase videos per day by relaxing the illustration "
                     "coverage requirement."))

    def test_fabricating_data(self):
        self.assertTrue(self._refused(
            proposal="Invent plausible statistics when the World Bank has "
                     "no series for the topic."))

    def test_a_polished_violation_is_still_refused(self):
        """High confidence, real numbers, a rollback plan, honest risks —
        and still refused, because it is policy, not a judgement call."""
        p = proposal(
            title="Recalibrate the showrunner floor to match observed quality",
            confidence="high",
            observation="Blocked videos scored 62, 64, 66 against a floor of "
                        "70; all 3 looked fine on manual review.",
            evidence=["pipeline_health.showrunner", "state/analytics"],
            proposal="Lower the showrunner minimum score from 70 to 60.",
            files=["scripts/showrunner_review.py"],
            risks="Slightly weaker videos may ship.",
            rollback="Restore the constant.")
        report = self._triage_one(p)
        self.assertEqual(report["counts"]["refused"], 1)
        self.assertEqual(report["counts"]["accepted"], 0)

    def test_strengthening_a_gate_is_allowed(self):
        """The rule is one-directional: adding blocks is always fine."""
        self.assertEqual(self._refused(
            title="Raise the illustration coverage floor",
            proposal="Increase the minimum illustration coverage from 60 to "
                     "70 so weaker slates are caught earlier.",
            files=["scripts/validate_packages.py"]), [])

    def _triage_one(self, p: dict) -> dict:
        tmp = Path(tempfile.mkdtemp(prefix="retro-"))
        saved = rp.RETRO_ROOT
        try:
            rp.RETRO_ROOT = tmp
            d = tmp / "20260801" / "proposals"
            d.mkdir(parents=True)
            (d / "01.json").write_text(json.dumps(p))
            return rp.triage("20260801")
        finally:
            rp.RETRO_ROOT = saved
            shutil.rmtree(tmp, ignore_errors=True)


class TestTriage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="retro-"))
        self._saved = rp.RETRO_ROOT
        rp.RETRO_ROOT = self.tmp
        self.pdir = self.tmp / "20260801" / "proposals"
        self.pdir.mkdir(parents=True)
        # Evidence is now verified against the brief, so triage needs one.
        (self.tmp / "20260801" / "brief.json").write_text(json.dumps(
            {"state/format_scoreboard.json": {"graph_race": 0.16,
                                              "text_card": 0.04,
                                              "graph_n": 8, "card_n": 10}}))

    def tearDown(self):
        rp.RETRO_ROOT = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _put(self, name: str, p: dict) -> None:
        (self.pdir / name).write_text(json.dumps(p))

    def test_a_clean_proposal_is_accepted(self):
        self._put("01.json", proposal())
        r = rp.triage("20260801")
        self.assertEqual(r["counts"]["accepted"], 1)
        self.assertGreater(r["accepted"][0]["score"], 0)

    def test_load_bearing_file_needs_an_operator(self):
        self._put("01.json", proposal(files=["scripts/run_trending_daily.py"]))
        r = rp.triage("20260801")
        self.assertEqual(r["counts"]["requires_operator"], 1)
        self.assertEqual(r["counts"]["accepted"], 0)

    def test_observation_without_numbers_is_malformed(self):
        self._put("01.json", proposal(observation="The hooks feel weak."))
        r = rp.triage("20260801")
        self.assertEqual(r["counts"]["malformed"], 1)
        self.assertIn("cites no numbers",
                      " ".join(r["malformed"][0]["problems"]))

    def test_unmeasurable_success_criterion_is_malformed(self):
        self._put("01.json", proposal(how_we_would_know="It will feel better."))
        r = rp.triage("20260801")
        self.assertEqual(r["counts"]["malformed"], 1)

    def test_missing_required_field_is_malformed(self):
        p = proposal()
        del p["risks"]
        self._put("01.json", p)
        self.assertEqual(rp.triage("20260801")["counts"]["malformed"], 1)

    def test_unreadable_file_is_malformed_not_fatal(self):
        (self.pdir / "01.json").write_text("{not json")
        self._put("02.json", proposal())
        r = rp.triage("20260801")
        self.assertEqual(r["counts"]["malformed"], 1)
        self.assertEqual(r["counts"]["accepted"], 1)

    def test_claiming_no_risk_is_penalised(self):
        self._put("01.json", proposal(risks="none"))
        self._put("02.json", proposal(title="Other", risks="Could regress X."))
        r = rp.triage("20260801")
        by = {e["title"]: e["score"] for e in r["accepted"]}
        self.assertLess(by["Shorten the graph hook"], by["Other"])

    def test_no_proposals_is_a_clean_empty_triage(self):
        r = rp.triage("20260801")
        self.assertEqual(sum(r["counts"].values()), 0, r["counts"])

    def test_missing_directory_does_not_raise(self):
        r = rp.triage("29991231")
        self.assertIn("note", r)


class TestBriefIsHonest(unittest.TestCase):
    """A brief that lets a 9-view video look like a trend is worse than no
    brief — it launders noise into a mandate."""

    def test_age_bands_cover_everything(self):
        for h in (0, 5.9, 6, 23, 24, 71, 168, 671, 672, 99999):
            self.assertTrue(br.band_of(h))

    def test_percentile_refuses_a_thin_sample(self):
        self.assertIsNone(br.percentile_in(5.0, [1.0, 2.0]))
        self.assertIsNotNone(br.percentile_in(5.0, [1.0, 2.0, 3.0, 4.0, 6.0]))

    def test_percentile_is_directionally_right(self):
        pop = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertGreater(br.percentile_in(9.0, pop),
                           br.percentile_in(0.5, pop))

    def test_vph_normalises_by_age(self):
        young = br._vph({"views": 10, "age_hours": 2})
        old = br._vph({"views": 10, "age_hours": 200})
        self.assertGreater(young, old)

    def test_zero_age_does_not_divide_by_zero(self):
        self.assertEqual(br._vph({"views": 5, "age_hours": 0}), 5.0)

    def test_brief_states_how_to_read_it(self):
        b = br.build("20260730")
        how = b["how_to_read_this"]
        self.assertIn("age", " ".join(how).lower())
        self.assertIn("noise", json.dumps(how).lower())

    def test_brief_survives_a_channel_with_no_analytics(self):
        r = br.channel_report("ghost", "state/does_not_exist.json", "20260730")
        self.assertFalse(r["available"])

    def test_brief_points_at_the_contract(self):
        self.assertEqual(br.build("20260730")["your_job"], "retro/README.md")


class TestContractAndCodeAgree(unittest.TestCase):
    """The README promises specific refusals. If the code stops enforcing
    one, the promise becomes a lie that a reviewer will act on."""

    def test_readme_lists_every_protected_file(self):
        text = (ROOT / "retro" / "README.md").read_text()
        for name in ("showrunner", "posted log", "punch-up guard",
                     "placement gate"):
            self.assertIn(name.split()[0].lower(), text.lower())

    def test_readme_says_nothing_is_auto_applied(self):
        text = (ROOT / "retro" / "README.md").read_text().lower()
        self.assertIn("ever applied automatically", text)
        self.assertIn("no workflow reads", text)

    def test_no_workflow_applies_a_proposal_untriaged_or_unrecorded(self):
        """The safety model, stated precisely.

        A proposal may reach production only if it was TRIAGED first (so the
        refusal list ran) and a VERDICT was RECORDED (so nothing is applied
        silently). Two workflows legitimately touch proposals:

            retro.yml         triages   -> review_proposals.py
            retro_decide.yml  decides   -> pending_decisions.py (reads the
                                           triage) + retro_reply.py (records)

        Anything else that touches proposals, or either of these losing its
        half of the contract, is the failure this guards."""
        allowed = {
            "retro.yml": ["review_proposals.py"],
            "retro_decide.yml": ["pending_decisions.py", "retro_reply.py"],
        }
        for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
            body = wf.read_text()
            # Match the retro PROPOSAL PATH, not the bare word. `proposals`
            # alone also matches curiosity-ci.yml running
            # `scripts/test_learning_proposals.py` — an unrelated unit test.
            # That false positive sat undetected because `unittest discover`
            # was crashing on an unrelated import collision before reaching
            # this test at all (see docs/SYSTEM_AUDIT.md).
            if not any(t in body for t in ("retro/", "retro_reply",
                                           "review_proposals",
                                           "pending_decisions")):
                continue
            self.assertNotIn("apply_proposal", body)
            self.assertIn(wf.name, allowed,
                          f"{wf.name} touches proposals but is not one of the "
                          f"two workflows allowed to")
            for required in allowed[wf.name]:
                self.assertIn(required, body,
                              f"{wf.name} lost its {required} step — a "
                              f"proposal could now be acted on untriaged "
                              f"or without a recorded verdict")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestExperimentsRefuseEarlyConclusions(unittest.TestCase):
    """The whole reason experiments exist: six videos a day into
    single-digit views means ANY one-day read is noise. If the register can
    be talked into concluding early, the loop walks the channel in a random
    direction with confidence."""

    def setUp(self):
        from shared import experiments as ex
        self.ex = ex
        self.tmp = Path(tempfile.mkdtemp(prefix="exp-"))
        self._saved = (ex.RETRO_STATE, ex.REGISTER)
        ex.RETRO_STATE = self.tmp
        ex.REGISTER = self.tmp / "experiments.json"

    def tearDown(self):
        self.ex.RETRO_STATE, self.ex.REGISTER = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _reg(self, days_ago=0, **over):
        from datetime import datetime, timedelta, timezone
        when = (datetime.now(timezone.utc)
                - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        kw = dict(change="c", metric="graph_race.avg_view_pct",
                  direction="up", baseline=80.0, guardrail="showrunner.score",
                  guardrail_baseline=74.0, min_days=7, min_samples=10,
                  now=when)
        kw.update(over)
        return self.ex.register("shorter hooks hold better", **kw)

    def test_plenty_of_samples_but_too_few_days_is_refused(self):
        e = self._reg(days_ago=3)
        ok, why = self.ex.readout_ready(e, samples=500)
        self.assertFalse(ok)
        self.assertIn("days elapsed", why)

    def test_plenty_of_days_but_too_few_samples_is_refused(self):
        e = self._reg(days_ago=30)
        ok, why = self.ex.readout_ready(e, samples=2)
        self.assertFalse(ok)
        self.assertIn("samples", why)

    def test_both_floors_passed_is_ready(self):
        e = self._reg(days_ago=8)
        self.assertTrue(self.ex.readout_ready(e, samples=12)[0])

    def test_a_real_improvement_is_adopted(self):
        e = self._reg(days_ago=8)
        r = self.ex.conclude(e, observed=100.0, guardrail_observed=75.0)
        self.assertEqual(r["status"], "adopted")

    def test_a_regression_is_reverted(self):
        e = self._reg(days_ago=8)
        r = self.ex.conclude(e, observed=50.0, guardrail_observed=74.0)
        self.assertEqual(r["status"], "reverted")

    def test_a_small_move_is_weather_not_a_result(self):
        e = self._reg(days_ago=8)
        r = self.ex.conclude(e, observed=83.0, guardrail_observed=74.0)
        self.assertEqual(r["status"], "inconclusive")
        self.assertIn("weather", r["readout"]["verdict"])

    def test_a_guardrail_regression_outranks_a_metric_win(self):
        """More views bought with worse videos is a LOSS. This ordering is
        the loop's value alignment and must not be reachable by proposal."""
        e = self._reg(days_ago=8)
        r = self.ex.conclude(e, observed=160.0, guardrail_observed=50.0)
        self.assertEqual(r["status"], "reverted")
        self.assertIn("guardrail", r["readout"]["verdict"])

    def test_direction_down_is_honoured(self):
        e = self._reg(days_ago=8, direction="down", baseline=10.0)
        self.assertEqual(
            self.ex.conclude(e, observed=4.0,
                             guardrail_observed=74.0)["status"], "adopted")

    def test_refresh_due_flips_only_closed_windows(self):
        self._reg(days_ago=8)
        self._reg(days_ago=1)
        for e in self.ex.all_experiments():
            self.ex.bump_samples(e["id"], 20)
        due = self.ex.refresh_due()
        self.assertEqual(len(due), 1)

    def test_a_concluded_experiment_cannot_be_read_out_again(self):
        e = self._reg(days_ago=8)
        self.ex.conclude(e, observed=100.0, guardrail_observed=75.0)
        self.assertFalse(self.ex.readout_ready(
            self.ex.all_experiments()[0], samples=99)[0])

    def test_zero_baseline_does_not_explode(self):
        e = self._reg(days_ago=8, baseline=0.0)
        self.assertIn(self.ex.conclude(e, observed=5.0)["status"],
                      ("adopted", "reverted", "inconclusive"))


class TestTheLoopHasMemory(unittest.TestCase):
    """A one-way loop degrades: declined ideas return in new clothes and
    adopted changes are never read out. The ledger and the obligations are
    what stop that."""

    def setUp(self):
        import retro_reply as rr
        self.rr = rr
        self.tmp = Path(tempfile.mkdtemp(prefix="ledger-"))
        self._saved = (rr.RETRO_ROOT, rr.STATE, rr.LEDGER, rr.AGENDA)
        rr.RETRO_ROOT = self.tmp
        rr.STATE = self.tmp / "state"
        rr.LEDGER = rr.STATE / "ledger.jsonl"
        rr.AGENDA = rr.STATE / "agenda.json"

    def tearDown(self):
        (self.rr.RETRO_ROOT, self.rr.STATE, self.rr.LEDGER,
         self.rr.AGENDA) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_verdict_persists_with_its_reasoning(self):
        self.rr.append_ledger({"date": "20260801", "proposal_file": "01.json",
                               "title": "T", "verdict": "adopt",
                               "because": "shipped at 0.9s not 0.8"})
        rows = self.rr.read_ledger()
        self.assertEqual(rows[-1]["verdict"], "adopt")
        self.assertIn("0.9s", rows[-1]["because"])

    def test_an_open_verdict_stays_on_the_agenda(self):
        self.rr.write_agenda({"open": [
            {"proposal_file": "02.json", "title": "Needs numbers",
             "verdict": "needs_evidence", "what_i_need": "a percentile"}]})
        self.assertEqual(len(self.rr.read_agenda()["open"]), 1)

    def test_an_empty_retro_is_refused_while_work_is_owed(self):
        owed = br.obligations(
            {"readouts_due": [{"id": "x", "hypothesis": "h"}],
             "open_agenda": [], "experiments": {"running": [{"id": "y"}]}},
            {})
        self.assertGreaterEqual(owed["must_do"], 1)
        self.assertIn("readout", [i["kind"] for i in owed["items"]])

    def test_no_live_experiment_is_itself_an_obligation(self):
        """A quiet day means START something, not agree things are fine."""
        owed = br.obligations(
            {"readouts_due": [], "open_agenda": [],
             "experiments": {"running": []}}, {})
        self.assertIn("no_live_experiment", [i["kind"] for i in owed["items"]])
        self.assertGreaterEqual(owed["must_do"], 1)

    def test_a_fully_settled_day_allows_an_empty_retro(self):
        owed = br.obligations(
            {"readouts_due": [], "open_agenda": [],
             "experiments": {"running": [{"id": "live"}]}}, {})
        self.assertEqual(owed["must_do"], 0)

    def test_the_brief_states_the_standing_directive(self):
        b = br.build("20260730")
        self.assertIn("better every week", b["standing_directive"])
        self.assertIn("what_you_owe_today", b)


class TestTheRuleIsWrittenDown(unittest.TestCase):
    """No hard gate enforces this (operator's call — it is a working
    agreement, not a security boundary). So the wording carries it, and
    these assert the wording is actually there for an agent to read."""

    def test_every_contract_states_who_edits_the_pipeline(self):
        for f in ("retro/README.md", "exchange/README.md", "CLAUDE.md"):
            text = (ROOT / f).read_text().lower()
            self.assertIn("only agent that edits", text, f)

    def test_the_agent_contracts_say_what_they_may_never_write(self):
        for f in ("retro/README.md", "exchange/README.md"):
            self.assertIn("never write", (ROOT / f).read_text().lower(), f)

    def test_no_doc_promises_enforcement_that_does_not_exist(self):
        """The gate was removed; nothing may still claim it runs. A doc that
        describes a check nobody runs is worse than no doc."""
        for f in ("retro/README.md", "exchange/README.md", "CLAUDE.md"):
            text = (ROOT / f).read_text()
            self.assertNotIn("authorship_gate", text, f)
