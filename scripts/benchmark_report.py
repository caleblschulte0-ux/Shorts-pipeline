#!/usr/bin/env python3
"""Aggregate a FULL-VIDEO benchmark run (Phase 4.3): complete rendered videos
(hook + narration + captions + scenes + ending + audio), judged by the
unchanged showrunner, rolled up into the required report:

    {run_id, stories, median_score, lowest_score, hard_failures,
     effective_fps_median, decorative_mascot_failures}

Written to state/benchmark_full.json and APPENDED to state/benchmark_runs.jsonl
(the consecutive-run history that the phase gates read: phase 1 needs median
>= 70 & lowest >= 65 & zero hard failures across TWO consecutive runs).

Usage: python scripts/benchmark_report.py --slugs a b c [--run-id X]
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def aggregate(slugs: list[str], run_id: str | None = None) -> dict:
    rows = []
    for s in slugs:
        vp = REPO / "output" / f"story_{s}.showrunner.json"
        if vp.exists():
            v = json.loads(vp.read_text())
            v["slug"] = s
            rows.append(v)
        else:
            rows.append({"slug": s, "score": 0, "verdict": "missing",
                         "auto_fails": ["missing: no verdict written"]})
    scores = [r.get("score") or 0 for r in rows]
    fpss = [((r.get("temporal") or {}).get("effective_fps") or 0.0)
            for r in rows]
    hard = sum(len(r.get("auto_fails") or []) for r in rows)
    deco = sum(1 for r in rows for a in (r.get("auto_fails") or [])
               if a.startswith("decorative_mascot"))
    rep = {
        "run_id": run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "stories": len(rows),
        "median_score": st.median(scores) if scores else 0,
        "lowest_score": min(scores) if scores else 0,
        "hard_failures": hard,
        "effective_fps_median": st.median(fpss) if fpss else 0.0,
        "decorative_mascot_failures": deco,
        "per_story": [{"slug": r["slug"], "score": r.get("score"),
                       "verdict": r.get("verdict"),
                       "auto_fails": len(r.get("auto_fails") or []),
                       "effective_fps": (r.get("temporal") or {}).get(
                           "effective_fps")} for r in rows],
    }
    return rep


def phase_gate(history: list[dict], median_bar: int, lowest_bar: int,
               runs_needed: int = 2) -> dict:
    """Evaluate the consecutive-run phase gate over the newest history."""
    recent = history[-runs_needed:]
    ok = (len(recent) >= runs_needed and all(
        r["median_score"] >= median_bar and r["lowest_score"] >= lowest_bar
        and r["hard_failures"] == 0 for r in recent))
    return {"consecutive_runs_checked": len(recent), "runs_needed": runs_needed,
            "median_bar": median_bar, "lowest_bar": lowest_bar, "pass": ok}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs", nargs="+", required=True)
    ap.add_argument("--run-id")
    ap.add_argument("--median-bar", type=int, default=70)
    ap.add_argument("--lowest-bar", type=int, default=65)
    args = ap.parse_args()
    rep = aggregate(args.slugs, args.run_id)
    out = REPO / "state" / "benchmark_full.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1))
    hist_p = REPO / "state" / "benchmark_runs.jsonl"
    with hist_p.open("a") as fh:
        fh.write(json.dumps(rep) + "\n")
    history = [json.loads(l) for l in hist_p.read_text().splitlines()
               if l.strip()]
    gate = phase_gate(history, args.median_bar, args.lowest_bar)
    print(json.dumps({**rep, "phase_gate": gate}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
