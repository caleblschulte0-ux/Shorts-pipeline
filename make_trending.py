#!/usr/bin/env python3
"""Trending-topic short workflow.

Two modes:

  Default (no flags): discover trending topics and exit. The intended
  flow is then to hand-author a script package and render it via
  make_explainer_stacked.py --package <file>. Hand-written scripts
  produce noticeably better videos than the LLM, so this is the
  recommended path.

  --auto: run the full LLM-script pipeline (Groq → script → render).
  Kept for cases where you want a fast first draft without writing
  the script yourself.

Always-available:
  --package <file>  render an existing script package, skip discovery + LLM.
  --topic <str>     force a specific topic instead of discovery.
  --dry-run         in --auto mode, generate the package but skip rendering.

Env: PEXELS_API_KEY + PIXABAY_API_KEY for stock fallback, KOKORO_VOICE
optional. GROQ_API_KEY only needed if you pass --auto.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scripts.discover_topic import discover, discover_all, as_dict  # noqa: E402
from scripts import rank_topics  # noqa: E402
import script_generator  # noqa: E402
import make_explainer_stacked  # noqa: E402


OUTPUT_DIR = ROOT / "output"
PACKAGE_DIR = ROOT / "state" / "trending_packages"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true",
                    help="run the LLM pipeline end-to-end instead of just "
                         "listing topics. Requires GROQ_API_KEY (or other backend).")
    ap.add_argument("--topic", help="skip discovery, use this topic string")
    ap.add_argument("--rank", type=int, default=1,
                    help="pick the Nth-ranked topic (default 1)")
    ap.add_argument("--min-score", type=float, default=4.0,
                    help="floor on discovery score; lower to find more candidates")
    ap.add_argument("--limit", type=int, default=10,
                    help="how many topics to list in discover-only mode")
    ap.add_argument("--dry-run", action="store_true",
                    help="in --auto mode, generate the package but don't render")
    ap.add_argument("--package", type=Path,
                    help="skip discovery + generation, render this saved package")
    ap.add_argument("--backend", choices=("groq", "gemini", "anthropic"),
                    help="force a specific LLM backend (only relevant with --auto)")
    ap.add_argument("--model", help="override the model name for the chosen backend")
    args = ap.parse_args()

    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Render-only path: pre-built package, no LLM, no discovery.
    if args.package:
        pkg = json.loads(args.package.read_text())
        print(f"[trending] using saved package: {args.package}")
        ts = time.strftime("%Y%m%d-%H%M%S")
        out = OUTPUT_DIR / f"trending_{ts}.mp4"
        print(f"[trending] rendering -> {out}")
        make_explainer_stacked.build_from_package(pkg, out)
        print(f"[trending] done: {out}")
        return 0

    # Discovery (always runs unless --topic overrides).
    if args.topic:
        topic_query = args.topic
        headlines: list[str] = []
        snippets: list[str] = []
        print(f"[trending] manual topic: {topic_query!r}")
    elif not args.auto:
        # Discover-only mode: multi-source fetch + Groq ranking, then
        # print picks and exit so the operator can hand-author a script
        # package for whichever one they want.
        print("[trending] fetching from all sources...")
        raw = discover_all()
        print(f"[trending] {len(raw)} raw candidates from {len(set().union(*(set(t.sources) for t in raw if t.sources)))} sources",
              file=sys.stderr)
        if not raw:
            print("[trending] no candidates from any source — check network", file=sys.stderr)
            return 1

        if os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
            print("[trending] asking Groq to rank...")
            picks = rank_topics.rank(raw, top_k=args.limit, backend=args.backend, model=args.model)
            print(f"\n[trending] top {len(picks)} picks:\n")
            for i, t in enumerate(picks, 1):
                print(f"  {i}. [{t.score:>4.1f}/10] {t.query[:90]}")
                if t.angle:
                    print(f"      angle:  {t.angle}")
                print(f"      source: {','.join(t.sources[:3])}")
                if t.urls:
                    print(f"      url:    {t.urls[0]}")
                print()
        else:
            # No LLM key — fall back to keyword heuristic on Trends-only
            # subset (the only source with proper traffic + context).
            print("[trending] no LLM key set — falling back to keyword heuristic",
                  file=sys.stderr)
            trends_only = [t for t in raw if any("google_trends" in s for s in t.sources)]
            from scripts.discover_topic import _score
            for t in trends_only:
                t.score = _score(t)
            trends_only.sort(key=lambda x: -x.score)
            for i, t in enumerate(trends_only[:args.limit], 1):
                print(f"  {i:2d}. [{t.score:>5.1f}] {t.query!r}  traffic={t.traffic}")
                for hl in t.headlines[:2]:
                    print(f"        - {hl[:110]}")

        print("Pick one, hand-write a script package JSON, then render:")
        print("  python3 make_explainer_stacked.py --package <file>.json")
        return 0
    else:
        # --auto path: discovery only on Trends US (the single-geo
        # rank-by-heuristic path), then LLM-write the script. Same as
        # before — quality is lower than hand-written but useful for
        # quick smoke tests.
        print("[trending] discovering trending topics (Trends US only)...")
        topics = discover(min_score=args.min_score)
        if not topics:
            print("[trending] no video-able trending topics right now "
                  "(lower --min-score, or set --topic manually)", file=sys.stderr)
            return 1
        pick = topics[args.rank - 1]
        topic_query = pick.query
        headlines = pick.headlines
        snippets = pick.snippets
        print(f"[trending] selected #{args.rank}: {topic_query!r}")

    # --auto path: LLM generates the script, then render.
    backend_label = args.backend or (
        "groq" if os.environ.get("GROQ_API_KEY") else
        "gemini" if os.environ.get("GEMINI_API_KEY") else
        "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else
        "(none — set GROQ_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY)"
    )
    print(f"[trending] generating script via {backend_label}...")
    pkg = script_generator.generate(topic_query, headlines, snippets,
                                    backend=args.backend, model=args.model)
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

    ts = time.strftime("%Y%m%d-%H%M%S")
    out = OUTPUT_DIR / f"trending_{ts}.mp4"
    print(f"[trending] rendering -> {out}")
    make_explainer_stacked.build_from_package(pkg, out)
    print(f"[trending] done: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
