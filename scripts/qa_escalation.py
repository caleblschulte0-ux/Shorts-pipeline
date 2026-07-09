#!/usr/bin/env python3
"""Escalation QA — the rule gate over the engine's event ledger (§7.5 v4).

The engine KNOWS whether escalation happened: it logged every travel,
reveal, event, payoff, reaction and discovery while rendering. This gate
validates the escalation laws against that ledger. Design QA runs on
rules, never on pixel inference — a camera pan changes every pixel while
nothing HAPPENS. (The pixel motion gate, qa_motion, stays: it catches
render bugs; this catches design bugs.)

    python3 scripts/qa_escalation.py output/curiosity_<slug>.ledger.json

Rules (doctrine targets in brackets — CURIOSITY_BRAIN §7.5):
  1. Inside every beat, no gap longer than 9.0 s without a visual
     happening [authoring target ~6 s]. A happening covers start+run_time.
  2. Every beat lands at least one PAYOFF (a punch bundle).
  3. Surprise cadence: no span longer than 60 s without a discovery-class
     row (discovery / cold_open) [authoring target: every 20–30 s].
  4. At least 2 authored discoveries per video.
  5. No skipped reactions — a world-reaction that couldn't fit its beat
     is a design error in that beat's timeline.

Exits 1 on any violation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EVENT_GAP_MAX = 9.0
SURPRISE_GAP_MAX = 60.0
MIN_DISCOVERIES = 2
HAPPENING = {"travel", "reveal", "event", "payoff", "reaction", "discovery"}
SURPRISE = {"discovery", "cold_open"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger", type=Path)
    args = ap.parse_args()

    d = json.loads(args.ledger.read_text())
    windows, rows = d["windows"], d["rows"]
    total = windows[-1][1]
    beats = windows[1:-1]
    fails: list[str] = []

    for i, (t0, t1) in enumerate(beats):
        rs = [r for r in rows if r.get("beat") == i]
        spans = sorted((r["t"], float(r.get("rt", 0.5))) for r in rs
                       if r["kind"] in HAPPENING)
        cur, gap = t0, 0.0
        for t, rt in spans:
            gap = max(gap, t - cur)
            cur = max(cur, t + rt)
        gap = max(gap, t1 - cur)
        n_ev = sum(1 for r in rs if r["kind"] in ("event", "payoff"))
        n_pay = sum(1 for r in rs if r["kind"] == "payoff")
        n_skip = sum(1 for r in rs
                     if r["kind"] == "skipped" and r.get("what") == "react")
        flags = []
        if gap > EVENT_GAP_MAX:
            flags.append(f"{gap:.1f}s hole")
            fails.append(f"beat {i}: {gap:.1f}s without a visual happening "
                         f"(law: <= {EVENT_GAP_MAX}s)")
        if n_pay == 0:
            flags.append("no payoff")
            fails.append(f"beat {i}: no payoff (every beat lands a punch)")
        if n_skip:
            flags.append(f"{n_skip} skipped reaction(s)")
            fails.append(f"beat {i}: {n_skip} planned reaction(s) never "
                         "fired — the beat's timeline is over-packed")
        print(f"beat {i}: {n_ev:2d} events  {n_pay} payoff  "
              f"max-hole {gap:4.1f}s  {'FAIL: ' + ', '.join(flags) if flags else 'ok'}")

    stimes = sorted(r["t"] for r in rows if r["kind"] in SURPRISE)
    cur, sgap = 0.0, 0.0
    for t in stimes:
        sgap = max(sgap, t - cur)
        cur = t
    sgap = max(sgap, total - cur)
    n_disc = sum(1 for r in rows if r["kind"] == "discovery")
    print(f"surprises: {len(stimes)} ({n_disc} discoveries)  "
          f"max-span {sgap:.1f}s")
    if sgap > SURPRISE_GAP_MAX:
        fails.append(f"{sgap:.1f}s without a discovery-class moment "
                     f"(law: <= {SURPRISE_GAP_MAX}s)")
    if n_disc < MIN_DISCOVERIES:
        fails.append(f"only {n_disc} discoveries authored "
                     f"(law: >= {MIN_DISCOVERIES})")

    if fails:
        print(f"\nFAIL — {len(fails)} escalation-law violation(s):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("\nOK: the ledger satisfies the escalation laws.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
