#!/usr/bin/env python3
"""ONE verdict system, and a breaker for when the judge itself is the fault.

Two defects this locks down, both found by auditing five failed production runs:

1. SPLIT BRAIN. produce() computed the legacy evaluate() status, ATTACHED the
   binding judge-policy decision as data, and returned the legacy one. The
   repairer acted on the new decision while the stopping condition and the batch
   layer read the old one.

2. NO JUDGE-FAULT DETECTION. The hook gate graded `narration.split(".")[0]` and
   returned an identical verdict and score for four consecutive ~2-hour renders,
   including one whose opening had been rewritten to clear it. Nothing noticed
   that a CHANGED film was producing an UNCHANGED complaint.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

import produce  # noqa: E402


def main():
    # --- 1. the policy may VETO a legacy pass -----------------------------
    r = {"status": "pass", "reasons": [],
         "judging": {"advance": False, "blockers": ["overall_10 4.1 < 7.0"]}}
    produce._reconcile_verdict("x", r)
    assert r["status"] == "quarantine", r
    assert r["legacy_status"] == "pass"
    assert any("4.1" in x for x in r["reasons"]), r["reasons"]
    print("ok  1. a legacy PASS is quarantined when the policy withholds "
          "advance (the blocker is carried into the reasons)")

    # --- 2. the policy may NOT override a legacy block --------------------
    # evaluate() holds fail-closed conditions the policy does not model: a dead
    # render, a missing narration track, an unresolved licence. A quality score
    # must never publish a film that is broken.
    r = {"status": "quarantine", "reasons": ["render failed (fail-closed)"],
         "judging": {"advance": True, "blockers": []}}
    produce._reconcile_verdict("x", r)
    assert r["status"] == "quarantine", r
    print("ok  2. a policy advance does NOT override a fail-closed block")

    # --- 3. agreement is a no-op -----------------------------------------
    r = {"status": "pass", "reasons": [], "judging": {"advance": True}}
    produce._reconcile_verdict("x", r)
    assert r["status"] == "pass"
    print("ok  3. when both agree the verdict is unchanged")

    # --- 4. no judging record -> legacy stands (never invent a verdict) ---
    r = {"status": "pass", "reasons": []}
    produce._reconcile_verdict("x", r)
    assert r["status"] == "pass" and "legacy_status" not in r
    print("ok  4. with no judging record the legacy verdict stands untouched")

    # --- 5. THE BREAKER: changed film + identical complaint = judge fault --
    same = [{"defect_code": "HOOK_WEAK", "target": "beat 0"}]
    a = produce._round_signature({"judging": {"findings": same, "overall_10": 5}})
    b = produce._round_signature({"judging": {"findings": same, "overall_10": 5}})
    assert a == b
    assert produce._judge_suspect(a, b, "aaaa1111", "bbbb2222") is True
    print("ok  5. a CHANGED render returning an identical complaint and score "
          "trips the breaker")

    # --- 6. it must not fire on the honest cases -------------------------
    assert produce._judge_suspect(a, b, "aaaa1111", "aaaa1111") is False, \
        "an unchanged render repeating itself is the film's fault, not the judge's"
    c = produce._round_signature({"judging": {"findings": same, "overall_10": 6}})
    assert produce._judge_suspect(a, c, "aaaa1111", "bbbb2222") is False, \
        "a moving score means the judge is reading the change"
    assert produce._judge_suspect(None, b, "aaaa1111", "bbbb2222") is False, \
        "the first round has nothing to compare against"
    assert produce._judge_suspect(a, b, None, "bbbb2222") is False, \
        "an unknown hash must never be treated as a changed one"
    print("ok  6. it stays silent on an unchanged render, a moving score, the "
          "first round, and an unknown hash")

    print("verdict authority + breaker: 6/6 checks pass")


if __name__ == "__main__":
    main()
