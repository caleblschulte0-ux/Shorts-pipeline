"""Wide-funnel news-image resolver.

The encyclopedia + stock stack the renderer used to lean on
(Wikipedia, Commons, Pexels, Pixabay) is useless for current news —
none of it carries today's photos of today's people. This module
fans out across ~13 free sources at once, expands every article URL
through `og_scrape.fetch()` (Wayback fallback included), verifies
every candidate is actually an image, scores them, and returns a
ranked list.

Providers, free-tier and no credit card unless noted:

  News-search APIs (5, email signup, key in env):
    NewsAPI.org        NEWSAPI_KEY        100 req/day
    GNews.io           GNEWS_KEY          100 req/day
    Brave Search News  BRAVE_KEY          2000 req/mo
    Tavily Search      TAVILY_KEY         1000 req/mo
    NewsData.io        NEWSDATA_KEY       200 req/day

  Social / forum (no auth):
    Reddit JSON deep   (fan-out across topical subreddits)
    Mastodon federated search
    Bluesky public search

  Image hosts:
    Imgur              IMGUR_CLIENT_ID    12,500 req/day
    DuckDuckGo Images  (unofficial vqd-token flow, no auth)

  Existing-but-fixed:
    Vimeo thumbnails   VIMEO_TOKEN        already wired
    YouTube thumbnails YOUTUBE_API_KEY    already wired

  Universal helpers (used on every article URL the others return):
    og:image scraper   og_scrape.fetch()
    Wayback Machine    (fallback in og_scrape)

Public API:
    search(story_angle: str, entities: list[str], hashtags=None)
        -> list[Candidate]
    Candidate = dict with keys:
        url, source, score, article_title, article_url, published_at

CLI: ``python media_funnel.py --probe "Brad Paisley"
                              --angle "country star opposes Nashville
                              data center"``
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


# Cache + quota JSON files are read/written by every provider thread
# in the parallel fan-out. Without a process-wide lock the renames
# race (same `.tmp` name across writers) and writes go missing or
# 404 on the rename target. One lock per file gives us both
# correctness and high enough throughput because reads are cheap
# in-memory after the first hit.
_CACHE_LOCK = threading.Lock()
_QUOTA_LOCK = threading.Lock()

import og_scrape


ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
CACHE_PATH = STATE_DIR / "news_image_cache.json"
QUOTA_PATH = STATE_DIR / "news_image_quota.json"

# 48-hour TTL — news photos roll off CDNs; same story re-rendered
# tomorrow might find better photos.
CACHE_TTL_SEC = 48 * 3600

# Bot-respectful UAs per platform. Reddit/Mastodon/Bluesky all ban
# generic UAs; rotating to platform-appropriate ones keeps us out of
# the spam buckets.
_UA_GENERIC = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
_UA_REDDIT = "shorts-pipeline:media-funnel:1.0 (by /u/caleblschulte0)"
_UA_MASTODON = "shorts-pipeline-media-funnel/1.0"
_UA_BLUESKY = _UA_MASTODON

_TIMEOUT = 6.0

# Regex that flags a candidate URL as junk (avatars, placeholders, etc.)
# These keep slipping through search APIs as "thumbnails" and lying
# about being content images.
_JUNK_URL = re.compile(
    r"/(avatar|placeholder|default|logo|icon|sprite|og-?default|"
    r"grey[-_]?square|missing|spacer|blank)/?",
    re.I,
)


# ---------- candidate ----------

@dataclass
class Candidate:
    url: str
    source: str
    article_title: str = ""
    article_url: str = ""
    published_at: str = ""    # ISO-8601 or empty
    score: float = 0.0
    # Internal — set during prefilter, used by the LLM reranker.
    boosts: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"url": self.url, "source": self.source,
                "score": round(self.score, 3),
                "article_title": self.article_title,
                "article_url": self.article_url,
                "published_at": self.published_at}


# ---------- cache + quota ----------

def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def _cache_key(story_slug: str, entity: str) -> str:
    return hashlib.sha1(
        f"{story_slug}|{entity.lower()}".encode("utf-8")
    ).hexdigest()


def _cache_get(story_slug: str, entity: str) -> Optional[list[dict]]:
    with _CACHE_LOCK:
        cache = _load_json(CACHE_PATH)
    rec = cache.get(_cache_key(story_slug, entity))
    if not rec:
        return None
    if time.time() - rec.get("ts", 0) > CACHE_TTL_SEC:
        return None
    return rec.get("candidates")


def _cache_put(story_slug: str, entity: str,
               candidates: list[Candidate]) -> None:
    with _CACHE_LOCK:
        cache = _load_json(CACHE_PATH)
        cache[_cache_key(story_slug, entity)] = {
            "ts": time.time(),
            "entity": entity,
            "story_slug": story_slug,
            "candidates": [c.to_dict() for c in candidates],
        }
        _save_json(CACHE_PATH, cache)


def _quota_check(provider: str, *, daily: int = 0,
                 monthly: int = 0) -> bool:
    """Returns True if the provider still has budget. Bumps the
    counter optimistically (decrement on failure if you care, but the
    free tiers all have enough slack that off-by-N is fine).

    Locked because every provider thread hits this concurrently."""
    with _QUOTA_LOCK:
        q = _load_json(QUOTA_PATH)
        rec = q.get(provider) or {}
        today = date.today().isoformat()
        month = today[:7]
        if rec.get("date") != today:
            rec = {"date": today, "month": month, "day_count": 0,
                   "month_count": rec.get("month_count", 0)
                   if rec.get("month") == month else 0}
        if rec.get("month") != month:
            rec["month"] = month
            rec["month_count"] = 0
        if daily and rec["day_count"] >= daily:
            return False
        if monthly and rec["month_count"] >= monthly:
            return False
        rec["day_count"] = rec["day_count"] + 1
        rec["month_count"] = rec["month_count"] + 1
        q[provider] = rec
        _save_json(QUOTA_PATH, q)
    return True


# ---------- HTTP helpers ----------

def _get(url: str, *, headers: Optional[dict] = None,
         timeout: float = _TIMEOUT) -> Optional[dict]:
    """JSON GET helper. Returns parsed dict/list or None on any
    error (timeout, 4xx/5xx, bad JSON). Single shared style across
    every provider."""
    h = {"User-Agent": _UA_GENERIC, "Accept": "application/json"}
    if headers:
        h.update(headers)
    try:
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "")
            if "json" not in ct and not data.lstrip().startswith((b"{", b"[")):
                return None
            return json.loads(data.decode("utf-8", errors="ignore"))
    except Exception:  # noqa: BLE001 — every provider may flake
        return None


def _build_query(entity: str, angle: str) -> str:
    """Compose a search query that uniquely identifies the entity
    within this specific story. Quoted entity + angle keywords."""
    angle_keys = re.findall(r"[A-Za-z][A-Za-z\-']+", angle or "")
    # Drop stopwords + duplicates of the entity.
    stop = {"the", "a", "an", "of", "to", "and", "or", "in", "for",
            "on", "with", "is", "as", "by", "at", "this", "that",
            "their", "his", "her", "its"}
    ent_words = {w.lower() for w in entity.split()}
    keys = [w for w in angle_keys
            if w.lower() not in stop and w.lower() not in ent_words]
    keep = " ".join(keys[:5])
    return f'"{entity}" {keep}'.strip()


# ---------- providers ----------
#
# Each provider exposes:
#   search(entity, angle) -> list[Candidate]
# and silently returns [] when its key is missing or any call fails.
# Providers DO NOT call og_scrape themselves — the orchestrator runs
# that expansion uniformly across every URL afterward.

def p_newsapi(entity: str, angle: str) -> list[Candidate]:
    key = os.environ.get("NEWSAPI_KEY")
    if not key or not _quota_check("newsapi", daily=90):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = (f"https://newsapi.org/v2/everything?q={q}"
           f"&pageSize=10&sortBy=relevancy&language=en&apiKey={key}")
    data = _get(url)
    if not data or data.get("status") != "ok":
        return []
    out = []
    for a in (data.get("articles") or [])[:10]:
        u = a.get("urlToImage") or ""
        if not u:
            continue
        out.append(Candidate(
            url=u, source="newsapi",
            article_title=(a.get("title") or "")[:200],
            article_url=a.get("url") or "",
            published_at=a.get("publishedAt") or ""))
    return out


def p_gnews(entity: str, angle: str) -> list[Candidate]:
    key = os.environ.get("GNEWS_KEY")
    if not key or not _quota_check("gnews", daily=90):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = (f"https://gnews.io/api/v4/search?q={q}"
           f"&max=10&lang=en&apikey={key}")
    data = _get(url)
    if not data:
        return []
    out = []
    for a in (data.get("articles") or [])[:10]:
        u = a.get("image") or ""
        if not u:
            continue
        out.append(Candidate(
            url=u, source="gnews",
            article_title=(a.get("title") or "")[:200],
            article_url=a.get("url") or "",
            published_at=a.get("publishedAt") or ""))
    return out


def p_brave(entity: str, angle: str) -> list[Candidate]:
    key = os.environ.get("BRAVE_KEY")
    if not key or not _quota_check("brave", monthly=1900):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = (f"https://api.search.brave.com/res/v1/news/search?q={q}"
           f"&count=10&spellcheck=1")
    data = _get(url, headers={
        "X-Subscription-Token": key,
        "Accept": "application/json",
    })
    if not data:
        return []
    out = []
    for a in (data.get("results") or [])[:10]:
        thumb = (a.get("thumbnail") or {}).get("src", "")
        if not thumb:
            continue
        out.append(Candidate(
            url=thumb, source="brave",
            article_title=(a.get("title") or "")[:200],
            article_url=a.get("url") or "",
            published_at=a.get("age") or a.get("page_age") or ""))
    return out


def p_tavily(entity: str, angle: str) -> list[Candidate]:
    key = os.environ.get("TAVILY_KEY")
    if not key or not _quota_check("tavily", monthly=900):
        return []
    body = json.dumps({
        "api_key": key,
        "query": _build_query(entity, angle),
        "topic": "news",
        "include_images": True,
        "include_image_descriptions": False,
        "max_results": 10,
        "search_depth": "basic",
    }).encode()
    try:
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=body,
            headers={"Content-Type": "application/json",
                     "User-Agent": _UA_GENERIC},
            method="POST")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.load(r)
    except Exception:  # noqa: BLE001
        return []
    out = []
    # Tavily returns both `images` (a flat list) and `results` (with
    # article URLs we can og-scrape downstream).
    for img in (data.get("images") or [])[:10]:
        u = img if isinstance(img, str) else (img.get("url") if isinstance(img, dict) else "")
        if not u:
            continue
        out.append(Candidate(url=u, source="tavily"))
    for a in (data.get("results") or [])[:10]:
        # No image attached to results but the article_url drives
        # og:image expansion in the second pass.
        if a.get("url"):
            out.append(Candidate(
                url="", source="tavily",
                article_title=(a.get("title") or "")[:200],
                article_url=a["url"],
                published_at=a.get("published_date") or ""))
    return out


def p_newsdata(entity: str, angle: str) -> list[Candidate]:
    key = os.environ.get("NEWSDATA_KEY")
    if not key or not _quota_check("newsdata", daily=180):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = (f"https://newsdata.io/api/1/news?apikey={key}&q={q}"
           f"&language=en")
    data = _get(url)
    if not data:
        return []
    out = []
    for a in (data.get("results") or [])[:10]:
        u = a.get("image_url") or ""
        if not u:
            continue
        out.append(Candidate(
            url=u, source="newsdata",
            article_title=(a.get("title") or "")[:200],
            article_url=a.get("link") or "",
            published_at=a.get("pubDate") or ""))
    return out


# --- social / forum (no key) ---

_REDDIT_SUBS = [
    "news", "worldnews", "UpliftingNews", "nottheonion",
    "Damnthatsinteresting", "interestingasfuck",
    "animalsbeingjerks", "HumansBeingBros", "PublicFreakout",
    "weather", "naturewasmetal",
]


def p_reddit(entity: str, angle: str) -> list[Candidate]:
    """Multi-subreddit JSON deep scrape. Reddit allows unauthenticated
    JSON access at a generous rate when the UA includes a real
    contact — we send the project's UA so we don't get IP-banned."""
    if not _quota_check("reddit", daily=600):
        return []
    out: list[Candidate] = []
    q = urllib.parse.quote(_build_query(entity, angle))
    # First: site-wide search, then per-subreddit when site-wide is thin.
    targets = [f"https://www.reddit.com/search.json?q={q}&limit=10&sort=relevance"]
    for sub in _REDDIT_SUBS[:6]:
        targets.append(
            f"https://www.reddit.com/r/{sub}/search.json"
            f"?q={q}&restrict_sr=1&limit=5&sort=relevance")
    for url in targets:
        data = _get(url, headers={"User-Agent": _UA_REDDIT})
        if not data:
            continue
        for child in (data.get("data") or {}).get("children") or []:
            post = child.get("data") or {}
            title = (post.get("title") or "")[:200]
            permalink = ("https://www.reddit.com"
                         + (post.get("permalink") or ""))
            created = post.get("created_utc")
            published = (
                datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
                if created else "")
            # Reddit-hosted preview image.
            prev = (post.get("preview") or {}).get("images") or []
            if prev:
                u = (prev[0].get("source") or {}).get("url", "")
                # Reddit HTML-encodes ampersands in preview URLs.
                u = u.replace("&amp;", "&")
                if u:
                    out.append(Candidate(
                        url=u, source="reddit",
                        article_title=title,
                        article_url=permalink,
                        published_at=published))
            # Linked-out URL (will be og-scraped in the expansion pass).
            link = post.get("url_overridden_by_dest") or post.get("url")
            if link and link != permalink and "reddit.com" not in link:
                out.append(Candidate(
                    url="", source="reddit_link",
                    article_title=title,
                    article_url=link,
                    published_at=published))
    return out[:30]    # avoid runaway when every sub returns 5+


def p_mastodon(entity: str, angle: str) -> list[Candidate]:
    if not _quota_check("mastodon", daily=400):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = (f"https://mastodon.social/api/v2/search"
           f"?type=statuses&q={q}&limit=15")
    data = _get(url, headers={"User-Agent": _UA_MASTODON})
    if not data:
        return []
    out = []
    for s in (data.get("statuses") or [])[:15]:
        for m in s.get("media_attachments") or []:
            if m.get("type") == "image" and m.get("url"):
                out.append(Candidate(
                    url=m["url"], source="mastodon",
                    article_title=(s.get("spoiler_text") or "")[:200],
                    article_url=s.get("url") or "",
                    published_at=s.get("created_at") or ""))
    return out


def p_bluesky(entity: str, angle: str) -> list[Candidate]:
    if not _quota_check("bluesky", daily=400):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = (f"https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts"
           f"?q={q}&limit=25")
    data = _get(url, headers={"User-Agent": _UA_BLUESKY})
    if not data:
        return []
    out = []
    for post in (data.get("posts") or [])[:25]:
        embed = post.get("embed") or {}
        # Direct images embed.
        for img in embed.get("images") or []:
            u = img.get("fullsize") or img.get("thumb")
            if u:
                out.append(Candidate(
                    url=u, source="bluesky",
                    article_title=((post.get("record") or {}).get("text") or "")[:200],
                    article_url="",
                    published_at=(post.get("record") or {}).get("createdAt") or ""))
        # External-link embed (most news shares look like this) — let
        # og_scrape recover the article hero downstream.
        ext = embed.get("external") or {}
        if ext.get("uri"):
            out.append(Candidate(
                url="", source="bluesky_link",
                article_title=ext.get("title", "")[:200],
                article_url=ext["uri"],
                published_at=(post.get("record") or {}).get("createdAt") or ""))
    return out


# --- image hosts ---

def p_imgur(entity: str, angle: str) -> list[Candidate]:
    cid = os.environ.get("IMGUR_CLIENT_ID")
    if not cid or not _quota_check("imgur", daily=12000):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = f"https://api.imgur.com/3/gallery/search?q={q}"
    data = _get(url, headers={"Authorization": f"Client-ID {cid}"})
    if not data:
        return []
    out = []
    for item in (data.get("data") or [])[:10]:
        u = item.get("link") or ""
        if u and item.get("type", "").startswith("image"):
            out.append(Candidate(
                url=u, source="imgur",
                article_title=(item.get("title") or "")[:200],
                article_url=f"https://imgur.com/gallery/{item.get('id', '')}",
                published_at=""))
        # Albums: take the cover.
        elif item.get("images") and not item.get("type"):
            cover = (item["images"] or [{}])[0]
            cu = cover.get("link") or ""
            if cu:
                out.append(Candidate(
                    url=cu, source="imgur",
                    article_title=(item.get("title") or "")[:200],
                    article_url=f"https://imgur.com/gallery/{item.get('id', '')}"))
    return out


def p_ddg(entity: str, angle: str) -> list[Candidate]:
    """DuckDuckGo image search. Two-step: hit the HTML endpoint to
    grab a `vqd` token, then use it on the JSON endpoint."""
    if not _quota_check("ddg", daily=400):
        return []
    q = _build_query(entity, angle)
    qenc = urllib.parse.quote(q)
    try:
        req = urllib.request.Request(
            f"https://duckduckgo.com/?q={qenc}&iax=images&ia=images",
            headers={"User-Agent": _UA_GENERIC})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            html = r.read().decode("utf-8", errors="ignore")
        m = re.search(r"vqd=['\"]?(\d-\d+-\d+)", html)
        if not m:
            return []
        vqd = m.group(1)
        api = (f"https://duckduckgo.com/i.js?l=us-en&o=json"
               f"&q={qenc}&vqd={vqd}&f=,,,&p=1")
        req = urllib.request.Request(api, headers={
            "User-Agent": _UA_GENERIC,
            "Referer": "https://duckduckgo.com/"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.load(r)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for it in (data.get("results") or [])[:15]:
        u = it.get("image") or ""
        if u:
            out.append(Candidate(
                url=u, source="ddg",
                article_title=(it.get("title") or "")[:200],
                article_url=it.get("url") or ""))
    return out


# --- existing-but-fixed: Vimeo thumbnails + YouTube thumbnails ---

def p_vimeo(entity: str, angle: str) -> list[Candidate]:
    """Vimeo's CC pool is too thin for news; flip to using Vimeo as a
    THUMBNAIL source instead. Drop the CC filter, pull `pictures.sizes`
    from every search hit — the highest-res thumbnail is usually the
    event hero photo and editorial use is fine."""
    token = os.environ.get("VIMEO_TOKEN")
    if not token or not _quota_check("vimeo", daily=200):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = (f"https://api.vimeo.com/videos?query={q}&per_page=8"
           f"&sort=relevant&fields=uri,name,created_time,pictures,link")
    data = _get(url, headers={
        "Authorization": f"bearer {token}",
        "Accept": "application/vnd.vimeo.*+json;version=3.4",
    })
    if not data:
        return []
    out = []
    for v in (data.get("data") or [])[:8]:
        sizes = ((v.get("pictures") or {}).get("sizes") or [])
        if not sizes:
            continue
        # Sizes come sorted small -> large; grab the largest.
        biggest = max(sizes, key=lambda s: int(s.get("width") or 0))
        u = biggest.get("link") or ""
        if not u:
            continue
        out.append(Candidate(
            url=u, source="vimeo",
            article_title=(v.get("name") or "")[:200],
            article_url=v.get("link") or "",
            published_at=v.get("created_time") or ""))
    return out


def p_youtube(entity: str, angle: str) -> list[Candidate]:
    """YouTube search thumbnails — frequently the news event hero for
    contemporary stories. Uses the existing YOUTUBE_API_KEY."""
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key or not _quota_check("youtube", daily=8000):
        return []
    q = urllib.parse.quote(_build_query(entity, angle))
    url = ("https://www.googleapis.com/youtube/v3/search"
           f"?part=snippet&type=video&maxResults=10&order=relevance"
           f"&q={q}&key={key}")
    data = _get(url)
    if not data:
        return []
    out = []
    for item in (data.get("items") or [])[:10]:
        sn = item.get("snippet") or {}
        thumbs = sn.get("thumbnails") or {}
        # Prefer high → medium → default.
        for k in ("high", "medium", "default"):
            t = thumbs.get(k)
            if t and t.get("url"):
                out.append(Candidate(
                    url=t["url"], source="youtube",
                    article_title=(sn.get("title") or "")[:200],
                    article_url=(
                        f"https://youtube.com/watch?v="
                        f"{(item.get('id') or {}).get('videoId', '')}"),
                    published_at=sn.get("publishedAt") or ""))
                break
    return out


# Provider registry — order is only for display; fan-out is parallel.
_PROVIDERS: list[tuple[str, Callable[[str, str], list[Candidate]]]] = [
    ("newsapi", p_newsapi),
    ("gnews", p_gnews),
    ("brave", p_brave),
    ("tavily", p_tavily),
    ("newsdata", p_newsdata),
    ("reddit", p_reddit),
    ("mastodon", p_mastodon),
    ("bluesky", p_bluesky),
    ("imgur", p_imgur),
    ("ddg", p_ddg),
    ("vimeo", p_vimeo),
    ("youtube", p_youtube),
]


# ---------- orchestrator ----------

def _expand_og(candidates: list[Candidate]) -> list[Candidate]:
    """For every candidate that came with an article URL but no image
    (or with a low-quality thumbnail), fan out og_scrape in parallel."""
    todo = []
    for c in candidates:
        if c.article_url and (not c.url or _JUNK_URL.search(c.url)):
            todo.append(c)
    if not todo:
        return candidates
    seen_articles: set[str] = set()
    unique = []
    for c in todo:
        if c.article_url in seen_articles:
            continue
        seen_articles.add(c.article_url)
        unique.append(c)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(og_scrape.fetch, c.article_url,
                              published_at=c.published_at or None): c
                   for c in unique}
        for fut in concurrent.futures.as_completed(futures, timeout=20):
            c = futures[fut]
            try:
                img = fut.result()
            except Exception:  # noqa: BLE001
                img = None
            if img:
                # Promote: build a NEW candidate that carries the
                # scraped hero, keep the source as <orig>_og so the
                # ranker can credit the article-host bonus.
                candidates.append(Candidate(
                    url=img, source=f"{c.source}_og",
                    article_title=c.article_title,
                    article_url=c.article_url,
                    published_at=c.published_at))
    return candidates


def _verify(candidates: list[Candidate]) -> list[Candidate]:
    """Drop dead URLs in parallel HEAD/GET. Reuses
    entity_media.url_is_image to keep one canonical verifier."""
    from entity_media import url_is_image
    keep: list[Candidate] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(url_is_image, c.url): c
                   for c in candidates if c.url}
        for fut in concurrent.futures.as_completed(futures, timeout=30):
            c = futures[fut]
            try:
                ok = fut.result()
            except Exception:  # noqa: BLE001
                ok = False
            if ok:
                keep.append(c)
    return keep


def _prefilter(candidates: list[Candidate]) -> list[Candidate]:
    """Apply junk-URL rejection + numeric boosts that don't need an
    LLM. Sorts the survivors by current score, highest first."""
    out: list[Candidate] = []
    for c in candidates:
        if _JUNK_URL.search(c.url):
            continue
        # Base score per source — trusts news-search APIs more than
        # social, social more than image hosts, image hosts more than
        # generic DDG.
        base = {
            "newsapi": 0.55, "gnews": 0.55, "brave": 0.55,
            "tavily": 0.55, "newsdata": 0.55,
            "newsapi_og": 0.70, "gnews_og": 0.70, "brave_og": 0.70,
            "tavily_og": 0.70, "newsdata_og": 0.70,
            "reddit": 0.45, "reddit_link_og": 0.65, "reddit_og": 0.65,
            "mastodon": 0.45, "mastodon_og": 0.60,
            "bluesky": 0.45, "bluesky_link_og": 0.65, "bluesky_og": 0.60,
            "imgur": 0.40, "ddg": 0.35,
            "vimeo": 0.45, "youtube": 0.40,
        }.get(c.source, 0.40)
        c.score = base
        # +0.20 if published within the last 7 days.
        if c.published_at:
            try:
                t = c.published_at.replace("Z", "+00:00")
                d = datetime.fromisoformat(t)
                age_d = (datetime.now(timezone.utc) - d).days
                if age_d <= 7:
                    c.score += 0.20
                    c.boosts["fresh"] = age_d
                elif age_d > 365:
                    c.score -= 0.15
                    c.boosts["stale"] = age_d
            except (ValueError, TypeError):
                pass
        # +0.30 if image host matches article host (genuine article
        # hero, not a stock-CDN). Skip when one side is missing.
        if c.url and c.article_url:
            try:
                ih = urllib.parse.urlparse(c.url).netloc.lower()
                ah = urllib.parse.urlparse(c.article_url).netloc.lower()
                if ih and ah and (ih == ah or ih.endswith("." + ah)
                                  or ah.endswith("." + ih)):
                    c.score += 0.30
                    c.boosts["same_host"] = True
            except Exception:  # noqa: BLE001
                pass
        out.append(c)
    out.sort(key=lambda c: c.score, reverse=True)
    return out


def _llm_rerank(candidates: list[Candidate], story_angle: str,
                entity: str) -> list[Candidate]:
    """Final tiebreaker: pass the top ~10 candidates to a small Groq
    model and ask which best matches the story angle. Free, fast."""
    if len(candidates) <= 1:
        return candidates
    top = candidates[:10]
    try:
        from script_generator import _call_llm
    except ImportError:
        return candidates
    listing = "\n".join(
        f'{i}. source={c.source} | age_days={c.boosts.get("fresh", "?")} '
        f'| title="{c.article_title[:100]}"'
        for i, c in enumerate(top))
    system = ("You rank candidate news photos for relevance to a "
              "specific story. Output strict JSON only.")
    user = (
        f'Entity in the story: "{entity}"\n'
        f'Story angle: "{story_angle}"\n\n'
        f'Candidates (one per line):\n{listing}\n\n'
        'Return JSON like {"ranking": [<index>, <index>, ...]} ordering '
        "the indices from most-relevant to least. Only include indices "
        "you are confident actually depict the entity in THIS story; "
        "drop indices where the title doesn't seem to match.")
    try:
        raw = _call_llm(system, user)
    except Exception:  # noqa: BLE001
        return candidates
    if not raw:
        return candidates
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return candidates
    order = data.get("ranking") if isinstance(data, dict) else None
    if not isinstance(order, list):
        return candidates
    # Apply a positional boost: the LLM's pick gains +0.25, second
    # +0.18, third +0.12, etc.
    seen = set()
    bonuses = [0.25, 0.18, 0.12, 0.08, 0.05, 0.03, 0.02, 0.01, 0.01, 0.005]
    for slot, idx in enumerate(order[:10]):
        if not isinstance(idx, int) or idx < 0 or idx >= len(top):
            continue
        if idx in seen:
            continue
        seen.add(idx)
        top[idx].score += bonuses[slot]
        top[idx].boosts["llm_rank"] = slot
    # Return the merged list (top reranked + tail unchanged).
    merged = top + candidates[10:]
    merged.sort(key=lambda c: c.score, reverse=True)
    return merged


def search(story_angle: str, entities: list[str],
           hashtags: Optional[list[str]] = None,
           *, story_slug: str = "", verbose: bool = True) -> list[Candidate]:
    """Run every provider in parallel, expand article URLs through
    og_scrape, verify, filter, score, rerank. Cached per
    (story_slug, entity)."""
    if not entities:
        return []
    primary = entities[0]
    if story_slug:
        cached = _cache_get(story_slug, primary)
        if cached is not None:
            if verbose:
                print(f"  [media_funnel] cache HIT for "
                      f"{primary!r} on {story_slug!r}: "
                      f"{len(cached)} candidates")
            return [Candidate(**{k: v for k, v in c.items()
                                  if k in {"url", "source", "score",
                                           "article_title", "article_url",
                                           "published_at"}})
                    for c in cached]

    # 1. Fan out — every provider for the PRIMARY entity. Other
    # entities are used only to disambiguate inside the LLM rerank
    # (we don't pay for separate searches per entity to stay inside
    # daily free tiers).
    all_candidates: list[Candidate] = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(_PROVIDERS)) as ex:
        futures = {ex.submit(fn, primary, story_angle): name
                   for name, fn in _PROVIDERS}
        for fut in concurrent.futures.as_completed(futures, timeout=15):
            name = futures[fut]
            try:
                cs = fut.result() or []
            except Exception as e:  # noqa: BLE001
                if verbose:
                    print(f"  [media_funnel] {name} failed: "
                          f"{type(e).__name__}: {str(e)[:80]}")
                cs = []
            all_candidates.extend(cs)
            if verbose and cs:
                print(f"  [media_funnel] {name}: {len(cs)} raw")

    # 2. og:image expansion on every article URL (Wayback fallback
    # baked into og_scrape).
    all_candidates = _expand_og(all_candidates)

    # 3. Verify image content-type.
    verified = _verify(all_candidates)
    if verbose:
        print(f"  [media_funnel] verified {len(verified)}/"
              f"{len(all_candidates)} URLs as actually images")

    # 4. Heuristic prefilter + scoring.
    filtered = _prefilter(verified)

    # 5. LLM rerank.
    final = _llm_rerank(filtered, story_angle, primary)

    if story_slug:
        _cache_put(story_slug, primary, final)
    return final


# ---------- CLI ----------

def _cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", required=True,
                    help="Entity name to probe (e.g. 'Brad Paisley')")
    ap.add_argument("--angle", default="",
                    help="Story angle (full sentence). Disambiguates.")
    ap.add_argument("--limit", type=int, default=10,
                    help="Max candidates to print.")
    ap.add_argument("--no-cache", action="store_true",
                    help="Bypass the disk cache for this probe.")
    a = ap.parse_args()
    slug = "" if a.no_cache else f"probe_{a.probe.lower().replace(' ', '_')}"
    results = search(a.angle, [a.probe], story_slug=slug)
    print()
    print(f"=== {len(results)} candidates for {a.probe!r} ===")
    for c in results[:a.limit]:
        boosts = ",".join(f"{k}={v}" for k, v in c.boosts.items())
        print(f"  {c.score:.2f}  {c.source:18s}  {c.url[:80]}")
        if c.article_title:
            print(f"          \"{c.article_title[:80]}\"  [{boosts}]")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
