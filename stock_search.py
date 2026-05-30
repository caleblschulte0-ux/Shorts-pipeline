#!/usr/bin/env python3
"""Unified stock video search across multiple providers.

Queries every configured provider, pools the candidates, ranks them by
relevance (the provider's own search rank) with resolution as a soft
tiebreaker, and downloads the best one that we can actually fetch. If
the top pick fails to download we walk down the ranked list rather than
abandoning to the next provider entirely.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


# Soft tiebreak: when two candidates tie on rank, prefer the provider
# with historically tighter curation. Pexels' curation is stricter than
# Pixabay's, but Pixabay still wins when it's strictly better-ranked.
_PROVIDER_TIEBREAK = {"pexels": 0, "pixabay": 1}


def _collect(query: str, **kwargs) -> tuple[list[dict], list[str]]:
    """Run every configured provider's search() and aggregate candidates.
    Returns (candidates, errors). Each candidate gets `provider` and
    `rank` (its position within that provider's results) added."""
    candidates: list[dict] = []
    errors: list[str] = []

    providers = []
    if os.environ.get("PEXELS_API_KEY"):
        import pexels_search
        providers.append(("pexels", pexels_search))
    if os.environ.get("PIXABAY_API_KEY"):
        import pixabay_search
        providers.append(("pixabay", pixabay_search))

    if not providers:
        raise RuntimeError("no stock providers configured (set PEXELS_API_KEY and/or PIXABAY_API_KEY)")

    for name, mod in providers:
        try:
            # Each provider's search() accepts the same canonical kwargs
            # (min_duration, max_duration, per_page). Pixabay's orientation
            # differs lexically ("horizontal" vs "landscape") so the
            # module owns its own default.
            results = mod.search(query, **{k: v for k, v in kwargs.items()
                                           if k in ("per_page", "min_duration", "max_duration")})
            for rank, r in enumerate(results):
                r["provider"] = name
                r["rank"] = rank
                candidates.append(r)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {type(e).__name__}: {e}")
    return candidates, errors


def _score_key(c: dict) -> tuple:
    """Sort key: lower-is-better.
      1. API rank (most relevant first)
      2. Provider tiebreak (curated > broad)
      3. Resolution (higher first, encoded as negative width)
    """
    return (
        int(c.get("rank", 999)),
        _PROVIDER_TIEBREAK.get(c.get("provider", ""), 9),
        -int(c.get("width") or 0),
    )


def _download(c: dict, dest: Path) -> Path:
    """Dispatch to the right provider's downloader."""
    if c["provider"] == "pexels":
        import pexels_search
        path = dest / f"pexels_{c['id']}.mp4"
        if not path.exists():
            pexels_search.download(c, path)
        return path
    if c["provider"] == "pixabay":
        import pixabay_search
        path = dest / f"pixabay_{c['id']}.mp4"
        if not path.exists():
            pixabay_search.download(c, path)
        return path
    raise RuntimeError(f"unknown provider: {c.get('provider')!r}")


def fetch_top(query: str, dest: Path, **kwargs) -> dict:
    """Aggregate candidates across all providers, sort by relevance, and
    return the best one we can download. Raises if every candidate fails."""
    candidates, errors = _collect(query, **kwargs)
    if not candidates:
        msg = f"no stock results for query: {query!r}"
        if errors:
            msg += "\n  " + "\n  ".join(errors)
        raise RuntimeError(msg)

    candidates.sort(key=_score_key)
    dest.mkdir(parents=True, exist_ok=True)

    for c in candidates[:6]:  # cap attempts so one bad query can't loop forever
        try:
            path = _download(c, dest)
            c["path"] = str(path)
            c["source"] = c["provider"]
            return c
        except Exception as e:  # noqa: BLE001
            errors.append(f"{c['provider']}#{c['rank']} ({c.get('id')}): {type(e).__name__}: {e}")
            continue

    raise RuntimeError(f"all stock candidates failed for {query!r}:\n  " + "\n  ".join(errors))


def list_candidates(query: str, top_n: int = 10, **kwargs) -> list[dict]:
    """Diagnostic helper: return the ranked candidate list without
    downloading. Useful for debugging poor matches."""
    candidates, _ = _collect(query, **kwargs)
    candidates.sort(key=_score_key)
    return candidates[:top_n]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: stock_search.py 'query' [dest_dir]")
    import json
    q = sys.argv[1]
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/stock")
    if os.environ.get("STOCK_LIST"):
        for c in list_candidates(q):
            print(f"  {c['provider']:8s} #{c['rank']:<2d} {c['width']}x{c['height']} "
                  f"{c['duration']}s  {c.get('url')}")
    else:
        print(json.dumps(fetch_top(q, dest), indent=2))
