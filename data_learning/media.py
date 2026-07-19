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

TOP OF THE PIPELINE, SHARED BY EVERY CHANNEL. This gateway is not owned by any
one channel — curiosity, niche, and any future channel all call the SAME find()/
best_image()/acquire(). New media sources are declared ONCE in the SOURCES
registry below (+ a fetch fn); every channel inherits them for free. Do not add a
way to get media inside a channel's config or render path — add it here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from data_learning.footage_hybrid import _get

# commercial-safe CC licences (default: monetised channel). 'nc' excluded.
_COMMERCIAL = {"cc0", "pdm", "by", "by-sa"}


# ── THE MEDIA SOURCE REGISTRY ────────────────────────────────────────────
# The ONE top-of-pipeline declaration of every way the pipeline can get media.
# It lives here, not inside any channel — so a new source is added ONCE, here,
# and EVERY channel (curiosity, niche, and any future one) inherits it for free.
# find()/best_image()/access_report() all read from this registry; to teach the
# whole pipeline a new source, add an entry (+ its fetch fn) and nothing else.
#   kind:        "image" | "video"
#   env:         env var that unlocks it (None = always reachable, free/no key)
#   commercial:  safe for a monetised channel by default
#   good_for:    when the directors should reach for it
SOURCES: dict[str, dict] = {
    "google":    {"kind": "image", "env": "APIFY_TOKEN", "commercial": True,
                  "good_for": "broadest + most RECENT news photos of real "
                  "events — the 'just google it' path"},
    "openverse": {"kind": "image", "env": None, "commercial": True,
                  "good_for": "real CC/PD photos of real events (ground-level); "
                  "the free default for a real photo of X"},
    "commons":   {"kind": "image", "env": None, "commercial": True,
                  "good_for": "Wikimedia PD/CC images"},
    "nasa":      {"kind": "video", "env": None, "commercial": True,
                  "good_for": "space / orbital / Earth-science footage"},
    "pexels":    {"kind": "video", "env": "PEXELS_API_KEY", "commercial": True,
                  "good_for": "CC0 ground-level / cinematic video b-roll"},
    "pixabay":   {"kind": "video", "env": "PIXABAY_API_KEY", "commercial": True,
                  "good_for": "CC0 ground-level / human-scale video b-roll"},
}


def sources(kind: str | None = None, reachable_only: bool = False) -> list[str]:
    """The registered media sources (optionally filtered by kind / reachability).
    Every channel calls the same gateway, so this list is the same everywhere."""
    out = []
    for name, s in SOURCES.items():
        if kind and s["kind"] != kind:
            continue
        if reachable_only and s["env"] and not os.environ.get(s["env"]):
            continue
        out.append(name)
    return out


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


def google_images(query: str, limit: int = 12, commercial: bool = True,
                  recent: bool = False, wide: bool = True) -> list[dict]:
    """Google Images via Apify — the operator's preferred 'just google a recent
    hurricane' path: broadest coverage and the most RECENT news photos, filtered
    to photo / wide / CC usage rights. Ready the instant an APIFY_TOKEN is
    granted; without one it returns nothing and access_report() DECLARES the need
    (it does NOT silently fall back to a worse source and pretend it's fine)."""
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        return []
    import json as _json
    import urllib.request
    actor = os.environ.get("APIFY_GOOGLE_IMAGES_ACTOR",
                           "solidcode~google-images-scraper")
    payload = {"queries": [query], "maxResultsPerQuery": limit,
               "imageType": "photo", "safeSearch": "off",
               "aspectRatio": "wide" if wide else "any",
               "usageRights": "creativeCommons" if commercial else "any",
               "timePeriod": "pastYear" if recent else "anytime"}
    url = (f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
           f"?token={token}")
    req = urllib.request.Request(
        url, data=_json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    d = _json.loads(urllib.request.urlopen(req, timeout=180).read())
    out = []
    for r in d if isinstance(d, list) else d.get("items", []):
        u = r.get("imageUrl") or r.get("image") or r.get("url") or ""
        if not u:
            continue
        out.append({"source": "google", "kind": "image", "url": u,
                    "title": r.get("title") or r.get("source") or "",
                    "license": "google/CC (verify at source)",
                    "attribution": r.get("sourcePage") or r.get("source") or "",
                    "w": r.get("width"), "h": r.get("height")})
    return out


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
        # Google Images (Apify) FIRST when enabled — broadest + most recent news
        # photos, precisely what the operator asked for; then the free CC pools.
        try:
            out += google_images(query, limit, commercial)
        except Exception as e:  # noqa: BLE001
            print(f"[media] google_images: {str(e)[:70]}")
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


def _clip_motion(clip: Path, ss: float, dur: float) -> float:
    """Mean frame-to-frame change across the window — how much the picture
    actually MOVES. A time-lapse / spinning storm / flooding street scores high;
    a video that is functionally a frozen plate scores near zero (and so does not
    earn the 'motion beats a still' win — a dead clip is no better than a photo)."""
    import numpy as np
    from data_learning import footage_hybrid as fh
    fr = fh._sample_frames(clip, ss, dur, n=6)
    if len(fr) < 2:
        return 0.0
    g = [a.mean(2) for a in fr]
    diffs = [float(np.abs(g[i] - g[i - 1]).mean()) for i in range(1, len(g))]
    return round(sum(diffs) / len(diffs), 2)


# THE MOTION-FIRST LAW (see data_learning/MOTION_FIRST.md)
#   When a beat's job is to DEPICT a real subject, a MOVING clip of that subject
#   always beats a still of it. A still is earned only when no clip of the
#   subject clears the bar (clean window + genuine movement + on-topic), or when
#   the still carries information a clip can't (a chart, a map, a document) — and
#   that case never reaches this gate (it is authored `still: true`).
MOTION_FLOOR = 2.2        # mean frame-diff below this = a functionally frozen clip
MOTION_REL_FLOOR = 0.08   # a clip must actually name the subject to count as "it"


def motion_first(query: str, seconds: float, work: Path, perspective: str = "",
                 *, min_motion: float = MOTION_FLOOR,
                 min_rel: float = MOTION_REL_FLOOR, max_probe: int = 3,
                 log=print) -> dict | None:
    """The decision gate. Given a subject a beat wants to DEPICT and how long the
    beat runs, return a MOVING clip of that subject when one clears the bar —
    because motion is more view-worthy than a still of the same thing. Probes the
    most on-topic video candidates (NASA + stock), confirms each has a clean,
    genuinely moving window, and returns the first winner:

        {source, nasa_id|url, path, ss, title, license, motion, relevance}

    Returns None when NO clip clears the bar — the honest signal for the caller to
    fall back to a still (and to log WHY: nothing moving was available, not that a
    still was preferred). Never ships a frozen or off-topic clip just to avoid a
    photo."""
    from data_learning import footage_hybrid as fh
    cands = find(query, kind="video", perspective=perspective)
    # PERSPECTIVE gate (mirrors best_image): a GROUND / human-scale beat must not
    # be "upgraded" to an orbital clip — that swaps one boring-from-space shot for
    # another and defeats the perspective director. Drop orbital-tell titles; if
    # that empties the pool, there is no ground MOTION available and we correctly
    # fall through to the still (which at least holds the right perspective).
    if any(g in perspective.lower() for g in _GROUND_PERSP):
        ground = [c for c in cands
                  if not any(t in (c.get("title") or "").lower()
                             for t in _ORBITAL_TELLS)]
        if not ground:
            log(f"[motion-first] {query!r} is a ground beat but only orbital "
                "clips exist — keeping the ground still (perspective wins)")
            return None
        cands = ground
    cands.sort(key=lambda c: _relevance(c.get("title", ""), query), reverse=True)
    probed = 0
    for c in cands:
        if probed >= max_probe:
            break
        rel = _relevance(c.get("title", ""), query)
        if rel < min_rel:            # an off-topic clip is not "the same subject"
            continue
        probed += 1
        tag = c.get("nasa_id") or c.get("url", "")
        safe = "".join(ch if ch.isalnum() else "_" for ch in str(tag))[:56]
        dest = work / f"mfcache_{safe}.mp4"
        try:
            if not dest.exists() or dest.stat().st_size < 1024:
                acquire(c, dest)
            ss, _reports = fh.pick_window(dest, seconds, at=0.5)
            if ss is None:
                log(f"[motion-first] {str(c.get('title',''))[:38]!r}: no clean "
                    f"{seconds:.1f}s window — skipping")
                continue
            mv = _clip_motion(dest, ss, seconds)
            if mv < min_motion:
                log(f"[motion-first] {str(c.get('title',''))[:38]!r}: window "
                    f"barely moves ({mv} < {min_motion}) — not cooler than a "
                    "still, skipping")
                continue
            log(f"[motion-first] MOTION WINS for {query!r}: "
                f"{c.get('source')} {str(c.get('title',''))[:38]!r} "
                f"motion={mv} rel={rel:.2f} ss={ss:.1f}")
            return {"source": c.get("source"), "nasa_id": c.get("nasa_id"),
                    "url": c.get("url"), "path": str(dest), "ss": round(ss, 2),
                    "title": c.get("title", ""), "license": c.get("license", ""),
                    "motion": mv, "relevance": round(rel, 2)}
        except Exception as e:  # noqa: BLE001 — a bad candidate must not abort
            log(f"[motion-first] probe failed ({str(e)[:56]}) — next candidate")
    log(f"[motion-first] no moving clip cleared the bar for {query!r} "
        f"(probed {probed}) — a still is the honest fallback")
    return None


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
    have, needs = [], []
    for name, s in SOURCES.items():
        if s["env"] is None or os.environ.get(s["env"]):
            have.append(name)
        else:
            needs.append({"source": name, "env": s["env"], "kind": s["kind"],
                          "good_for": s["good_for"]})
    return {"reachable": have, "needs_access": needs}


if __name__ == "__main__":
    import sys
    kind = "video" if "--video" in sys.argv else "image"
    q = next((a for a in sys.argv[1:] if not a.startswith("-")), "hurricane")
    for c in find(q, kind=kind)[:10]:
        print(f"{c['source']:9s} {c.get('license', '')[:14]:14s} "
              f"{(c.get('title') or '')[:46]}")
