#!/usr/bin/env python3
"""Script-first explainer pipeline.

Different shape from make_short.py: instead of stacking copyrighted
video on top of gameplay, this takes a written script + a folder of
PD/CC stills (or short clips) and produces a 9:16 explainer with
ken-burns motion, TTS narration, and burned captions.

Usage:
    python make_explainer.py SCRIPT_FILE IMAGES_DIR [--output OUT]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"

W, H = 1080, 1920
FPS = 25
TTS_VOICE = "en-US-GuyNeural"


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    if capture:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
    return subprocess.run(cmd, check=True)


def ffprobe_duration(path: Path) -> float:
    out = run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture=True,
    ).stdout.strip()
    return float(out)


# ---------- TTS ----------

async def _tts(text: str, out: Path) -> None:
    # Force edge_tts to use the system CA bundle so the egress proxy's
    # self-signed cert in the chain is trusted. The bundled certifi
    # doesn't include the egress gateway CA.
    import ssl
    import edge_tts.communicate as _ec
    _ec._SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
    import edge_tts
    await edge_tts.Communicate(text, TTS_VOICE).save(str(out))


def synthesize_voiceover(text: str, workdir: Path) -> Path:
    out = workdir / "voice.mp3"
    asyncio.run(_tts(text, out))
    return out


# ---------- Ken Burns on stills ----------

def ken_burns_clip(image: Path, out: Path, duration: float, mode: str = "in") -> None:
    """Generate a 9:16 Ken Burns clip from a single image. mode = 'in'
    zooms in over the duration; 'out' zooms out; 'pan' pans across."""
    total_frames = int(duration * FPS)
    if mode == "in":
        # Slow zoom in from 1.0 -> 1.15
        zoom = f"min(zoom+0.0015,1.15)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif mode == "out":
        zoom = f"if(eq(on,1),1.15,max(zoom-0.0015,1.0))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    else:  # pan
        zoom = "1.15"
        x = f"((iw-iw/zoom)/2)*(on/{total_frames})"
        y = "ih/2-(ih/zoom/2)"

    # Pre-scale up so zoompan has high-resolution source to draw from,
    # then zoompan + crop to 1080x1920.
    vf = (
        f"scale=8000:-1,"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={total_frames}:fps={FPS}:s=1080x1920,"
        f"setsar=1"
    )
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-i", str(image),
        "-vf", vf,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(out),
    ])


# ---------- Captions ----------

@dataclass
class Word:
    start: float
    end: float
    text: str


def transcribe(audio: Path) -> list[Word]:
    import whisper
    model = whisper.load_model(os.environ.get("WHISPER_MODEL", "base"))
    result = model.transcribe(str(audio), word_timestamps=True, fp16=False, verbose=False)
    words: list[Word] = []
    for seg in result.get("segments", []):
        for w in seg.get("words", []) or []:
            txt = (w.get("word") or "").strip()
            if not txt:
                continue
            words.append(Word(float(w["start"]), float(w["end"]), txt))
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
    # Anchored vertically center-ish so it reads on top of imagery without
    # blocking faces in the top third.
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Impact,88,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for c in words:
        lines.append(
            f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Pop,,0,0,0,,{_ass_escape(c.text.upper())}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


# ---------- Assemble ----------

def concat_clips(clips: list[Path], out: Path) -> None:
    list_file = out.with_suffix(".txt")
    list_file.write_text("\n".join(f"file '{c}'" for c in clips))
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy",
        str(out),
    ])


def compose(visual: Path, audio: Path, subs: Path, out: Path, duration: float) -> None:
    subs_path = str(subs).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    vf = f"ass='{subs_path}'"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(visual),
        "-i", str(audio),
        "-vf", vf,
        "-map", "0:v", "-map", "1:a",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(out),
    ])


# ---------- Main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Script-first explainer pipeline.")
    ap.add_argument("script_file", help="Plain text file containing the narration script.")
    ap.add_argument("images_dir", help="Folder of stills (.jpg/.png) to use as B-roll.")
    ap.add_argument("--output", help="Output MP4 path.", default=None)
    ap.add_argument("--keep-temp", action="store_true")
    args = ap.parse_args()

    script_text = Path(args.script_file).read_text().strip()
    images = sorted(p for p in Path(args.images_dir).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not images:
        sys.exit(f"No images in {args.images_dir}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_path = Path(args.output) if args.output else OUTPUT_DIR / f"explainer_{ts}.mp4"

    workdir = Path(tempfile.mkdtemp(prefix="exp_"))
    print(f"workdir: {workdir}")

    try:
        # 1. TTS
        print("[1/5] synthesizing voiceover")
        voice = synthesize_voiceover(script_text, workdir)
        voice_duration = ffprobe_duration(voice)
        print(f"      voiceover: {voice_duration:.2f}s")

        # 2. Allocate per-image durations
        per_image = voice_duration / len(images)
        print(f"[2/5] {len(images)} images × {per_image:.2f}s each")

        # 3. Render ken-burns clips
        modes = ["in", "out", "pan"]
        clips: list[Path] = []
        for i, img in enumerate(images):
            clip = workdir / f"clip_{i:02d}.mp4"
            print(f"      ken-burns {img.name} ({modes[i % len(modes)]})")
            ken_burns_clip(img, clip, per_image, mode=modes[i % len(modes)])
            clips.append(clip)

        # 4. Concat
        print("[3/5] concatenating clips")
        visual = workdir / "visual.mp4"
        concat_clips(clips, visual)

        # 5. Transcribe + write subs
        print("[4/5] transcribing for captions")
        words = transcribe(voice)
        chunks = group_words(words, per_chunk=3)
        subs = workdir / "captions.ass"
        write_ass(chunks, subs)
        print(f"      {len(words)} words -> {len(chunks)} caption chunks")

        # 6. Burn captions + mix audio
        print(f"[5/5] composing -> {out_path}")
        compose(visual, voice, subs, out_path, voice_duration)

        print(f"\ndone: {out_path}")
        return 0
    finally:
        if args.keep_temp:
            print(f"workdir kept: {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
