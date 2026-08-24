#!/usr/bin/env python3
"""Compact old committed state (audit Ticket 6) — keep the data, shrink the
file count. Idempotent; safe to run every day (no-ops until things age).

  python3 scripts/rollup_state.py [--max-age-days 90] [--dry-run]

What it does, per the audit's retention policy:
- state/analytics*/YYYYMMDD.json older than the cutoff fold into
  state/analytics*/rollup/YYYYMM.json: per-day summaries survive, and each
  video's LAST snapshot in that month survives (final metrics + retention),
  then the dailies are deleted. `latest.json` is never touched.
- state/{trending,third}_packages/YYYYMMDD/ dirs older than the cutoff fold
  into <root>/archive/YYYYMM.json ({date: {filename: package}}), then the
  day-dirs are deleted.

NEVER touches posted logs — those are sacred append-only dedupe state.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.fsutil import atomic_write_json, load_json, load_state_json  # noqa: E402

# Sentinel so an unparseable file can be told apart from one that parses to
# null/None — load_json collapses "missing", "corrupt" and "null" into the
# default, and this script DELETES originals after folding them, so that
# collapse would silently destroy the only copy of an unreadable file.
_UNREADABLE = object()

_DATE_FILE = re.compile(r"^(\d{8})\.json$")
_DATE_DIR = re.compile(r"^(\d{8})$")


def _cutoff(max_age_days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max_age_days)).strftime("%Y%m%d")


def rollup_analytics(adir: Path, cutoff: str, dry: bool) -> int:
    """Fold aged daily snapshots into monthly rollups. Returns files folded."""
    folded = 0
    monthly: dict[str, dict] = {}
    for f in sorted(adir.glob("*.json")):
        m = _DATE_FILE.match(f.name)
        if not m or m.group(1) >= cutoff:
            continue
        date = m.group(1)
        month = date[:6]
        snap = load_json(f, _UNREADABLE)
        if snap is _UNREADABLE or snap is None:
            # Unparseable (or vacuously null) snapshot: leave it on disk and
            # say so — never fold-and-delete what could not be read.
            print(f"  SKIP {adir.name}/{f.name}: unreadable — left in place")
            continue
        roll_path = adir / "rollup" / f"{month}.json"
        # Strict load of the fold TARGET: a corrupt monthly rollup read as
        # empty would be rewritten below with only this batch's days, and
        # every previously-folded day in that month (whose dailies were
        # already deleted) would be gone for good. Missing = first fold of
        # the month = honest default.
        roll = monthly.setdefault(month, load_state_json(
            roll_path, {"month": month, "days": {}, "videos": {}},
            expect_type=dict))
        roll["days"][date] = snap.get("summary", {})
        # Later days overwrite earlier ones -> each video keeps its final
        # (most complete) metrics for the month.
        for v in snap.get("videos", []):
            vid = v.get("id") or v.get("url") or v.get("title")
            if vid:
                roll["videos"][str(vid)] = v
        folded += 1
        if not dry:
            f.unlink()
        print(f"  folded {adir.name}/{f.name} -> rollup/{month}.json")
    if not dry:
        for month, roll in monthly.items():
            atomic_write_json(adir / "rollup" / f"{month}.json", roll)
    return folded


def archive_packages(pdir: Path, cutoff: str, dry: bool) -> int:
    """Fold aged package day-dirs into monthly archives. Returns dirs folded."""
    folded = 0
    monthly: dict[str, dict] = {}
    for d in sorted(pdir.iterdir()) if pdir.is_dir() else []:
        m = _DATE_DIR.match(d.name)
        if not m or not d.is_dir() or d.name >= cutoff:
            continue
        month = d.name[:6]
        # Read the whole day BEFORE touching the archive: if any file in
        # the dir is unparseable, the old code archived it as `null` and
        # then rmtree'd the dir — destroying the only copy of the bytes.
        # An unreadable day stays on disk, un-archived, and says so.
        day: dict = {}
        bad: list[str] = []
        for f in sorted(d.glob("*.json")):
            val = load_json(f, _UNREADABLE)
            if val is _UNREADABLE:
                bad.append(f.name)
            else:
                day[f.name] = val
        if bad:
            print(f"  SKIP {pdir.name}/{d.name}/: unreadable "
                  f"{', '.join(bad)} — left in place, not archived")
            continue
        arch_path = pdir / "archive" / f"{month}.json"
        # Strict load of the archive TARGET, same reason as the analytics
        # rollup: corrupt-read-as-empty + rewrite = every already-archived
        # (and already-deleted) day in the month lost.
        arch = monthly.setdefault(month, load_state_json(arch_path, {},
                                                         expect_type=dict))
        arch.setdefault(d.name, {}).update(day)
        folded += 1
        if not dry:
            shutil.rmtree(d)
        print(f"  archived {pdir.name}/{d.name}/ -> archive/{month}.json")
    if not dry:
        for month, arch in monthly.items():
            atomic_write_json(pdir / "archive" / f"{month}.json", arch)
    return folded


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=90)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cutoff = _cutoff(args.max_age_days)
    print(f"[rollup] cutoff {cutoff} (>{args.max_age_days}d old)"
          + (" [dry-run]" if args.dry_run else ""))
    total = 0
    for adir in sorted(ROOT.glob("state/analytics*")):
        if adir.is_dir():
            total += rollup_analytics(adir, cutoff, args.dry_run)
    for pdir in (ROOT / "state" / "trending_packages",
                 ROOT / "state" / "third_packages"):
        total += archive_packages(pdir, cutoff, args.dry_run)
    print(f"[rollup] {total} items folded" if total else "[rollup] nothing old enough")
    return 0


if __name__ == "__main__":
    sys.exit(main())
