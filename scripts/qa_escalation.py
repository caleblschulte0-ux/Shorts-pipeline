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

PAYOFF GRADE (§7.5 v5 — world consequence), per beat:
  A. the world STATE changed (an intensity rise or a persistent entity
     mutation logged in the beat);
  B. the camera REVEALED NEW SPACE (travel zoom ratio or normalized
     distance above threshold);
  C. the beat ENDS STRONGER than it starts (its last payoff lands in
     the second half of the window).
Any of A–C failing fails the build, like the base rules.

HERO CONTRACT (§7.5 v8), with --director <report.json> — per planned
beat hero: a breach row inside its beat with the splice span fitting and
a >=2.5s tail; a hero_consequence state row in the covered span; a
capability grant; a payoff AFTER the splice end (the DELETABILITY law —
cutting the hero must force later footage to change); an echo row in the
final window; capability inheritance in every later beat (no-downgrade);
and no skipped:hero rows. Legibility rows (engine-measured text px /
off-frame) always fail.

Exits 1 on any violation.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

EVENT_GAP_MAX = 9.0
SURPRISE_GAP_MAX = 60.0
MIN_DISCOVERIES = 2
SPACE_ZOOM_MIN = 0.15      # |log(w1/w0)| — the camera changed magnitude
SPACE_MOVE_MIN = 0.30      # centre travel in units of the target width
HAPPENING = {"travel", "reveal", "event", "payoff", "reaction",
             "discovery", "evidence", "breach"}
SURPRISE = {"discovery", "cold_open", "evidence"}


def _check_heroes(report: dict, windows, rows, fails: list[str]):
    """The hero-integration contract, verified from what the engine
    actually logged (never from pixels)."""
    plan_ids = list(report.get("plan") or [])
    planned = {c["id"]: c for c in report.get("candidates", [])
               if c.get("id") in plan_ids}
    for r in rows:
        if r["kind"] == "skipped" and r.get("what") == "hero":
            fails.append(f"hero {r.get('hero')}: planned but the window "
                         "couldn't fit it — fix seconds/window before "
                         "the premium run")
    fin0, fin1 = windows[-1]
    for hid, c in planned.items():
        beat = int(c["beat"])
        t0, t1 = windows[beat + 1]
        brs = [r for r in rows if r["kind"] == "breach"
               and r.get("hero") == hid]
        if len(brs) != 1:
            fails.append(f"hero {hid}: {len(brs)} breach rows in the "
                         "ledger (contract: exactly one)")
            continue
        br = brs[0]
        cut0 = br["t"] + float(br.get("rt", 0.0))
        cut1 = cut0 + float(c.get("splice", 0.0))
        if not (t0 <= br["t"] and cut1 <= t1 - 2.5):
            fails.append(f"hero {hid}: splice [{cut0:.1f},{cut1:.1f}] "
                         f"doesn't fit beat {beat} "
                         f"[{t0:.1f},{t1:.1f}] with a >=2.5s tail")
        if not any(r["kind"] == "state"
                   and r.get("what") == "hero_consequence"
                   and r.get("hero") == hid
                   and cut0 - 0.1 <= r["t"] <= cut1 + 0.1 for r in rows):
            fails.append(f"hero {hid}: no persistent consequence in the "
                         "covered span — the hero is decorative")
        if not any(r["kind"] == "capability" and r.get("by") == hid
                   for r in rows):
            fails.append(f"hero {hid}: granted no capability")
        if not any(r["kind"] == "payoff" and r.get("beat") == beat
                   and r["t"] >= cut1 - 0.1 for r in rows):
            fails.append(f"hero {hid}: beat {beat} has no payoff AFTER "
                         "the splice — the hero could be deleted "
                         "without changing later footage (deletability "
                         "law)")
        if not any(r["kind"] == "echo" and r.get("hero") == hid
                   and r["t"] >= fin0 - 0.5 for r in rows):
            fails.append(f"hero {hid}: the ending never echoes it")
        # no-downgrade: every later beat inherits >=1 capability
        n_beats = len(windows) - 2
        for j in range(beat + 1, n_beats):
            if not any(r["kind"] == "capability" and r.get("beat") == j
                       and r.get("consumed") for r in rows):
                fails.append(f"beat {j}: inherits nothing from hero "
                             f"{hid} (no-downgrade law)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger", type=Path)
    ap.add_argument("--director", type=Path, default=None,
                    help="director report — enables the hero-contract "
                         "rules (§7.5 v8)")
    args = ap.parse_args()

    d = json.loads(args.ledger.read_text())
    windows, rows = d["windows"], d["rows"]
    total = windows[-1][1]
    beats = windows[1:-1]
    fails: list[str] = []

    # LEGIBILITY (§7.5 v8): the engine measured every text at its beat's
    # planned frame — a violation row is a build-time fact.
    for r in rows:
        if r["kind"] == "legibility":
            fails.append(f"beat {r.get('beat')}: {r.get('what')} text "
                         f"{r.get('text')!r} "
                         + (f"({r.get('px')}px < 18px min)"
                            if r.get("what") == "too-small" else
                            f"(dx={r.get('dx')}, dy={r.get('dy')})"))

    if args.director and args.director.exists():
        _check_heroes(json.loads(args.director.read_text()),
                      windows, rows, fails)

    for i, (t0, t1) in enumerate(beats):
        rs = [r for r in rows if r.get("beat") == i]
        # a breach covers its whole splice: the premium hero occupies
        # that span in the assembled video (the 2D take underneath is
        # busy mutating the world, not performing)
        spans = sorted((r["t"], float(r.get("rt", 0.5))
                        + (float(r.get("splice", 0.0))
                           if r["kind"] == "breach" else 0.0))
                       for r in rs if r["kind"] in HAPPENING)
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
        # --- payoff grade (§7.5 v5) ---
        grade = []
        if not any(r["kind"] == "state" for r in rs):
            grade.append("A:no-state-change")
            fails.append(f"beat {i}: the world state never changed "
                         "(no intensity rise or entity mutation)")
        trav = next((r for r in rs if r["kind"] == "travel"), None)
        revealed = False
        if trav and trav.get("w0"):
            zoom = abs(math.log(max(trav.get("w1", 1), 1e-9)
                                / max(trav["w0"], 1e-9)))
            revealed = (zoom > SPACE_ZOOM_MIN
                        or trav.get("moved", 0) > SPACE_MOVE_MIN)
        if not revealed:
            grade.append("B:no-new-space")
            fails.append(f"beat {i}: the camera revealed no new space")
        pays = [r["t"] for r in rs if r["kind"] == "payoff"]
        if pays and max(pays) < (t0 + t1) / 2:
            grade.append("C:weak-ending")
            fails.append(f"beat {i}: last payoff at {max(pays):.1f}s — "
                         "the beat must end stronger than it starts")
        flags.extend(grade)
        print(f"beat {i}: {n_ev:2d} events  {n_pay} payoff  "
              f"max-hole {gap:4.1f}s  "
              f"{'FAIL: ' + ', '.join(flags) if flags else 'ok'}")

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
