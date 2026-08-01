#!/usr/bin/env python3
"""The BINDING quality law. These tests exist because the pipeline used to
advance a 3.0/10 film on `no reject labels AND personality >= 3`."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import judge_policy as jp  # noqa: E402

OK_JUDGES = {"taste": {"status": "ok", "pass": True},
             "technical": {"status": "ok", "pass": True},
             "factual": {"status": "ok", "pass": True}}


def combined(overall=9.2, personality=4, findings=None, verdicts=None):
    v = dict(OK_JUDGES) if verdicts is None else verdicts
    if "taste" in v:
        v["taste"] = {**v["taste"], "overall_10": overall,
                      "personality": personality}
    return {"overall_10": overall, "personality": personality,
            "findings": findings or [], "verdicts": v}


def main():
    pol = jp.load()

    # 1. a low overall score CANNOT pass on personality alone — the exact
    #    failure this whole module exists to prevent.
    d = jp.decide(combined(overall=3.0, personality=5, findings=[]), pol)
    assert not d["advance"], d
    assert any("below the development floor" in b for b in d["blockers"]), d
    assert d["band"] == "structural_failure"
    print("ok  1. overall 3.0 with personality 5/5 is REFUSED")

    # 2. a clean high score advances and is owner-review eligible
    d = jp.decide(combined(overall=9.2, personality=4), pol)
    assert d["advance"] and d["eligible_for_owner_review"], d
    assert d["band"] == "owner_review"
    print("ok  2. 9.2/10 clean advances and is owner-review eligible")

    # 3. bands are exactly as specified
    for score, want in ((7.4, "structural_failure"), (7.5, "repair_required"),
                        (8.49, "repair_required"), (8.5, "internal_review"),
                        (8.99, "internal_review"), (9.0, "owner_review")):
        assert jp.band(score, pol) == want, (score, jp.band(score, pol))
    assert jp.band(None, pol) == "unscored"
    print("ok  3. band edges 7.5 / 8.5 / 9.0 are exact; None is 'unscored'")

    # 4. a MISSING professional-quality score is missing evidence, not a pass
    d = jp.decide(combined(overall=None, personality=5), pol)
    assert not d["advance"] and any("overall_10" in b for b in d["blockers"]), d
    print("ok  4. no overall_10 => blocked (missing evidence, not consent)")

    # 5. ONE hard objection is never averaged away by other happy judges
    hard = [{"defect_code": "SAMENESS", "severity": "blocker",
             "judge": "taste", "complaint": "every shot looks alike"}]
    d = jp.decide(combined(overall=9.6, personality=5, findings=hard), pol)
    assert not d["advance"], d
    assert "SAMENESS" in d["hard_objections"], d
    print("ok  5. a 9.6/10 film with ONE blocker still cannot advance")

    # 6. a resolved finding stops blocking
    done = [{**hard[0], "resolved": True}]
    assert jp.decide(combined(9.6, 5, done), pol)["advance"]
    print("ok  6. resolved findings no longer block")

    # 7. an auto-reject LABEL blocks even when severity was understated
    soft = [{"defect_code": "CARDS_OVER_BUDGET", "severity": "minor",
             "judge": "variety", "complaint": "46% cards"}]
    d = jp.decide(combined(9.6, 5, soft), pol)
    assert not d["advance"] and "CARDS_OVER_BUDGET" in d["hard_objections"]
    print("ok  7. an auto-reject label is hard regardless of claimed severity")

    # 8. a required judge that FAILED or ABSTAINED fails closed
    for status in ("failed", "abstained"):
        v = {**OK_JUDGES, "factual": {"status": status, "error": "no report"}}
        d = jp.decide(combined(9.5, 5, verdicts=v), pol)
        assert not d["advance"], (status, d)
        assert any("factual" in b for b in d["blockers"]), d
    # ...and a required judge that is simply absent
    d = jp.decide(combined(9.5, 5, verdicts={"taste": {"status": "ok", "pass": True}}), pol)
    assert not d["advance"] and any("technical" in b for b in d["blockers"])
    print("ok  8. missing / failed / abstained required judge FAILS CLOSED")

    # 9. judge DISAGREEMENT is its own blocker, and is preserved
    v = {**OK_JUDGES, "media_context": {"status": "ok", "pass": False}}
    d = jp.decide(combined(9.5, 5, verdicts=v), pol)
    assert not d["advance"], d
    assert d["dissent"] and any("disagree" in b for b in d["blockers"]), d
    judges_in_dissent = {x["judge"] for x in d["dissent"]}
    assert "media_context" in judges_in_dissent and "taste" in judges_in_dissent
    print("ok  9. dissent blocks and every dissenting judge is preserved")

    # 10. too many unresolved MAJOR findings blocks
    majors = [{"defect_code": "WEAK_DEPICTION", "severity": "major",
               "judge": "taste", "complaint": f"beat {i}"} for i in range(2)]
    assert not jp.decide(combined(9.5, 5, majors), pol)["advance"]
    print("ok 10. unresolved major findings over budget block")

    # 11. the score NEVER unlocks publishing on its own
    d = jp.decide(combined(10.0, 5), pol)
    assert d["advance"] and not d["autonomous_publish_allowed"], d
    print("ok 11. a perfect score does not enable autonomous publishing")

    # 12. policy is configurable, and env overrides apply
    os.environ["CURIOSITY_JUDGE_DEVELOPMENT_MIN_OVERALL"] = "5.0"
    try:
        loose = jp.load()
        assert loose["development_min_overall"] == 5.0
        assert jp.decide(combined(6.0, 4), loose)["advance"]
        assert not jp.decide(combined(6.0, 4), pol)["advance"]
    finally:
        del os.environ["CURIOSITY_JUDGE_DEVELOPMENT_MIN_OVERALL"]
    print("ok 12. thresholds are configurable and the default stays strict")

    # 13. personality still has a floor (it just isn't sufficient any more)
    d = jp.decide(combined(9.8, 1), pol)
    assert not d["advance"] and any("personality" in b for b in d["blockers"])
    print("ok 13. personality floor still enforced")

    print("judge policy: 13/13 checks pass")


if __name__ == "__main__":
    main()
