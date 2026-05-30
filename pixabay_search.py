#!/usr/bin/env python3
"""Pixabay Videos search client.

Returns ranked candidate clips (mirrors the shape of pexels_search.py),
so the pipeline can use either source interchangeably.

Required env: PIXABAY_API_KEY
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


PIXABAY_API = "https://pixabay.com/api/videos/"


def search(
    query: str,
    *,
    per_page: int = 20,
    orientation: str = "horizontal",  # pixabay uses 'horizontal' not 'landscape'
    min_duration: int = 4,
    max_duration: int = 30,
    min_width: int = 1080,
) -> list[dict]:
    """Return Pixabay videos matching `query`. Filtered to landscape,
    HD-or-better, in a usable duration range."""
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        raise RuntimeError("PIXABAY_API_KEY env var not set")
    params = urllib.parse.urlencode({
        "key": key,
        "q": query,
        "per_page": per_page,
        "orientation": orientation,
        "video_type": "film",
        "safesearch": "true",
    })
    req = urllib.request.Request(
        f"{PIXABAY_API}?{params}",
        headers={
            "User-Agent": "shorts-pipeline/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())

    out: list[dict] = []
    for v in data.get("hits", []) or []:
        dur = int(v.get("duration") or 0)
        if dur < min_duration or dur > max_duration:
            continue
        # Pixabay returns nested video sources keyed by quality.
        files = v.get("videos") or {}
        best = None
        # Quality preference: medium > large > tiny (small=480p, medium=960x540,
        # large=1080p+). We want at least 1080 width.
        for q in ("large", "medium", "small", "tiny"):
            f = files.get(q)
            if not f:
                continue
            w = int(f.get("width") or 0)
            if w < min_width:
                continue
            if best is None or int(f.get("width") or 0) > int(best.get("width") or 0):
                best = f
        if best is None:
            # Fallback: take whatever's largest, even if sub-1080.
            sized = [f for f in files.values() if isinstance(f, dict)]
            if sized:
                best = max(sized, key=lambda f: int(f.get("width") or 0))
        if not best:
            continue
        out.append({
            "id": v["id"],
            "duration": dur,
            "url": v.get("pageURL"),
            "user": v.get("user"),
            "width": best.get("width"),
            "height": best.get("height"),
            "download_url": best.get("url"),
            "source": "pixabay",
        })
    return out


def download(video: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        video["download_url"],
        headers={"User-Agent": "shorts-pipeline/1.0"},
    )
    with urllib.request.urlopen(req, timeout=180) as r, open(out_path, "wb") as f:
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return out_path


def fetch_top(query: str, dest: Path, **search_kwargs) -> dict:
    matches = search(query, **search_kwargs)
    if not matches:
        raise RuntimeError(f"no Pixabay results for query: {query!r}")
    top = matches[0]
    path = dest / f"pixabay_{top['id']}.mp4"
    if not path.exists():
        download(top, path)
    top["path"] = str(path)
    return top


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: pixabay_search.py 'query' [dest_dir]")
    q = sys.argv[1]
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/pixabay")
    top = fetch_top(q, dest)
    print(json.dumps(top, indent=2))
