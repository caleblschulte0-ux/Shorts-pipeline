#!/usr/bin/env python3
"""Fetch the royalty-free music library (Kevin MacLeod / incompetech, CC BY 4.0)
into data_learning/music/<vibe>/. Idempotent — skips files already present.

Licensing: every track is Kevin MacLeod, licensed Creative Commons By
Attribution 4.0. The renderer/uploader appends the required credit to each
video's description (see post_stories.py / studio_render). CC-BY allows
commercial use with attribution.

Run once locally, and in CI (cached) before rendering:
    python3 scripts/fetch_music.py
"""
from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUSIC = ROOT / "data_learning" / "music"
BASE = "https://incompetech.com/music/royalty-free/mp3-royaltyfree"

# vibe -> [track titles]. Deliberately NEUTRAL / UPBEAT-adjacent ~85% of the
# time (this is a teaching channel, not a thriller). Only the "cinematic" pool
# keeps one atmospheric track (Lightless Dawn) for space/nature awe. Each vibe
# has a few so videos still vary.
LIBRARY = {
    "calm":      ["Wholesome", "Carefree", "Almost New"],
    "dark":      ["Inspired", "Cool Vibes", "Almost New"],
    "cinematic": ["Cool Vibes", "Inspired", "Lightless Dawn"],
    "pulse":     ["Cool Vibes", "Bossa Antigua", "Inspired"],
}


def _slug(title: str) -> str:
    return title.lower().replace(" ", "-").replace("'", "")


def main() -> int:
    got = skipped = failed = 0
    for vibe, titles in LIBRARY.items():
        d = MUSIC / vibe
        d.mkdir(parents=True, exist_ok=True)
        for title in titles:
            out = d / f"{_slug(title)}.mp3"
            if out.exists() and out.stat().st_size > 400_000:
                skipped += 1
                continue
            url = f"{BASE}/{urllib.parse.quote(title)}.mp3"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                if len(data) < 400_000:
                    raise ValueError(f"too small ({len(data)}b)")
                out.write_bytes(data)
                got += 1
                print(f"  ✓ {vibe}/{out.name} ({len(data)//1024} KB)")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  ✗ {vibe}/{title}: {e}", file=sys.stderr)
    print(f"music: {got} fetched, {skipped} cached, {failed} failed")
    # Don't hard-fail CI if a track 404s — the renderer falls back to synth.
    return 0


if __name__ == "__main__":
    sys.exit(main())
