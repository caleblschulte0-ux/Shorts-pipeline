#!/usr/bin/env python3
"""The reviewer's mailbox — which brief needs reviewing, and has it been?

GitHub cannot summon ChatGPT. A separate scheduled ChatGPT task polls this
repo, and the only thing it can do is look. So the repo's job is to make
"what should I work on right now" answerable from the filesystem alone,
without the reviewer guessing at today's UTC folder.

That guess is the bug this replaces. A reviewer that computes
`retro/<today UTC>/` finds nothing when the brief was written at 23:15 UTC
and it polls at 00:30 UTC — the folder is yesterday's. And a review missed
on Tuesday is simply lost, because Wednesday's reviewer never looks back.

    python scripts/retro_mailbox.py                # what needs review?
    python scripts/retro_mailbox.py --json
    python scripts/retro_mailbox.py --all          # every open brief

A brief is OPEN when `brief.json` exists and `proposals.json` does not.
Answering is therefore idempotent by construction: once the reviewer writes
`proposals.json` that date drops out of the mailbox and cannot be answered
twice. Missed days stay open until someone gets to them, oldest first.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETRO_ROOT = ROOT / "retro"
DATE_DIR = re.compile(r"^\d{8}$")

# Older than this and the analytics have moved on so far that a review would
# be archaeology, not steering. Reported as expired rather than silently
# dropped — a run of them means the reviewer task is not firing.
MAX_OPEN_DAYS = 10


def review_dirs() -> list[Path]:
    if not RETRO_ROOT.is_dir():
        return []
    return sorted((d for d in RETRO_ROOT.iterdir()
                   if d.is_dir() and DATE_DIR.match(d.name)),
                  key=lambda d: d.name)


def status_of(d: Path) -> dict:
    """One review date's state. `proposals.json` is the single answer file —
    its presence is what makes answering idempotent."""
    brief = d / "brief.json"
    proposals = d / "proposals.json"
    legacy = sorted((d / "proposals").glob("*.json")) if (
        d / "proposals").is_dir() else []
    def rel(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:          # retro root redirected (tests)
            return str(path)

    return {
        "review_date": d.name,
        "brief": rel(brief) if brief.exists() else None,
        "proposals": rel(proposals) if proposals.exists() else None,
        "legacy_proposal_files": [rel(p) for p in legacy],
        "decisions": ((d / "decisions.json").exists()),
        "reviewed": proposals.exists() or bool(legacy),
        "open": brief.exists() and not (proposals.exists() or bool(legacy)),
    }


def open_reviews() -> list[dict]:
    """Every brief still awaiting proposals, OLDEST FIRST — a missed day is
    still worth answering, and answering it before today keeps the ledger in
    chronological order."""
    return [s for s in (status_of(d) for d in review_dirs()) if s["open"]]


def next_review() -> dict | None:
    """The one the reviewer should pick up now."""
    todo = open_reviews()
    return todo[0] if todo else None


def mailbox() -> dict:
    dirs = review_dirs()
    todo = open_reviews()
    fresh = todo[-MAX_OPEN_DAYS:] if todo else []
    return {
        "schema": "shorts-retro-mailbox/v1",
        "next_review": next_review(),
        "open_count": len(todo),
        "open": todo,
        "expired": [t for t in todo if t not in fresh],
        "reviewed_recently": [s for s in (status_of(d) for d in dirs[-7:])
                              if s["reviewed"]],
        "where_to_write": (
            "retro/<review_date>/proposals.json — ONE file, an object with a "
            "`proposals` array. If that file already exists for a date, that "
            "date is answered: do not write it again."),
        "how_to_pick": (
            "Take `next_review` — the oldest brief with no proposals.json. "
            "Do NOT assume today's UTC date: the brief is written at 23:15 "
            "UTC and a reviewer polling after midnight would look at the "
            "wrong folder and find nothing."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="list every open review, not just the next one")
    ap.add_argument("--next-date", action="store_true",
                    help="print ONLY the next review date (empty if none) — "
                         "so a workflow can use it without embedding Python")
    args = ap.parse_args()

    m = mailbox()
    if args.next_date:
        print((m.get("next_review") or {}).get("review_date") or "")
        return 0
    if args.json:
        print(json.dumps(m, indent=2))
        return 0

    nxt = m["next_review"]
    if not nxt:
        print("mailbox: nothing awaiting review")
        recent = m["reviewed_recently"]
        if recent:
            print(f"  last answered: {recent[-1]['review_date']}")
        return 0

    print(f"mailbox: {m['open_count']} brief(s) awaiting review")
    print(f"  NEXT: {nxt['review_date']}  ->  read {nxt['brief']}")
    print(f"        write retro/{nxt['review_date']}/proposals.json")
    if args.all:
        for s in m["open"][1:]:
            print(f"  also: {s['review_date']}  ({s['brief']})")
    if m["expired"]:
        print(f"::warning::{len(m['expired'])} brief(s) older than "
              f"{MAX_OPEN_DAYS} days are still unreviewed — the reviewer "
              f"task may not be firing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
