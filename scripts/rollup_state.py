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

from fsutil import atomic_write_json, load_json  # noqa: E402

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
        snap = load_json(f, None)
        if snap is None:
            continue
        roll_path = adir / "rollup" / f"{month}.json"
        roll = monthly.setdefault(month, load_json(
            roll_path, {"month": month, "days": {}, "videos": {}}))
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
        arch_path = pdir / "archive" / f"{month}.json"
        arch = monthly.setdefault(month, load_json(arch_path, {}))
        day = arch.setdefault(d.name, {})
        for f in sorted(d.glob("*.json")):
            day[f.name] = load_json(f, None)
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
