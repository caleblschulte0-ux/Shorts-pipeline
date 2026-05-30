#!/usr/bin/env python3
"""Tiny Pexels Videos client.

Searches Pexels by keyword and returns ranked candidate video files,
downloading the chosen one to disk. Pexels free API ceiling is 200
requests/hour and 20k/month, plenty for a short pipeline.

Required env: PEXELS_API_KEY
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


PEXELS_API = "https://api.pexels.com/videos/search"


def search(
    query: str,
    *,
    per_page: int = 15,
    orientation: str = "landscape",
    min_duration: int = 4,
    max_duration: int = 30,
) -> list[dict]:
    """Return Pexels videos matching `query`, filtered + sorted by
    usefulness for B-roll: long enough to cut without looping, short
    enough not to balloon the download."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        raise RuntimeError("PEXELS_API_KEY env var not set")
    params = urllib.parse.urlencode({
        "query": query,
        "per_page": per_page,
        "orientation": orientation,
    })
    req = urllib.request.Request(
        f"{PEXELS_API}?{params}",
        headers={
            "Authorization": key,
            "User-Agent": "shorts-pipeline/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    videos = data.get("videos", []) or []
    out: list[dict] = []
    for v in videos:
        dur = int(v.get("duration") or 0)
        if dur < min_duration or dur > max_duration:
            continue
        files = v.get("video_files") or []
        # Prefer 1280x720 if available, else 1920x1080, else the largest
        # under-1080p that's still landscape.
        best = None
        for f in files:
            w = int(f.get("width") or 0)
            h = int(f.get("height") or 0)
            if h not in (720, 1080):
                continue
            if best is None or (w == 1280 and best.get("width") != 1280):
                best = f
        if best is None and files:
            best = max(files, key=lambda f: int(f.get("width") or 0))
        if not best:
            continue
        out.append({
            "id": v["id"],
            "duration": dur,
            "url": v.get("url"),
            "user": (v.get("user") or {}).get("name"),
            "width": best.get("width"),
            "height": best.get("height"),
            "download_url": best.get("link"),
        })
    return out


def download(video: dict, out_path: Path) -> Path:
    """Download a Pexels video file by url to disk."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        video["download_url"],
        headers={"User-Agent": "shorts-pipeline/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return out_path


def fetch_top(query: str, dest: Path, **search_kwargs) -> dict:
    """Search + download the top-ranked match. Returns the metadata dict
    (with `path` added pointing to the downloaded file)."""
    matches = search(query, **search_kwargs)
    if not matches:
        raise RuntimeError(f"no Pexels results for query: {query!r}")
    top = matches[0]
    path = dest / f"pexels_{top['id']}.mp4"
    if not path.exists():
        download(top, path)
    top["path"] = str(path)
    return top


if __name__ == "__main__":
    # CLI: python pexels_search.py "query string" [dest_dir]
    if len(sys.argv) < 2:
        sys.exit("usage: pexels_search.py 'query' [dest_dir]")
    q = sys.argv[1]
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/pexels")
    top = fetch_top(q, dest)
    print(json.dumps(top, indent=2))
