"""Mixkit free-stock-video scraper.

Mixkit's per-category pages expose direct CDN MP4 URLs without
authentication. We use it as a no-API-key stock-video provider so
local/offline renders can still get topical B-roll. Pexels and
Pixabay remain primary in production; this is the safety net.

The provider mirrors the search() contract in pexels_search /
pixabay_search so stock_search can swap it in transparently.
"""
from __future__ import annotations

import re
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 shorts-pipeline/1.0"
TIMEOUT = 15

# Mixkit category pages live at /free-stock-video/<slug>/. Multi-word
# queries become hyphen-separated slugs. Many shot queries are too long
# to match a real category, so we progressively shorten them until we
# hit one with results.
_BASE = "https://mixkit.co/free-stock-video"


def _slugify(q: str) -> str:
    s = re.sub(r"[^A-Za-z0-9\s-]", "", q.lower()).strip()
    return re.sub(r"\s+", "-", s)


def _fetch_video_ids(slug: str) -> list[str]:
    """Hit the category page and return the unique video IDs found in
    its CDN URLs. Returns [] for 404 or empty pages."""
    url = f"{_BASE}/{slug}/"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        html = urllib.request.urlopen(req, timeout=TIMEOUT).read().decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return []
    # CDN URL: https://assets.mixkit.co/videos/{id}/{id}-1080.mp4
    ids = re.findall(r"https://assets\.mixkit\.co/videos/(\d+)/\d+-1080\.mp4", html)
    seen: set[str] = set()
    out: list[str] = []
    for vid in ids:
        if vid in seen:
            continue
        seen.add(vid)
        out.append(vid)
    return out


def _query_variants(query: str) -> list[str]:
    """Try the full query, then progressively shorter prefixes, then
    each individual keyword. Mixkit has roughly 5k category pages so
    short common nouns hit more often than long phrases."""
    tokens = [t for t in re.split(r"\s+", query.strip()) if t]
    variants: list[str] = []
    seen: set[str] = set()

    def _add(toks: list[str]) -> None:
        s = _slugify(" ".join(toks))
        if s and s not in seen:
            seen.add(s)
            variants.append(s)

    # Full query, then drop one token from the tail at a time.
    for cut in range(len(tokens), 0, -1):
        _add(tokens[:cut])
    # Each token alone (common nouns are the most likely Mixkit categories).
    for t in tokens:
        _add([t])
    return variants


def search(query: str, per_page: int = 8, min_duration: float = 2.0,
           max_duration: float = 30.0) -> list[dict]:
    """Return up to per_page candidate clips matching `query`. Each item
    is a dict shaped like the other providers' so stock_search can rank
    cross-provider without special-casing. Duration is omitted (Mixkit
    pages don't expose it); the renderer trims as needed."""
    ids: list[str] = []
    for variant in _query_variants(query):
        ids = _fetch_video_ids(variant)
        if ids:
            break
    out: list[dict] = []
    for i, vid in enumerate(ids[:per_page]):
        out.append({
            "url": f"https://assets.mixkit.co/videos/{vid}/{vid}-1080.mp4",
            "width": 1920,
            "height": 1080,
            # Mixkit clips are typically 5-15s; report a midpoint so
            # the renderer's seek logic stays inside the actual file.
            "duration": 8.0,
            "id": vid,
        })
    return out


def download(item: dict, dest_dir) -> "Path":
    """Download a search() result to dest_dir, return the local Path."""
    from pathlib import Path
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"mixkit_{item['id']}.mp4"
    if out.exists() and out.stat().st_size > 1024:
        return out
    req = urllib.request.Request(item["url"], headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        out.write_bytes(r.read())
    return out
