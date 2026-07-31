#!/usr/bin/env python3
"""Which triaged proposals are still waiting on a decision from Claude?

Without this the loop is a suggestion inbox: ChatGPT writes, triage sorts,
and then nothing happens unless a human remembers. A proposal that is never
answered is worse than one that is declined — the reviewer cannot tell the
difference between "we disagreed" and "nobody looked", so it keeps re-filing
and never learns anything.

    python scripts/pending_decisions.py            # human summary
    python scripts/pending_decisions.py --json     # for the decide workflow
    python scripts/pending_decisions.py --dates    # just the dates, oldest first

Exit 0 always. This reports; it never decides.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

RETRO_ROOT = ROOT / "retro"
DATE_DIR = re.compile(r"^\d{8}$")
# Categories that need a verdict. `refused` is already a final answer — the
# policy said no — and re-deciding it would just re-litigate policy.
NEEDS_VERDICT = ("accepted", "requires_operator", "malformed")


def answered_keys() -> set[tuple]:
    try:
        from retro_reply import read_ledger
        return {(r.get("date"), r.get("proposal_file"))
                for r in read_ledger()}
    except Exception:                                # noqa: BLE001
        return set()


def pending() -> list[dict]:
    """Every triaged proposal with no ledger entry, oldest date first."""
    if not RETRO_ROOT.is_dir():
        return []
    done = answered_keys()
    out = []
    for d in sorted((p for p in RETRO_ROOT.iterdir()
                     if p.is_dir() and DATE_DIR.match(p.name)),
                    key=lambda p: p.name):
        try:
            t = json.loads((d / "triage.json").read_text())
        except Exception:                            # noqa: BLE001
            continue
        for bucket in NEEDS_VERDICT:
            for e in t.get(bucket) or []:
                if (d.name, e.get("file")) in done:
                    continue
                out.append({"date": d.name, "file": e.get("file"),
                            "bucket": bucket, "title": e.get("title"),
                            "channel": e.get("channel"),
                            "score": e.get("score"),
                            "why": (e.get("problems") or e.get("because")
                                    or [])[:3]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dates", action="store_true")
    args = ap.parse_args()
    rows = pending()

    if args.dates:
        seen = []
        for r in rows:
            if r["date"] not in seen:
                seen.append(r["date"])
        print("\n".join(seen))
        return 0
    if args.json:
        print(json.dumps({"pending": rows, "count": len(rows)}, indent=2))
        return 0

    if not rows:
        print("no proposals awaiting a decision")
        return 0
    print(f"{len(rows)} proposal(s) awaiting a decision from Claude:")
    for r in rows:
        print(f"  [{r['bucket']}] {r['date']} {r['file']} — {r['title']}")
    print()
    print("Answer each with:")
    print("  python scripts/retro_reply.py --date <date> --file <file> \\")
    print("      --verdict adopt|revise|decline|needs_evidence|deferred \\")
    print("      --because \"...\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
