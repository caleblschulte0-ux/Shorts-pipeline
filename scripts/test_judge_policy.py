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

    # 12. policy is configurable — but only in the STRICTER direction for
    #     the safety floors. Raising a floor via env applies; LOWERING one
    #     is bar-removal and is refused with the default kept (doctor
    #     finding 9fe73cb62e3f — the old behavior let env set the
    #     development floor to 5.0 and advance a 6.0/10 film).
    os.environ["CURIOSITY_JUDGE_DEVELOPMENT_MIN_OVERALL"] = "8.8"
    try:
        strict = jp.load()
        assert strict["development_min_overall"] == 8.8
        assert not jp.decide(combined(8.5, 4), strict)["advance"]
        assert jp.decide(combined(8.5, 4), pol)["advance"]
    finally:
        del os.environ["CURIOSITY_JUDGE_DEVELOPMENT_MIN_OVERALL"]
    os.environ["CURIOSITY_JUDGE_DEVELOPMENT_MIN_OVERALL"] = "5.0"
    try:
        floor = jp.load()
        assert floor["development_min_overall"] == \
            jp.DEFAULT_POLICY["development_min_overall"], floor
        assert not jp.decide(combined(6.0, 4), floor)["advance"]
    finally:
        del os.environ["CURIOSITY_JUDGE_DEVELOPMENT_MIN_OVERALL"]
    print("ok 12. floors can be raised via env; lowering one is refused")

    # 13. personality still has a floor (it just isn't sufficient any more)
    d = jp.decide(combined(9.8, 1), pol)
    assert not d["advance"] and any("personality" in b for b in d["blockers"])
    print("ok 13. personality floor still enforced")

    # 14. doctor finding 69a0ad32a52f: required judges UNANIMOUSLY saying
    #     "ok, and I reject this" (status ok, pass=False) used to produce no
    #     blocker at all — missing/failed/abstained were the only checks, and
    #     unanimous agreement (even unanimous rejection) never counts as
    #     dissent. A 9.5/10 overall with no separate hard finding used to
    #     advance despite every required judge rejecting it.
    unanimous_reject = {n: {"status": "ok", "pass": False}
                        for n in OK_JUDGES}
    d = jp.decide(combined(9.5, 5, verdicts=unanimous_reject), pol)
    assert not d["advance"], d
    assert not d["dissent"], d  # unanimous agreement is never dissent
    assert all(any(n in b for b in d["blockers"]) for n in OK_JUDGES), d
    print("ok 14a. unanimous required-judge rejection (pass=False) FAILS CLOSED")

    # ...one reject among passes is caught the same way, independent of the
    #    dissent path (which also fires here, but the per-judge blocker must
    #    name the rejecting judge regardless).
    one_reject = {**OK_JUDGES, "factual": {"status": "ok", "pass": False}}
    d = jp.decide(combined(9.5, 5, verdicts=one_reject), pol)
    assert not d["advance"] and any("factual" in b and "did not pass" in b
                                    for b in d["blockers"]), d
    print("ok 14b. one required-judge reject among passes FAILS CLOSED")

    # ...a required judge that spoke (status ok) but never set `pass` at all,
    #    or set something non-boolean, is treated the same as a reject —
    #    missing evidence is not consent, spoken or not.
    for bad_pass in (None, "true", 1, {}):
        v = {**OK_JUDGES, "technical": {"status": "ok", "pass": bad_pass}}
        d = jp.decide(combined(9.5, 5, verdicts=v), pol)
        assert not d["advance"], (bad_pass, d)
        assert any("technical" in b and "did not pass" in b
                  for b in d["blockers"]), (bad_pass, d)
    print("ok 14c. a missing/non-boolean required pass FAILS CLOSED")

    print("judge policy: 14/14 checks pass")


if __name__ == "__main__":
    main()
