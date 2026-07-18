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


_RASTER = (".jpg", ".jpeg", ".png", ".webp")

# When a beat asks for a GROUND / human-scale photo, an orbital/satellite image
# is not just off-perspective — it is the exact boring 'cloud from the sky' the
# perspective director exists to reject. Drop those titles outright.
_ORBITAL_TELLS = ("satellite", "modis", "goes-", "viirs", "landsat", "sentinel",
                  "from space", "from orbit", "orbital", "aerial view",
                  "seen from", "iss", "space station", "nasa earth")
_GROUND_PERSP = ("ground", "human", "street", "pov", "consequence", "close",
                 "surge", "landfall", "damage", "aftermath")
_STOP = {"the", "a", "an", "of", "and", "in", "on", "at", "from", "to", "with",
         "over", "into", "storm", "view", "photo", "image"}


def _tokens(s: str) -> set[str]:
    return {w for w in "".join(c if c.isalnum() else " "
                              for c in s.lower()).split()
            if len(w) > 3 and w not in _STOP}


def _relevance(title: str, query: str) -> float:
    """Fraction of the query's content words that appear (prefix-matched) in the
    title — so an off-topic high-appeal image (a scenic river flood under a
    hurricane query) ranks below a real, on-topic one."""
    qt, tt = _tokens(query), _tokens(title)
    if not qt:
        return 0.0
    hit = sum(1 for q in qt if any(t.startswith(q[:4]) or q.startswith(t[:4])
                                   for t in tt))
    return hit / len(qt)


def best_image(query: str, dest: Path, perspective: str = "",
               min_appeal: float = 0.42, tries: int = 6,
               usage: str = "commercial",
               must_match: list[str] | None = None) -> dict | None:
    """Search the gateway for a real photo, download candidates, and return the
    highest-APPEAL one (Hasler-Süsstrunk colour + edge + contrast) — so a beat
    gets a view-worthy image, never merely an on-topic one. Downloads to `dest`.
    Returns {path, source, license, attribution, title, appeal} or None if no
    candidate clears `min_appeal`. Records attribution for CC credit."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from interest_judge import _appeal
    from PIL import Image
    want_ground = any(g in perspective.lower() for g in _GROUND_PERSP)
    cands = [c for c in find(query, kind="image", perspective=perspective,
                             usage=usage, limit=max(tries * 3, 18))
             if c["url"].lower().split("?")[0].endswith(_RASTER)]
    # PERSPECTIVE gate: for a ground beat, drop orbital/satellite titles — they
    # are the 'boring cloud from the sky' the perspective director rejects.
    if want_ground:
        cands = [c for c in cands
                 if not any(t in (c.get("title") or "").lower()
                            for t in _ORBITAL_TELLS)] or cands
    # TOPICAL ANCHOR gate: a candidate must name the actual subject (or a known
    # instance of it) — otherwise a scenic, high-appeal but OFF-TOPIC image (a
    # river flood under a hurricane query) wins on looks alone. If nothing is
    # anchored, we return None and let the gateway DECLARE the access need rather
    # than ship a pretty lie.
    if must_match:
        ml = [m.lower() for m in must_match]
        anchored = [c for c in cands
                    if any(m in (c.get("title") or "").lower() for m in ml)]
        if not anchored:
            print(f"[media] no on-topic photo for {query!r} in the free pool "
                  f"(anchors {must_match}) — declaring the access need")
            return None
        cands = anchored
    # RELEVANCE-first ordering: probe the most on-topic candidates first, so a
    # thin free pool doesn't spend its budget on scenic-but-off-topic images.
    cands.sort(key=lambda c: _relevance(c.get("title", ""), query), reverse=True)
    best, best_score = None, 0.0
    tmp = dest.with_suffix(".probe.tmp")
    for c in cands[:tries]:
        rel = _relevance(c.get("title", ""), query)
        try:
            acquire(c, tmp)
            ap = _appeal(Image.open(tmp).convert("RGB"))
        except Exception as e:  # noqa: BLE001
            print(f"[media] probe {c['source']}: {str(e)[:60]}")
            continue
        if ap < min_appeal:
            tmp.unlink(missing_ok=True)
            continue
        # a view-worthy AND on-topic photo: appeal weighted, relevance as a
        # strong multiplier so an on-topic 0.5 beats an off-topic 0.75.
        score = ap * (0.55 + 0.45 * min(1.0, rel * 1.5))
        if score >= best_score:
            best = dict(c, appeal=round(ap, 3), relevance=round(rel, 2))
            best_score = score
            tmp.replace(dest)
        else:
            tmp.unlink(missing_ok=True)
    if best is None:
        return None
    if not dest.exists():                      # winner wasn't the last probed
        acquire(best, dest)
    best["path"] = str(dest)
    print(f"[media] best_image {query!r}: {best['source']} appeal="
          f"{best['appeal']} rel={best['relevance']} "
          f"{best.get('title', '')[:40]!r}")
    return best


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
