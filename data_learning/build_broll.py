#!/usr/bin/env python3
"""Build the bottom-strip b-roll into one long ``satisfying.mp4`` that the
studio renderer samples a rotating segment from (so the same footage is
reused across many videos without obviously repeating).

The theme is the **real pressure-washing / grime-reveal genre** (POV
"dirty surface -> clean" footage), not generic satisfying stock.

Sources, in priority order:

  1. LOCAL drop folder ``data_learning/broll/src/*.{mp4,mov,webm,mkv}``
     — drop any long pressure-washing video(s) here. **Best option.**
  2. PEXELS video API   — set ``PEXELS_API_KEY`` (free). Pulls real
     "pressure washing" clips.
  3. PIXABAY video API  — set ``PIXABAY_API_KEY`` (free).
  4. YOUTUBE (yt-dlp)   — set ``YT_COOKIES`` (path to a Netscape
     cookies.txt). Pulls the actual pressure-washing-satisfying genre.
     Required because YouTube bot-blocks datacenter IPs without cookies.
     Third-party content — only reuse clips you have the rights to.
  5. COVERR (no key)    — last-resort fallback; limited / loosely matched.

Run:
    python -m data_learning.build_broll                 # topic=pressure washing
    python -m data_learning.build_broll --topic "carpet cleaning"
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parent
BROLL_DIR = PKG / "broll"
SRC_DIR = BROLL_DIR / "src"        # user-dropped clips (priority)
DL_DIR = BROLL_DIR / "clips"       # downloaded clips
OUT = BROLL_DIR / "satisfying.mp4"

NW, NH, NFPS = 1080, 720, 30       # normalized strip size
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux) shorts-pipeline/1.0"}
VIDEO_EXT = (".mp4", ".mov", ".webm", ".mkv", ".m4v")

# The theme is real pressure-washing / grime-reveal footage (the POV
# "dirty surface -> clean" genre), NOT generic satisfying stock. The YouTube
# path pulls the actual genre but is restricted to **Creative Commons
# Attribution** uploads (reuse allowed) so the footage is free, real (not
# stock) and legally reusable. YouTube bot-blocks datacenter IPs, so a
# cookies file is required to download from a server.
PRESSURE_WASHING = "pressure washing"
YT_SEARCH = "pressure washing satisfying"
# YouTube search filter token for "Creative Commons" license (reuse allowed).
YT_CC_FILTER = "EgIwAQ%3D%3D"


def from_youtube(topic: str, dest: Path, n: int = 12,
                 cookies: str | None = None) -> list[Path]:
    """Download Creative-Commons pressure-washing clips from YouTube via yt-dlp.

    Only CC-Attribution (reuse-allowed) uploads are fetched, so the footage is
    free and legally reusable (attribute the creators). YouTube bot-blocks
    datacenter IPs, so set ``YT_COOKIES`` to a Netscape ``cookies.txt`` from a
    logged-in browser to download from a server. Returns the clip paths.
    """
    dest.mkdir(parents=True, exist_ok=True)
    q = YT_SEARCH if topic.strip().lower() == PRESSURE_WASHING else topic
    # Search restricted to the Creative Commons license filter.
    url = ("https://www.youtube.com/results?search_query=%s&sp=%s"
           % (urllib.parse.quote(q), YT_CC_FILTER))
    out_tmpl = str(dest / "yt_%(autonumber)03d.%(ext)s")
    cmd = ["yt-dlp", "--no-warnings", "--no-check-certificates",
           "--no-playlist", "--ignore-errors", "--playlist-end", str(n),
           "-f", "bv*[height<=1080][ext=mp4]/b[height<=1080]",
           "--max-filesize", "80M",
           # Belt-and-suspenders: skip anything not actually CC-licensed
           # and anything longer than ~5 min.
           "--match-filter", "license*='Creative Commons' & duration<300",
           "-o", out_tmpl, url]
    if cookies:
        cmd += ["--cookies", cookies]
    subprocess.run(cmd)
    return [p for p in sorted(dest.glob("yt_*"))
            if p.suffix.lower() in VIDEO_EXT and p.stat().st_size > 100_000]


def _get(url: str, timeout: int = 20) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read()


def from_pexels(topic: str, key: str, n: int = 20) -> list[str]:
    """Return downloadable mp4 URLs for `topic` from the Pexels video API."""
    url = ("https://api.pexels.com/videos/search?per_page=%d&query=%s"
           % (n, urllib.parse.quote(topic)))
    req = urllib.request.Request(url, headers={"Authorization": key, **UA})
    data = json.loads(urllib.request.urlopen(req, timeout=25).read())
    urls = []
    for v in data.get("videos", []):
        files = sorted(v.get("video_files", []),
                       key=lambda f: (f.get("height") or 0))
        # pick the largest <=1080p
        pick = None
        for f in files:
            if (f.get("height") or 0) <= 1080 and f.get("link"):
                pick = f["link"]
        if pick:
            urls.append(pick)
    return urls


def from_pixabay(topic: str, key: str, n: int = 20) -> list[str]:
    url = ("https://pixabay.com/api/videos/?key=%s&per_page=%d&q=%s"
           % (key, n, urllib.parse.quote(topic)))
    data = json.loads(_get(url, 25))
    urls = []
    for v in data.get("hits", []):
        vids = v.get("videos", {})
        f = vids.get("large") or vids.get("medium") or vids.get("small")
        if f and f.get("url"):
            urls.append(f["url"])
    return urls


def from_coverr(topic: str, n: int = 20) -> list[str]:
    url = ("https://coverr.co/api/videos?query=%s&page=1&urls=true"
           % urllib.parse.quote(topic))
    data = json.loads(_get(url, 20))
    urls = []
    for h in (data.get("hits") or [])[:n]:
        bf = h.get("base_filename")
        if bf:
            urls.append(f"https://cdn.coverr.co/videos/{bf}/1080p.mp4")
    return urls


def download_urls(urls: list[str], dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    out = []
    for i, u in enumerate(urls):
        p = dest / f"dl_{i:03d}.mp4"
        try:
            p.write_bytes(_get(u, 120))
            if p.stat().st_size > 100_000:
                out.append(p)
        except Exception as e:  # noqa: BLE001
            print(f"  dl fail {u[:60]}: {e}", file=sys.stderr)
    return out


def local_sources() -> list[Path]:
    if not SRC_DIR.exists():
        return []
    return [p for p in sorted(SRC_DIR.iterdir())
            if p.suffix.lower() in VIDEO_EXT]


def normalize(src: Path, dst: Path) -> bool:
    vf = (f"scale={NW}:{NH}:force_original_aspect_ratio=increase,"
          f"crop={NW}:{NH},fps={NFPS},setsar=1")
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-an",
         "-vf", vf, "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", str(dst)])
    return r.returncode == 0 and dst.exists()


def build(topic: str) -> Path:
    clips = local_sources()
    src_label = "local drop folder"
    if not clips:
        key = os.environ.get("PEXELS_API_KEY")
        pix = os.environ.get("PIXABAY_API_KEY")
        ytc = os.environ.get("YT_COOKIES")
        try:
            if key:
                clips = download_urls(from_pexels(topic, key), DL_DIR); src_label = "Pexels"
            elif pix:
                clips = download_urls(from_pixabay(topic, pix), DL_DIR); src_label = "Pixabay"
            elif ytc:
                clips = from_youtube(topic, DL_DIR, cookies=ytc); src_label = "YouTube (yt-dlp)"
            else:
                clips = download_urls(from_coverr(topic), DL_DIR); src_label = "Coverr (no-key fallback)"
        except Exception as e:  # noqa: BLE001
            print(f"[broll] source fetch failed: {e}", file=sys.stderr)
    if not clips:
        raise SystemExit(
            "[broll] no footage. Drop a pressure-washing video into "
            f"{SRC_DIR.relative_to(REPO)}/, or set PEXELS_API_KEY / YT_COOKIES, "
            "then re-run.")
    print(f"[broll] {len(clips)} clips from {src_label}")

    norm_dir = BROLL_DIR / "_norm"
    norm_dir.mkdir(parents=True, exist_ok=True)
    normed = []
    for i, c in enumerate(clips):
        d = norm_dir / f"n{i:03d}.mp4"
        if normalize(c, d):
            normed.append(d)
    if not normed:
        raise SystemExit("[broll] nothing normalized")
    listf = norm_dir / "list.txt"
    listf.write_text("\n".join(f"file '{p}'" for p in normed) + "\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(listf), "-c", "copy", str(OUT)],
                   check=True)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(OUT)],
                         capture_output=True, text=True).stdout.strip()
    print(f"[broll] built {OUT} ({float(dur):.0f}s) from {src_label}")
    return OUT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default=PRESSURE_WASHING)
    build(ap.parse_args().topic)
    return 0


if __name__ == "__main__":
    sys.exit(main())
