"""Clean article text from a URL — script-quality source material.

The trending channel authors scripts from headlines; the actual article
body is far better raw material. This pulls a URL and returns readable
text plus metadata, with two lanes:

  1. trafilatura, if the wheel happens to be installed (best quality);
  2. a dependency-free readability heuristic (good enough): strip the
     chrome tags, score candidate blocks by text mass minus link density,
     return the winner's paragraphs.

Contract matches the funnel: ``extract()`` returns a dict or ``None``,
never raises. Results are TTL-cached in cache/funnel/articles/ (articles
don't change; the TTL is just cache hygiene).

    from funnel import article_extract
    art = article_extract.extract(url)
    # {"title", "text", "site", "published", "url", "method"} | None
"""
from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from shared.fsutil import atomic_write_json

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache" / "funnel" / "articles"
CACHE_TTL = 7 * 86400
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_DROP_TAGS = re.compile(
    r"<(script|style|noscript|template|svg|iframe|form|nav|header|footer|"
    r"aside|figure|button)\b.*?</\1\s*>", re.I | re.S)
_COMMENTS = re.compile(r"<!--.*?-->", re.S)
_BLOCK = re.compile(r"<(article|main|section|div)\b[^>]*>(.*?)</\1\s*>",
                    re.I | re.S)
_PARA = re.compile(r"<(p|h2|h3|li)\b[^>]*>(.*?)</\1\s*>", re.I | re.S)
_ANCHOR_TEXT = re.compile(r"<a\b[^>]*>(.*?)</a\s*>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\r\f\v]+")
_META = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](og:title|article:published_time|'
    r'og:site_name|date)["\'][^>]+content=["\']([^"\']*)["\']', re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _clean_text(fragment: str) -> str:
    txt = _TAGS.sub(" ", fragment)
    txt = html_mod.unescape(txt)
    return _WS.sub(" ", txt).strip()


def _heuristic(html_text: str) -> str:
    """Pick the densest content block; return its paragraphs as text."""
    body = _COMMENTS.sub("", html_text)
    for _ in range(3):  # nested chrome tags need repeated passes
        body = _DROP_TAGS.sub(" ", body)

    best_score, best_paras = 0.0, []
    for m in _BLOCK.finditer(body):
        frag = m.group(2)
        paras = [_clean_text(p.group(2)) for p in _PARA.finditer(frag)]
        paras = [p for p in paras if len(p) > 40]
        if not paras:
            continue
        text_len = sum(len(p) for p in paras)
        anchor_len = sum(len(_clean_text(a.group(1)))
                         for a in _ANCHOR_TEXT.finditer(frag))
        link_density = anchor_len / max(1, text_len)
        score = text_len * (1.0 - min(0.9, link_density))
        if score > best_score:
            best_score, best_paras = score, paras

    if not best_paras:  # page without block structure: fall back to all <p>
        best_paras = [p for p in
                      (_clean_text(x.group(2)) for x in _PARA.finditer(body))
                      if len(p) > 40]
    return "\n\n".join(best_paras)


def extract_html(html_text: str, url: str = "") -> dict | None:
    """Extraction over HTML you already fetched. None if nothing usable."""
    try:
        title, published, site = "", "", ""
        for m in _META.finditer(html_text):
            key, val = m.group(1).lower(), html_mod.unescape(m.group(2))
            if key == "og:title" and not title:
                title = val
            elif key in ("article:published_time", "date") and not published:
                published = val
            elif key == "og:site_name":
                site = val
        if not title:
            m = _TITLE.search(html_text)
            title = _clean_text(m.group(1)) if m else ""
        if not site and url:
            site = urllib.parse.urlparse(url).netloc

        text, method = "", "heuristic"
        try:  # best lane when the wheel exists; never required
            import trafilatura  # type: ignore
            text = trafilatura.extract(html_text) or ""
            method = "trafilatura"
        except Exception:
            pass
        if len(text) < 200:
            text, method = _heuristic(html_text), "heuristic"
        text = text.strip()
        if len(text) < 200:
            return None
        return {"title": title, "text": text[:20000], "site": site,
                "published": published, "url": url, "method": method}
    except Exception:
        return None


def extract(url: str, *, timeout: int = 25, ttl: int = CACHE_TTL
            ) -> dict | None:
    """Fetch + extract with cache. None on any failure. Respects the
    repo-wide rule: plain GETs only — never bypass paywalls or logins."""
    try:
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        cache_file = CACHE_DIR / f"{key}.json"
        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text())
                if time.time() - cached.get("fetched_at", 0) < ttl:
                    return cached.get("article")
            except Exception:
                pass
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "text/html,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype and "xml" not in ctype:
                return None
            body = resp.read(3_000_000).decode("utf-8", "replace")
        art = extract_html(body, url)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_json(cache_file,
                          {"fetched_at": time.time(), "article": art})
        return art
    except Exception:
        return None
