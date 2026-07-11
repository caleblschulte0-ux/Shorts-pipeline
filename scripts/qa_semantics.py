#!/usr/bin/env python3
"""Semantic-progression QA (CURIOSITY_BRAIN §7.5 v8) — the gate above
the motion and escalation gates.

The defect this catches: the scene technically MOVES while the audience
watches one unchanged visual idea for 20-40 seconds. Counters climbing,
trails growing, continuous travel, ambient drift, and value updates all
pass the older gates — they are movement, not meaning.

The engine logs `semantic` rows only when a NEW VISUAL IDEA lands (new
scale band, environment, metaphor, camera dimension, comparison method,
object role, irreversible state). Discovery / breach / cold_open /
evidence / echo rows are semantic by nature. This gate validates:

  1. THE 12-15s LAW: no span of the video longer than SEM_GAP_MAX
     without a semantic-class moment.
  2. Long beats DEVELOP: any beat longer than LONG_BEAT must land at
     least one semantic-class moment mid-beat (after its arrival), not
     just at its border — long narration means multiple visual phases.
  3. NO PLATEAU: two consecutive beats may not present the identical
     grammar set (same metaphor + comparison rows, nothing else new) —
     bars after bars is an emotional downgrade, not a beat.
  4. DOMINANT SUBJECT: every beat declares at least one focus row (who
     owns the frame).

    python3 scripts/qa_semantics.py output/curiosity_<slug>.ledger.json

Exits 1 on any violation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SEM_GAP_MAX = 15.0
LONG_BEAT = 15.0
MID_BEAT_AFTER = 5.0       # a semantic row this far in counts as mid-beat

SEMANTIC_KINDS = {"semantic", "discovery", "breach", "cold_open",
                  "evidence", "echo"}
GRAMMAR_DIMS = {"metaphor", "comparison"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger", type=Path)
    args = ap.parse_args()

    d = json.loads(args.ledger.read_text())
    windows, rows = d["windows"], d["rows"]
    total = windows[-1][1]
    beats = windows[1:-1]
    fails: list[str] = []

    # 1. the 12-15s law, video-wide. A breach covers its whole splice:
    # the viewer is inside the premium transformation for all of it.
    marks = sorted((r["t"], float(r.get("rt", 0.0))
                    + (float(r.get("splice", 0.0))
                       if r["kind"] == "breach" else 0.0)) for r in rows
                   if r["kind"] in SEMANTIC_KINDS)
    cur, gap, at = 0.0, 0.0, 0.0
    for t, rt in marks:
        if t - cur > gap:
            gap, at = t - cur, cur
        cur = max(cur, t + rt)
    if total - cur > gap:
        gap, at = total - cur, cur
    print(f"semantic moments: {len(marks)}  max-gap {gap:.1f}s @ {at:.1f}s")
    if gap > SEM_GAP_MAX:
        fails.append(f"{gap:.1f}s (from {at:.1f}s) with zero semantic "
                     f"progression (law: <= {SEM_GAP_MAX}s — the screen "
                     "changed, the viewer's understanding didn't)")

    # 2 + 3 + 4, per beat
    prev_grammar = None
    for i, (t0, t1) in enumerate(beats):
        rs = [r for r in rows if r.get("beat") == i]
        sem = [r for r in rs if r["kind"] in SEMANTIC_KINDS]
        mid = [r for r in sem if r["t"] >= t0 + MID_BEAT_AFTER]
        if (t1 - t0) > LONG_BEAT and not mid:
            fails.append(f"beat {i}: {t1 - t0:.0f}s long but every "
                         "semantic moment is at its border — long beats "
                         "must develop through multiple visual phases")
        grammar = {(r.get("dim"), r.get("what")) for r in rs
                   if r["kind"] == "semantic"
                   and r.get("dim") in GRAMMAR_DIMS}
        extra = [r for r in sem
                 if not (r["kind"] == "semantic"
                         and r.get("dim") in GRAMMAR_DIMS)]
        if (prev_grammar is not None and grammar
                and grammar == prev_grammar and not extra):
            fails.append(f"beat {i}: identical visual grammar to beat "
                         f"{i - 1} with nothing else new — a plateau, "
                         "not a beat")
        prev_grammar = grammar
        n_focus = sum(1 for r in rs if r["kind"] == "focus")
        if n_focus == 0:
            fails.append(f"beat {i}: no dominant subject declared "
                         "(nothing ever owned the frame)")
        print(f"beat {i}: {len(sem):2d} semantic  {len(mid):2d} mid-beat  "
              f"{n_focus} focus  "
              f"grammar={sorted(w for _, w in grammar)}")

    if fails:
        print(f"\nFAIL — {len(fails)} semantic-progression violation(s):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nOK: the viewer's understanding never sits still.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
