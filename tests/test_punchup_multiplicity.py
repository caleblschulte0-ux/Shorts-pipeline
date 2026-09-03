"""The punch-up guard must count claims, not just spot them.

Doctor finding ddfcb2ed4837 (2026-08-13): `numeric_claims` returned a set,
so deleting one of two sentences that carry the SAME number left the guard
satisfied — one copy still matched the membership test. The guard's own
docstring says every number in the original must still be present; a
repeated stat is a repeated beat, and multiplicity is part of the claim.
`numeric_claims` now returns a Counter and `check()` compares counts in
both directions, with the occurrence delta named in the report.

    python -m unittest tests.test_punchup_multiplicity -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import punchup_guard  # noqa: E402


def _pkg(script: str) -> dict:
    return {"script": script, "shots": []}


# The finding's own reproduction: same number, same year, two sentences.
TWICE = ("SpaceX hit 40% of global launches in 2025 and kept climbing. "
         "Rivals said 40% was impossible — SpaceX proved it in 2025.")
ONCE = ("SpaceX hit 40% of global launches in 2025 and rivals said it was "
        "impossible until SpaceX proved them wrong for good that season.")


class TestMultiplicityIsPreserved(unittest.TestCase):
    def test_numeric_claims_counts_occurrences(self):
        c = punchup_guard.numeric_claims(TWICE)
        self.assertEqual(c["40%"], 2)
        self.assertEqual(c["2025"], 2)

    def test_dropping_one_of_two_copies_is_rejected(self):
        """The exact bug: this pair passed check() when claims were a set."""
        ok, problems = punchup_guard.check(_pkg(TWICE), _pkg(ONCE))
        self.assertFalse(ok, problems)
        blob = " ".join(problems)
        self.assertIn("dropped numeric claim", blob)
        # the report names the token AND the occurrence delta
        self.assertIn("40% (x2 -> x1)", blob)
        self.assertIn("2025 (x2 -> x1)", blob)

    def test_duplicating_a_claim_is_an_invented_occurrence(self):
        """The other direction: a rewrite repeating a number the original
        stated once is manufacturing emphasis on a claim count that never
        existed — counted, reported with its delta, rejected."""
        ok, problems = punchup_guard.check(_pkg(ONCE), _pkg(TWICE))
        self.assertFalse(ok)
        blob = " ".join(problems)
        self.assertIn("INVENTED numeric claim", blob)
        self.assertIn("40% (x1 -> x2)", blob)

    def test_equal_counts_still_pass(self):
        """Rewording around claims kept at identical multiplicity is the
        legitimate punch-up move and must stay allowed."""
        rewrite = ("SpaceX seized 40% of global launches in 2025 — and kept "
                   "climbing. Rivals swore 40% could never happen; SpaceX "
                   "made 2025 the year it did.")
        ok, problems = punchup_guard.check(_pkg(TWICE), _pkg(rewrite))
        self.assertTrue(ok, problems)

    def test_a_fully_dropped_claim_reads_as_before(self):
        """A token that vanished entirely keeps the old plain-token message
        — no confusing (x1 -> x0) noise on the common case."""
        ok, problems = punchup_guard.check(
            _pkg("It cost $3 billion and took 14 years of the program."),
            _pkg("It took 14 years of the program, start to finish, and a "
                 "fortune besides."))
        self.assertFalse(ok)
        blob = " ".join(problems)
        self.assertIn("$3b", blob)      # _MONEY's own normalization, unchanged
        self.assertNotIn("x0", blob)

    def test_counter_keeps_set_like_reads_for_existing_callers(self):
        """`in` and iteration were the public surface of the old set —
        both must survive the Counter (tests/test_exchange.py relies on
        them)."""
        c = punchup_guard.numeric_claims(
            "It cost $1.2 million in 2024, up 15% from 900 units.")
        self.assertIn("2024", c)
        self.assertIn("15%", c)
        self.assertTrue(any("1.2" in tok for tok in c))


if __name__ == "__main__":
    unittest.main(verbosity=2)
