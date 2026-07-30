#!/usr/bin/env python3
"""Reserve package bank — CLI over `shared/package_buffer.py`.

The bank is the pipeline's cover for "the brain went dark": no Routine
run, a revoked CLAUDE_CODE_OAUTH_TOKEN, an expired subscription. While the
brain is healthy it banks EVERGREEN packages; on a dead day `fill` draws
them into the day's package directory and the rest of the pipeline never
notices the difference.

    python scripts/package_reserve.py status
    python scripts/package_reserve.py status --json
    python scripts/package_reserve.py deposit state/trending_packages/_bank/*.json
    python scripts/package_reserve.py deposit --dir state/trending_packages/_bank
    python scripts/package_reserve.py fill --date 20260801 --target 6
    python scripts/package_reserve.py fill --date 20260801 --dry-run
    python scripts/package_reserve.py prune --max-age-days 120

`fill` is a no-op when the day already has `--target` packages, so it is
safe to run unconditionally before every Phase A. It NEVER displaces work
the brain actually produced.

Exit codes: 0 success (including "nothing to do"), 1 a requested fill came
up short, 2 bad arguments.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import package_buffer as buf              # noqa: E402


def cmd_status(args) -> int:
    inv = buf.inventory()
    counts = {f: len(inv.get(f) or []) for f in buf.FORMATS}
    low = buf.low_formats()
    used = buf.drawn_count()
    # Full slates the bank could serve right now, honouring the 2/2/2 mix.
    slates = min(counts[f] // buf.TARGET_MIX[f] for f in buf.FORMATS)
    if args.json:
        print(json.dumps({"counts": counts, "low": low, "slates": slates,
                          "drawn_all_time": used,
                          "low_water": buf.LOW_WATER}, indent=2))
        return 0
    print(f"reserve bank: {sum(counts.values())} package(s), "
          f"{slates} full slate(s) of cover")
    for f in buf.FORMATS:
        mark = "  LOW" if f in low else ""
        print(f"  {f:<13} {counts[f]:>3}  (want >= {buf.LOW_WATER[f]}){mark}")
    print(f"  drawn all time: {used}")
    for f in buf.FORMATS:
        for e in (inv.get(f) or [])[:3]:
            print(f"    {f}: {e['package'].get('slug')} "
                  f"(banked {e.get('banked_at')})")
    if low:
        print(f"::warning::reserve bank is low on {', '.join(low)} — "
              f"the Routine should bank evergreen packages for these")
    return 0


def cmd_deposit(args) -> int:
    paths: list[Path] = [Path(p) for p in args.paths]
    if args.dir:
        paths += sorted(Path(args.dir).glob("*.json"))
    if not paths:
        # An empty inbox is the normal state, not a usage error — CI runs
        # this unconditionally.
        if args.dir:
            print(f"deposit: inbox {args.dir} is empty — nothing to bank")
            return 0
        print("nothing to deposit", file=sys.stderr)
        return 2
    banked = refused = 0
    for p in paths:
        if p.name.startswith("_"):
            continue
        try:
            pkg = json.loads(p.read_text())
        except Exception as exc:                       # noqa: BLE001
            print(f"  REFUSED {p.name}: unreadable ({exc})")
            refused += 1
            continue
        pkg.setdefault("slug", p.stem)
        if args.dry_run:
            ok, problems = buf.eligible(pkg)
            print(f"  {'OK      ' if ok else 'REFUSED '}{p.name}")
            for why in problems:
                print(f"      - {why}")
            banked, refused = banked + ok, refused + (not ok)
            continue
        dest, problems = buf.deposit(pkg, source=args.source,
                                     force=args.force)
        if dest is None:
            refused += 1
            print(f"  REFUSED {p.name}:")
            for why in problems:
                print(f"      - {why}")
        else:
            banked += 1
            print(f"  banked  {p.name} -> {dest.relative_to(ROOT)}")
            if args.delete:
                p.unlink(missing_ok=True)
    print(f"deposit: {banked} banked, {refused} refused")
    return 0


def cmd_fill(args) -> int:
    date = args.date or datetime.now(timezone.utc).strftime("%Y%m%d")
    report = buf.fill_day(date, target=args.target, reason=args.reason,
                          dry_run=args.dry_run)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"reserve fill {date}: {report['existing']} authored, "
              f"target {report['target']}, need {report['need']}")
        for d in report["drawn"]:
            print(f"  drew {d}")
        if report["need"] and not report["drawn"]:
            print("::warning::the day is short and the reserve bank is "
                  "EMPTY — the pipeline will fall to its weaker writers")
        if report["shortfall"]:
            print(f"::warning::reserve fill came up {report['shortfall']} "
                  f"package(s) short")
    if report["need"] and not args.dry_run and report["drawn"]:
        print(f"::notice::reserve served {len(report['drawn'])} package(s) "
              f"for {date} — bank the replacements when the brain is back")
    return 1 if (report["shortfall"] and args.strict) else 0


def cmd_prune(args) -> int:
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=args.max_age_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    dropped = 0
    for e in buf.entries():
        if (e.get("banked_at") or "") < cutoff:
            print(f"  pruning {e['package'].get('slug')} "
                  f"(banked {e.get('banked_at')})")
            if not args.dry_run:
                Path(e["_file"]).unlink(missing_ok=True)
            dropped += 1
    print(f"prune: {dropped} package(s) older than {args.max_age_days}d")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="what the bank holds")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    d = sub.add_parser("deposit", help="bank evergreen packages")
    d.add_argument("paths", nargs="*")
    d.add_argument("--dir", help="bank every *.json in this directory")
    d.add_argument("--source", default="manual")
    d.add_argument("--delete", action="store_true",
                   help="remove the source file once banked")
    d.add_argument("--force", action="store_true",
                   help="bank despite eligibility problems (duplicates are "
                        "still refused)")
    d.add_argument("--dry-run", action="store_true",
                   help="report eligibility, bank nothing")
    d.set_defaults(fn=cmd_deposit)

    f = sub.add_parser("fill", help="draw into a day's package directory")
    f.add_argument("--date", default="")
    f.add_argument("--target", type=int, default=6)
    f.add_argument("--reason", default="brain produced no packages")
    f.add_argument("--dry-run", action="store_true")
    f.add_argument("--strict", action="store_true",
                   help="exit 1 if the fill came up short")
    f.add_argument("--json", action="store_true")
    f.set_defaults(fn=cmd_fill)

    p = sub.add_parser("prune", help="drop stale banked packages")
    p.add_argument("--max-age-days", type=int, default=120)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_prune)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
