#!/usr/bin/env python3
"""Unified stock video search across multiple providers.

Tries each configured provider in order until one returns a usable
match. Lets the caller specify a single per-shot query and not worry
about which API has the best match for it.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def fetch_top(query: str, dest: Path, **kwargs) -> dict:
    """Try providers in priority order (Pexels → Pixabay) and return the
    first one that yields a downloadable match. Raises if all fail."""
    errors: list[str] = []
    providers: list[tuple[str, callable]] = []

    if os.environ.get("PEXELS_API_KEY"):
        import pexels_search
        providers.append(("pexels", pexels_search.fetch_top))
    if os.environ.get("PIXABAY_API_KEY"):
        import pixabay_search
        providers.append(("pixabay", pixabay_search.fetch_top))

    if not providers:
        raise RuntimeError("no stock providers configured (set PEXELS_API_KEY and/or PIXABAY_API_KEY)")

    for name, fn in providers:
        try:
            top = fn(query, dest, **kwargs)
            top.setdefault("source", name)
            return top
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {type(e).__name__}: {e}")
            continue

    raise RuntimeError(f"all stock providers failed for {query!r}:\n  " + "\n  ".join(errors))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: stock_search.py 'query' [dest_dir]")
    import json
    q = sys.argv[1]
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/stock")
    print(json.dumps(fetch_top(q, dest), indent=2))
