#!/usr/bin/env python3
"""THE CLOCK — because GitHub's cron is not a clock.

    python scripts/clock.py --plan      # what GitHub's cron has missed, no action
    python scripts/clock.py --fire      # dispatch every missed slot (needs gh)
    python scripts/clock.py --tick      # sleep to the next boundary, dispatch clock.yml

2026-09-22. Every scheduled run in this repo landed two to five hours late
or never came: the explainer's 13:40, Phase B's 13:30 backstop and the
dead-man's 11:05 and 13:05 slots did not fire at all, and the hourly claim
cron ran three times in fourteen hours (00:12, 05:12, 10:09). GitHub says
so itself — "the schedule event can be delayed during periods of high
loads" — and this repo carries thirty-odd cron entries. The dead-man's
answer was MORE crons ("several independent chances"), which is more
tickets in the same lottery.

The clock is a `workflow_dispatch` CHAIN instead. A dispatch is an API
call, not a scheduled event: it is honoured immediately, it is the one
event the repository's own GITHUB_TOKEN may raise, and the dead-man has
proved it live. `clock.yml` fires what the crons missed, sleeps to the
next quarter hour, dispatches itself, and exits — a runner-minute clock
on a public repository, where minutes are free. Its own cron is only a
bootstrap: if the chain ever dies, GitHub restarts it, late.

WHAT IT FIRES. Every workflow file with a `schedule:` and a
`workflow_dispatch:` is read at run time (`schedule()`); a slot GitHub was
given GRACE_MIN to honour and did not — no run of that workflow created
since the slot — is dispatched with the inputs its cron path uses
(`DISPATCH_INPUTS`), once. A slot older than STALE_MIN is abandoned and
said so: a 09:45 Phase A fired at 20:00 is not a repair. Any run counts
as covering a slot, whatever raised it — the dead-man's 11:51 re-fire is
the 11:05 slot's job done.

WHAT IT NEVER DOES. It lifts no gate: a dispatched run is the same run,
through the same editorial gate and the same showrunner veto. It keeps
no state — the runs ARE the record (`gh run list`). It stops when `PAUSED`
or `state/clock/OFF` exists, and it never dispatches itself while another
clock run is queued or in progress.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF_DIR = ROOT / ".github" / "workflows"
SELF = "clock.yml"
GRACE_MIN = 12          # GitHub's own chance to fire the cron
STALE_MIN = 240         # older than this, a slot is abandoned, not fired
TICK_MIN = 15           # the chain's cadence
OFF_FILES = ("PAUSED", "state/clock/OFF")

#: Inputs a dispatch needs to reach the SAME path the cron reaches. An empty
#: `mode` on the explainer is 'verify' (posts nothing) — the dead-man learned
#: that on 2026-09-13; Phase B on a cron is a `--backstop` that no-ops before
#: the ChatGPT finalizer's window and when the day is already applied.
DISPATCH_INPUTS = {
    "explainer.yml": {"mode": "schedule"},
    "deadman.yml": {"dry_run": "false"},
    "exchange_phase_b.yml": {"backstop": "true"},
    # a missed sleep-film slot is the cron path: render, judge, publish
    "curiosity.yml": {"mode": "sleep", "enable_publish": "true"},
}

#: Crons the clock deliberately leaves to GitHub, each with its reason.
CRON_ONLY = {
    SELF: "the clock's own bootstrap — it must not dispatch itself here",
}


# ---------------------------------------------------------------- crons
def _field(spec: str, lo: int, hi: int) -> list[int]:
    """One cron field to the values it names. Supports N, a,b, *, */N and
    a-b. Anything else is refused loudly — a cron the clock cannot read is a
    cron it cannot cover, and the test says so."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            part, s = part.split("/", 1)
            step = int(s)
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
        else:
            a = b = int(part)
        if not (lo <= a <= b <= hi):
            raise ValueError(f"cron field {spec!r} outside {lo}..{hi}")
        out.update(range(a, b + 1, step))
    return sorted(out)


def parse_cron(expr: str) -> dict:
    """{'minutes': [...], 'hours': [...], 'dow': set|None}. Day-of-month and
    month must be '*': this clock keeps a day, not a calendar."""
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"not a 5-field cron: {expr!r}")
    m, h, dom, mon, dow = parts
    if dom != "*" or mon != "*":
        raise ValueError(f"day-of-month/month crons are not covered: {expr!r}")
    return {"minutes": _field(m, 0, 59), "hours": _field(h, 0, 23),
            "dow": None if dow == "*" else set(_field(dow, 0, 6))}


def slots_today(expr: str, now: datetime) -> list[datetime]:
    """Every UTC time this cron names today, at or before `now`."""
    c = parse_cron(expr)
    py_dow = now.weekday()                     # Monday=0
    cron_dow = (py_dow + 1) % 7                # cron: Sunday=0
    if c["dow"] is not None and cron_dow not in c["dow"]:
        return []
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out = [day + timedelta(hours=h, minutes=m)
           for h in c["hours"] for m in c["minutes"]]
    return sorted(t for t in out if t <= now)


# ------------------------------------------------------------- workflows
def _on_block(doc: dict) -> dict:
    on = doc.get(True, doc.get("on")) or {}
    return on if isinstance(on, dict) else {k: {} for k in on}


def crons_of(path: Path) -> list[str]:
    import yaml
    doc = yaml.safe_load(path.read_text()) or {}
    sched = _on_block(doc).get("schedule") or []
    return [str(e.get("cron")) for e in sched if isinstance(e, dict) and e.get("cron")]


def dispatchable(path: Path) -> bool:
    import yaml
    doc = yaml.safe_load(path.read_text()) or {}
    return "workflow_dispatch" in _on_block(doc)


def schedule(wf_dir: Path | None = None) -> dict[str, list[str]]:
    """{workflow file: [cron, ...]} for every cron the clock covers."""
    wf_dir = Path(wf_dir or WF_DIR)
    out: dict[str, list[str]] = {}
    for p in sorted(wf_dir.glob("*.yml")):
        if p.name in CRON_ONLY:
            continue
        crons = crons_of(p)
        if crons and dispatchable(p):
            out[p.name] = crons
    return out


# ------------------------------------------------------------------ due
def due(now: datetime, sched: dict[str, list[str]],
        runs: dict[str, list[datetime]],
        grace_min: int = GRACE_MIN, stale_min: int = STALE_MIN) -> dict:
    """What to fire, what is covered, what is abandoned. Pure.

    A slot is COVERED by any run of that workflow created at or after it
    (a minute of clock skew allowed). It is DUE once `grace_min` has passed
    with no such run, and ABANDONED once `stale_min` has. One dispatch per
    workflow: its latest missed slot — a workflow fired now does the job
    of every slot it missed."""
    fire, covered, abandoned = {}, {}, {}
    for wf, crons in sched.items():
        slots = sorted({s for c in crons for s in slots_today(c, now)})
        had = runs.get(wf, [])
        missed = []
        for s in slots:
            if any(r >= s - timedelta(minutes=1) for r in had):
                covered[wf] = covered.get(wf, []) + [s]
                continue
            age = (now - s).total_seconds() / 60.0
            if age < grace_min:
                continue                    # GitHub's turn, still
            if age > stale_min:
                abandoned[wf] = abandoned.get(wf, []) + [s]
                continue
            missed.append(s)
        if missed:
            fire[wf] = max(missed)
    return {"fire": fire, "covered": covered, "abandoned": abandoned}


# ------------------------------------------------------------------- gh
def _gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {r.stderr.strip()[:300]}")
    return r.stdout


def gh_runs_today(wf: str, now: datetime) -> list[datetime]:
    """Creation times of every run of `wf` since midnight UTC, any event."""
    raw = _gh("run", "list", "--workflow", wf, "--limit", "80",
              "--json", "createdAt,event,status")
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for r in json.loads(raw or "[]"):
        try:
            t = datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            continue
        if t >= day - timedelta(minutes=2):
            out.append(t)
    return out


def gh_dispatch(wf: str, inputs: dict) -> None:
    args = ["workflow", "run", wf, "--ref", "main"]
    for k, v in inputs.items():
        args += ["-f", f"{k}={v}"]
    _gh(*args)


def other_clock_alive(own_run_id: str) -> bool:
    """Another clock run queued or running? Then this one must not spawn."""
    for status in ("in_progress", "queued", "waiting", "requested"):
        try:
            raw = _gh("run", "list", "--workflow", SELF, "--status", status,
                      "--limit", "10", "--json", "databaseId")
        except RuntimeError:
            continue
        for r in json.loads(raw or "[]"):
            if str(r.get("databaseId")) != str(own_run_id):
                return True
    return False


def switched_off() -> str | None:
    for f in OFF_FILES:
        if (ROOT / f).exists():
            return f
    return None


def seconds_to_next_tick(now: datetime, tick_min: int = TICK_MIN) -> float:
    nxt = now.replace(second=0, microsecond=0)
    nxt += timedelta(minutes=tick_min - (nxt.minute % tick_min))
    return max(5.0, (nxt - now).total_seconds())


# ----------------------------------------------------------------- main
def _fmt(t: datetime) -> str:
    return t.strftime("%H:%M")


def report(plan: dict, now: datetime) -> str:
    lines = [f"[clock] {now.strftime('%Y-%m-%d %H:%M')} UTC"]
    for wf, s in sorted(plan["fire"].items()):
        lines.append(f"  FIRE      {wf:26s} slot {_fmt(s)} missed by GitHub's cron")
    for wf, ss in sorted(plan["abandoned"].items()):
        lines.append(f"  abandoned {wf:26s} {', '.join(_fmt(s) for s in ss)} "
                     f"(older than {STALE_MIN} min)")
    for wf, ss in sorted(plan["covered"].items()):
        lines.append(f"  covered   {wf:26s} {', '.join(_fmt(s) for s in ss)}")
    if not plan["fire"]:
        lines.append("  nothing missed")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--fire", action="store_true")
    g.add_argument("--tick", action="store_true")
    args = ap.parse_args()
    now = datetime.now(timezone.utc)

    if args.tick:
        off = switched_off()
        if off:
            print(f"[clock] {off} exists — the clock stops here")
            return 0
        own = os.environ.get("GITHUB_RUN_ID", "")
        if other_clock_alive(own):
            print("[clock] another clock run is queued or running — not spawning")
            return 0
        wait = seconds_to_next_tick(now)
        print(f"[clock] sleeping {wait:.0f}s to the next {TICK_MIN}-minute boundary")
        time.sleep(wait)
        if switched_off():
            print("[clock] switched off while sleeping — not spawning")
            return 0
        gh_dispatch(SELF, {})
        print("[clock] next tick dispatched")
        return 0

    sched = schedule()
    runs = {}
    for wf in sched:
        try:
            runs[wf] = gh_runs_today(wf, now)
        except (RuntimeError, OSError) as e:
            if args.fire:
                print(f"[clock] could not list runs of {wf}: {e}", file=sys.stderr)
                runs[wf] = [now]          # unknown: treat as covered, never double-fire
            else:
                runs[wf] = []             # a plan without gh shows every slot as open
    plan = due(now, sched, runs)
    print(report(plan, now))
    if not args.fire:
        return 0
    failed = []
    for wf, slot in plan["fire"].items():
        inputs = DISPATCH_INPUTS.get(wf, {})
        try:
            gh_dispatch(wf, inputs)
            print(f"[clock] dispatched {wf} for the {_fmt(slot)} slot {inputs or ''}")
        except RuntimeError as e:
            print(f"::error title=clock-dispatch-failed::{wf}: {e}")
            failed.append(wf)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
