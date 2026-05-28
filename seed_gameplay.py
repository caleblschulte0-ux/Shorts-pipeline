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
    # (tag, source URL — direct A/V on archive.org). The .mov originals are
    # the full-resolution iPhone captures; archive.org's auto-derived .mp4
    # versions are heavily downscaled (222x480) and look bad once stacked.
    ("subway", "https://archive.org/download/rpreplay-final-1704729538/RPReplay_Final1704729538.mov"),
    # Minecraft parkour through the Nether (lava + nether brick) — actual
    # parkour movement, not Skywars PvP. The full clip is 160s; we trim
    # 15-145 to drop the YouTuber's intro / outro title cards before saving.
    ("minecraft", "https://archive.org/download/youtube-N6sPzFUrLqI/N6sPzFUrLqI.mp4"),
]

# After download, trim these tags to skip leading intro / trailing outro
# frames so the random gameplay picker stays in the actual gameplay window.
TRIMS: dict[str, tuple[float, float]] = {
    "minecraft": (15.0, 145.0),  # keep t=15s..t=145s
}


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


def trim(tag: str, span: tuple[float, float]) -> None:
    """Trim downloaded clip in-place to the [start, end] second range."""
    start, end = span
    files = [p for p in GAMEPLAY_DIR.iterdir() if p.stem.startswith(f"{tag}_")]
    if not files:
        return
    src = files[0]
    tmp = src.with_name(src.stem + "_trim" + src.suffix)
    subprocess.check_call([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-i", str(src),
        "-t", f"{end - start:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an",
        str(tmp),
    ])
    src.unlink()
    tmp.rename(src.with_suffix(".mp4"))


def main() -> int:
    GAMEPLAY_DIR.mkdir(parents=True, exist_ok=True)
    failed = 0
    for tag, q in SEEDS:
        if any(p.stem.startswith(f"{tag}_") for p in GAMEPLAY_DIR.iterdir()):
            print(f"   {tag}: already present, skipping")
            continue
        if fetch(tag, q) != 0:
            failed += 1
            continue
        if tag in TRIMS:
            print(f"   {tag}: trimming to {TRIMS[tag]}")
            trim(tag, TRIMS[tag])
    print(f"\ngameplay/ now contains: {[p.name for p in GAMEPLAY_DIR.iterdir()]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
