#!/usr/bin/env python3
"""Build the bottom-strip b-roll into one long ``satisfying.mp4`` that the
studio renderer samples a rotating segment from (so the same footage is
reused across many videos without obviously repeating).

The default theme is **oddly-satisfying ASMR macro/pour footage** (slow-mo
pours, honeycomb dripping, falling salt & spices, frothing milk, whipped
cream, espresso) — not pressure washing.

Sources, in priority order:

  1. LOCAL drop folder ``data_learning/broll/src/*.{mp4,mov,webm,mkv}``
     — drop any long satisfying video(s) here. **Best option.**
  2. PEXELS video API   — set ``PEXELS_API_KEY`` (free). Pulls real
     "<topic>" clips.
  3. PIXABAY video API  — set ``PIXABAY_API_KEY`` (free).
  4. COVERR (no key)    — fallback. For the default ``satisfying`` topic this
     curates clean ASMR clips across several sub-queries; for any other topic
     it does a plain Coverr search.

Run:
    python -m data_learning.build_broll                 # topic=satisfying
    python -m data_learning.build_broll --topic "glass blowing"

Note on YouTube: yt-dlp works but YouTube bot-blocks datacenter IPs without
cookies. If you have a long clip, just drop it in broll/src/ (option 1).
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

# Default theme. Coverr's no-key search is loosely tag-matched, so a single
# term is unreliable — for this theme we aggregate several sub-queries and
# keep only clips whose *title* reads like true ASMR macro/pour footage.
SATISFYING = "satisfying"
CURATED_QUERIES = (
    "pouring", "slow motion food", "macro food", "honey", "honeycomb",
    "cream", "milk pour", "chocolate", "coffee pour", "espresso",
    "salt", "sugar", "dough", "sauce", "batter", "syrup",
)
# A clip is kept only if its title contains one of these (satisfying action /
# material) terms...
CURATED_GOOD = (
    "pour", "drip", "honeycomb", "honey", "salt", "peppercorn", "spice",
    "sprinkle", "syrup", "whipped cream", "melted", "melting", "espresso",
    "crema", "froth", "foam", "batter", "dough", "swirl", "stir",
    "splash", "basil", "pesto", "cereal", "truffle", "butter", "sugar",
)
# ...and none of these (people / lifestyle / place) terms.
CURATED_BAD = (
    "drinking", "drinks", "drink from", "girlfriend", "boyfriend", "office",
    "bitcoin", "price", "reading", "working", "friends", "enjoying", "cafe",
    "paris", "headset", "battery", "teamwork", "monastery", "workout",
    "jogging", "couple", "smartphone", "field", "boat", "excursion", "flag",
    "architecture", "view of", "hugging", "street", "buying", "pizza",
    "woman", "girl", "man ", "guy", "people", " her ", " his ",
)


def from_coverr_curated(n: int = 40) -> list[str]:
    """Aggregate clean satisfying clips across several Coverr sub-queries.

    No API key required. Returns de-duplicated direct mp4 URLs whose titles
    pass the ASMR keyword filter, capped at ``n``.
    """
    seen: dict[str, None] = {}
    for q in CURATED_QUERIES:
        try:
            url = ("https://coverr.co/api/videos?query=%s&page=1&urls=true"
                   % urllib.parse.quote(q))
            data = json.loads(_get(url, 15))
        except Exception as e:  # noqa: BLE001
            print(f"  coverr '{q}' fail: {e}", file=sys.stderr)
            continue
        for h in (data.get("hits") or []):
            title = (h.get("title") or "").lower().strip()
            if any(b in title for b in CURATED_BAD):
                continue
            if not any(g in title for g in CURATED_GOOD):
                continue
            link = (h.get("urls") or {}).get("mp4")
            if not link:
                bf = h.get("base_filename")
                link = f"https://cdn.coverr.co/videos/{bf}/1080p.mp4" if bf else None
            if link and link not in seen:
                seen[link] = None
        if len(seen) >= n:
            break
    return list(seen)[:n]


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
        is_default = topic.strip().lower() == SATISFYING
        try:
            if key:
                clips = download_urls(from_pexels(topic, key), DL_DIR); src_label = "Pexels"
            elif pix:
                clips = download_urls(from_pixabay(topic, pix), DL_DIR); src_label = "Pixabay"
            elif is_default:
                clips = download_urls(from_coverr_curated(), DL_DIR)
                src_label = "Coverr curated (no-key)"
            else:
                clips = download_urls(from_coverr(topic), DL_DIR); src_label = "Coverr (no-key fallback)"
        except Exception as e:  # noqa: BLE001
            print(f"[broll] source fetch failed: {e}", file=sys.stderr)
    if not clips:
        raise SystemExit(
            "[broll] no footage. Drop a satisfying video into "
            f"{SRC_DIR.relative_to(REPO)}/ or set PEXELS_API_KEY, then re-run.")
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
    ap.add_argument("--topic", default=SATISFYING)
    build(ap.parse_args().topic)
    return 0


if __name__ == "__main__":
    sys.exit(main())
