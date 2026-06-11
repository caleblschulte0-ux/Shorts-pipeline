#!/usr/bin/env python3
"""Stop the channel from re-covering subjects it already did.

The explainer channel kept shipping near-duplicates (a second "ocean vs space",
another "loneliness") because the only rule was "don't reuse a slug" — which
misses same-TOPIC, different-slug repeats. This guard works at the TOPIC level.

  python scripts/topic_guard.py --list                 # every subject already covered
  python scripts/topic_guard.py --check "Why flights are always late" rank delays airtravel
        # -> prints the closest existing story + an overlap score; exits 1 if too close

Heuristic, not magic: it tokenises each existing story's title + hook + topics
+ hashtags into a keyword set and compares against the candidate. A score at or
above the threshold means "you've basically done this — pick something else."
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "data_learning" / "niche.config.json"

# Words too generic to signal topic overlap.
_STOP = set("""
the a an and or of to in on for is are was were be been it its your you we our
how why what when where who much more less than that this these those a4 charts
chart data graph explained heres here s not now never ever just only most least
americans american us usa year years from up down by at as with into about
""".split())


def _kw(*texts: str) -> set[str]:
    words = re.findall(r"[a-z]{4,}", " ".join(t.lower() for t in texts if t))
    return {w for w in words if w not in _STOP}


def _story_keywords(s: dict) -> set[str]:
    topics = " ".join(seg.get("topic", "") for seg in s.get("segments", []))
    return _kw(s.get("title", ""), s.get("hook", ""), topics,
               " ".join(s.get("hashtags", [])))


def _load() -> list[dict]:
    return json.loads(CONFIG.read_text()).get("stories", [])


def cmd_list() -> int:
    for s in _load():
        kws = sorted(_story_keywords(s))
        print(f"{s['slug']:28} {s.get('title','')}")
        print(f"    keywords: {', '.join(kws)}")
    return 0


def cmd_check(title: str, keywords: list[str], threshold: float) -> int:
    cand = _kw(title, " ".join(keywords))
    if not cand:
        print("no usable candidate keywords")
        return 0
    worst_slug, worst_score, worst_shared = None, 0.0, set()
    for s in _load():
        existing = _story_keywords(s)
        shared = cand & existing
        # Overlap as a share of the (smaller) candidate set — "how much of this
        # idea is already covered".
        score = len(shared) / max(1, len(cand))
        if score > worst_score:
            worst_slug, worst_score, worst_shared = s["slug"], score, shared
    print(f"candidate keywords: {', '.join(sorted(cand))}")
    print(f"closest existing:   {worst_slug}  (overlap {worst_score:.0%})")
    if worst_shared:
        print(f"shared:             {', '.join(sorted(worst_shared))}")
    if worst_score >= threshold:
        print(f"::error::TOO CLOSE to {worst_slug} (>= {threshold:.0%}). "
              f"Pick a genuinely new subject.")
        return 1
    print("OK — distinct enough.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="list covered subjects")
    ap.add_argument("--check", nargs="+", metavar="TITLE_THEN_KEYWORDS",
                    help="first arg = candidate title, rest = keywords/hashtags")
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="overlap fraction that counts as a duplicate (default 0.5)")
    args = ap.parse_args()
    if args.list:
        return cmd_list()
    if args.check:
        return cmd_check(args.check[0], args.check[1:], args.threshold)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
