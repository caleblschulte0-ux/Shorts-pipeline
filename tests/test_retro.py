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
sys.path.insert(0, str(ROOT / "scripts"))

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
        self.assertEqual(r["counts"],
                         {"accepted": 0, "requires_operator": 0,
                          "refused": 0, "malformed": 0})

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

    def test_no_workflow_applies_a_proposal(self):
        """The safety model is that no automation reads a proposal and
        edits code. Assert it, so a future workflow cannot quietly add it."""
        for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
            body = wf.read_text()
            if "proposals" not in body:
                continue
            self.assertNotIn("apply_proposal", body)
            self.assertIn("review_proposals.py", body,
                          f"{wf.name} touches proposals without triaging them")


if __name__ == "__main__":
    unittest.main(verbosity=2)
