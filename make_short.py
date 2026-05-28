#!/usr/bin/env python3
"""Build a 9:16 YouTube Short from any video URL or local file.

Stacks the source on top of a random gameplay loop, optionally lays
a generated voiceover over it, transcribes the resulting audio with
Whisper, and burns in TikTok-style captions.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
GAMEPLAY_DIR = ROOT / "gameplay"
OUTPUT_DIR = ROOT / "output"

W, H = 1080, 1920
HALF_H = H // 2
TTS_VOICE = "en-US-GuyNeural"

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".m4v", ".avi"}


# ---------- shell helpers ----------

def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command, streaming output unless capture=True."""
    if capture:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
    return subprocess.run(cmd, check=True)


def ffprobe_duration(path: Path) -> float:
    out = run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            str(path),
        ],
        capture=True,
    ).stdout.strip()
    return float(out)


# ---------- source ----------

def is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s))


def download_source(url_or_file: str, workdir: Path) -> Path:
    if not is_url(url_or_file):
        src = Path(url_or_file).expanduser().resolve()
        if not src.exists():
            sys.exit(f"input not found: {src}")
        dst = workdir / f"source{src.suffix}"
        shutil.copy2(src, dst)
        return dst

    out_tmpl = str(workdir / "source.%(ext)s")
    run([
        "yt-dlp",
        "--no-playlist",
        "--quiet", "--no-warnings",
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        url_or_file,
    ])
    for p in workdir.iterdir():
        if p.stem == "source" and p.suffix.lower() in VIDEO_EXTS:
            return p
    sys.exit("yt-dlp did not produce a source video")


# ---------- gameplay ----------

def list_gameplay(tag: str) -> list[Path]:
    if not GAMEPLAY_DIR.exists():
        return []
    files = [p for p in GAMEPLAY_DIR.iterdir() if p.suffix.lower() in VIDEO_EXTS]
    if tag == "random":
        return files
    return [p for p in files if tag.lower() in p.stem.lower()]


def pick_gameplay(tag: str, target_seconds: float, workdir: Path) -> Path:
    pool = list_gameplay(tag)
    if not pool:
        sys.exit(
            f"no gameplay clips matching '{tag}' in {GAMEPLAY_DIR}. "
            f"Run: python seed_gameplay.py"
        )
    clip = random.choice(pool)
    clip_dur = ffprobe_duration(clip)
    if clip_dur <= target_seconds + 0.1:
        return clip
    start = random.uniform(0, clip_dur - target_seconds)
    trimmed = workdir / "gameplay_trim.mp4"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}",
        "-i", str(clip),
        "-t", f"{target_seconds:.3f}",
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        str(trimmed),
    ])
    return trimmed


# ---------- voiceover ----------

async def _tts(text: str, out: Path) -> None:
    import edge_tts
    await edge_tts.Communicate(text, TTS_VOICE).save(str(out))


def synthesize_voiceover(text: str, workdir: Path) -> Path:
    out = workdir / "voice.mp3"
    asyncio.run(_tts(text, out))
    return out


def mix_audio(source: Path, voice: Path | None, workdir: Path) -> Path:
    """Return a wav with source audio (ducked) + voiceover, or just source audio."""
    mixed = workdir / "audio.wav"
    if voice is None:
        run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(source),
            "-vn", "-ac", "2", "-ar", "44100",
            str(mixed),
        ])
        return mixed
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(source),
        "-i", str(voice),
        "-filter_complex",
        "[0:a]volume=0.25[src];[1:a]volume=1.6[vo];[src][vo]amix=inputs=2:duration=longest:dropout_transition=0[a]",
        "-map", "[a]",
        "-ac", "2", "-ar", "44100",
        str(mixed),
    ])
    return mixed


# ---------- captions ----------

@dataclass
class Word:
    start: float
    end: float
    text: str


def transcribe(audio: Path, workdir: Path) -> list[Word]:
    import whisper
    model = whisper.load_model(os.environ.get("WHISPER_MODEL", "base"))
    result = model.transcribe(
        str(audio),
        word_timestamps=True,
        fp16=False,
        verbose=False,
    )
    words: list[Word] = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            txt = (w.get("word") or "").strip()
            if not txt:
                continue
            words.append(Word(float(w["start"]), float(w["end"]), txt))
    if not words:
        for seg in result.get("segments", []):
            txt = (seg.get("text") or "").strip()
            if txt:
                words.append(Word(float(seg["start"]), float(seg["end"]), txt))
    return words


def _ass_time(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def group_words(words: Iterable[Word], per_chunk: int = 3) -> list[Word]:
    chunks: list[Word] = []
    bucket: list[Word] = []
    for w in words:
        bucket.append(w)
        if len(bucket) >= per_chunk:
            chunks.append(Word(bucket[0].start, bucket[-1].end, " ".join(b.text for b in bucket)))
            bucket = []
    if bucket:
        chunks.append(Word(bucket[0].start, bucket[-1].end, " ".join(b.text for b in bucket)))
    return chunks


def write_ass(words: list[Word], path: Path) -> None:
    # TikTok-style: large white, thick black outline, centered, near vertical middle.
    # MarginV is from the bottom in ASS, so put it just below the stack seam.
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Impact,96,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,{HALF_H - 140},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for c in words:
        lines.append(
            f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Pop,,0,0,0,,{_ass_escape(c.text.upper())}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


# ---------- compose ----------

def compose(source: Path, gameplay: Path, audio: Path, subs: Path, out: Path, duration: float) -> None:
    # Top half (source): scale-to-fit with a blurred zoomed copy filling any
    # leftover space — source aspect varies and we don't want to crop news /
    # sports / talking-head content.
    # Bottom half (gameplay): scale-to-fill with center crop, no blur. With
    # landscape gameplay (e.g. Minecraft 16:9) the world is uniform so the
    # side crop is invisible; the bottom now fills cleanly edge-to-edge.
    subs_path = str(subs).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    vf = (
        f"[0:v]split=2[s0a][s0b];"
        f"[s0a]scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{HALF_H},boxblur=24:2,setsar=1[topbg];"
        f"[s0b]scale={W}:{HALF_H}:force_original_aspect_ratio=decrease,"
        f"setsar=1[topfg];"
        f"[topbg][topfg]overlay=(W-w)/2:(H-h)/2[top];"
        f"[1:v]scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{HALF_H},setsar=1[bot];"
        f"[top][bot]vstack=inputs=2[stacked];"
        f"[stacked]ass='{subs_path}'[v]"
    )
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(source),
        "-i", str(gameplay),
        "-i", str(audio),
        "-filter_complex", vf,
        "-map", "[v]", "-map", "2:a",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ])


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
        words = transcribe(voice if voice else audio, workdir)
        chunks = group_words(words, per_chunk=3)
        subs = workdir / "captions.ass"
        write_ass(chunks, subs)
        print(f"      {len(words)} words -> {len(chunks)} caption chunks")

        ts = time.strftime("%Y%m%d-%H%M%S")
        out = OUTPUT_DIR / f"short_{ts}.mp4"
        print(f"[6/6] composing -> {out}")
        compose(source, gameplay, audio, subs, out, target)

        print(f"\ndone: {out}")
        return 0
    finally:
        if args.keep_temp:
            print(f"workdir kept: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
