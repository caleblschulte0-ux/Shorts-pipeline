#!/usr/bin/env python3
"""Promote ChatGPT-authored packages into a day's slate — validated first.

The other half of the authoring takeover (`shared/authoring_brief.py`). When
Phase A finds the day short it puts an `authoring_request` in the bundle;
ChatGPT writes the missing packages; this promotes them into
`state/trending_packages/<date>/` so the renderer sees an ordinary slate.

Two sources, both read (a connector-limited writer gets more than one shot):

    exchange/bundles/<date>/response.json   -> "authored": [ {package}, ... ]
    exchange/bundles/<date>/authored/*.json -> one package per file

Nothing is trusted. Every package runs the same structural gate the reserve
bank and the renderers use, and anything that fails is QUARANTINED with its
reasons into `exchange/bundles/<date>/authored_report.json` rather than
promoted. A slate of four good packages ships; a broken fifth does not sink
it, and does not silently render either.

    python scripts/ingest_authored.py --date 20260801
    python scripts/ingest_authored.py --date 20260801 --dry-run

Exit 0 always unless the date is unusable — "ChatGPT authored nothing" is a
normal, successful outcome on a day the Routine ran.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared import authoring_brief as brief          # noqa: E402
from shared import exchange_bundle as xb             # noqa: E402
from shared.fsutil import atomic_write_json          # noqa: E402

PACKAGE_DIRS = {"trending": "state/trending_packages",
                "third": "state/third_packages"}


def collect(date: str) -> list[tuple[str, dict]]:
    """(origin, package) pairs from both accepted drop points."""
    out: list[tuple[str, dict]] = []
    response = xb.read_response(date)
    if isinstance(response, dict):
        for pkg in response.get("authored") or []:
            if isinstance(pkg, dict):
                out.append(("response.json", pkg))

    loose = xb.bundle_dir(date) / "authored"
    if loose.is_dir():
        for p in sorted(loose.glob("*.json")):
            try:
                pkg = json.loads(p.read_text())
            except Exception as exc:                  # noqa: BLE001
                print(f"[ingest] unreadable {p.name}: {exc}")
                continue
            if isinstance(pkg, dict):
                pkg.setdefault("slug", p.stem)
                out.append((f"authored/{p.name}", pkg))
    return out


def existing_slate(channel: str, date: str) -> list[dict]:
    day = ROOT / PACKAGE_DIRS.get(channel, PACKAGE_DIRS["trending"]) / str(date)
    if not day.is_dir():
        return []
    pkgs = []
    for p in sorted(day.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            pkgs.append(json.loads(p.read_text()))
        except Exception:                             # noqa: BLE001
            continue
    return pkgs


def ingest(date: str, channel: str = "trending", *, target: int = 6,
           dry_run: bool = False) -> dict:
    """Validate and promote. Returns a report; `promoted` lists the paths
    written (or the slugs, on a dry run). Safe to call unconditionally —
    a day with no ChatGPT-authored packages reports zero of everything."""
    args = argparse.Namespace(date=date, channel=channel, target=target,
                              dry_run=dry_run)

    candidates = collect(args.date)
    if not candidates:
        print(f"[ingest] no ChatGPT-authored packages for {args.date} "
              f"(normal when the Routine ran)")
        return {"date": str(date), "channel": channel, "offered": 0,
                "promoted": [], "rejected": [], "slate_problems": [],
                "slate_size_after": len(existing_slate(channel, date))}

    have = existing_slate(args.channel, args.date)
    known_titles = {(p.get("title") or "").strip() for p in have}
    known_titles |= set(brief._recent_titles(args.channel))
    known_titles.discard("")
    taken_slugs = {(p.get("slug") or "") for p in have}

    day = ROOT / PACKAGE_DIRS[args.channel] / str(args.date)
    room = max(0, args.target - len(have))
    promoted, rejected = [], []

    for origin, pkg in candidates:
        slug = brief.safe_slug(pkg.get("slug") or "")
        problems = brief.validate_authored(pkg, known_titles=known_titles)
        if slug in taken_slugs:
            problems.append(f"slug already in today's slate: {slug}")
        if not problems and len(promoted) >= room:
            problems.append(
                f"slate is full ({args.target}) — not promoted, but nothing "
                f"is wrong with it")
        if problems:
            rejected.append({"origin": origin, "slug": slug,
                             "title": pkg.get("title"), "problems": problems})
            print(f"[ingest] REJECT {origin} ({slug}):")
            for why in problems:
                print(f"           - {why}")
            continue

        pkg = {k: v for k, v in pkg.items() if not k.startswith("_")}
        pkg["slug"] = slug
        pkg["_authored_by"] = "chatgpt-takeover"
        promoted.append(pkg)
        taken_slugs.add(slug)
        if pkg.get("title"):
            known_titles.add(pkg["title"].strip())

    slate_gripes = brief.slate_problems(have + promoted, target=args.target)
    for g in slate_gripes:
        print(f"::warning::[ingest] {g}")

    report = {"date": str(args.date), "channel": args.channel,
              "offered": len(candidates), "promoted": [], "rejected": rejected,
              "slate_problems": slate_gripes,
              "slate_size_after": len(have) + len(promoted)}

    if args.dry_run:
        report["promoted"] = [p.get("slug") for p in promoted]
        print(json.dumps(report, indent=2))
        print("[ingest] dry run — nothing written")
        return report

    day.mkdir(parents=True, exist_ok=True)
    for i, pkg in enumerate(promoted, start=len(have) + 1):
        path = day / f"{i:02d}_{pkg['slug']}.json"
        atomic_write_json(path, pkg)
        report["promoted"].append(str(path.relative_to(ROOT)))
        print(f"[ingest] promoted {path.relative_to(ROOT)}")

    out = xb.bundle_dir(args.date) / "authored_report.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(out, report)
    except Exception:                                 # noqa: BLE001
        pass

    print(f"[ingest] {len(promoted)} promoted, {len(rejected)} rejected — "
          f"slate is now {report['slate_size_after']}/{args.target}")
    if promoted:
        print(f"::notice::ChatGPT authored {len(promoted)} package(s) for "
              f"{args.date} — the Claude brain did not run today")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", required=True)
    ap.add_argument("--channel", default="trending",
                    choices=sorted(PACKAGE_DIRS))
    ap.add_argument("--target", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ingest(args.date, args.channel, target=args.target, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
