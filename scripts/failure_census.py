#!/usr/bin/env python3
"""Failure census — classify every recorded verdict failure into engineering
classes (ChatGPT review: "take the last 15-20 verdicts and classify every
failure ... those become engineering epics, not individual rerender notes").

Reads verdict records from (in order of preference):
  1. a verdicts-log.jsonl path passed as argv[1]
  2. `git show origin/preview-renders:verdicts-log.jsonl`
  3. state/showrunner_verdicts.jsonl

Writes ``state/failure_census.json`` (a durable artifact the repair loop and
humans can consult) and prints the census table. Each failure is keyed by CLASS
(auto-fail type or weak dimension), with per-story recurrence and whether it
RECURRED AFTER the most recent fix commit that claimed to address it (detected
by class keywords in `git log`).

Usage:
    python scripts/failure_census.py [verdicts.jsonl] [--last N]
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# engineering classes -> keywords that identify them in auto-fail text / commits
CLASSES = {
    "decorative_mascot": ["decorative_mascot", "decorative mascot", "mascot"],
    "empty_void": ["empty_void", "empty void", "void"],
    "dead_air": ["dead_air", "dead air"],
    "temporal_gate": ["temporal_gate", "cadence", "effective_fps", "fps"],
    "bare_number": ["bare_number", "bare number"],
    "junk_imagery": ["irrelevant", "junk"],
}
DIMS = ("hook", "data_demo", "mascot", "craft", "pace", "payoff",
        "temporal_craft")


def _load_rows(argv: list[str]) -> list[dict]:
    if len(argv) > 1 and not argv[1].startswith("--"):
        p = Path(argv[1])
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    try:
        out = subprocess.run(
            ["git", "show", "origin/preview-renders:verdicts-log.jsonl"],
            capture_output=True, text=True, cwd=REPO, timeout=30)
        if out.returncode == 0 and out.stdout.strip():
            return [json.loads(l) for l in out.stdout.splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        pass
    led = REPO / "state" / "showrunner_verdicts.jsonl"
    if led.exists():
        return [json.loads(l) for l in led.read_text().splitlines() if l.strip()]
    return []


def _classify(af_text: str) -> str:
    low = af_text.lower()
    for cls, kws in CLASSES.items():
        if any(k in low for k in kws):
            return cls
    return "other"


def _fix_commits() -> dict:
    """class -> ts of the most recent commit whose message claims to fix it."""
    try:
        out = subprocess.run(
            ["git", "log", "--format=%cI %s", "-100"],
            capture_output=True, text=True, cwd=REPO, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return {}
    fixes: dict = {}
    for line in out.splitlines():
        ts, _, msg = line.partition(" ")
        low = msg.lower()
        for cls, kws in CLASSES.items():
            if any(k in low for k in kws) and cls not in fixes:
                fixes[cls] = ts        # log is newest-first: first hit = latest
    return fixes


def build_census(rows: list[dict], last: int = 20) -> dict:
    rows = rows[-last:]
    fixes = _fix_commits()
    census: dict = {"n_verdicts": len(rows), "classes": {}, "weak_dims": {},
                    "scores": [r.get("score") for r in rows]}
    by_class: dict = defaultdict(lambda: {"count": 0, "stories": defaultdict(int),
                                          "timestamps": [], "examples": [],
                                          "recurred_after_fix": False})
    dim_lows: dict = defaultdict(list)
    for r in rows:
        for af in r.get("auto_fails", []) or []:
            cls = _classify(af)
            e = by_class[cls]
            e["count"] += 1
            e["stories"][r.get("slug", "?")] += 1
            e["timestamps"].append(r.get("ts", ""))
            if len(e["examples"]) < 3:
                e["examples"].append(af[:200])
            fix_ts = fixes.get(cls)
            if fix_ts and r.get("ts", "") > fix_ts:
                e["recurred_after_fix"] = True
        for d in DIMS:
            v = (r.get("dimensions") or {}).get(d)
            if v is not None:
                dim_lows[d].append(v)
    census["classes"] = {k: {**v, "stories": dict(v["stories"])}
                         for k, v in sorted(by_class.items(),
                                            key=lambda kv: -kv[1]["count"])}
    for d, vals in dim_lows.items():
        s = sorted(vals)
        census["weak_dims"][d] = {"median": s[len(s) // 2], "min": min(vals),
                                  "max": max(vals)}
    return census


def main() -> int:
    rows = _load_rows(sys.argv)
    last = 20
    if "--last" in sys.argv:
        last = int(sys.argv[sys.argv.index("--last") + 1])
    if not rows:
        print("no verdict rows found")
        return 1
    census = build_census(rows, last)
    out = REPO / "state" / "failure_census.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(census, indent=1))
    print(f"censused last {census['n_verdicts']} verdicts -> {out}")
    print(f"scores: {census['scores']}")
    print(f"{'CLASS':<20} {'N':>3}  {'RECURRED-AFTER-FIX':<19} STORIES")
    for cls, e in census["classes"].items():
        print(f"{cls:<20} {e['count']:>3}  {str(e['recurred_after_fix']):<19} "
              f"{e['stories']}")
    print("weak dimensions (median/min/max):")
    for d, v in sorted(census["weak_dims"].items(), key=lambda kv: kv[1]["median"]):
        print(f"  {d:<15} {v['median']}/{v['min']}/{v['max']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
