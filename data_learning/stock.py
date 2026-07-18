#!/usr/bin/env python3
"""MULTI-SOURCE FOOTAGE (PERSPECTIVE_DIRECTOR — beyond NASA).

NASA only has orbital / space / Earth-science footage. To show a subject the way
a viewer actually experiences it (a hurricane FROM THE GROUND — bending palms,
surge, horizontal rain), the perspective director needs stock / CC / PD sources.

Sources, best-first for clean human-scale b-roll:
  - Pexels, Pixabay   — CC0 stock video, need a free API key (PEXELS_API_KEY /
    PIXABAY_API_KEY). The enabler for visceral ground footage.
  - Wikimedia Commons — open (no key), PD/CC, gov + user uploads.
  - archive.org       — large PD/CC library (filter to a PD/CC licence).

`stock_search(query)` returns candidates [{source, title, url, license, dur?}].
`download(url, dest)` fetches any of them; ffmpeg downstream handles ogv/webm.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote

from data_learning.footage_hybrid import _get


def search_pexels(query: str, limit: int = 8) -> list[dict]:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    import urllib.request
    req = urllib.request.Request(
        f"https://api.pexels.com/videos/search?query={quote(query)}"
        f"&per_page={limit}&size=medium",
        headers={"Authorization": key})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    out = []
    for v in d.get("videos", []):
        files = sorted(v.get("video_files", []),
                       key=lambda f: abs((f.get("height") or 0) - 1080))
        hd = next((f for f in files if (f.get("height") or 0) >= 720), None) \
            or (files[0] if files else None)
        if hd:
            out.append({"source": "pexels", "title": v.get("url", ""),
                        "url": hd["link"], "license": "Pexels (CC0-like)",
                        "dur": v.get("duration")})
    return out


def search_pixabay(query: str, limit: int = 8) -> list[dict]:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    d = json.loads(_get(
        f"https://pixabay.com/api/videos/?key={key}&q={quote(query)}"
        f"&per_page={limit}"))
    out = []
    for v in d.get("hits", []):
        vids = v.get("videos", {})
        f = vids.get("large") or vids.get("medium") or {}
        if f.get("url"):
            out.append({"source": "pixabay", "title": v.get("pageURL", ""),
                        "url": f["url"], "license": "Pixabay (CC0-like)",
                        "dur": v.get("duration")})
    return out


def search_commons(query: str, limit: int = 8) -> list[dict]:
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json"
           f"&generator=search&gsrsearch={quote(query)}%20filetype:video"
           f"&gsrnamespace=6&gsrlimit={limit}&prop=imageinfo"
           "&iiprop=url|mime|size|extmetadata")
    d = json.loads(_get(url))
    out = []
    for p in d.get("query", {}).get("pages", {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}) or {}).get("value", "")
        out.append({"source": "commons", "title": p.get("title", ""),
                    "url": ii.get("url", ""), "license": lic or "PD/CC"})
    return [c for c in out if c["url"]]


# archive.org licences we accept (public-domain / creative-commons only)
_OK_LIC = ("publicdomain", "creativecommons", "cc0", "/by/", "/by-sa/",
           "usgov", "publicresource")


def search_archive(query: str, limit: int = 8) -> list[dict]:
    q = f"({query}) AND mediatype:movies"
    url = (f"https://archive.org/advancedsearch.php?q={quote(q)}"
           "&fl[]=identifier&fl[]=title&fl[]=licenseurl&fl[]=rights"
           f"&rows={limit}&output=json")
    d = json.loads(_get(url))
    out = []
    for x in d.get("response", {}).get("docs", []):
        lic = (x.get("licenseurl", "") or x.get("rights", "") or "").lower()
        if not any(k in lic for k in _OK_LIC):
            continue                    # skip unknown/all-rights-reserved
        ident = x.get("identifier", "")
        # resolve the actual video file via the item metadata
        try:
            meta = json.loads(_get(f"https://archive.org/metadata/{ident}"))
        except Exception:  # noqa: BLE001
            continue
        vids = [f for f in meta.get("files", [])
                if str(f.get("name", "")).lower().endswith(
                    (".mp4", ".webm", ".ogv", ".mov"))]
        vids.sort(key=lambda f: int(f.get("size", 0) or 0), reverse=True)
        if vids:
            out.append({"source": "archive", "title": x.get("title", ""),
                        "url": f"https://archive.org/download/{ident}/"
                        f"{quote(vids[0]['name'])}", "license": lic})
    return out


def stock_search(query: str, limit: int = 8) -> list[dict]:
    """All sources, best-first: Pexels/Pixabay (if keyed) -> Commons -> archive."""
    out: list[dict] = []
    for fn in (search_pexels, search_pixabay, search_commons, search_archive):
        try:
            out += fn(query, limit)
        except Exception as e:  # noqa: BLE001
            print(f"[stock] {fn.__name__} failed: {str(e)[:80]}")
    return out


def download(url: str, dest: Path) -> Path:
    """Fetch a stock/CC clip. Source URLs (Commons, archive, Pexels) are already
    valid/encoded, so fetch as-is — do NOT re-quote (that double-encodes %20)."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent":
                                 "OpenRangeInteractive/1.0 (science education)"})
    dest.write_bytes(urllib.request.urlopen(req, timeout=180).read())
    return dest


if __name__ == "__main__":
    import sys
    for c in stock_search(sys.argv[1] if len(sys.argv) > 1 else "hurricane"):
        print(f"{c['source']:8s} {c['license'][:22]:22s} {c['title'][:50]}")
        print(f"         {c['url'][:100]}")
