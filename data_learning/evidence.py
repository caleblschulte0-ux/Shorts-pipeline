#!/usr/bin/env python3
"""EVIDENCE SHOTS (CURIOSITY_BRAIN §7.5 v7): real imagery cuts the hero
moments — animation EXPLAINS, evidence GROUNDS.

THE ON-TOPIC GUARANTEE (operator law: other channels drown in wrong
stock — we will not):
  1. NASA Image Library first (keyless, public domain, and it returns
     THE actual thing, not lookalike stock).
  2. Metadata relevance gate: a search result is accepted only when the
     query's key terms appear in its own title/description; below
     threshold we try the next result, then GIVE UP CLEANLY — "a wrong
     picture is worse than no picture" and the beat keeps its animation.
  3. Pinned evidence: {"nasa_id": ...} bypasses search entirely
     (flagship stories ship fully pinned).
  4. Every accepted image lands on the evidence contact sheet for
     eye-QA before anything publishes.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

RELEVANCE_MIN = 0.6


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "curiosity-pipeline/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# Metadata can match while the PICTURE is wrong (the probe's transport
# crate, a survey poster). Penalize titles that scream "not the thing
# itself" — and pin flagship stories so search never decides.
_NOISE = ("transport", "offload", "arrival", "marshal", "crate",
          "packing", "poster", "chart", "logo", "ceremony", "briefing",
          "press", "interview", "crowd", "administrator")


def _relevance(query: str, title: str, desc: str) -> float:
    terms = [w for w in re.findall(r"[a-z0-9]+", query.lower())
             if len(w) > 3]
    if not terms:
        return 0.0
    hay = f"{title} {desc}".lower()
    score = sum(1 for t in terms if t in hay) / len(terms)
    if any(n in title.lower() for n in _NOISE):
        score -= 0.5
    return score


def _download_asset(nasa_id: str, dest: Path) -> Path:
    """Pick the largest reasonable jpg from a NASA asset manifest."""
    man = json.loads(_get(
        f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nasa_id)}"))
    hrefs = [i.get("href", "") for i in man["collection"]["items"]]
    jpgs = [h for h in hrefs if h.lower().endswith((".jpg", ".jpeg"))]
    for tag in ("~large", "~medium", "~orig", "~small", "~thumb"):
        pick = next((h for h in jpgs if tag in h), None)
        if pick:
            break
    else:
        pick = jpgs[0] if jpgs else None
    if not pick:
        raise RuntimeError(f"no jpg asset for {nasa_id}")
    dest.write_bytes(_get(pick))
    return dest


def fetch_nasa(spec: dict, dest: Path):
    """Returns (path, credit) or raises. Honors pinned nasa_id."""
    if spec.get("nasa_id"):
        nasa_id = str(spec["nasa_id"])
        _download_asset(nasa_id, dest)
        return dest, f"NASA image {nasa_id} (public domain)"
    query = str(spec.get("query", "")).strip()
    if not query:
        raise RuntimeError("evidence needs a query or nasa_id")
    res = json.loads(_get(
        "https://images-api.nasa.gov/search?media_type=image&q="
        + urllib.parse.quote(query)))
    for item in res["collection"]["items"][:10]:
        d = (item.get("data") or [{}])[0]
        score = _relevance(query, d.get("title", ""),
                           d.get("description", "") or "")
        if score < RELEVANCE_MIN:
            continue
        _download_asset(d["nasa_id"], dest)
        return dest, (f"NASA: {d.get('title', d['nasa_id'])} "
                      "(public domain)")
    raise RuntimeError(
        f"no NASA result passed the on-topic gate for {query!r}")


def fetch_footage(spec: dict, work: Path, tag: str):
    """Real NASA VIDEO footage for a B-roll beat (CURIOSITY_BRAIN §7.5 v9 —
    the footage hybrid). Honors a pinned {"footage_nasa_id": ...}; otherwise
    searches with {"footage_query": ...} (or falls back to "query"), keeping
    only clips that read as real camera footage (animations/viz rejected).
    Returns (path, credit). The assembler cuts it full-frame from a black-free
    window and dissolves it in — never a pasted rectangle."""
    from data_learning.footage_hybrid import (
        download_video, is_real_footage, search_footage)
    dest = work / f"footage_{tag}.mp4"
    pinned = spec.get("footage_nasa_id")
    if pinned:
        download_video(str(pinned), dest)
        return dest, f"NASA video {pinned} (public domain)"
    q = str(spec.get("footage_query") or spec.get("query") or "").strip()
    if not q:
        raise RuntimeError("footage needs footage_nasa_id or a query")
    hits = search_footage(q, limit=6)
    if not hits:
        raise RuntimeError(f"no real NASA footage passed the gate for {q!r}")
    download_video(hits[0]["nasa_id"], dest)
    return dest, (f"NASA: {hits[0]['title'][:70]} (public domain)")


def fetch_evidence(spec: dict, work: Path, tag: str):
    """NASA first; Pexels fallback only when the spec allows it
    (earthly generics). Returns (kind, path, credit): kind is
    'image' or 'video'. Raises when nothing passes — the beat then
    keeps its animation.

    When the spec asks for footage ({"footage": true} or a
    footage_nasa_id/footage_query), real NASA VIDEO is tried FIRST — the
    photoreal beats the CG substrate can't reach, panel-certified as
    full-frame dissolved B-roll, not pasted stills (§7.5 v9)."""
    if spec.get("footage") or spec.get("footage_nasa_id") \
            or spec.get("footage_query"):
        try:
            p, credit = fetch_footage(spec, work, tag)
            return "video", p, credit
        except Exception as foot_err:  # noqa: BLE001 — fall through to stills
            print(f"[evidence] footage gate failed ({foot_err}); "
                  "trying NASA still", file=__import__("sys").stderr)
    dest = work / f"evidence_{tag}.jpg"
    try:
        p, credit = fetch_nasa(spec, dest)
        return "image", p, credit
    except Exception as nasa_err:  # noqa: BLE001
        if not spec.get("stock_ok"):
            raise RuntimeError(
                f"NASA gate failed ({nasa_err}); stock fallback not "
                "allowed for this evidence") from nasa_err
        from stock_search import fetch_top
        d = work / f"evstock_{tag}"
        d.mkdir(exist_ok=True)
        c = fetch_top(str(spec.get("query", "")), d)
        if not c or not c.get("path"):
            raise RuntimeError("stock fallback found nothing")
        return "video", Path(c["path"]), c.get(
            "credit", f"Stock footage: {spec.get('query')} (Pexels)")
