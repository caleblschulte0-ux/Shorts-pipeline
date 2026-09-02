"""decide() must block on a required judge's own reject, not just on absence.

Doctor finding 69a0ad32a52f: the binding gate only checked whether a
required judge had SPOKEN (missing/failed/abstained), never whether it had
PASSED. dissent() surfaces disagreement between judges, but a UNANIMOUS
pass=False from every required judge is not a disagreement — len(set of
pass values) is 1 — so it produced zero dissent and zero blocker. A film
could clear the score floor on overall_10 (owned by the taste judge alone)
while technical and factual both explicitly reject it, and still advance.

    python -m unittest tests.test_judge_policy_decide -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_learning import judge_policy as jp   # noqa: E402


def _combined(overall=9.0, personality=8.0, verdicts=None, findings=None):
    return {"overall_10": overall, "personality": personality,
            "findings": findings or [], "verdicts": verdicts or {}}


class UnanimousRejectCase(unittest.TestCase):
    def setUp(self):
        self.pol = jp.load(None)
        self.required = self.pol["required_judges"]

    def test_unanimous_required_reject_is_blocked(self):
        # A high overall_10 and no dissent (every required judge agrees) used
        # to be enough to advance even though every single one of them
        # explicitly rejected the film.
        verdicts = {n: {"status": "ok", "pass": False} for n in self.required}
        d = jp.decide(_combined(overall=9.0, verdicts=verdicts), self.pol)
        self.assertFalse(d["advance"])
        self.assertTrue(
            any("did not pass" in b for b in d["blockers"]),
            d["blockers"])
        # and it must not be smuggled in only as "dissent" — there is none,
        # every required judge agrees with the others (all False).
        self.assertEqual(jp.dissent(verdicts), [])

    def test_one_required_reject_among_passes_is_blocked(self):
        verdicts = {n: {"status": "ok", "pass": True} for n in self.required}
        verdicts[self.required[0]] = {"status": "ok", "pass": False}
        d = jp.decide(_combined(overall=9.0, verdicts=verdicts), self.pol)
        self.assertFalse(d["advance"])

    def test_malformed_pass_value_is_blocked_not_truthy_coerced(self):
        # A non-boolean pass (a stray string, a None on an "ok" status) must
        # never be treated as consent by accident.
        for bad in ("yes", "true", 1, None, 0):
            verdicts = {n: {"status": "ok", "pass": True}
                       for n in self.required}
            verdicts[self.required[0]] = {"status": "ok", "pass": bad}
            d = jp.decide(_combined(overall=9.0, verdicts=verdicts), self.pol)
            self.assertFalse(d["advance"], f"pass={bad!r} must not advance")

    def test_unanimous_required_pass_still_advances(self):
        # The repair must not turn into a false positive in the other
        # direction — a real unanimous pass still clears the gate.
        verdicts = {n: {"status": "ok", "pass": True} for n in self.required}
        d = jp.decide(_combined(overall=9.0, personality=8.0,
                                verdicts=verdicts), self.pol)
        self.assertTrue(d["advance"], d["blockers"])


if __name__ == "__main__":
    unittest.main()
