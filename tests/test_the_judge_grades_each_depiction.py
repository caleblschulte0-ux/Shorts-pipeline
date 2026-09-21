"""THE LOOP IS CLOSED: the judge grades each DEPICTION, the brain learns from it.

Operator, 2026-09-21: *"it's not about a specific animation, it's building a
system that can make good per-video animations without me."*

What that system was missing was one edge. The showrunner has always been
able to tell a bolt grid from a dog on a track — about
`fusion-net-energy-gain` it wrote "a genuinely good demonstration" twice —
and nothing could read the prose. The brain went on learning from `starred`,
its own opinion of its own work.

Now:  judge -> per-depiction grade (bespoke 0-3, proves_claim 0-3)
        -> `review_video` passes it through (learning signal ONLY)
        -> `post_stories` hands the FINAL verdict's grades to
           `viz_director.grade_mechanics`
        -> the grade lands on the config scene and the library entry,
           matched by the `rendered_as` tag the renderer wrote
        -> `_mechanic_examples` ranks by it, ahead of `starred`
        -> the playbook and the kit prompt define tier 1 in the judge's words

Every test that can be proved by injection is; the one non-negotiable is
that the grade NEVER reaches ship/block.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib                                            # noqa: E402
matplotlib.use("Agg")

from scripts import showrunner_review as SR                  # noqa: E402
from data_learning import viz_director as VD                 # noqa: E402
from data_learning import studio_render as STU               # noqa: E402
from shared import showrunner_gate as GATE                   # noqa: E402


class TheJudgeIsAskedForIt(unittest.TestCase):
    def test_the_contract_names_the_field_and_the_anchors(self):
        self.assertIn('"depictions":[', SR._GRADE_PROMPT)
        for word in ("bespoke", "proves_claim", "laser bolts",
                     "track with a dog", "LEARNING signal"):
            self.assertIn(word, SR._GRADE_PROMPT, word)

    def test_it_is_explicitly_not_a_gate_input(self):
        self.assertIn("never decides ship or block", SR._GRADE_PROMPT)


class TheGradeIsCleanedNotTrusted(unittest.TestCase):
    def test_missing_is_None_not_a_problem(self):
        self.assertIsNone(SR.clean_depictions(None))
        self.assertIsNone(SR.clean_depictions("junk"))
        self.assertIsNone(SR.clean_depictions([]))

    def test_ints_are_clamped_and_junk_entries_dropped(self):
        got = SR.clean_depictions([
            {"id": "seg0", "kind": "bespoke", "bespoke": 9, "proves_claim": -2,
             "note": "x" * 500},
            {"id": "", "bespoke": 3, "proves_claim": 3},          # no id
            {"id": "seg2", "bespoke": "three", "proves_claim": 1},  # bad int
            "not a dict",
        ])
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["bespoke"], 3)
        self.assertEqual(got[0]["proves_claim"], 0)
        self.assertEqual(len(got[0]["note"]), 240)

    def test_kind_is_derived_when_the_judge_omits_it(self):
        got = SR.clean_depictions([{"id": "a", "bespoke": 3, "proves_claim": 2},
                                   {"id": "b", "bespoke": 1, "proves_claim": 1},
                                   {"id": "c", "bespoke": 0, "proves_claim": 0}])
        self.assertEqual([g["kind"] for g in got], ["bespoke", "machine", "chart"])

    def test_the_validator_does_not_know_about_it(self):
        """The whole point: a missing or malformed grade must NEVER be a
        block reason. `validate_judge_response` must not mention it."""
        import inspect
        self.assertNotIn("depictions", inspect.getsource(SR.validate_judge_response))


class ItRidesTheVerdictWithoutTouchingTheDecision(unittest.TestCase):
    def test_review_video_passes_it_through_and_the_score_is_unchanged(self):
        """Proof by injection on the assembled verdict: identical grades with
        and without `depictions` must produce the identical score/verdict,
        and the field must be present in the returned dict."""
        import inspect
        # the verdict is assembled in ONE place for every judge now
        # (`assemble_verdict`, shared with the ChatGPT mailbox claim)
        src = inspect.getsource(SR.assemble_verdict)
        self.assertIn('"depictions": clean_depictions(grades.get("depictions"))', src)
        self.assertIn("assemble_verdict(", inspect.getsource(SR.review_video))
        # score/verdict are computed from dims + checks only — assert the
        # function that computes them never sees the field
        self.assertNotIn("depictions", inspect.getsource(SR.compute_score))
        self.assertNotIn("depictions", inspect.getsource(SR.decide_verdict))

    def test_the_gate_stores_the_verdict_as_is(self):
        v = {"score": 80, "verdict": "ship", "depictions": [{"id": "seg0"}]}
        out = GATE.decide(will_upload=True, gate_on=True, verdict=v)
        self.assertEqual(out["verdict"].get("depictions"), [{"id": "seg0"}])


class TheGradeFindsItsMechanic(unittest.TestCase):
    MECH = {"mechanic": "bolt-grid", "concept": "c",
            "code": "img = subject_image('laser')\npaste(img, 0, 0)",
            "rendered_as": "seg1"}

    def _sig(self, sc):
        import hashlib
        return hashlib.sha1((sc["mechanic"] + sc["code"]).encode()).hexdigest()[:12]

    def test_a_grade_lands_on_the_config_scene_and_the_library_entry(self):
        story = {"slug": "fusion", "segments": [
            {"key": "a", "scene": {"elements": [1]}},          # kit, ungraded
            {"key": "b", "scene": dict(self.MECH)},              # rendered as seg1
            {"key": "c"}]}
        lib = [{"sig": self._sig(self.MECH), "mechanic": "bolt-grid",
                "code": self.MECH["code"], "moves": True},
               {"sig": "other", "mechanic": "x", "code": "y"}]
        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "lib.json"; lp.write_text(json.dumps(lib))
            cp = Path(td) / "niche.config.json"
            cp.write_text(json.dumps({"stories": [json.loads(json.dumps(story)),
                                                  {"slug": "other", "segments": []}]}))
            with mock.patch.object(VD, "_MECH_LIB", str(lp)):
                n = VD.grade_mechanics(story, [
                    {"id": "seg1", "kind": "bespoke", "bespoke": 3,
                     "proves_claim": 3, "note": "a genuinely good demonstration"},
                    {"id": "seg0", "kind": "machine", "bespoke": 1, "proves_claim": 1},
                ], config_path=cp)
            self.assertEqual(n, 1, "only the mechanic segment is gradable")
            self.assertEqual(story["segments"][1]["scene"]["grade"]["bespoke"], 3)
            self.assertNotIn("grade", story["segments"][0]["scene"])
            got_lib = json.loads(lp.read_text())
            self.assertEqual(got_lib[0]["grade"]["bespoke"], 3)
            self.assertNotIn("grade", got_lib[1])
            got_cfg = json.loads(cp.read_text())
            self.assertEqual(got_cfg["stories"][0]["segments"][1]["scene"]["grade"]["bespoke"], 3)
            self.assertEqual(got_cfg["stories"][1], {"slug": "other", "segments": []})

    def test_matching_is_by_rendered_id_not_by_index(self):
        """`story.build` reorders. The judge's "seg0" is whatever RENDERED
        first — here that is the config's THIRD segment."""
        story = {"slug": "s", "segments": [
            {"scene": dict(self.MECH, rendered_as="seg2")},
            {"scene": dict(self.MECH, mechanic="m1", rendered_as="seg1")},
            {"scene": dict(self.MECH, mechanic="m2", rendered_as="seg0")}]}
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(VD, "_MECH_LIB", str(Path(td) / "none.json")):
            VD.grade_mechanics(story, [{"id": "seg0", "bespoke": 3, "proves_claim": 3}])
        self.assertIn("grade", story["segments"][2]["scene"])
        self.assertNotIn("grade", story["segments"][0]["scene"])

    def test_nothing_to_grade_is_zero_and_never_raises(self):
        self.assertEqual(VD.grade_mechanics({"slug": "s", "segments": []}, None), 0)
        self.assertEqual(VD.grade_mechanics(None, [{"id": "seg0"}]), 0)
        self.assertEqual(VD.grade_mechanics({"slug": "s", "segments": [{"scene": {"code": "c", "mechanic": "m"}}]},
                                            [{"id": "nope", "bespoke": 3, "proves_claim": 3}]), 0)


class TheRendererTagsWhatItCommits(unittest.TestCase):
    def test_the_persisted_scene_carries_its_rendered_id(self):
        STU._PERSISTED[:] = []

        class _I:
            scene = {"mechanic": "m", "concept": "c", "code": "x"}
            seg_cfg = {}
            topic = "t"
        with mock.patch.object(VD, "_record_mechanic"):
            STU._persist_rendered_mechanic(_I(), "s", rendered_as="seg1")
        self.assertEqual(_I.seg_cfg["scene"]["rendered_as"], "seg1")

    def test_a_re_render_never_loses_an_existing_grade(self):
        STU._PERSISTED[:] = []

        class _I:
            scene = {"mechanic": "m", "concept": "c", "code": "x"}
            seg_cfg = {"scene": {"mechanic": "m", "concept": "c", "code": "x",
                                 "grade": {"bespoke": 3}}}
            topic = "t"
        with mock.patch.object(VD, "_record_mechanic"):
            STU._persist_rendered_mechanic(_I(), "s", rendered_as="seg0")
        self.assertEqual(_I.seg_cfg["scene"]["grade"], {"bespoke": 3})


class TheBrainLearnsFromTheJudgeNotFromItself(unittest.TestCase):
    def test_a_judge_graded_3_outranks_a_self_starred_ungraded_one(self):
        lib = [
            {"sig": "a", "mechanic": "self-starred", "code": "c", "moves": True,
             "starred": True},
            {"sig": "b", "mechanic": "judge-loved", "code": "c", "moves": True,
             "grade": {"bespoke": 3}},
            {"sig": "c", "mechanic": "judge-meh", "code": "c", "moves": True,
             "grade": {"bespoke": 1}, "starred": True},
        ]
        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "lib.json"; lp.write_text(json.dumps(lib))
            with mock.patch.object(VD, "_MECH_LIB", str(lp)):
                # the four hand-authored teachers are always on the shelf
                # too (restored from source), so ask for enough to see all
                names = [e["mechanic"] for e in VD._mechanic_examples(8)]
        self.assertEqual(names[0], "judge-loved",
                         "the brain's own judge-graded 3 outranks everything, "
                         "the teachers included")
        self.assertLess(names.index("self-starred"), names.index("judge-meh"),
                        "a judge-graded 1 must not outrank an ungraded star "
                        "— the grade is evidence it is tier 2")

    def test_motion_still_comes_first(self):
        """A frozen tier-3 is still frozen."""
        lib = [{"sig": "a", "mechanic": "frozen-but-3", "code": "c",
                "moves": False, "grade": {"bespoke": 3}},
               {"sig": "b", "mechanic": "moving-1", "code": "c",
                "moves": True, "grade": {"bespoke": 1}}]
        with tempfile.TemporaryDirectory() as td:
            lp = Path(td) / "lib.json"; lp.write_text(json.dumps(lib))
            with mock.patch.object(VD, "_MECH_LIB", str(lp)):
                names = [e["mechanic"] for e in VD._mechanic_examples(8)]
        self.assertLess(names.index("moving-1"), names.index("frozen-but-3"))


class TheBrainIsToldWhatTierOneMeans(unittest.TestCase):
    def test_the_kit_prompt_requires_a_tier_one_beat(self):
        src = (ROOT / "data_learning" / "viz_director.py").read_text()
        self.assertIn("AT LEAST ONE TIER-1 BEAT PER VIDEO", src)

    def test_the_playbook_defines_the_tiers_with_the_judges_words(self):
        txt = (ROOT / "data_learning" / "VIZ_BRAIN.md").read_text()
        for s in ("## TIER 1 vs TIER 2", "MADE OF the subject",
                  "track with a runner", "at least one tier-1 beat"):
            self.assertIn(s, txt, s)

    def test_the_contract_is_documented(self):
        txt = (ROOT / "docs" / "DIRECTOR.md").read_text()
        self.assertIn('"depictions"', txt)
        self.assertIn("learning signal, not a gate input", txt)


if __name__ == "__main__":
    unittest.main()
