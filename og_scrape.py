"""Universal og:image / hero-image scraper.

Every news/social search API returns article URLs. The IMAGE attached
to the search result is usually a small thumbnail or a CDN stub; the
ACTUAL hero photo lives in the article's `<meta property="og:image">`
(or one of its cousins — twitter:image, schema.org ImageObject,
JSON-LD article body, the first big `<img>` in <article>).

This module exposes one function:

    fetch(article_url, *, published_at=None) -> str | None

Returns a verified image URL (guaranteed image/* content-type), or
None if no scrape succeeded. Falls back to the Internet Archive's
Wayback Machine when the live page returns 404/410/451 — common for
hot news content rotated off CDNs within days.

Lifted from and generalized over `topic_media._gdelt_news_image()`
so the entire media funnel can share one battle-hardened scraper.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional


_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_TIMEOUT = 8.0


# Order matters: og:image is the universal canonical, but a handful
# of publishers omit it and only set twitter:image (NYT historically),
# and some bury the hero in JSON-LD only.
_META_PATTERNS = [
    re.compile(
        r'<meta[^>]+property\s*=\s*["\']og:image(?::secure_url)?["\']'
        r'[^>]*content\s*=\s*["\']([^"\']+)',
        re.I),
    re.compile(
        r'<meta[^>]+content\s*=\s*["\']([^"\']+)["\']'
        r'[^>]*property\s*=\s*["\']og:image(?::secure_url)?["\']',
        re.I),
    re.compile(
        r'<meta[^>]+name\s*=\s*["\']twitter:image(?::src)?["\']'
        r'[^>]*content\s*=\s*["\']([^"\']+)',
        re.I),
    re.compile(
        r'<meta[^>]+content\s*=\s*["\']([^"\']+)["\']'
        r'[^>]*name\s*=\s*["\']twitter:image(?::src)?["\']',
        re.I),
    # itemprop image (older schema.org markup).
    re.compile(
        r'<meta[^>]+itemprop\s*=\s*["\']image["\']'
        r'[^>]*content\s*=\s*["\']([^"\']+)',
        re.I),
]

# JSON-LD blocks frequently carry the article hero in
# {"@type":"NewsArticle","image":[…]} — parse those when meta fails.
_JSONLD_RE = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>'
    r'(.*?)</script>',
    re.I | re.S)


def _http_get(url: str, *, max_bytes: int = 600_000) -> Optional[str]:
    """Fetch HTML, cap response size — article pages can be huge and
    we only need the <head>. Returns decoded text or None."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": _UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            raw = r.read(max_bytes)
        return raw.decode("utf-8", errors="ignore")
    except Exception:  # noqa: BLE001 — timeouts, DNS, 5xx, redirects
        return None


def _abs_url(base: str, candidate: str) -> str:
    """Resolve protocol-relative + path-only image URLs against base."""
    if candidate.startswith(("http://", "https://")):
        return candidate
    if candidate.startswith("//"):
        return "https:" + candidate
    return urllib.parse.urljoin(base, candidate)


def _from_meta(html: str, base: str) -> Optional[str]:
    for pat in _META_PATTERNS:
        m = pat.search(html)
        if m:
            u = m.group(1).strip()
            if u and not u.startswith("data:"):
                return _abs_url(base, u)
    return None


def _from_jsonld(html: str, base: str) -> Optional[str]:
    """Walk every JSON-LD <script> block looking for `image`. The
    JSON can be a single object, a list of objects, or @graph-style
    nested — try a few shapes."""
    for m in _JSONLD_RE.finditer(html):
        body = m.group(1).strip()
        if not body:
            continue
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            continue
        for obj in _walk(data):
            img = obj.get("image") if isinstance(obj, dict) else None
            if not img:
                continue
            if isinstance(img, str):
                return _abs_url(base, img)
            if isinstance(img, dict):
                u = img.get("url") or img.get("contentUrl")
                if isinstance(u, str):
                    return _abs_url(base, u)
            if isinstance(img, list) and img:
                first = img[0]
                if isinstance(first, str):
                    return _abs_url(base, first)
                if isinstance(first, dict):
                    u = first.get("url") or first.get("contentUrl")
                    if isinstance(u, str):
                        return _abs_url(base, u)
    return None


def _walk(o):
    """Yield every dict reachable from `o` — handles @graph nesting."""
    if isinstance(o, dict):
        yield o
        # Common nesting: @graph holds the real list.
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for item in o:
            yield from _walk(item)


def _wayback_snapshot(url: str, ts: Optional[str]) -> Optional[str]:
    """Ask the Wayback Machine for the closest snapshot to `ts` (an
    ISO-8601 date or None for 'most recent'). Returns the snapshot's
    archived URL or None."""
    qs = {"url": url}
    if ts:
        # Wayback wants YYYYMMDDhhmmss; tolerate ISO inputs.
        try:
            t = ts.replace("Z", "+00:00")
            d = datetime.fromisoformat(t)
            qs["timestamp"] = d.astimezone(timezone.utc).strftime(
                "%Y%m%d%H%M%S")
        except (ValueError, TypeError):
            pass
    api = ("https://archive.org/wayback/available?"
           + urllib.parse.urlencode(qs))
    try:
        req = urllib.request.Request(api, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.load(r)
    except Exception:  # noqa: BLE001
        return None
    snap = (data.get("archived_snapshots") or {}).get("closest")
    if isinstance(snap, dict) and snap.get("available"):
        return snap.get("url")
    return None


def _verify_image(url: str) -> bool:
    """Lightweight HEAD-with-GET-fallback that returns True only when
    the URL serves an image. Mirrors entity_media.url_is_image but
    inlined here to avoid an import cycle into the funnel."""
    for method in ("HEAD", "GET"):
        try:
            headers = {"User-Agent": _UA}
            if method == "GET":
                headers["Range"] = "bytes=0-0"
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if resp.status in (200, 206) and ctype.startswith("image/"):
                    return True
                if resp.status in (200, 206):
                    return False     # 200 but HTML — not an image
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return False
        except Exception:  # noqa: BLE001
            return False
    return False


def fetch(article_url: str, *,
          published_at: Optional[str] = None) -> Optional[str]:
    """Scrape an article URL for its hero image. Returns a verified
    image URL or None.

    Strategy:
      1. GET the page, try og:image / twitter:image / schema.org meta.
      2. If meta fails, scan JSON-LD for `image` fields.
      3. If both fail OR the discovered URL doesn't actually serve an
         image, retry through the Wayback Machine snapshot nearest to
         `published_at` (or most recent if not provided).
    """
    if not article_url or not article_url.startswith("http"):
        return None
    html = _http_get(article_url)
    if html:
        for finder in (_from_meta, _from_jsonld):
            img = finder(html, article_url)
            if img and _verify_image(img):
                return img
    # Wayback retry — covers CDN-rotated images on hot news.
    snap = _wayback_snapshot(article_url, published_at)
    if not snap:
        return None
    html = _http_get(snap)
    if not html:
        return None
    for finder in (_from_meta, _from_jsonld):
        img = finder(html, snap)
        if img and _verify_image(img):
            return img
    return None


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: python og_scrape.py <article-url> [published-at]")
        sys.exit(1)
    out = fetch(sys.argv[1], published_at=sys.argv[2] if len(sys.argv) > 2 else None)
    print(out or "(no image found)")
