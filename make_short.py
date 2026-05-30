#!/usr/bin/env python3
"""Build a 9:16 YouTube Short from any video URL or local file.

Stacks the source on top of a random gameplay loop, optionally lays
a generated voiceover over it, transcribes the resulting audio with
Whisper, and burns in TikTok-style captions.

The individual stages (source fetch, gameplay pick, TTS, audio mix,
captions, render) now live in the shared/ core so the livestream and
localize modules can reuse them. This file is a thin CLI + orchestration
wrapper; its output is byte-identical to the pre-refactor version
(see tools/verify_identical.py).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from shared import (  # noqa: E402
    GAMEPLAY_DIR,
    OUTPUT_DIR,
    compose,
    download_source,
    ffprobe_duration,
    group_words,
    mix_audio,
    pick_gameplay,
    run,
    synthesize_voiceover,
    transcribe,
    write_ass,
)


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Make a YouTube Short from any video source.")
    ap.add_argument("input", help="URL or local file path")
    ap.add_argument("--script", help="Voiceover script (uses edge-tts).")
    ap.add_argument(
        "--gameplay", default="random",
        help="gameplay tag substring (e.g. subway, minecraft) or 'random'",
    )
    ap.add_argument("--start", type=float, default=0.0, help="seek N seconds into the source before clipping (skip intros)")
    ap.add_argument("--duration", type=float, default=60.0, help="output length cap in seconds (default 60, Shorts max)")
    ap.add_argument("--upload", help="comma-separated upload targets (youtube,tiktok,instagram,facebook,rumble). Requires per-platform env vars; see uploaders.py.")
    ap.add_argument("--title", help="title for uploaded post (defaults to first 80 chars of --script)")
    ap.add_argument("--description", help="description for uploaded post (defaults to --script)")
    ap.add_argument("--tags", help="comma-separated tags for uploaded post")
    ap.add_argument("--publish-at", help="RFC3339 timestamp (2026-05-29T13:00:00Z); uploads as private, auto-publishes at that time. YouTube only for now.")
    ap.add_argument("--keep-temp", action="store_true", help="don't delete the work dir")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GAMEPLAY_DIR.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="short_"))

    try:
        print(f"[1/6] fetching source: {args.input}")
        source = download_source(args.input, workdir)
        src_dur = ffprobe_duration(source)
        if args.start > 0:
            if args.start >= src_dur - 1:
                sys.exit(f"--start {args.start}s exceeds source duration {src_dur:.2f}s")
            trimmed = workdir / f"source_trim{source.suffix}"
            run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-ss", f"{args.start:.3f}", "-i", str(source),
                "-c", "copy", str(trimmed),
            ])
            source = trimmed
            src_dur = ffprobe_duration(source)
            print(f"      seeked to {args.start:.2f}s, remaining {src_dur:.2f}s")
        # Cap to --duration (default 60, YouTube Shorts max).
        target = min(src_dur, args.duration)
        print(f"      duration: {src_dur:.2f}s (using {target:.2f}s)")

        print(f"[2/6] picking gameplay: {args.gameplay}")
        gameplay = pick_gameplay(args.gameplay, target, workdir)

        voice = None
        if args.script:
            print("[3/6] synthesizing voiceover (edge-tts)")
            voice = synthesize_voiceover(args.script, workdir)
        else:
            print("[3/6] no --script, skipping voiceover")

        print("[4/6] mixing audio")
        audio = mix_audio(source, voice, workdir)

        print("[5/6] transcribing with whisper")
        words = transcribe(voice if voice else audio)
        chunks = group_words(words, per_chunk=3)
        subs = workdir / "captions.ass"
        write_ass(chunks, subs)
        print(f"      {len(words)} words -> {len(chunks)} caption chunks")

        ts = time.strftime("%Y%m%d-%H%M%S")
        out = OUTPUT_DIR / f"short_{ts}.mp4"
        print(f"[6/6] composing -> {out}")
        compose(source, gameplay, audio, subs, out, target)

        print(f"\ndone: {out}")

        if args.upload:
            from uploaders import upload_to
            title = args.title or (args.script or "").strip()[:80] or out.stem
            description = args.description or (args.script or "")
            tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
            upload_to(
                args.upload.split(","), out,
                title=title, description=description, tags=tags,
                publish_at=args.publish_at,
            )

        return 0
    finally:
        if args.keep_temp:
            print(f"workdir kept: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
