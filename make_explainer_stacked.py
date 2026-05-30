#!/usr/bin/env python3
"""Script-aligned stacked explainer.

Newsreel B-roll on top, Minecraft brain-rot gameplay on bottom, big
punch-text overlays + standard captions. The key feature: each B-roll
segment and each big-text overlay is anchored to a TRIGGER PHRASE in
the script, so timings are derived from the actual TTS audio (via
whisper word-level timestamps) instead of guessed by hand.

This is the version we use after the user said the previous stacked
video's top half wasn't on cue with the narration.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
GAMEPLAY_DIR = ROOT / "gameplay"

W, H = 1080, 1920
HALF_H = H // 2
FPS = 30
TTS_VOICE = "en-US-GuyNeural"


# ---------- helpers ----------

def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True).strip()
    return float(out)


# ---------- TTS ----------

KOKORO_MODEL = ROOT / "kokoro_models" / "kokoro-v1.0.onnx"
KOKORO_VOICES = ROOT / "kokoro_models" / "voices-v1.0.bin"
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "am_michael")


def tts(text: str, out: Path) -> None:
    """Synthesize narration. Prefers local Kokoro TTS (free, unlimited,
    significantly more natural than edge-tts) if model files are
    present. Falls back to edge-tts otherwise."""
    if KOKORO_MODEL.exists() and KOKORO_VOICES.exists():
        _tts_kokoro(text, out)
    else:
        asyncio.run(_tts_edge(text, out))


def _tts_kokoro(text: str, out: Path) -> None:
    import soundfile as sf
    from kokoro_onnx import Kokoro
    k = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    samples, sr = k.create(text, voice=KOKORO_VOICE, speed=1.05, lang="en-us")
    wav_path = out.with_suffix(".wav")
    sf.write(str(wav_path), samples, sr)
    # Convert to mp3 so downstream ffmpeg paths don't choke on the wav.
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(wav_path), "-codec:a", "libmp3lame", "-qscale:a", "2",
        str(out),
    ], check=True)
    wav_path.unlink(missing_ok=True)


async def _tts_edge(text: str, out: Path) -> None:
    import edge_tts.communicate as _ec
    _ec._SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
    import edge_tts
    await edge_tts.Communicate(text, TTS_VOICE).save(str(out))


# ---------- whisper ----------

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


def find_phrase_start(words: list[Word], phrase: str, hint_after: float = 0.0) -> float | None:
    """Find the start time of the first occurrence of `phrase` in the
    transcript, optionally after a hint time. Matches are loose — the
    phrase is split into words and matched left-to-right, ignoring
    punctuation and case."""
    target = [_norm(w) for w in phrase.split()]
    n = len(target)
    transcript = [_norm(w.text) for w in words]
    for i in range(len(transcript) - n + 1):
        if words[i].start < hint_after:
            continue
        if all(transcript[i + j].startswith(target[j]) or target[j] in transcript[i + j]
               for j in range(n)):
            return words[i].start
    return None


def _norm(s: str) -> str:
    return "".join(ch.lower() for ch in s if ch.isalnum())


# ---------- captions (same brain-rot style) ----------

def _ass_time(t: float) -> str:
    if t < 0: t = 0
    h = int(t // 3600); m = int((t % 3600) // 60); s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def group_words(words: list[Word], max_chars: int = 22, max_words: int = 5) -> list[Word]:
    """Group whisper words into caption chunks that break on punctuation
    when possible. The previous fixed-N-per-chunk approach cut phrases
    like "POINT NORTH / CAROLINA" mid-thought; this version flushes the
    bucket at any clause/sentence boundary so chunks read as natural
    sub-phrases."""
    chunks: list[Word] = []
    bucket: list[Word] = []
    for w in words:
        bucket.append(w)
        joined = " ".join(b.text for b in bucket)
        tail = w.text.rstrip()
        boundary = tail.endswith((".", ",", "!", "?", ":", ";"))
        too_long = len(joined) >= max_chars
        too_many = len(bucket) >= max_words
        if boundary or too_long or too_many:
            chunks.append(Word(bucket[0].start, bucket[-1].end, joined))
            bucket = []
    if bucket:
        chunks.append(Word(bucket[0].start, bucket[-1].end, " ".join(b.text for b in bucket)))
    return chunks


def write_ass(chunks: list[Word], path: Path, margin_v: int) -> None:
    # Style notes:
    #   Fontsize 110 (was 80) — bigger TikTok pop.
    #   Outline 10 (was 5) + shadow 4 — survives over busy Minecraft bg.
    #   Alignment 2 (bottom-center); margin_v positions the text block's
    #   bottom edge `margin_v` px above the frame bottom.
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Impact,110,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,10,4,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for c in chunks:
        lines.append(f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Pop,,0,0,0,,{_ass_escape(c.text.upper())}\n")
    path.write_text("".join(lines), encoding="utf-8")


# ---------- shot list ----------

@dataclass
class Shot:
    """Anchor a B-roll segment to a script phrase. The segment plays from
    when the phrase starts being spoken until the next shot's phrase
    starts (or end of audio).

    Source modes:
      - `clip` + `clip_start`: hardcoded file + seek (legacy)
      - `pexels_query`: search Pexels for B-roll matching the query and
        download the top match
    """
    phrase: str
    clip: Path | None = None
    clip_start: float = 0.0
    pexels_query: str | None = None
    fallback_extend: float = 0.0

@dataclass
class Punch:
    """Big text that pops on at a trigger phrase."""
    phrase: str
    text: str
    color: str = "#ffffff"
    size: int = 160
    duration: float = 2.5
    flash_bg: str = ""


# ---------- B-roll assembly ----------

def build_timed_top(
    shots: list[Shot],
    shot_times: list[float],
    total_dur: float,
    top_h: int,
    workdir: Path,
) -> Path:
    """Cut each B-roll segment to exactly fill from one shot's trigger
    time to the next's. Resolves Pexels queries on demand. Output a
    1080x(top_h) concat."""
    pexels_cache = Path("/tmp/pexels")
    pexels_cache.mkdir(exist_ok=True)

    segments: list[Path] = []
    for i, (shot, start_t) in enumerate(zip(shots, shot_times)):
        end_t = shot_times[i + 1] if i + 1 < len(shot_times) else total_dur
        seg_dur = max(0.5, end_t - start_t)

        # Resolve source: prefer stock query (multi-provider) if provided.
        if shot.pexels_query:
            import stock_search
            meta = stock_search.fetch_top(shot.pexels_query, pexels_cache)
            print(f"      [{meta.get('source','?')}] {shot.pexels_query!r} -> "
                  f"{meta.get('url','?')} ({meta['width']}x{meta['height']}, "
                  f"{meta['duration']}s)")
            clip_path = Path(meta["path"])
            clip_start = 0.5 if meta["duration"] > seg_dur + 1 else 0
        else:
            clip_path = shot.clip
            clip_start = shot.clip_start

        out = workdir / f"top_{i:02d}.mp4"
        # Scale-to-fill the top half, crop, no blur — we want the
        # footage to read clearly.
        run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{clip_start:.3f}", "-i", str(clip_path),
            "-t", f"{seg_dur:.3f}",
            "-vf", f"scale={W}:{top_h}:force_original_aspect_ratio=increase,"
                   f"crop={W}:{top_h},setsar=1,fps={FPS}",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            str(out),
        ])
        segments.append(out)

    list_file = workdir / "top_list.txt"
    list_file.write_text("\n".join(f"file '{s}'" for s in segments))
    top_out = workdir / "top.mp4"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(top_out),
    ])
    return top_out


def pick_gameplay_clip(tag: str, target: float, workdir: Path) -> Path:
    pool = [p for p in GAMEPLAY_DIR.iterdir()
            if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")
            and tag.lower() in p.stem.lower()]
    if not pool:
        sys.exit(f"no gameplay clips matching {tag!r} in {GAMEPLAY_DIR}")
    src = random.choice(pool)
    dur = ffprobe_duration(src)
    # Stay away from the tail of the clip — that's where the YouTuber's
    # world-select menu / outro screens tend to sit and they read as
    # "this is a video game" not as abstract motion.
    max_seek = max(0, dur - target - 25)
    seek = random.uniform(5, max(5, max_seek))
    out = workdir / "bottom_raw.mp4"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{seek:.3f}", "-i", str(src),
        "-t", f"{target:.3f}",
        "-vf", f"scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
               f"crop={W}:{HALF_H}:0:'(ih-{HALF_H})*0.7',setsar=1,fps={FPS}",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        str(out),
    ])
    return out


# ---------- compose ----------

def build_video(
    script: str,
    shots: list[Shot],
    punches: list[Punch],
    gameplay_tag: str,
    out_path: Path,
) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="exps_"))
    print(f"workdir: {workdir}")
    try:
        # 1. TTS
        print("[1/7] tts")
        voice = workdir / "voice.mp3"
        tts(script, voice)
        total_dur = ffprobe_duration(voice)
        print(f"      voice {total_dur:.2f}s")

        # 2. Whisper transcribe for timing + captions
        print("[2/7] whisper transcribe")
        words = transcribe(voice)
        print(f"      {len(words)} words")

        # 3. Resolve trigger times for each shot
        print("[3/7] resolving shot timings")
        shot_times: list[float] = []
        hint = 0.0
        for shot in shots:
            t = find_phrase_start(words, shot.phrase, hint_after=hint)
            if t is None:
                print(f"      !! trigger phrase not found: {shot.phrase!r}")
                t = hint  # fallback: continue from previous shot's slot
            shot_times.append(t)
            hint = t + 0.1
            print(f"      shot {shot.phrase[:30]:30s} -> t={t:.2f}s")

        # 4. Build timed top half (B-roll)
        print("[4/7] top: assembling B-roll")
        top = build_timed_top(shots, shot_times, total_dur, HALF_H, workdir)

        # 5. Pick gameplay for bottom
        print(f"[5/7] bottom: {gameplay_tag} gameplay")
        bottom = pick_gameplay_clip(gameplay_tag, total_dur, workdir)

        # 6. Stack + captions + punches in one big filter
        print("[6/7] compose")
        chunks = group_words(words)
        subs = workdir / "captions.ass"
        # Captions live in the bottom-half lower-middle, well clear of
        # the seam (so the top B-roll's bottom edge doesn't crop into
        # them) and clear of the Minecraft hotbar.
        write_ass(chunks, subs, margin_v=380)
        subs_path = str(subs).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\\'")

        # Resolve punch times
        punch_filters: list[str] = []
        prev_label = "stacked"
        for i, p in enumerate(punches):
            t = find_phrase_start(words, p.phrase, hint_after=0)
            if t is None:
                print(f"      !! punch phrase not found: {p.phrase!r}")
                continue
            end = t + p.duration
            esc = (p.text.replace("\\", "\\\\")
                   .replace(":", r"\:")
                   .replace("'", r"\\'"))
            # punches sit roughly in the upper-third of the screen
            # (over the top half / B-roll) so they don't fight the
            # bottom captions.
            out_label = f"p{i}"
            # Auto-size: cap font so phrase fits in 920px wide.
            size = p.size
            est_w = len(p.text) * size * 0.65
            if est_w > 920:
                size = max(60, int(920 / (len(p.text) * 0.65)))
            chain = (
                f"[{prev_label}]drawtext=text='{esc}'"
                f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                f":fontsize={size}"
                f":fontcolor={p.color}"
                f":x=(w-text_w)/2:y=h*0.28-(text_h/2)"
                f":borderw=8:bordercolor=black"
                f":enable='between(t,{t:.3f},{end:.3f})'"
                f"[{out_label}]"
            )
            punch_filters.append(chain)
            prev_label = out_label

        final_label = prev_label
        graph = (
            f"[0:v]format=yuv420p[topf];"
            f"[1:v]format=yuv420p[botf];"
            f"[topf][botf]vstack=inputs=2[stacked];"
            + (";".join(punch_filters) + ";" if punch_filters else "")
            + f"[{final_label}]ass='{subs_path}'[v]"
        )

        run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(top),
            "-i", str(bottom),
            "-i", str(voice),
            "-filter_complex", graph,
            "-map", "[v]", "-map", "2:a",
            "-t", f"{total_dur:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(out_path),
        ])
        print(f"[7/7] done -> {out_path}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------- main ----------

def main() -> int:
    # Fast furniture v2 — same script as before but shots and punches
    # are now anchored to actual TTS-aligned phrases so the top half
    # changes on cue with what's being said.
    script = (
        "Americans throw out twelve million tons of furniture. Every year. "
        "This is fast furniture, and it makes fast fashion look efficient. "
        "In 1950, your couch was solid wood, real upholstery, built in High "
        "Point North Carolina. It lasted twenty five years. Today, most "
        "American furniture is imported, glued together from particle board, "
        "and wrapped in vinyl. Designed to fall apart after one move. IKEA, "
        "Wayfair, and Amazon trained a generation to treat furniture like "
        "clothes. Millennials are now paying twice. Once to buy it. Once to "
        "replace it."
    )

    # Modern Pexels B-roll matched to each script beat. The pipeline
    # searches, downloads the top match, and uses it. No more 1937 film
    # grain.
    shots = [
        Shot(phrase="Americans throw out",  pexels_query="landfill aerial"),
        Shot(phrase="In 1950",              pexels_query="vintage furniture workshop"),
        Shot(phrase="Today",                pexels_query="warehouse boxes"),
        Shot(phrase="particle",             pexels_query="cheap furniture assembly"),
        Shot(phrase="Millennials are now",  pexels_query="dumpster furniture"),
    ]
    # Trigger phrases use 1-2 distinctive words that whisper reliably
    # tokenizes; "twelve million" can transcribe as "12 million" and
    # "twenty five" as "25" depending on the model.
    punches = [
        Punch(phrase="tons of",       text="12 MILLION TONS", color="#ff3030", size=170, duration=2.6, flash_bg="#220404"),
        Punch(phrase="every year",    text="EVERY YEAR",       color="#ffffff", size=200, duration=1.8),
        Punch(phrase="fast furniture",text="FAST FURNITURE",   color="#ff5050", size=200, duration=2.8),
        Punch(phrase="lasted",        text="25 YEARS",         color="#50ff80", size=200, duration=2.4),
        Punch(phrase="particle",      text="PARTICLE BOARD",   color="#cccccc", size=180, duration=2.5),
        Punch(phrase="paying",        text="PAY TWICE",        color="#ffffff", size=240, duration=3.5),
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_str = time.strftime("%Y%m%d-%H%M%S")
    out = OUTPUT_DIR / f"stacked_{ts_str}.mp4"
    build_video(script, shots, punches, gameplay_tag="minecraft", out_path=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
