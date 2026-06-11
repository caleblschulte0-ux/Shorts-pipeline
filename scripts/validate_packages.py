#!/usr/bin/env python3
"""Pre-flight coverage check for a day's trending-package directory.

Runs `entity_media.validate_package` against every JSON in the target
directory and prints a per-package coverage report. Exits non-zero
when the worst package falls below `--min-coverage` so the daily
routine can fix the package list BEFORE render time, when the
operator can still re-pick a visual to cover the uncovered entity.

Designed to be fast: the validator only does the LLM round-trip +
shot-phrase matching. It does NOT call Wikipedia/Commons/GDELT
(those happen at render time and add 30s+ per package). One LLM
call per package, ~5s total for a 6-package batch.

Usage:
    python3 scripts/validate_packages.py state/trending_packages/20260608
    python3 scripts/validate_packages.py state/trending_packages/20260608 \
        --min-coverage 80
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import entity_media  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path,
                    help="package directory (e.g. "
                         "state/trending_packages/20260608)")
    ap.add_argument("--min-coverage", type=float, default=70.0,
                    help="fail if any package's shot-coverage % is below "
                         "this (default 70). 100 = every visual the LLM "
                         "names has a shot covering it.")
    ap.add_argument("--min-illustration", type=float, default=0.0,
                    help="fail if any package's ILLUSTRATION coverage %% is "
                         "below this — the fraction of shots that show a real "
                         "image_url or a fundable named entity rather than "
                         "bare keyword stock. Default 0 (off). The daily "
                         "render gate enforces this; set it here (e.g. 60) "
                         "to catch off-topic-imagery slates before render.")
    args = ap.parse_args()

    if not args.dir.is_dir():
        print(f"ERROR: not a directory: {args.dir}", file=sys.stderr)
        return 2

    pkgs = sorted(args.dir.glob("*.json"))
    if not pkgs:
        print(f"no packages in {args.dir}", file=sys.stderr)
        return 0

    worst = 100.0
    worst_illus = 100.0
    failures: list[str] = []
    for p in pkgs:
        try:
            pkg = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"  {p.name}: PARSE FAIL — {e}")
            failures.append(p.name)
            continue
        report = entity_media.validate_package(pkg)
        cov = report["coverage_pct"]
        illus = report.get("illustration_pct", 100.0)
        worst = min(worst, cov)
        worst_illus = min(worst_illus, illus)
        bad = cov < args.min_coverage or illus < args.min_illustration
        flag = "LOW" if bad else "OK"
        title = (pkg.get("title") or "(no title)")[:50]
        print(f"  [{flag}] {p.name}: {cov}% entity-coverage, "
              f"{illus}% illustration "
              f"({len(report['matched'])}/{report['total_visuals']} "
              f"via {report['source']}) — {title!r}")
        if report["uncovered"]:
            print(f"      uncovered entities: {report['uncovered']}")
        if report.get("keyword_only_shots"):
            print(f"      keyword-stock-only shots (pin a real image): "
                  f"{report['keyword_only_shots']}")
        if bad:
            failures.append(p.name)

    print()
    print(f"summary: {len(pkgs)} packages, worst entity-coverage {worst}%, "
          f"worst illustration {worst_illus}%, "
          f"{len(failures)} below threshold "
          f"(coverage<{args.min_coverage}% or illustration<"
          f"{args.min_illustration}%)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
