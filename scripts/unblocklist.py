#!/usr/bin/env python3
"""Reverse blocklist entries written by a gate that was provably broken.

WHY THIS EXISTS, AND WHY IT IS NARROW
-------------------------------------
`state/third_posted_log.json` is sacred append-only dedupe state: losing an
entry means a duplicate upload (docs/STORAGE_AUDIT.md). This tool edits it,
so it has to justify itself precisely.

The log holds two different kinds of record:

  * an UPLOAD    — `clip-YYYYMMDD-N`, carries a `url`. Losing one re-posts a
                   video that is already live. THIS TOOL NEVER TOUCHES THEM,
                   and refuses outright if asked to.
  * a REJECTION  — `rejected-<clipkey>`, carries no `url` because nothing was
                   ever uploaded. It exists so a slot retry does not re-judge
                   a clip that already failed. Losing one costs a re-judge.

Only the second kind is in scope. Removing one cannot produce a duplicate
upload, because nothing was uploaded.

On 2026-08-01 the content gate's floor (0.70) sat above the judge's entire
achievable range (rubric max 0.55, median 0.20 across every score ever
recorded) — a threshold in a dead zone of its own rubric. It refused 17 of
17 clips and the channel shipped nothing. Those rejections are not verdicts
on the clips; they are artifacts of a miscalibrated number. Leaving them in
place would keep good clips banned forever on evidence that was never valid.

This is a data correction, NOT a bar being lowered. A rejection whose
recorded score is genuinely below the (new, calibrated) hard floor is left
exactly where it is — sponsor reads and menu talk stay banned.

    python scripts/unblocklist.py --since 2026-08-01 --floor 0.35
    python scripts/unblocklist.py --since 2026-08-01 --floor 0.35 --apply

Dry run by default. Prints every entry it would remove and why.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / "state" / "third_posted_log.json"

# the recorded reason looks like "0.55 < 0.7 (genuine laughing reaction)"
_SCORE = re.compile(r"^\s*([01]?\.\d+)\s*<")


def _score_of(entry: dict):
    m = _SCORE.match(str(entry.get("rejected_why", "")))
    return float(m.group(1)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True,
                    help="only rejections stamped on/after this date "
                         "(YYYY-MM-DD) — the broken-gate window")
    ap.add_argument("--floor", type=float, required=True,
                    help="keep rejections scored BELOW this; reverse the "
                         "rest. Use the calibrated hard floor.")
    ap.add_argument("--by", default="content gate",
                    help="only reverse rejections from this judge")
    ap.add_argument("--apply", action="store_true",
                    help="actually write (default: dry run)")
    a = ap.parse_args()

    log = json.loads(LOG.read_text())
    posted = log["posted"]

    remove, kept, skipped = [], [], []
    for slug, e in posted.items():
        # HARD GUARD 1: only rejection records. An upload record is out of
        # scope no matter what any other flag says.
        if not slug.startswith("rejected-"):
            continue
        # HARD GUARD 2: anything carrying a video URL was uploaded. Refuse
        # loudly rather than quietly skipping — a `rejected-` slug with a
        # url means an assumption in this tool is wrong.
        if e.get("url"):
            print(f"::error::{slug} is a rejection record WITH a video url "
                  f"— refusing to touch the log at all", file=sys.stderr)
            return 2
        if str(e.get("rejected_by", "")) != a.by:
            continue
        if str(e.get("ts", "")) < a.since:
            continue
        s = _score_of(e)
        if s is None:
            # no recorded score = no evidence it was the broken threshold
            skipped.append((slug, e))
            continue
        (remove if s >= a.floor else kept).append((slug, e, s))

    print(f"rejections by {a.by!r} since {a.since}: "
          f"{len(remove) + len(kept) + len(skipped)}")
    print(f"\nREVERSE ({len(remove)}) — scored >= {a.floor}, so the old "
          f"threshold was the only reason they failed:")
    for slug, e, s in sorted(remove, key=lambda r: -r[2]):
        print(f"  {s:.2f}  {str(e.get('streamer','')):>14}  "
              f"{str(e.get('title',''))[:44]!r}")
    print(f"\nKEEP ({len(kept)}) — genuinely under the hard floor:")
    for slug, e, s in sorted(kept, key=lambda r: -r[2]):
        print(f"  {s:.2f}  {str(e.get('streamer','')):>14}  "
              f"{str(e.get('rejected_why',''))[:60]}")
    if skipped:
        print(f"\nSKIP ({len(skipped)}) — no recorded score, no evidence")

    if not a.apply:
        print("\n(dry run — re-run with --apply to write)")
        return 0
    if not remove:
        print("\nnothing to do")
        return 0

    for slug, _e, _s in remove:
        posted.pop(slug, None)
    from shared.fsutil import atomic_write_json
    atomic_write_json(LOG, log)
    print(f"\nremoved {len(remove)} rejection record(s). Uploads touched: 0.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(REPO))
    sys.exit(main())
