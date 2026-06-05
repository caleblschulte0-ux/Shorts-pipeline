#!/usr/bin/env python3
"""Build the long "oddly-satisfying" b-roll used in the bottom strip.

Downloads free, no-API-key process clips from Mixkit (CNC machining,
pressure washing, glass blowing, welding, laser cutting, woodworking...),
normalizes them to one size, and concatenates them into a single long
``satisfying.mp4``. The studio renderer then samples a *different* segment
each render (tracked in a state file) so the same footage is reused across
many videos without obviously repeating.

Re-run any time to refresh/extend the pool:
    python -m data_learning.build_broll
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import mixkit_search as mk  # noqa: E402

BROLL_DIR = PKG / "broll"
CLIPS_DIR = BROLL_DIR / "clips"
OUT = BROLL_DIR / "satisfying.mp4"

# Satisfying industrial / process categories that exist on Mixkit.
QUERIES = ["cnc machine", "welding", "pressure washing", "cleaning",
           "glass blowing", "laser cutting", "woodworking",
           "factory machine", "glass"]

# Normalized size for the bottom strip (renderer scales to the exact band).
NW, NH, NFPS = 1080, 720, 30


def fetch_clips() -> list[Path]:
    seen: dict[str, dict] = {}
    for q in QUERIES:
        try:
            for r in mk.search(q, per_page=6):
                seen[r["id"]] = r
        except Exception as e:  # noqa: BLE001
            print(f"  search '{q}' failed: {e}", file=sys.stderr)
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for vid, item in seen.items():
        try:
            p = mk.download(item, CLIPS_DIR)
            if p.stat().st_size > 50_000:
                paths.append(p)
        except Exception as e:  # noqa: BLE001
            print(f"  download {vid} failed: {e}", file=sys.stderr)
    return paths


def normalize(src: Path, dst: Path) -> bool:
    vf = (f"scale={NW}:{NH}:force_original_aspect_ratio=increase,"
          f"crop={NW}:{NH},fps={NFPS},setsar=1")
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-an",
         "-vf", vf, "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
         "-pix_fmt", "yuv420p", str(dst)])
    return r.returncode == 0 and dst.exists()


def build() -> Path:
    clips = fetch_clips()
    print(f"[broll] {len(clips)} source clips")
    norm_dir = BROLL_DIR / "_norm"
    norm_dir.mkdir(parents=True, exist_ok=True)
    normed = []
    for i, c in enumerate(sorted(clips)):
        d = norm_dir / f"n{i:03d}.mp4"
        if normalize(c, d):
            normed.append(d)
    if not normed:
        raise RuntimeError("no clips normalized")
    listf = norm_dir / "list.txt"
    listf.write_text("\n".join(f"file '{p}'" for p in normed) + "\n")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listf), "-c", "copy", str(OUT)], check=True)
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(OUT)], capture_output=True, text=True).stdout.strip()
    print(f"[broll] built {OUT} ({float(dur):.0f}s)")
    return OUT


if __name__ == "__main__":
    build()
