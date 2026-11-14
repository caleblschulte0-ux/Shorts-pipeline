"""Is the explainer still posting, and is the gate still naming new things?
(operator, 2026-11-14: "learn from this and expand 10 times in every
direction on every problem").

2026-11-08..11 the explainer posted nothing across sixteen runs. Each run
said "0 posted, 75 held by the gate, 0 faults" and exited green — a hold is
not a fault, rightly — and the only place the pattern showed was in sixteen
logs nobody opened: the same stories "not_current" run after run, waiting
for scenes a rate-limited brain never drew.

This reads `state/explainer_runs.json` (one record per run, written by
`post_stories.py`; this run's is already in it) and the showrunner's
verdicts on explainer stories, and FAILS the run (exit 1, reason in the step
summary) when, over the last `DAYS` days of live runs:

- any story died on a fault (a crash, a lost claim, a failed upload);
- `MIN_RUNS` or more runs tried stories and not one was posted;
- a story was held `not_current` in `STUCK_RUNS` or more runs: whatever
  should finish it is not finishing it;
- the showrunner judged `GATE_MIN` or more cuts and over `SHARE` were
  blocked, or over half carried the SAME auto-fail: the gate keeps naming
  one fixable defect, and the fix belongs upstream of it.

    python scripts/explainer_health.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from shared import channel_health  # noqa: E402

RUNS = ROOT / "state" / "explainer_runs.json"
VERDICTS = ROOT / "state" / "showrunner_verdicts.jsonl"
CONFIG = ROOT / "data_learning" / "niche.config.json"
DAYS = 3
MIN_RUNS = 2
STUCK_RUNS = 6
GATE_MIN = 4
SHARE = 2 / 3


def _class(auto_fail: str) -> str:
    return str(auto_fail).split(":", 1)[0].strip()


def problems(runs: list[dict], verdicts: list[dict]) -> list[str]:
    """What is wrong across these runs and verdicts; [] when nothing is."""
    runs = [r for r in runs if not r.get("dry_run")]
    out = []

    faults = [f for r in runs for f in r.get("faults") or []]
    if faults:
        out.append(f"{len(faults)} stor(ies) died on a fault, e.g. "
                   f"{faults[0].get('slug')}: "
                   f"{str(faults[0].get('error'))[:160]!r}")

    if len(runs) >= MIN_RUNS and not any(r.get("posted") for r in runs):
        held = Counter()
        for r in runs:
            for code, slugs in (r.get("held") or {}).items():
                held[code] += len(slugs)
        example = next((r["example"] for r in reversed(runs)
                        if r.get("example")), {})
        why = "; ".join(f"{code} x{n}"
                        + (f" (e.g. {example[code][:100]!r})"
                           if code in example else "")
                        for code, n in held.most_common(3))
        out.append(f"{len(runs)} runs and not one story posted: "
                   f"{why or 'nothing was tried'}")

    waiting = Counter(s for r in runs
                      for s in (r.get("held") or {}).get("not_current", []))
    stuck = [s for s, n in waiting.most_common() if n >= STUCK_RUNS]
    if stuck:
        out.append(f"{len(stuck)} stor(ies) held not_current in "
                   f"{STUCK_RUNS}+ runs, never finished: "
                   + ", ".join(stuck[:5]))

    if len(verdicts) >= GATE_MIN:
        blocked = [v for v in verdicts if v.get("verdict") != "ship"]
        if len(blocked) > SHARE * len(verdicts):
            out.append(f"{len(blocked)} of {len(verdicts)} cuts were "
                       "blocked by the showrunner: " + channel_health.top(
                           v.get("one_line") for v in blocked))
        named = Counter(c for v in verdicts
                        for c in {_class(a) for a in v.get("auto_fails")
                                  or []})
        for cls, n in named.most_common(1):
            if n > len(verdicts) / 2:
                eg = next(a for v in verdicts
                          for a in v.get("auto_fails") or []
                          if _class(a) == cls)
                out.append(f"the showrunner named {cls} in {n} of "
                           f"{len(verdicts)} cuts — one defect, made "
                           f"upstream: {str(eg)[:140]!r}")
    return out


def _explainer_verdicts() -> list[dict]:
    try:
        slugs = {s.get("slug") for s in
                 json.loads(CONFIG.read_text()).get("stories", [])}
    except (OSError, ValueError):
        return []
    rows = []
    try:
        with open(VERDICTS) as f:
            for line in f:
                try:
                    v = json.loads(line)
                except ValueError:
                    continue
                if v.get("slug") in slugs:
                    rows.append(v)
    except OSError:
        pass
    return rows


def main() -> int:
    try:
        runs = json.loads(RUNS.read_text()).get("runs", [])
    except (OSError, ValueError) as e:
        print(f"::warning::[health] no run records ({e})", flush=True)
        runs = []
    found = problems(channel_health.window(runs, DAYS),
                     channel_health.window(_explainer_verdicts(), DAYS))
    return channel_health.emit(
        "Explainer health", found, "stories are being drawn, judged and "
        "posted")


if __name__ == "__main__":
    sys.exit(main())
