"""The premise gate's LLM judge may only speak in exact verdicts.

Doctor finding ec1665fbf9fa (2026-08-15): `premise_ok` blocked only on the
literal verdict "REJECT" and labeled EVERY other parsed response — `{}`, a
misspelled verdict, a non-string, an unrelated object — as "llm-pass". A
judge whose prompt says "default to REJECT when unsure" was having its
garbage recorded as affirmative quality evidence. The rule now: only an
exact normalized PASS approves, only an exact REJECT blocks, and anything
else is UNAVAILABLE evidence — the deterministic floor stands (exactly as
it does when no brain is reachable) and the verdict is never labeled an
LLM pass.

    python -m unittest tests.test_editorial_gate -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import editorial_gate  # noqa: E402
import shared.script_generator  # noqa: E402,F401 — the patch target


# A premise that clears the deterministic floor on its own: a consequential
# number in the hook, a title with tension. Whatever the LLM says (or fails
# to say), the deterministic result is ok=True — so any ok=True verdict
# labeled "llm-pass" can ONLY have come from the brain's answer.
SC = {"title": "Why 90% of Lighthouses Lost Their Keepers",
      "hook": "Only 3 are still staffed."}


def _judge(raw: str) -> dict:
    with mock.patch("shared.script_generator._call_llm", return_value=raw):
        return editorial_gate.premise_ok(SC, use_llm=True)


class TestOnlyExactVerdictsCount(unittest.TestCase):
    def test_exact_pass_is_an_llm_pass(self):
        v = _judge('{"verdict": "PASS", "reason": "genuine reversal"}')
        self.assertTrue(v["ok"])
        self.assertEqual(v["judge"], "llm-pass")

    def test_lowercase_pass_normalizes_to_a_pass(self):
        v = _judge('{"verdict": "pass", "reason": "ok"}')
        self.assertTrue(v["ok"])
        self.assertEqual(v["judge"], "llm-pass")

    def test_exact_reject_blocks(self):
        v = _judge('{"verdict": "REJECT", "reason": "searchable noun phrase"}')
        self.assertFalse(v["ok"])
        self.assertEqual(v["judge"], "llm")
        self.assertTrue(any("searchable noun phrase" in r
                            for r in v["reasons"]))

    def test_lowercase_reject_blocks(self):
        v = _judge('{"verdict": "reject", "reason": "weak"}')
        self.assertFalse(v["ok"])
        self.assertEqual(v["judge"], "llm")


class TestGarbageIsNeverAPass(unittest.TestCase):
    """The regression class from the finding: each of these used to return
    judge='llm-pass'. Now the deterministic result stands, honestly
    labeled, and 'llm-pass' appears nowhere."""

    def _assert_unavailable(self, v: dict):
        # The deterministic floor passed, so a floor-preserving outcome is
        # ok=True — but NEVER on the brain's say-so.
        self.assertTrue(v["ok"], v)
        self.assertNotEqual(v["judge"], "llm-pass")
        self.assertIn("deterministic", v["judge"])

    def test_empty_object_is_not_a_pass(self):
        self._assert_unavailable(_judge("{}"))

    def test_misspelled_verdict_is_not_a_pass(self):
        # "REJECTED" is not "REJECT": an inexact token is no evidence in
        # EITHER direction — the deterministic floor governs.
        self._assert_unavailable(_judge('{"verdict": "REJECTED"}'))
        self._assert_unavailable(_judge('{"verdict": "APPROVE"}'))

    def test_non_string_verdict_is_not_a_pass(self):
        self._assert_unavailable(_judge('{"verdict": 1}'))
        self._assert_unavailable(_judge('{"verdict": null}'))
        self._assert_unavailable(_judge('{"verdict": ["PASS"]}'))

    def test_unrelated_object_is_not_a_pass(self):
        self._assert_unavailable(_judge('{"score": 9, "notes": "great"}'))

    def test_malformed_json_is_not_a_pass(self):
        # Unparseable braces raise inside the try, landing on the existing
        # llm-unavailable path — deterministic, never llm-pass.
        self._assert_unavailable(_judge('{"verdict": PASS oops'))

    def test_no_json_at_all_is_not_a_pass(self):
        self._assert_unavailable(_judge("I think it is fine."))

    def test_a_failing_deterministic_floor_still_fails(self):
        """Unavailable evidence must never RESCUE a premise the floor
        already refused — the floor short-circuits before the brain."""
        weak = {"title": "Tectonic Plates", "hook": "They move around."}
        with mock.patch("shared.script_generator._call_llm",
                        return_value="{}") as llm:
            v = editorial_gate.premise_ok(weak, use_llm=True)
            llm.assert_not_called()
        self.assertFalse(v["ok"])


# ---------------------------------------------------------------------------
# Doctor finding 8d1b5d1e1f69: the gate proved facts but never checked that
# every segment actually advances the SAME headline claim.
# ---------------------------------------------------------------------------
COHERENT_SC = {
    "title": "World Renewable Power Was Still Only 19.7% After Two Decades",
    "hook": "You'd think green energy took off years ago — two decades in, "
            "it had barely moved.",
    "segments": [
        {"topic": "Renewable energy investment",
         "say": "Investment in renewables rose steadily."},
        {"topic": "Renewable electricity output",
         "say": "World renewable electricity was 19.3 percent in 1990."},
    ],
}


def _real_story(slug: str) -> dict:
    import json as _json
    cfg = _json.loads(
        (editorial_gate.REPO / "data_learning" / "niche.config.json")
        .read_text())
    for s in cfg.get("stories", []):
        if s.get("slug") == slug:
            return s
    raise AssertionError(f"fixture story {slug!r} not found in niche.config.json")


class TestBeatsSupportOneThesis(unittest.TestCase):
    def test_every_segment_bridges_needs_no_brain(self):
        with mock.patch("shared.script_generator._call_llm") as llm:
            v = editorial_gate.beats_support_one_thesis(
                COHERENT_SC, use_llm=True)
            llm.assert_not_called()
        self.assertTrue(v["ok"])
        self.assertEqual(v["judge"], "deterministic")

    def test_too_few_segments_or_no_subject_is_unjudged(self):
        v = editorial_gate.beats_support_one_thesis(
            {"title": "", "hook": "", "segments": [{"topic": "a"}]})
        self.assertTrue(v["ok"])

    # The three real anthologies-wearing-one-headline the finding named.
    # Regression fixtures against the live queue, not a synthetic story.
    def test_renewable_power_story_flags_the_unrelated_segments(self):
        sc = _real_story(
            "world-renewable-power-was-still-only-19-7-after-two-decades")
        v = editorial_gate.beats_support_one_thesis(sc, use_llm=False)
        self.assertFalse(v["ok"])
        self.assertTrue(any("Agricultural irrigated land" in r
                        for r in v["reasons"]))
        self.assertTrue(any("Fixed broadband subscriptions" in r
                        for r in v["reasons"]))
        # The one segment actually about renewable power is not flagged.
        self.assertFalse(any("Renewable electricity output" in r
                         for r in v["reasons"]))

    def test_rail_story_flags_the_unrelated_segments(self):
        sc = _real_story("the-us-still-has-148-553-km-of-rail-more-than-china")
        v = editorial_gate.beats_support_one_thesis(sc, use_llm=False)
        self.assertFalse(v["ok"])
        self.assertTrue(any("Mobile cellular subscriptions" in r
                        for r in v["reasons"]))
        self.assertTrue(any("Methane" in r for r in v["reasons"]))

    def test_less_land_story_flags_the_unrelated_segments(self):
        sc = _real_story("the-world-has-less-land-than-it-did-in-2013")
        v = editorial_gate.beats_support_one_thesis(sc, use_llm=False)
        self.assertFalse(v["ok"])
        self.assertTrue(any("External health expenditure" in r
                        for r in v["reasons"]))
        self.assertTrue(any("Crop production index" in r
                        for r in v["reasons"]))

    def test_llm_can_rescue_an_ambiguous_segment(self):
        """A segment with no literal keyword overlap is not an automatic
        reject — the semantic judge gets to say it genuinely bridges."""
        sc = {"title": "Grocery Bills Kept Winning",
              "hook": "The math never worked in your favor.",
              "segments": [
                  {"topic": "price jump since 2020", "say": "prices rose"},
                  {"topic": "share of income spent on food", "say": "..."},
              ]}
        raw = '{"bridges": {"0": true, "1": true}}'
        with mock.patch("shared.script_generator._call_llm",
                        return_value=raw):
            v = editorial_gate.beats_support_one_thesis(sc, use_llm=True)
        self.assertTrue(v["ok"])
        self.assertEqual(v["judge"], "llm")

    def test_llm_rejecting_a_segment_blocks_it(self):
        sc = {"title": "Grocery Bills Kept Winning", "hook": "",
              "segments": [
                  {"topic": "price jump since 2020", "say": "x"},
                  {"topic": "solar panel output", "say": "y"},
              ]}
        raw = '{"bridges": {"0": true, "1": false}}'
        with mock.patch("shared.script_generator._call_llm",
                        return_value=raw):
            v = editorial_gate.beats_support_one_thesis(sc, use_llm=True)
        self.assertFalse(v["ok"])
        self.assertTrue(any("solar panel output" in r for r in v["reasons"]))
        self.assertFalse(any("price jump" in r for r in v["reasons"]))

    def test_garbage_llm_answer_is_never_a_rescue(self):
        """Same class of mistake as ec1665fbf9fa: only an exact per-segment
        boolean counts as evidence. Anything else stays unproven == held."""
        sc = {"title": "Grocery Bills Kept Winning", "hook": "",
              "segments": [
                  {"topic": "solar panel output", "say": "y"},
                  {"topic": "another unrelated topic", "say": "z"},
              ]}
        for raw in ('{}', '{"bridges": "yes"}', '{"bridges": {"0": "true"}}',
                    'not even json'):
            with mock.patch("shared.script_generator._call_llm",
                            return_value=raw):
                v = editorial_gate.beats_support_one_thesis(sc, use_llm=True)
            self.assertFalse(v["ok"], raw)
            self.assertNotEqual(v["judge"], "llm-pass")

    def test_unreachable_brain_fails_closed(self):
        sc = {"title": "Grocery Bills Kept Winning", "hook": "",
              "segments": [
                  {"topic": "solar panel output", "say": "y"},
                  {"topic": "another unrelated topic", "say": "z"},
              ]}
        with mock.patch("shared.script_generator._call_llm",
                        side_effect=RuntimeError("no brain")):
            v = editorial_gate.beats_support_one_thesis(sc, use_llm=True)
        self.assertFalse(v["ok"])
        self.assertIn("deterministic", v["judge"])


class TestPreRenderVerdictSkipsThesisWhenAlreadyHeld(unittest.TestCase):
    def test_no_extra_llm_call_when_data_already_fails(self):
        """The thesis judge is a second LLM call; it must never be spent on
        a story pre_render_verdict is holding anyway on data/premise/beats
        grounds (post_stories.py's own rate-limit-budget comment)."""
        sc = {"title": "Grocery Bills Kept Winning", "hook": "",
              "segments": [
                  {"topic": "solar panel output", "say": "y",
                   "key": "missing_dataset_file"},
              ]}
        with mock.patch("shared.script_generator._call_llm") as llm:
            v = editorial_gate.pre_render_verdict(sc, use_llm=True)
            llm.assert_not_called()
        self.assertFalse(v["ok"])
        self.assertFalse(v["data_ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
