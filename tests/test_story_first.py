"""STORY FIRST — the idea brief, the blind scorecard, the sidecar.

Operator, 2026-11-17: "our scripts suck ... ChatGPT made some thing about
how we should improve our scripts, and it's in the GitHub, so go find that
and do it." That is data_learning/STORY_FIRST_SCRIPT_PLAYBOOK.md; these
tests hold its §13 as built for the illustrated explainer.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shared import story_brief as sb  # noqa: E402
from scripts import editorial_gate as eg  # noqa: E402


def _pitch(**over):
    d = {"belief": "condors are gone", "surprise": "they came back",
         "stakes": "lead still kills them", "visual_proof": "an aviary opening",
         "promise": "can they last?", "payoff": "only if the lead goes",
         "hooks": [{"angle": a, "line": f"line {a}"} for a in sb.ANGLES],
         "pick": 2, "weak": False}
    d.update(over)
    return json.dumps(d)


def _card(**scores):
    base = {k: v for k, v in sb.CRITERIA.items()}
    base.update(scores)
    return json.dumps({"scores": base, "fatal": [], "weakest_note": "x"})


STORY = {"slug": "s", "title": "Condors Escaped An Extinction Trap",
         "hook": "The condor came back, and lead is still killing it.",
         "closing": "The rescue worked; the lead decides if it lasts.",
         "segments": [
             {"topic": "condor low", "say": "They fell to 27 birds.",
              "illustrated_scene": 'def draw():\n    """HERO: a condor\n'
                                   '    SUBSTANCE: condors\n    CAUSE: Data '
                                   'launches condors\n    """\n'},
             {"topic": "condor rebound", "say": "Now there are 500."},
             {"topic": "lead deaths", "say": "Lead kills half of them."}]}


class TheIdeaBriefComesFirst(unittest.TestCase):
    def test_a_brief_carries_every_field_and_the_picked_hook(self):
        b = sb.parse_pitch(_pitch())
        self.assertEqual(b["hook"], "line scale")
        self.assertFalse(b["weak"])
        self.assertEqual(len(b["hooks"]), 5)

    def test_garbage_is_no_brief_never_a_pass(self):
        for raw in ("", "{}", _pitch(weak="false"), _pitch(pick=9),
                    _pitch(stakes=""), _pitch(hooks=[{"line": "same"}] * 5)):
            self.assertIsNone(sb.parse_pitch(raw), raw[:60])

    def test_a_weak_pitch_is_refused_before_any_words_are_written(self):
        from scripts import story_forge as sf
        dss = [{"key": "k", "title": "Thing", "unit": "", "insight_type": "rank",
                "geography": "world", "points": [{"label": "a", "value": 1}]}]
        with mock.patch.object(sb, "pitch", return_value=sb.parse_pitch(
                _pitch(weak=True, why_weak="three statistics"))), \
                mock.patch.object(sf, "_brain_words") as words:
            w, by = sf._words_that_clear_the_bar(dss)
        words.assert_not_called()
        self.assertIsNone(w)
        self.assertEqual(by, "weak-pitch")

    def test_the_writer_is_handed_the_brief(self):
        b = sb.parse_pitch(_pitch())
        text = sb.brief_for_writer(b)
        for k in ("condors are gone", "an aviary opening", "line scale"):
            self.assertIn(k, text)


class TheScorecardIsBlindAndDecidesByTheRegistry(unittest.TestCase):
    def test_the_bands_live_in_the_registry(self):
        reg = json.loads((REPO / "config/channel_registry.json").read_text())
        g = reg["channels"]["explainer"]["formats"]["data_story"]["story_gate"]
        self.assertEqual(sb.gate_policy()["pass_at"], g["pass_at"])
        self.assertEqual(sb.gate_policy()["rewrite_at"], g["rewrite_at"])
        self.assertLess(g["rewrite_at"], g["pass_at"])
        # the fallback for an old snapshot is the registry's, not a second policy
        self.assertEqual(sb.IF_UNSET, {"pass_at": g["pass_at"],
                                       "rewrite_at": g["rewrite_at"]})

    def test_the_bands_are_the_calibrations(self):
        cal = json.loads((REPO / "data_learning/story_gate_calibration.json")
                         .read_text())
        pol = sb.gate_policy()
        # no strong story in the calibration set would have been held
        self.assertLessEqual(pol["pass_at"], min(cal["strong"]))

    def test_the_weights_are_the_playbooks_hundred(self):
        self.assertEqual(sum(sb.CRITERIA.values()), 100)

    def test_bands(self):
        pol = {"pass_at": 85, "rewrite_at": 70}
        full = sb.parse_card(_card())
        self.assertEqual(sb.decide(full, pol)["action"], "ship")
        mid = sb.parse_card(_card(arc=5, payoff=5))          # 80
        d = sb.decide(mid, pol)
        self.assertEqual(d["action"], "rewrite")
        self.assertIn("weakest: arc", d["reason"])
        low = sb.parse_card(_card(arc=0, hook=5, payoff=0))  # 55
        self.assertEqual(sb.decide(low, pol)["action"], "reconceive")

    def test_a_fatal_flag_holds_whatever_the_number(self):
        raw = json.loads(_card())
        raw["fatal"] = ["invented_fact"]
        d = sb.decide(sb.parse_card(json.dumps(raw)), {"pass_at": 85,
                                                       "rewrite_at": 70})
        self.assertEqual(d["action"], "hold")

    def test_an_unusable_card_is_no_card(self):
        for raw in ("", "{}", _card(hook=21), _card(hook="20"),
                    _card(hook=True), json.dumps({"scores": {}, "fatal": []})):
            self.assertIsNone(sb.parse_card(raw), raw[:80])
        self.assertEqual(sb.decide(None)["action"], "unscored")

    def test_the_judge_sees_the_script_and_pictures_never_a_self_score(self):
        p = sb.score_prompt(dict(STORY, scorecard={"total": 99},
                                 brief={"payoff": "SECRET"}))
        self.assertIn("They fell to 27 birds.", p)
        self.assertIn("Data launches condors", p)
        self.assertNotIn("99", p)
        self.assertNotIn("SECRET", p)

    def test_a_card_is_reused_until_the_words_change(self):
        sc = json.loads(json.dumps(STORY))
        calls = []

        def llm(s, u):
            calls.append(u)
            return _card()
        with mock.patch.object(sb, "_persist_card"), \
                mock.patch.object(sb, "write_sidecar"):
            sb.gate(sc, llm=llm, log=lambda m: None)
            sb.gate(sc, llm=llm, log=lambda m: None)
            self.assertEqual(len(calls), 1)
            sc["hook"] = "A different hook about condors."
            sb.gate(sc, llm=llm, log=lambda m: None)
        self.assertEqual(len(calls), 2)

    def test_a_held_story_goes_to_the_rewrite_mailbox(self):
        from shared import rewrite_mailbox as rw
        reasons = sb.hold_reasons({"action": "rewrite",
                                   "reason": "scorecard 74/100 — weakest: arc"})
        self.assertTrue(all(r.startswith(rw._WORD_PREFIX) for r in reasons))
        with mock.patch.object(rw, "file_request", return_value="rid") as fr:
            ids = rw.file_for_run(
                [{"slug": "s", "ok": False, "error": "story_hold",
                  "reasons": reasons}], {"s": STORY})
        self.assertEqual(ids, ["rid"])
        self.assertIn("weakest: arc", fr.call_args[0][1][0])

    def test_a_story_hold_is_a_hold_not_a_fault(self):
        from scripts import post_stories as ps
        self.assertIn("story_hold", ps.HELD_REASONS)

    def test_the_posting_run_calls_the_gate_before_the_render(self):
        src = (REPO / "scripts/post_stories.py").read_text()
        i_gate = src.index("_sb.gate(sc")
        self.assertLess(src.index("_eg.pre_render_verdict(sc)"), i_gate)
        self.assertLess(i_gate, src.index("studio_render.render(slug"))


class EarsEyesEvidence(unittest.TestCase):
    def test_one_row_per_window(self):
        rows = sb.sidecar(STORY)
        self.assertEqual([r["window"] for r in rows],
                         ["hook", "beat 0", "beat 1", "beat 2", "closing"])
        self.assertEqual(rows[1]["ears"], "They fell to 27 birds.")
        self.assertIn("Data launches condors", rows[1]["eyes"])

    def test_evidence_is_the_beats_own_dataset(self):
        cfg = json.loads((REPO / "data_learning/niche.config.json").read_text())
        sc = next(s for s in cfg["stories"]
                  if s["slug"] == "california-condor-comeback")
        self.assertIn("Fish and Wildlife", sb.sidecar(sc)[1]["evidence"])


class TheQuestionIsOptionalForTheIllustratedExplainer(unittest.TestCase):
    def test_an_empty_question_means_no_cta(self):
        from data_learning import story
        cfg = json.loads((REPO / "data_learning/niche.config.json").read_text())
        sc = dict(next(s for s in cfg["stories"]
                       if s["slug"] == "california-condor-comeback"))
        sc["question"] = ""
        self.assertEqual(story.question_of(sc), "")
        sc.pop("question")
        self.assertTrue(story.question_of(sc))      # the old default stays
        src = (REPO / "data_learning/story.py").read_text()
        self.assertIn("question=question_of(story_cfg)", src)

    def test_the_writers_no_longer_force_one(self):
        for f in ("scripts/story_forge.py", "scripts/author_stories.py"):
            src = (REPO / f).read_text()
            self.assertNotIn('"Which number surprised you most?"', src, f)


class AConcretePremiseReplacedTheMandatoryDigit(unittest.TestCase):
    def test_a_premise_that_names_its_subject_needs_no_number(self):
        sc = {"title": "Cow Burps Are Cooking The Planet",
              "hook": "Cow burps are cooking the planet.",
              "segments": [{"topic": "cow methane"}, {"topic": "cow herds"}]}
        self.assertTrue(eg.premise_ok(sc, use_llm=False)["ok"])

    def test_a_vague_premise_still_fails(self):
        sc = {"title": "Something Big Changed Quietly Here Today",
              "hook": "Nobody saw this coming.",
              "segments": [{"topic": "cow methane"}, {"topic": "cow herds"}]}
        v = eg.premise_ok(sc, use_llm=False)
        self.assertFalse(v["ok"])
        self.assertIn("not concrete", v["reasons"][0])


class SemanticContinuity(unittest.TestCase):
    SC = {"title": "The Condor Escaped An Extinction Trap",
          "hook": "Condors came back from 27 birds.",
          "segments": [{"topic": "condor low", "say": "a"},
                       {"topic": "condor rebound", "say": "b"},
                       {"topic": "condor diet", "say": "c"}]}

    def test_with_a_brain_every_beat_is_judged_keyword_or_not(self):
        with mock.patch("shared.script_generator._call_llm", return_value=json.dumps(
                {"bridges": {"0": True, "1": True, "2": False},
                 "why": {"2": "and then"}})) as llm:
            v = eg.beats_support_one_thesis(self.SC, use_llm=True)
        llm.assert_called_once()
        self.assertFalse(v["ok"])
        self.assertIn("seg2", v["reasons"][0])

    def test_no_brain_is_the_keyword_floor_never_a_pass(self):
        sc = json.loads(json.dumps(self.SC))
        sc["segments"][2]["topic"] = "broadband subscriptions"
        with mock.patch("shared.script_generator._call_llm",
                        side_effect=RuntimeError("down")):
            v = eg.beats_support_one_thesis(sc, use_llm=True)
        self.assertFalse(v["ok"])
        self.assertIn("broadband", v["reasons"][0])

    def test_an_unusable_answer_is_the_keyword_floor(self):
        with mock.patch("shared.script_generator._call_llm",
                        return_value='{"bridges": "yes"}'):
            v = eg.beats_support_one_thesis(self.SC, use_llm=True)
        self.assertTrue(v["ok"])        # every topic shares "condor"
        self.assertTrue(v["judge"].startswith("deterministic"))


if __name__ == "__main__":
    unittest.main()
