#!/usr/bin/env python3
"""Union-merge two posted-log/dedupe-ledger JSON files (audit Ticket 1).

Usage: merge_posted_log.py THEIRS OURS OUT

Union is the only safe merge for an append-only dedupe ledger: an entry
present on EITHER side must survive, because a lost entry means the video
it records gets re-uploaded as a duplicate. Handles both shapes in use:

  {"posted": {slug: entry, ...}}   # explainer / curiosity / third
  {"posted": [entry, ...]}         # trending / longform

For dict logs: union of keys, OURS wins per-slug (our entry is fresher —
it was just written by the run doing the merge). For list logs: THEIRS
order preserved, then any OURS entries not already present, identity =
catalog_id / url / video_url / id / slug (first present), else the whole
entry. Unknown top-level keys: OURS wins. A MISSING input is treated as
empty (a fresh checkout or first run is legitimate); a CORRUPT input is
FATAL — a union merge with one side read as empty is not a union, it is a
silent mass-delete of that side's entries, and every video they record
re-uploads. The CI retry loop that calls this must surface the failure,
not paper over it with an empty side.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load(p: str):
    path = Path(p)
    if not path.exists():
        return {}          # missing side = fresh checkout / first run: empty is honest
    try:
        obj = json.loads(path.read_text())
    except Exception as e:  # noqa: BLE001 — exists-but-unreadable is corruption
        raise SystemExit(
            f"FATAL: {path} is corrupt ({e}). Refusing to union-merge: a "
            f"corrupt side read as empty would silently drop every entry "
            f"on that side, and each dropped entry is a duplicate upload. "
            f"Restore the file from git history and re-run.")
    if not isinstance(obj, dict):
        raise SystemExit(
            f"FATAL: {path} is not a JSON object (got "
            f"{type(obj).__name__}) — refusing to merge a log whose shape "
            f"cannot be trusted. Restore it from git history and re-run.")
    return obj


_ID_KEYS = ("catalog_id", "url", "video_url", "id", "slug")


def _identity(entry) -> str:
    if isinstance(entry, dict):
        for k in _ID_KEYS:
            if entry.get(k):
                return f"{k}={entry[k]}"
    return json.dumps(entry, sort_keys=True)


def merge(theirs: dict, ours: dict) -> dict:
    out = dict(theirs)
    out.update({k: v for k, v in ours.items() if k != "posted"})
    tp, op = theirs.get("posted"), ours.get("posted")
    if isinstance(tp, dict) or isinstance(op, dict):
        merged = dict(tp if isinstance(tp, dict) else {})
        merged.update(op if isinstance(op, dict) else {})
        out["posted"] = merged
    else:
        tl = tp if isinstance(tp, list) else []
        ol = op if isinstance(op, list) else []
        seen = {_identity(e) for e in tl}
        out["posted"] = tl + [e for e in ol if _identity(e) not in seen]
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    theirs, ours = _load(argv[1]), _load(argv[2])
    merged = merge(theirs, ours)
    n = len(merged.get("posted", []))
    Path(argv[3]).write_text(json.dumps(merged, indent=2) + "\n")
    print(f"[merge_posted_log] union -> {n} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
