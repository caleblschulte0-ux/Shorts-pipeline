#!/usr/bin/env python3
"""THE MEDIA GATEWAY (top of the pipeline — one place to get media from many).

Media acquisition is a FIRST-CLASS front-of-pipeline layer, not something bolted
on per beat. Given what a beat needs (an image or a video, at a perspective —
ground / orbital / human-scale), the gateway reaches the source that can DELIVER
it, honours licensing, and — when it can't reach the ideal source — DECLARES the
access it needs instead of silently shipping a worse shot.

Sources (each tagged with what it delivers + what it needs):
  IMAGES
    openverse  — 800M+ CC/PD images (real photos of real events, ground-level);
                 free, no key. The default for 'find a real photo of X'.
    commons    — Wikimedia PD/CC images.
    google     — Google Images via Apify (broadest / most RECENT news photos);
                 premium (Apify credits) — the operator's preferred 'just google
                 it' path, used when enabled.
  VIDEO
    nasa       — space / orbital / Earth-science (free).
    commonsvid — PD/CC satellite viz + some footage (free).
    pexels/pixabay — CC0 ground-level / human-scale b-roll (free key).

Everything the gateway returns still passes the downstream gates (exact-window /
appeal / interest / continuity). A viewer never sees a clip just because it was
on-topic; it has to be point-conveying and view-worthy.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from data_learning.footage_hybrid import _get

# commercial-safe CC licences (default: monetised channel). 'nc' excluded.
_COMMERCIAL = {"cc0", "pdm", "by", "by-sa"}


# ---- IMAGE sources -------------------------------------------------------
def openverse_images(query: str, limit: int = 12,
                     commercial: bool = True) -> list[dict]:
    """Real CC/PD photos of real events — the default image source."""
    lic = "&license_type=commercial,modification" if commercial else ""
    url = (f"https://api.openverse.org/v1/images/?q={quote(query)}"
           f"&page_size={limit}{lic}&mature=false")
    d = json.loads(_get(url))
    out = []
    for r in d.get("results", []):
        out.append({"source": "openverse", "kind": "image",
                    "url": r.get("url", ""), "title": r.get("title", ""),
                    "license": (r.get("license") or "").lower(),
                    "attribution": r.get("attribution")
                    or f"{r.get('creator', '')} ({r.get('license', '')})",
                    "w": r.get("width"), "h": r.get("height")})
    return [c for c in out if c["url"]]


def commons_images(query: str, limit: int = 10) -> list[dict]:
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
           f"&generator=search&gsrsearch={quote(query)}%20filetype:bitmap"
           f"&gsrnamespace=6&gsrlimit={limit}&prop=imageinfo"
           "&iiprop=url|mime|size|extmetadata")
    d = json.loads(_get(url))
    out = []
    for p in d.get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        lic = ((ii.get("extmetadata", {}) or {}).get("LicenseShortName", {})
               or {}).get("value", "")
        out.append({"source": "commons", "kind": "image",
                    "url": ii.get("url", ""), "title": p.get("title", ""),
                    "license": lic or "PD/CC", "attribution": lic,
                    "w": ii.get("width"), "h": ii.get("height")})
    return [c for c in out if c["url"]]


# ---- the gateway ---------------------------------------------------------
def find(query: str, kind: str = "image", perspective: str = "",
         usage: str = "commercial", limit: int = 12) -> list[dict]:
    """One entry point. kind='image'|'video'. Returns ranked candidates from the
    sources that can deliver this kind+perspective, best-first. Never invents a
    fallback that can't actually deliver — see access_report() for what's missing.
    """
    from data_learning import stock
    commercial = usage == "commercial"
    out: list[dict] = []
    if kind == "image":
        for fn in (openverse_images, commons_images):
            try:
                out += (fn(query, limit, commercial)
                        if fn is openverse_images else fn(query, limit))
            except Exception as e:  # noqa: BLE001
                print(f"[media] {fn.__name__}: {str(e)[:70]}")
        if usage == "commercial":
            out = [c for c in out
                   if any(t in c["license"] for t in _COMMERCIAL)
                   or "public" in c["license"]] or out
    else:  # video
        try:
            for h in __import__("data_learning.footage_hybrid",
                                fromlist=["x"]).search_footage(query, limit):
                out.append({"source": "nasa", "kind": "video",
                            "nasa_id": h.get("nasa_id"), "title":
                            h.get("title", ""), "license": "PD (NASA)"})
        except Exception as e:  # noqa: BLE001
            print(f"[media] nasa: {str(e)[:70]}")
        out += stock.stock_search(query, limit)
    return out


def acquire(candidate: dict, dest: Path) -> Path:
    """Download a candidate (image or video) to dest."""
    url = candidate.get("url")
    if not url and candidate.get("nasa_id"):
        from data_learning.footage_hybrid import download_video
        return download_video(candidate["nasa_id"], dest)
    p = urlsplit(url)
    enc = urlunsplit((p.scheme, p.netloc, quote(p.path), p.query, p.fragment))
    import urllib.request
    req = urllib.request.Request(enc, headers={"User-Agent":
                                 "OpenRangeInteractive/1.0 (science education)"})
    dest.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    return dest


def access_report() -> dict:
    """What the gateway can reach now, and what it needs granted. Google Images
    (Apify) and Pexels/Pixabay are the premium reaches — declared, not faked."""
    have = ["openverse", "commons", "nasa"]
    needs = []
    if not os.environ.get("PEXELS_API_KEY"):
        needs.append({"source": "pexels", "env": "PEXELS_API_KEY",
                      "good_for": "CC0 ground-level / cinematic video b-roll"})
    if not os.environ.get("APIFY_ENABLE_GOOGLE_IMAGES"):
        needs.append({"source": "google_images", "via": "Apify actor",
                      "good_for": "broadest / most RECENT news photos of events"})
    return {"reachable": have, "needs_access": needs}


if __name__ == "__main__":
    import sys
    kind = "video" if "--video" in sys.argv else "image"
    q = next((a for a in sys.argv[1:] if not a.startswith("-")), "hurricane")
    for c in find(q, kind=kind)[:10]:
        print(f"{c['source']:9s} {c.get('license', '')[:14]:14s} "
              f"{(c.get('title') or '')[:46]}")
