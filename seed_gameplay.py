#!/usr/bin/env python3
"""Seed the gameplay/ folder with a couple of long no-copyright clips.

Run once per machine. Pulls a Subway Surfers clip and a Minecraft parkour
clip from Internet Archive (works in restricted-egress environments where
YouTube's signed CDN URLs IP-bind and break across rotating egress IPs).
Sources are public archive.org items. Edit SEEDS to taste.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GAMEPLAY_DIR = ROOT / "gameplay"

SEEDS = [
    # (tag, source URL — direct MP4 on archive.org)
    ("subway", "https://archive.org/download/vcompress_340/vcompress_340.mp4"),
    ("minecraft", "https://archive.org/download/UsingParkourToWinSkywars/using%20parkour%20to%20win%20skywars.mp4"),
]


def fetch(tag: str, url: str) -> int:
    out_tmpl = str(GAMEPLAY_DIR / f"{tag}_%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "b",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        url,
    ]
    print(f"-> {tag}: {url}")
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
