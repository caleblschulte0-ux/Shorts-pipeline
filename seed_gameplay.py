#!/usr/bin/env python3
"""Seed the gameplay/ folder with a couple of long no-copyright clips.

Run once per machine. Default fetches one Subway Surfers and one Minecraft
parkour compilation from YouTube via yt-dlp. Edit SEEDS to taste.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GAMEPLAY_DIR = ROOT / "gameplay"

SEEDS = [
    # (tag, youtube search query)
    ("subway", "ytsearch1:subway surfers gameplay no copyright 10 minutes"),
    ("minecraft", "ytsearch1:minecraft parkour gameplay no copyright 10 minutes"),
]


def fetch(tag: str, query: str) -> int:
    out_tmpl = str(GAMEPLAY_DIR / f"{tag}_%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        query,
    ]
    print(f"-> {tag}: {query}")
    return subprocess.call(cmd)


def main() -> int:
    GAMEPLAY_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    for tag, q in SEEDS:
        if any(p.stem.startswith(f"{tag}_") for p in GAMEPLAY_DIR.iterdir()):
            print(f"   {tag}: already present, skipping")
            continue
        if fetch(tag, q) != 0:
            failed += 1
    print(f"\ngameplay/ now contains: {[p.name for p in GAMEPLAY_DIR.iterdir()]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
