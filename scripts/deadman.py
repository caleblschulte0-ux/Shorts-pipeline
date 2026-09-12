#!/usr/bin/env python3
"""THE DEAD-MAN'S SWITCH: is today's slate delivered, and if not, fire again.

Operator, 2026-09-12: *"I want you to add a million levels of redundancy and
fail safes. It would take fucking Godzilla crushing the Apple headquarters
for a video not to post for us one day."*

WHY `alarm.yml` DID NOT CATCH THE THING IT EXISTS TO CATCH.

`daily_alarm.py` asks "did today work?" at 01:15 UTC — after the day is
over — and COMMENTS. It never fired across the five days the operator spent
dispatching the explainer by hand every morning, and it was right not to:
videos DID post. They posted because a human noticed at 09:30 and pushed the
button. The watchdog was measuring the outcome of the repair, not the fault.

A monitor a human silently repairs every day reports a healthy system
forever. So detection is not the gap. MID-DAY REPAIR is the gap: something
that notices at 12:00 that the day has not shipped and FIRES THE WORKFLOW
ITSELF, instead of writing it down at 01:15 the next morning.

WHAT THIS DELIBERATELY DOES NOT DO.

It does not touch the showrunner. "A video always posts" cannot mean "a
video posts anyway" — `docs/EDITORIAL_RESET.md` and CLAUDE.md are explicit
that a fail-closed gate with a bypass is not a gate, and
`scripts/review_proposals.py` hard-refuses volume bought with a lower bar. A
video the gate holds is the system working. What this guarantees is that
every video which SHOULD post gets a real chance to, repeatedly, until the
day is delivered or the attempts are honestly exhausted and someone is told
loudly.

Re-firing a gate-emptied day is not a bypass — it is the operator's own
standing ruling, quoted in CLAUDE.md: *"if something doesn't run properly,
it goes through and tries again."* The replacement goes through the
identical QA and showrunner path, and a replacement the gate also refuses
stays refused.

    python scripts/deadman.py                 # human-readable status
    python scripts/deadman.py --json          # machine-readable decision
    python scripts/deadman.py --date 20260912
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import daily_alarm as al                        # noqa: E402
from shared import channel_registry as reg                   # noqa: E402

#: How many times the switch may fire one channel in one day.
#:
#: Bounded on purpose. Unbounded retry against a genuinely bad data day burns
#: CI minutes and the Claude subscription the showrunner needs to judge with,
#: and an exhausted budget that shouts is more useful than a loop that never
#: admits defeat. Three is enough to ride out a transient (a 429, a runner
#: failure, a GitHub scheduler stall) and short enough to notice.
MAX_FIRES = 3

#: Don't judge a day before its content could plausibly exist. The Routine
#: authors at ~09:19 UTC and lands via auto-merge shortly after; the first
#: honest moment to ask "why has nothing shipped?" is a clear hour later.
FIRST_JUDGE_HOUR_UTC = 11

#: Which workflow delivers each channel. A channel with no entry is reported
#: but never fired — the switch will not guess at a delivery path.
WORKFLOWS = {
    "explainer": "explainer.yml",
    "trending": "daily.yml",
    "third": "third.yml",
}

STATE_DIR = ROOT / "state" / "deadman"


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def ledger_path(date: str) -> Path:
    return STATE_DIR / f"{date}.json"


def load_ledger(date: str) -> dict:
    try:
        return json.loads(ledger_path(date).read_text())
    except Exception:  # noqa: BLE001 — a missing ledger is an empty one
        return {}


def record_fire(date: str, channel: str, note: str = "") -> dict:
    """Append one intervention. The ledger is the bound AND the evidence."""
    led = load_ledger(date)
    fires = led.setdefault(channel, [])
    fires.append({"at": datetime.now(timezone.utc).isoformat(
        timespec="seconds"), "note": note})
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ledger_path(date).write_text(json.dumps(led, indent=2, sort_keys=True))
    return led


def _hour_utc(now=None) -> int:
    return (now or datetime.now(timezone.utc)).hour


def assess(date: str | None = None, now=None, registry=None) -> dict:
    """What each channel owes today, what it delivered, and what to do.

    Pure apart from reading the repo: no network, no dispatch. The workflow
    decides nothing — it does what this says.
    """
    date = date or _today_utc()
    registry = registry if registry is not None else reg.load()
    led = load_ledger(date)
    hour = _hour_utc(now)
    early = hour < FIRST_JUDGE_HOUR_UTC
    out = {"date": date, "hour_utc": hour, "early": early, "channels": []}

    for cid in reg.channel_ids(registry):
        ch = reg.channel(cid, registry) or {}
        if not ch.get("enabled"):
            continue
        target = reg.target_count(cid, registry) or 0
        log_rel = (reg.paths(cid, registry) or {}).get("posted_log")
        if not target or not log_rel:
            continue
        posted = len(al._posted_on(ROOT / log_rel, date))
        fires = len(led.get(cid, []))
        short = max(0, target - posted)
        row = {"channel": cid, "expected": target, "posted": posted,
               "short": short, "fires": fires,
               "workflow": WORKFLOWS.get(cid)}
        if short == 0:
            row["action"], row["reason"] = "ok", "the day is delivered"
        elif early:
            row["action"] = "wait"
            row["reason"] = (f"only {hour:02d}:00 UTC — the day's content may "
                             f"not exist yet (judging from "
                             f"{FIRST_JUDGE_HOUR_UTC:02d}:00)")
        elif not row["workflow"]:
            row["action"] = "report"
            row["reason"] = ("no delivery workflow is registered for this "
                             "channel — the switch will not guess one")
        elif fires >= MAX_FIRES:
            row["action"] = "give_up"
            row["reason"] = (f"fired {fires}/{MAX_FIRES} times and the day is "
                             f"still {short} short — this needs a human, and "
                             f"a loop that never admits defeat would hide it")
        else:
            row["action"] = "fire"
            row["reason"] = (f"{posted}/{target} posted at {hour:02d}:00 UTC; "
                             f"firing {row['workflow']} "
                             f"(attempt {fires + 1}/{MAX_FIRES})")
        out["channels"].append(row)

    out["fire"] = [r["channel"] for r in out["channels"]
                   if r["action"] == "fire"]
    out["alarm"] = [r["channel"] for r in out["channels"]
                    if r["action"] in ("give_up", "report")]
    out["ok"] = not out["fire"] and not out["alarm"]
    return out


def render(a: dict) -> str:
    lines = [f"# Dead-man's switch — {a['date']} at {a['hour_utc']:02d}:00 UTC",
             ""]
    if not a["channels"]:
        lines.append("No enabled channel declares both a target and a posted "
                     "log. Nothing to guarantee.")
        return "\n".join(lines)
    lines += ["| channel | posted | expected | fires | action |",
              "|---|---|---|---|---|"]
    for r in a["channels"]:
        lines.append(f"| {r['channel']} | {r['posted']} | {r['expected']} "
                     f"| {r['fires']} | **{r['action']}** |")
    lines.append("")
    for r in a["channels"]:
        if r["action"] != "ok":
            lines.append(f"- **{r['channel']}** — {r['reason']}")
    if a["ok"]:
        lines.append("Every enabled channel has delivered its slate.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--record-fire", metavar="CHANNEL", default="",
                    help="append an intervention for CHANNEL to the ledger")
    args = ap.parse_args()
    date = args.date or _today_utc()
    if args.record_fire:
        record_fire(date, args.record_fire, "dispatched by deadman.yml")
        print(f"[deadman] recorded a fire for {args.record_fire} on {date}")
        return 0
    a = assess(date)
    print(json.dumps(a, indent=2) if args.json else render(a))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
