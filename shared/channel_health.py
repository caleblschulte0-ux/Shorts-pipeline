"""What every channel's health check shares (operator, 2026-11-14: "learn
from this and expand 10 times in every direction on every problem").

Baller Bro posted bare clips for three weeks while every run was green; the
Twitch channel posted nothing for three days on a judge that scored every
candidate 0.20; the explainer posted nothing for four days while each run
said "held by the gate, nothing broken". Every one of those was plain in
the channel's own run records, days before anyone looked. A health check
reads those records and turns the pattern into a red run with the reason
in the step summary.

Each channel keeps its own pure `problems()` (what is wrong, in words) in
`scripts/<channel>_health.py`. This module is the part they share: which
records count, and how a finding is reported.
"""
from __future__ import annotations

import datetime as dt
import os
from collections import Counter

# Runs before the 2026-11-14 fixes are the problems these checks were
# written from; counting them would keep every check red for days after.
FLOOR = "2026-11-14"


def since(days: int, floor: str = FLOOR,
          today: dt.date | None = None) -> str:
    """The first ISO date a check counts: `days` back, never before
    `floor`."""
    today = today or dt.date.today()
    return max(floor, (today - dt.timedelta(days=days)).isoformat())


def window(records: list[dict], days: int, key: str = "ts",
           floor: str = FLOOR, today: dt.date | None = None) -> list[dict]:
    """The records whose `key` timestamp falls inside the window."""
    first = since(days, floor, today)
    return [r for r in records if str(r.get(key) or "")[:10] >= first]


def top(reasons, n: int = 3, width: int = 90) -> str:
    """The commonest reasons, counted: "12x quality floor...; 3x ..."."""
    c = Counter(str(r)[:width] for r in reasons if r)
    return "; ".join(f"{k} (x{v})" if v > 1 else k
                     for k, v in c.most_common(n))


def emit(title: str, found: list[str], healthy: str) -> int:
    """Print the finding, add it to the step summary, annotate each
    problem, and return the exit code (1 when anything was found)."""
    lines = ([f"- {p}" for p in found] if found else [f"- {healthy}"])
    text = f"### {title}\n" + "\n".join(lines) + "\n"
    print(text, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(text)
    for p in found:
        print(f"::error::[health] {p}", flush=True)
    return 1 if found else 0
