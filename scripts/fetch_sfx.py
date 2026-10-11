#!/usr/bin/env python3
"""Fetch a well-known meme sound effect so the editor can use the REAL one.

Operator, 2026-10-11, of the synthesised zoom boom: "that's not it ... the
Vine boom sound effect ... that's for, like, moments ... go get it." A
synthesised copy of a sound everybody knows reads as a knock-off, so this
pulls the actual clip from a public soundboard (myinstants), trims the
silence off both ends and writes a 48 kHz mono wav the editor can mix.

It runs in CI (`fetch-sfx.yml`), which publishes the result to
`preview-renders:sfx/<run id>/` for a session to check by ear and commit
under `assets/sfx/`. Nothing here posts anything.

    python scripts/fetch_sfx.py --name vine_boom --query "vine boom" --out sfx
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BOARD = "https://www.myinstants.com"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def candidates(query: str) -> list[str]:
    """Sound URLs the board lists for `query`, best match first."""
    words = [w for w in re.split(r"\W+", query.lower()) if w]
    urls: list[str] = []
    try:
        page = _get(f"{BOARD}/en/search/?name="
                    f"{urllib.parse.quote_plus(query)}").decode("utf-8",
                                                                 "replace")
        for m in re.findall(r"/media/sounds/[^'\"\s)]+\.mp3", page):
            u = BOARD + m
            if u not in urls:
                urls.append(u)
    except Exception as e:  # noqa: BLE001
        print(f"[sfx] search failed: {type(e).__name__}: {e}", flush=True)
    # the file names that match every query word first
    urls.sort(key=lambda u: -sum(w in u.lower() for w in words))
    guess = f"{BOARD}/media/sounds/{'-'.join(words)}.mp3"
    if guess not in urls:
        urls.append(guess)
    return urls


def _probe(path: Path) -> float:
    try:
        return float(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)], text=True, timeout=30).strip())
    except Exception:  # noqa: BLE001
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--out", default="sfx")
    ap.add_argument("--max-s", type=float, default=6.0)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    tried = []
    for url in candidates(a.query)[:8]:
        raw = out / f"{a.name}.source.mp3"
        try:
            data = _get(url)
        except Exception as e:  # noqa: BLE001
            tried.append({"url": url, "error": f"{type(e).__name__}: {e}"})
            continue
        raw.write_bytes(data)
        dur = _probe(raw)
        tried.append({"url": url, "bytes": len(data), "seconds": dur})
        if not (0.2 <= dur <= a.max_s):
            continue
        wav = out / f"{a.name}.wav"
        # trim leading/trailing silence, mono 48 kHz, peak-normalised
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af",
             "silenceremove=start_periods=1:start_threshold=-50dB,"
             "areverse,silenceremove=start_periods=1:start_threshold=-60dB,"
             "areverse,loudnorm=I=-14:TP=-1",
             "-ac", "1", "-ar", "48000", str(wav)], check=True)
        (out / f"{a.name}.json").write_text(json.dumps(
            {"name": a.name, "query": a.query, "source": url,
             "seconds": _probe(wav), "tried": tried}, indent=1))
        print(f"[sfx] {a.name}: {url} -> {wav} ({_probe(wav):.2f}s)",
              flush=True)
        return 0
    (out / f"{a.name}.json").write_text(json.dumps(
        {"name": a.name, "query": a.query, "tried": tried}, indent=1))
    print(f"::error::no usable sound for {a.query!r}: {tried}", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
