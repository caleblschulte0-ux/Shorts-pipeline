"""RSS/Atom research intake — top-of-funnel article discovery, stdlib only.

Channels ask "what happened in my niche today?" — this answers with
normalized entries from any RSS 2.0 or Atom feed, TTL-cached under
cache/funnel/feeds/ so repeated calls inside one run (or across the
actions/cache-persisted CI cache) cost zero network.

    from funnel import feeds
    entries = feeds.entries("https://example.com/rss")   # [] on any failure
    # entry: {title, link, summary, published, source}

Contract matches the funnel: never raises; empty list on any failure.
Pair with funnel.article_extract to turn a chosen link into clean text.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from shared.fsutil import atomic_write_json

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache" / "funnel" / "feeds"
DEFAULT_TTL = 1800  # 30 min — news moves, but a run shouldn't refetch
UA = ("Mozilla/5.0 (compatible; shorts-pipeline-funnel/1.0; "
      "+https://github.com/caleblschulte0-ux/Shorts-pipeline)")

_TAG_STRIP = re.compile(r"<[^>]+>")


def _local(tag: str) -> str:
    """Element tag without namespace."""
    return tag.rsplit("}", 1)[-1].lower()


def _text(el) -> str:
    if el is None:
        return ""
    return _TAG_STRIP.sub(" ", "".join(el.itertext())).strip()


def _parse(xml_text: str, source: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out: list[dict] = []
    rootname = _local(root.tag)

    if rootname == "rss" or rootname == "channel":
        for item in root.iter():
            if _local(item.tag) != "item":
                continue
            e = {"title": "", "link": "", "summary": "", "published": "",
                 "source": source}
            for child in item:
                name = _local(child.tag)
                if name == "title":
                    e["title"] = _text(child)
                elif name == "link":
                    e["link"] = (child.text or "").strip()
                elif name in ("description", "encoded"):
                    if not e["summary"]:
                        e["summary"] = _text(child)[:1000]
                elif name in ("pubdate", "date"):
                    e["published"] = _text(child)
            if e["title"] or e["link"]:
                out.append(e)

    elif rootname == "feed":  # Atom
        for entry in root.iter():
            if _local(entry.tag) != "entry":
                continue
            e = {"title": "", "link": "", "summary": "", "published": "",
                 "source": source}
            for child in entry:
                name = _local(child.tag)
                if name == "title":
                    e["title"] = _text(child)
                elif name == "link":
                    href = child.attrib.get("href", "")
                    rel = child.attrib.get("rel", "alternate")
                    if href and (rel == "alternate" or not e["link"]):
                        e["link"] = href
                elif name in ("summary", "content"):
                    if not e["summary"]:
                        e["summary"] = _text(child)[:1000]
                elif name in ("published", "updated"):
                    if not e["published"]:
                        e["published"] = _text(child)
            if e["title"] or e["link"]:
                out.append(e)

    return out


def parse_feed_text(xml_text: str, source: str = "") -> list[dict]:
    """Parse feed XML you already have (offline/testing path)."""
    try:
        return _parse(xml_text, source)
    except Exception:
        return []


def entries(url: str, *, ttl: int = DEFAULT_TTL, limit: int = 50,
            timeout: int = 20) -> list[dict]:
    """Fetch + parse a feed with TTL cache. [] on any failure."""
    try:
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        cache_file = CACHE_DIR / f"{key}.json"
        now = time.time()
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text())
                if now - cached.get("fetched_at", 0) < ttl:
                    return cached.get("entries", [])[:limit]
            except Exception:
                pass
        req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                   "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(4_000_000).decode("utf-8", "replace")
        parsed = _parse(body, source=url)[:limit]
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(cache_file, {"fetched_at": now, "url": url,
                                       "entries": parsed})
        return parsed
    except Exception:
        return []


def multi(urls: list[str], *, per_feed: int = 20, **kw) -> list[dict]:
    """Entries from several feeds, interleaved newest-ish first (source
    order preserved round-robin so one giant feed can't drown the rest)."""
    pools = [entries(u, limit=per_feed, **kw) for u in urls]
    out: list[dict] = []
    for i in range(per_feed):
        for pool in pools:
            if i < len(pool):
                out.append(pool[i])
    return out
