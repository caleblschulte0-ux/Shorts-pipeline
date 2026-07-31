#!/usr/bin/env python3
"""Warm the provider cache for a story's subjects, ahead of a render.

Originally written to work around Pexels 403s. Those turned out to be a missing
User-Agent in our own request (data_learning/stock.py), not an outage, a key or
an IP block — so this is no longer required to get Pexels footage.

It stays because it is still worth having: it proves in seconds, before an
hour-long render, that every beat's subject actually resolves to candidates, and
it leaves a cached answer if a provider is ever down or rate-limited when the
render runs.

Only the candidate LIST is written — titles, licences, CDN urls, a few KB of
JSON per query. Never media: the storage audit forbids committing binaries.

    python scripts/prefetch_media.py shared-air
    python scripts/prefetch_media.py --all
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import stock, stock_cache  # noqa: E402

STORIES = REPO / "data_learning" / "pro_stories"
PROVIDERS = (("pexels", stock.search_pexels), ("pixabay", stock.search_pixabay))


def queries_of(path: Path) -> list[str]:
    """Every subject the story will actually search for, in beat order."""
    out, seen = [], set()
    for b in json.loads(path.read_text()).get("beats", []):
        for q in (str((b.get("image") or {}).get("query", "")).strip(),
                  str(b.get("subject", "")).strip()):
            if q and q.lower() not in seen:
                seen.add(q.lower())
                out.append(q)
    return out


def main(argv) -> int:
    slugs = [a for a in argv if not a.startswith("-")]
    if "--all" in argv:
        slugs = sorted(p.name.split(".")[0] for p in STORIES.glob("*.beats.json"))
    if not slugs:
        print(__doc__.strip().splitlines()[-2].strip())
        return 2
    total, filled = 0, 0
    for slug in slugs:
        path = STORIES / f"{slug}.beats.json"
        if not path.exists():
            print(f"no such story: {slug}", file=sys.stderr)
            return 1
        qs = queries_of(path)
        print(f"\n=== {slug}: {len(qs)} subject(s) ===")
        for q in qs:
            total += 1
            got = {}
            for name, fn in PROVIDERS:
                # call the PRIVATE fn so the cache wrapper cannot hand us back
                # its own earlier answer and call that a fresh fetch
                live = getattr(stock, f"_search_{name}")
                try:
                    c = live(q, 8) or []
                except Exception as e:  # noqa: BLE001 — one dead provider is not fatal
                    c = []
                    print(f"  {name:<8} FAILED ({str(e)[:44]})")
                if c:
                    stock_cache.save(name, q, c)
                    got[name] = len(c)
            if got:
                filled += 1
            print(f"  {q[:44]:<46} " + (", ".join(f"{k}={v}" for k, v in got.items())
                                        or "NOTHING — this beat will fall back"))
    print(f"\n{filled}/{total} subject(s) now have pre-fetched candidates -> "
          f"{stock_cache.ROOT.relative_to(REPO)}")
    print("Commit that directory; the render will use it wherever a provider "
          "refuses the call.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
