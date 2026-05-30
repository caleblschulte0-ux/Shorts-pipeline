#!/usr/bin/env python3
"""End-to-end trending-topic short.

Chains:
  1. scripts/discover_topic.py  → today's most video-able trend
  2. script_generator.py        → Claude turns it into a script + shots + punches
  3. make_explainer_stacked.py  → renders the actual video

Run with no args to make today's #1 topic. Optional flags let you peek
at the discovery list, force a specific topic, or stop after generating
the script package (useful for review-before-render).

Env: ANTHROPIC_API_KEY, PEXELS_API_KEY, PIXABAY_API_KEY (one or both),
optionally KOKORO_VOICE.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scripts.discover_topic import discover, as_dict  # noqa: E402
import script_generator  # noqa: E402
import make_explainer_stacked  # noqa: E402


OUTPUT_DIR = ROOT / "output"
PACKAGE_DIR = ROOT / "state" / "trending_packages"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", help="skip discovery, use this topic string")
    ap.add_argument("--rank", type=int, default=1,
                    help="pick the Nth-ranked topic (default 1)")
    ap.add_argument("--min-score", type=float, default=4.0,
                    help="floor on discovery score; lower to find more candidates")
    ap.add_argument("--dry-run", action="store_true",
                    help="generate the script package but don't render the video")
    ap.add_argument("--package", type=Path,
                    help="skip discovery + generation, render this saved package")
    ap.add_argument("--model", default=script_generator.DEFAULT_MODEL)
    args = ap.parse_args()

    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Get the script package — either from disk, from a manual topic
    # override, or by discovering today's trend.
    if args.package:
        pkg = json.loads(args.package.read_text())
        print(f"[trending] using saved package: {args.package}")
    else:
        if args.topic:
            topic_query = args.topic
            headlines: list[str] = []
            snippets: list[str] = []
            print(f"[trending] manual topic: {topic_query!r}")
        else:
            print("[trending] discovering trending topics...")
            topics = discover(min_score=args.min_score)
            if not topics:
                print("[trending] no video-able trending topics today "
                      "(lower --min-score, set --topic manually)", file=sys.stderr)
                return 1
            print(f"[trending] {len(topics)} candidates, top 3:")
            for t in topics[:3]:
                print(f"   [{t.score:>5.1f}] {t.query!r}")
            pick = topics[args.rank - 1]
            topic_query = pick.query
            headlines = pick.headlines
            snippets = pick.snippets
            print(f"[trending] selected #{args.rank}: {topic_query!r}")

        # 2. Claude → JSON package.
        print(f"[trending] generating script via {args.model}...")
        pkg = script_generator.generate(topic_query, headlines, snippets, model=args.model)
        ts = time.strftime("%Y%m%d-%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in topic_query.lower())[:40]
        pkg_path = PACKAGE_DIR / f"{ts}_{slug}.json"
        pkg_path.write_text(json.dumps(pkg, indent=2))
        print(f"[trending] script saved: {pkg_path}")
        print(f"[trending] title: {pkg.get('title')!r}")
        print(f"[trending] script ({len(pkg['script'].split())} words):")
        print(f"   {pkg['script']}")

    if args.dry_run:
        print("[trending] --dry-run set, skipping render")
        return 0

    # 3. Render.
    ts = time.strftime("%Y%m%d-%H%M%S")
    out = OUTPUT_DIR / f"trending_{ts}.mp4"
    print(f"[trending] rendering -> {out}")
    make_explainer_stacked.build_from_package(pkg, out)
    print(f"[trending] done: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
