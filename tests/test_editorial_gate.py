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


if __name__ == "__main__":
    unittest.main(verbosity=2)
