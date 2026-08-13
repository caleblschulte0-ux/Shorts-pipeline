"""The interim rebuild policy: exactly what the operator ruled, and no more.

Operator ruling 2026-08-13, made twice in as many days: "I don't care if the
quality dips. That's fine. We can work on that on the back end. But we should
never not be posting." The explainer channel had posted nothing for fourteen
days at that point, and the ledger shows why: of 23 blocks since 08-11, ZERO
were held by the score floor alone — every hold came from the any-auto-fail
rule, with the craft classes (empty_void, decorative_mascot,
bare_number_card, dead_air) holding videos the judge itself scored 55-78.

The rebuild policy is the smallest change that obeys the ruling:

  * craft auto-fails stop HARD-blocking and the numeric floor decides;
  * junk_imagery still blocks at ANY score — mismatched or misleading
    imagery is a trust defect, and "quality can dip" does not cover
    publishing visuals that misrepresent the data;
  * nothing else moves: the brain grades exactly as before, the measured
    temporal gate stays, publish runs still fail closed, every craft check
    is still recorded for the repair loop and the retro.

These tests hold BOTH policies, the default (which must remain the standard
rule, byte-for-byte in behaviour), and the scoping — rebuild is opted into
by ONE workflow's env, never globally.

    python -m unittest tests.test_rebuild_policy -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# APPEND, never insert: scripts/ has its own test_*.py and putting it first
# shadows the real tests package during discovery.
sys.path.append(str(ROOT / "scripts"))

import showrunner_review as sr  # noqa: E402


def checks(*present):
    return {k: {"present": k in present,
                "evidence": "seen" if k in present else ""}
            for k in sr.AUTOFAIL_CHECKS}


class TestStandardPolicyIsUnchanged(unittest.TestCase):
    """The default must behave exactly as the old one-line rule did."""

    def v(self, score, *fails):
        return sr.decide_verdict(score, checks(*fails), policy="standard")

    def test_any_autofail_blocks_regardless_of_score(self):
        for f in sr.AUTOFAIL_CHECKS:
            self.assertEqual(self.v(95, f), "block", f)

    def test_sub_floor_blocks(self):
        self.assertEqual(self.v(sr.MIN_SCORE - 1), "block")

    def test_clean_at_floor_ships(self):
        self.assertEqual(self.v(sr.MIN_SCORE), "ship")

    def test_the_default_policy_is_standard(self):
        """No env set -> standard/70. Ending the rebuild is deleting two env
        lines, not editing code."""
        self.assertEqual(sr.POLICY, "standard")
        self.assertEqual(sr.MIN_SCORE, 70)


class TestRebuildPolicy(unittest.TestCase):

    def v(self, score, *fails):
        return sr.decide_verdict(score, checks(*fails),
                                 policy="rebuild", min_score=55)

    def test_the_exact_holds_from_the_ledger_now_ship(self):
        """The measured cases the ruling was made against: craft auto-fails
        on videos scoring 55-78."""
        self.assertEqual(self.v(62, "empty_void"), "ship")
        self.assertEqual(self.v(78, "dead_air", "empty_void"), "ship")
        self.assertEqual(self.v(57, "decorative_mascot",
                                "bare_number_card"), "ship")

    def test_junk_imagery_still_blocks_at_any_score(self):
        self.assertEqual(self.v(95, "junk_imagery"), "block")
        self.assertEqual(self.v(95, "junk_imagery", "empty_void"), "block")

    def test_the_floor_still_blocks(self):
        self.assertEqual(self.v(54), "block")
        self.assertEqual(self.v(54, "empty_void"), "block")

    def test_clean_at_floor_ships(self):
        self.assertEqual(self.v(55), "ship")

    def test_fatal_set_is_exactly_junk_imagery(self):
        """Widening FATAL_CHECKS is always allowed (it only ADDS blocks);
        narrowing it below this is not — pin the floor of the floor."""
        self.assertIn("junk_imagery", sr.FATAL_CHECKS)


class TestNothingElseMoved(unittest.TestCase):
    """The ruling touched the code-side floor policy and nothing else."""

    SRC = (ROOT / "scripts" / "showrunner_review.py").read_text()

    def test_the_brain_is_still_never_told_the_threshold(self):
        """The model grades blind; code decides. That is what stops scores
        compressing to a safe ~72, and it survives the rebuild."""
        self.assertIn("The model is NEVER", self.SRC)

    def test_all_five_checks_are_still_asked_and_recorded(self):
        for k in ("junk_imagery", "decorative_mascot", "bare_number_card",
                  "dead_air", "empty_void"):
            self.assertIn(k, sr.AUTOFAIL_CHECKS)

    def test_the_temporal_gate_is_untouched_by_policy(self):
        """temporal_hard_fail takes no policy argument — frozen video blocks
        in code under every policy."""
        import inspect
        sig = inspect.signature(sr.temporal_hard_fail)
        self.assertNotIn("policy", sig.parameters)

    def test_the_ruling_is_documented_where_the_code_is(self):
        self.assertIn("INTERIM OPERATOR RULING (2026-08-13", self.SRC)
        self.assertIn("To END the rebuild", self.SRC)


class TestRebuildIsScopedToExplainerOnly(unittest.TestCase):
    """One channel opted in by env. Trending never asked and never gets it."""

    EXPLAINER = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
    DAILY = (ROOT / ".github" / "workflows" / "daily.yml").read_text()

    def test_explainer_opts_in_with_both_lines(self):
        self.assertIn("SHOWRUNNER_POLICY", self.EXPLAINER)
        self.assertIn("SHOWRUNNER_MIN_SCORE", self.EXPLAINER)

    def test_the_workflow_says_how_to_end_it(self):
        self.assertIn("delete", self.EXPLAINER.lower())

    def test_trending_does_not_inherit_the_rebuild(self):
        self.assertNotIn("SHOWRUNNER_POLICY", self.DAILY)


if __name__ == "__main__":
    unittest.main()
