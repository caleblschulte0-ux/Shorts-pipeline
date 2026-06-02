"""Free, no-API-key topic-specific image search.

When a shot doesn't supply its own `image_url`, the renderer would
otherwise fall straight through to Pexels/Pixabay stock — which produces
generic-feeling videos ("Anthropic profit story" gets a stock laptop
shot). This module tries three free sources first so the top half of the
frame actually shows what the script is talking about:

  1. Wikipedia article hero (best for named entities — companies, people,
     places, products).
  2. Wikimedia Commons keyword search (broader; pulls in event photos,
     diagrams, logos).
  3. GDELT Doc 2.0 (free, no key) -> news article `socialimage` /
     og:image. This is the "search news of that place" angle: gives
     actual photos of the event under discussion when it's a current
     story.

All three are unlimited and require no API key. Caller passes the
returned URL to the renderer's existing `_fetch_image` cache.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) shorts-pipeline/1.0")
TIMEOUT = 12


def _get(url: str, timeout: int = TIMEOUT) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            # Wikimedia rejects bare urllib UA without an Accept header.
            "Accept": "application/json,text/html,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _wikipedia_image(topic: str) -> str | None:
    """Resolve a topic to a Wikipedia article and return its main image.
    `prop=pageimages&piprop=original` returns the article's lead photo at
    full resolution, which is what Wikipedia itself shows in the infobox."""
    if not topic.strip():
        return None
    qs = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "prop": "pageimages",
        "piprop": "original",
        "redirects": 1,
        "titles": topic,
    })
    try:
        data = json.loads(_get(f"https://en.wikipedia.org/w/api.php?{qs}"))
    except Exception:  # noqa: BLE001
        return None
    pages = (data.get("query") or {}).get("pages") or {}
    for p in pages.values():
        src = (p.get("original") or {}).get("source")
        if src and src.startswith("http"):
            return src
    return None


def _commons_images(topic: str, limit: int = 3) -> list[str]:
    """Search Wikimedia Commons for files matching `topic`. Returns
    thumbnail URLs (1280px) ordered by Commons' own relevance score."""
    if not topic.strip():
        return []
    qs = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": 6,        # File namespace
        "gsrsearch": topic,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "iiurlwidth": 1280,
    })
    try:
        data = json.loads(_get(f"https://commons.wikimedia.org/w/api.php?{qs}"))
    except Exception:  # noqa: BLE001
        return []
    out: list[str] = []
    pages = (data.get("query") or {}).get("pages") or {}
    # Commons returns pages in a dict keyed by page id — order is not
    # guaranteed, so sort by the "index" the search generator assigns.
    ordered = sorted(pages.values(), key=lambda p: p.get("index", 999))
    for p in ordered:
        for ii in p.get("imageinfo", []) or []:
            mime = ii.get("mime", "")
            if not mime.startswith("image/"):
                continue
            url = ii.get("thumburl") or ii.get("url")
            if url and url.startswith("http"):
                out.append(url)
                break
    return out


def _gdelt_news_image(topic: str, max_hours: int = 24 * 30) -> str | None:
    """Search GDELT for recent English-language articles mentioning
    `topic`. Returns the first article's `socialimage` (og:image picked
    up by GDELT's crawler) or, if missing, scrapes og:image from the
    article HTML directly."""
    if not topic.strip():
        return None
    qs = urllib.parse.urlencode({
        "query": f"{topic} sourcelang:eng",
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 5,
        "timespan": f"{max_hours}h",
    })
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?{qs}"
    try:
        data = json.loads(_get(url))
    except Exception:  # noqa: BLE001
        return None
    arts = data.get("articles") or []
    for art in arts:
        img = art.get("socialimage")
        if img and isinstance(img, str) and img.startswith("http"):
            return img
    # Fallback: fetch first article's HTML and scrape og:image.
    for art in arts[:2]:
        page = art.get("url")
        if not page:
            continue
        try:
            html = _get(page, timeout=8).decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        m = re.search(
            r'<meta[^>]+(?:property|name)\s*=\s*["\']og:image["\'][^>]*content\s*=\s*["\']([^"\']+)',
            html, re.I,
        )
        if m:
            cand = m.group(1)
            if cand.startswith("http"):
                return cand
    return None


def search(topic: str, context: str = "") -> list[str]:
    """Return a list of topic-specific image URLs, best first.

    `topic` is the shot's primary keyword (e.g. "cave rescue divers");
    `context` is the broader package title (e.g. "Miners Trapped 10 Days
    Swam Out of the Cave Themselves"). Context disambiguates generic
    shot queries — Wikipedia/GDELT do much better on a real headline
    than on three loose nouns.
    """
    seen: set[str] = set()
    results: list[str] = []

    def _add(u: str | None) -> None:
        if u and u not in seen:
            seen.add(u)
            results.append(u)

    # Wikipedia first — use the package title since it's most likely to
    # name an actual article ("Tesla", "Anthropic", "Strait of Hormuz").
    if context:
        _add(_wikipedia_image(context))
    # Topic alone as a backup in case the title was vague.
    _add(_wikipedia_image(topic))

    # Commons: combined query gets us event/diagram photos. Two results
    # is usually enough — more than that and we're scraping the long tail.
    combined = f"{topic} {context}".strip()
    for url in _commons_images(combined, limit=3):
        _add(url)

    # GDELT: the news angle. Search the combined topic so a story like
    # "Strait of Hormuz deal" lands recent shipping-lane photos rather
    # than the wikipedia article hero.
    _add(_gdelt_news_image(combined))

    return results
