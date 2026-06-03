#!/usr/bin/env python3
"""Generate data-driven micro-learning packages for Shorts-pipeline.

This is the add-on's entrypoint. For each video in ``niche.config.json`` it:

    fetch dataset -> build insight -> render chart PNG -> build package
                  -> QA validate -> write package JSON (+ chart)

The package JSON matches the base-pipeline schema, so the *unchanged*
orchestrator (``scripts/run_trending_daily.py``) can render + upload it.

By default packages land in a REVIEW folder (``data_learning/review/<date>/``)
— a human-approval gate, as recommended for an automated channel. Pass
``--publish`` to write straight into ``state/trending_packages/<date>/`` so
the daily workflow renders them with no other changes.

Examples:
    python -m data_learning.generate                 # all videos -> review/
    python -m data_learning.generate --slug inflation-pain-points
    python -m data_learning.generate --publish       # into the daily pipeline
    python -m data_learning.generate --no-chart      # skip matplotlib charts
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running both as a module (-m data_learning.generate) and directly.
PKG_DIR = Path(__file__).resolve().parent
REPO = PKG_DIR.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import charts, insights, packager, qa          # noqa: E402
from data_learning.sources import get_source                       # noqa: E402
from data_learning.sources.offline import OfflineSource            # noqa: E402

CONFIG_PATH = PKG_DIR / "niche.config.json"


def _date() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _resolve_baseline(spec: dict, src) -> dict | None:
    """Pull the optional baseline block. Offline datasets embed it; live
    adapters can carry it via params['baseline']."""
    if not spec.get("use_baseline"):
        return None
    if isinstance(src, OfflineSource):
        return src.baseline(spec["key"], spec.get("params"))
    return (spec.get("params") or {}).get("baseline")


def generate_one(spec: dict, cfg: dict, *, date_str: str, chart: bool) -> dict:
    """Produce one package dict for a single video spec."""
    src = get_source(spec["source"])
    dataset = src.fetch(spec["key"], spec.get("params"))
    baseline = _resolve_baseline(spec, src)

    insight = insights.build(
        dataset,
        insight_type=spec.get("insight_type", "auto"),
        baseline=baseline,
        ascending=bool(spec.get("ascending", False)),
    )
    # Optional clean topic override for titling + chart heading.
    if spec.get("topic"):
        insight.topic = spec["topic"]

    chart_rel = None
    if chart:
        chart_dir = PKG_DIR / "charts" / date_str
        chart_abs = chart_dir / f"{spec['slug']}.png"
        result = charts.render_chart(insight, chart_abs)
        if result is not None:
            # Repo-relative path resolves at render time (orchestrator runs
            # from repo root; the base renderer accepts local paths).
            chart_rel = str(chart_abs.relative_to(REPO))

    pkg = packager.build_package(
        insight,
        slug=spec["slug"],
        chart_path=chart_rel,
        hashtags=spec.get("hashtags", []),
        music_vibe=spec.get("music_vibe", cfg.get("music_vibe", "cinematic")),
        query_theme=spec.get("query_theme", cfg.get("query_theme",
                                                     "data chart statistics")),
    )
    return pkg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=CONFIG_PATH,
                    help="niche config JSON (default: data_learning/niche.config.json)")
    ap.add_argument("--slug", help="only generate the video with this slug")
    ap.add_argument("--publish", action="store_true",
                    help="write into state/trending_packages/<date>/ for the "
                         "daily workflow (default: review folder, human gate)")
    ap.add_argument("--out-dir", type=Path,
                    help="explicit output dir (overrides --publish)")
    ap.add_argument("--no-chart", action="store_true",
                    help="skip matplotlib chart rendering")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if any package fails QA")
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text())
    date_str = _date()

    if args.out_dir:
        out_dir = args.out_dir
    elif args.publish:
        out_dir = REPO / "state" / "trending_packages" / date_str
    else:
        out_dir = PKG_DIR / "review" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    videos = cfg.get("videos", [])
    if args.slug:
        videos = [v for v in videos if v.get("slug") == args.slug]
        if not videos:
            print(f"no video with slug {args.slug!r} in config", file=sys.stderr)
            return 2

    allowlist = cfg.get("source_allowlist")
    n_ok = n_fail = 0
    for i, spec in enumerate(videos, 1):
        slug = spec.get("slug", f"video{i}")
        try:
            pkg = generate_one(spec, cfg, date_str=date_str,
                               chart=not args.no_chart)
        except Exception as e:  # noqa: BLE001 — one bad video shouldn't tank batch
            print(f"[{slug}] FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            n_fail += 1
            continue

        errors = qa.validate(pkg, source_allowlist=allowlist)
        out_path = out_dir / f"{i:02d}_{slug}.json"
        out_path.write_text(json.dumps(pkg, indent=2) + "\n")

        if errors:
            n_fail += 1
            print(f"[{slug}] QA FAIL ({len(errors)}):", file=sys.stderr)
            for e in errors:
                print(f"    - {e}", file=sys.stderr)
        else:
            n_ok += 1
            chart_note = "with chart" if pkg["shots"][1].get("image_url") else "no chart"
            print(f"[{slug}] ok ({chart_note}) -> {out_path.relative_to(REPO)}")

    print(f"\n=== {n_ok} ok, {n_fail} failed -> {out_dir.relative_to(REPO)} ===")
    if args.strict and n_fail:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
