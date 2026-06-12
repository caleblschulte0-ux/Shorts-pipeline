#!/usr/bin/env python3
"""Deterministically pin an archival image to every shot in a package.

This is the repeatable replacement for hand-curating Wikimedia URLs. The
daily routine writes packages where each shot already carries a `query`
(its stock-search phrase); this tool turns that query into a real,
verified image_url from FREE sources (Wikipedia hero -> Wikimedia Commons
keyword search -> GDELT news photo, via topic_media.search), so a
history/mystery video gets archival imagery on every shot with zero
manual picking and zero API keys.

It reuses the pipeline's own infrastructure:
  - topic_media.search(query, title)  -> candidate URLs, best first
  - entity_media.url_is_image(url)    -> verify each resolves to an image
    (with the Wikimedia-policy User-Agent + 429-tolerant logic)

Run it as a pre-pass between writing a package and rendering it:

    python3 scripts/autofill_images.py state/trending_packages/<date>/0N_slug.json
    python3 scripts/autofill_images.py <dir>            # every *.json in a dir
    python3 scripts/autofill_images.py <pkg> --force    # re-pick even pinned shots

Operator-supplied `image_url`s are kept unless --force is passed. Shots
that resolve to nothing keep their `query` so the renderer's stock path
still covers them. Exit code is non-zero if any shot ended up with no
image (so CI / the routine can flag thin coverage).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import entity_media  # noqa: E402
import topic_media   # noqa: E402

_STOP = frozenset((
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at",
    "is", "are", "was", "were", "by", "with", "as", "it", "from", "this",
    "that", "into", "over", "off", "out", "up",
))


def _fallback_query(phrase: str) -> str:
    """When a shot has no `query`, build one from its content words."""
    words = [w for w in phrase.split() if w.lower() not in _STOP]
    return " ".join(words[:6]) or phrase


def _candidates(query: str, title: str) -> list[str]:
    """Image URLs for a shot, best first. We DON'T use topic_media.search
    here — it concatenates the query with the full title, which
    over-constrains Commons to zero hits on descriptive shot queries.
    Instead: Commons keyword search on the shot's own query (progressively
    shortened until it returns hits), then the Wikipedia hero photo for
    named entities."""
    seen: set[str] = set()
    out: list[str] = []

    def add(u: str | None) -> None:
        if u and u not in seen:
            seen.add(u)
            out.append(u)

    words = query.split()
    for cut in range(len(words), 0, -1):
        hits = topic_media._commons_files(" ".join(words[:cut]), limit=4)
        if hits:
            for u in hits:
                add(u)
            break               # stop at the first variant that returns hits
    add(topic_media._wikipedia_image(query))
    if title:
        add(topic_media._wikipedia_image(title))
    return out


def fill_shot(shot: dict, title: str, *, force: bool) -> bool:
    """Pin a verified image_url on one shot. Returns True if it now has
    one (either kept or newly found)."""
    if shot.get("image_url") and not force:
        return True
    query = shot.get("query") or _fallback_query(shot.get("phrase", ""))
    try:
        candidates = _candidates(query, title)
    except Exception as e:  # noqa: BLE001
        print(f"      search failed for {query!r}: {e}")
        candidates = []
    for url in candidates:
        try:
            if entity_media.url_is_image(url):
                shot["image_url"] = url
                print(f"      [{query[:42]:42s}] -> {url.split('/')[-1][:48]}")
                return True
        except Exception:  # noqa: BLE001
            continue
    print(f"      [{query[:42]:42s}] -> (no image; keeping stock query)")
    return bool(shot.get("image_url"))


def fill_package(path: Path, *, force: bool) -> tuple[int, int]:
    pkg = json.loads(path.read_text())
    title = pkg.get("title", "")
    shots = pkg.get("shots", [])
    print(f"  {path.name}: {len(shots)} shots")
    filled = 0
    for shot in shots:
        if fill_shot(shot, title, force=force):
            filled += 1
        time.sleep(0.3)   # be polite to the free APIs
    path.write_text(json.dumps(pkg, indent=2, ensure_ascii=False) + "\n")
    print(f"  -> {filled}/{len(shots)} shots have an image")
    return filled, len(shots)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", type=Path,
                    help="package .json file or a directory of them")
    ap.add_argument("--force", action="store_true",
                    help="re-pick images even for shots that already have one")
    args = ap.parse_args(argv[1:])

    if args.target.is_dir():
        paths = sorted(args.target.glob("*.json"))
    else:
        paths = [args.target]
    if not paths:
        print(f"no package json found at {args.target}")
        return 2

    total_filled = total_shots = 0
    for p in paths:
        f, n = fill_package(p, force=args.force)
        total_filled += f
        total_shots += n
    print(f"\nDONE: {total_filled}/{total_shots} shots imaged across "
          f"{len(paths)} package(s)")
    return 0 if total_filled == total_shots else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
