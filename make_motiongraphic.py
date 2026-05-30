#!/usr/bin/env python3
"""Motion-graphic explainer pipeline.

Fast-paced version of make_explainer.py — abandons Ken Burns stills in
favor of dark animated background + large pop-on text overlays at key
beats, hard cuts, brain-rot style burned captions. Tuned for short-
attention-span Shorts.

Input: a SHOT LIST (script + timed text impacts) defined in Python.
Output: 9:16 MP4.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import ssl
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
FPS = 30
TTS_VOICE = "en-US-GuyNeural"

# --- TTS ---

async def _tts(text: str, out: Path) -> None:
    import edge_tts.communicate as _ec
    _ec._SSL_CTX = ssl.create_default_context(cafile="/etc/ssl/certs/ca-certificates.crt")
    import edge_tts
    await edge_tts.Communicate(text, TTS_VOICE).save(str(out))


def tts(text: str, out: Path) -> None:
    asyncio.run(_tts(text, out))


def ffprobe_duration(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True).strip())


# --- Captions ---

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
    if t < 0: t = 0
    h = int(t // 3600); m = int((t % 3600) // 60); s = t - h * 3600 - m * 60
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
    # Captions go LOW so they don't fight the big punch-text in the middle.
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Impact,72,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,5,2,2,80,80,260,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for c in words:
        lines.append(f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Pop,,0,0,0,,{_ass_escape(c.text.upper())}\n")
    path.write_text("".join(lines), encoding="utf-8")


# --- Shot list type ---

@dataclass
class PunchText:
    """A big chunk of text that pops on at a moment and disappears."""
    text: str
    start: float
    end: float
    color: str = "white"     # ffmpeg color name or #hex
    size: int = 140
    y_pct: float = 0.35      # 0 top, 1 bottom
    flash_bg: str = ""       # optional hex color the bg flashes to


def _esc_drawtext(text: str) -> str:
    """ffmpeg drawtext escape rules: backslash, colon, single quote.
    Dollar sign and comma DO NOT need escaping in normal drawtext args."""
    return (
        text.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\\'")
    )


def _auto_size(text: str, base_size: int, max_width: int = 900) -> int:
    """Trim font size if a phrase would overflow horizontally. Bold
    DejaVu (what we're using) draws at roughly 0.65 × fontsize per
    character at the sizes we hit here."""
    width_per_char = 0.65
    est_w = len(text) * base_size * width_per_char
    if est_w <= max_width:
        return base_size
    return max(60, int(max_width / (len(text) * width_per_char)))


def build_video(
    script: str,
    punches: list[PunchText],
    out_path: Path,
    bg_color: str = "#0a0e1a",
    accent_hue_rate: float = 0.0,
    bg_video: Path | None = None,
    bg_blur: int = 40,
    bg_dim: float = 0.45,
    bg_seek: float = 30.0,
) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="mg_"))
    print(f"workdir: {workdir}")
    try:
        voice = workdir / "voice.mp3"
        print("[1/4] tts")
        tts(script, voice)
        dur = ffprobe_duration(voice)
        print(f"      duration {dur:.2f}s, {len(punches)} punches")

        # Background: either a solid color, or a video file scaled to 9:16,
        # heavily blurred + dimmed so it reads as abstract motion under the
        # text and doesn't fight the foreground.
        if bg_video and bg_video.exists():
            # Loop the bg video if it's shorter than the narration. Seek
            # 30s in to skip whatever intro / title-card / branded frames
            # are at the start of the source clip — these leak through
            # even heavy blur and read as "video game" instead of
            # "abstract motion."
            bg_dur = ffprobe_duration(bg_video)
            loop = max(0, int(dur // bg_dur))
            bg_input = [
                "-ss", str(bg_seek),
                "-stream_loop", str(loop),
                "-i", str(bg_video),
            ]
            # Brighten and saturate so the motion shows through clearly
            # underneath the text + semi-transparent flashes.
            bg_filter = (
                f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},"
                f"boxblur={bg_blur}:2,"
                f"eq=brightness=0.05:saturation=1.4:contrast=1.1,"
                f"format=yuv420p,"
                f"setpts=PTS-STARTPTS"
            )
            audio_input_idx = "2:a"  # voice is 3rd input
            audio_inputs = ["-f", "lavfi", "-i", "anullsrc=cl=stereo:r=44100",
                            "-i", str(voice)]
        else:
            bg_input = []
            bg_filter = f"color=c={bg_color}:s={W}x{H}:d={dur:.3f}:r={FPS},format=yuv420p"
            audio_input_idx = "1:a"
            audio_inputs = ["-i", str(voice)]

        # Build the filter graph: base bg -> N drawbox flashes -> N drawtext
        # punches -> ASS subs.
        chain_parts: list[str] = []
        prev_label = "bg"

        # Semi-transparent flashes so the moving bg shows through.
        # Alpha 0.55 = strong color cast without covering motion underneath.
        flash_idx = 0
        for p in punches:
            if not p.flash_bg:
                continue
            out_label = f"flash{flash_idx}"
            chain_parts.append(
                f"[{prev_label}]drawbox=x=0:y=0:w={W}:h={H}:"
                f"color={p.flash_bg}@0.55:t=fill:"
                f"enable='between(t,{p.start:.3f},{p.end:.3f})'[{out_label}]"
            )
            prev_label = out_label
            flash_idx += 1

        # Then punch texts
        for i, p in enumerate(punches):
            esc = _esc_drawtext(p.text)
            size = _auto_size(p.text, p.size)
            out_label = "withtext" if i == len(punches) - 1 else f"t{i}"
            chain_parts.append(
                f"[{prev_label}]drawtext=text='{esc}'"
                f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                f":fontsize={size}"
                f":fontcolor={p.color}"
                f":x=(w-text_w)/2"
                f":y=h*{p.y_pct:.3f}-(text_h/2)"
                f":borderw=8:bordercolor=black"
                f":enable='between(t,{p.start:.3f},{p.end:.3f})'"
                f"[{out_label}]"
            )
            prev_label = out_label
        text_chain_parts = chain_parts

        # Transcribe + caption file
        print("[2/4] transcribe")
        words = transcribe(voice)
        chunks = group_words(words, per_chunk=3)
        subs = workdir / "captions.ass"
        write_ass(chunks, subs)
        subs_path = str(subs).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\\'")
        print(f"      {len(words)} words -> {len(chunks)} chunks")

        # Final filter graph
        graph = (
            f"{bg_filter}[bg];" +
            ";".join(text_chain_parts) +
            f";[withtext]ass='{subs_path}'[v]"
        )

        print("[3/4] render")
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            *bg_input,
            *audio_inputs,
            "-filter_complex", graph,
            "-map", "[v]", "-map", audio_input_idx,
            "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True)
        print(f"[4/4] done -> {out_path}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main() -> int:
    # Fast furniture topic. Hook: lead with the shock stat (12M tons of
    # furniture trashed every year in the US), foreshadow the "fast
    # furniture" framing by second 3, end on the millennial pay-twice
    # punchline. Stats sourced from EPA Sustainable Materials Management
    # report (~12M tons of furniture + bedding waste annually) and
    # post-NAFTA furniture import data.
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

    punches = [
        # Frame-1 visual hook — number visible at t=0 so it lands without
        # sound on the swipe-past decision.
        PunchText("12 MILLION TONS", 0.0, 2.4, color="#ff3030", size=170, y_pct=0.40,
                  flash_bg="#220404"),
        PunchText("EVERY YEAR", 2.6, 4.8, color="#ffffff", size=200, y_pct=0.40),
        # Foreshadow by second 5 — the "fast furniture" frame
        PunchText("FAST FURNITURE", 5.5, 8.5, color="#ff5050", size=200, y_pct=0.40,
                  flash_bg="#220404"),
        # The contrast — what used to be
        PunchText("1950: 25 YEARS", 12.5, 15.0, color="#50ff80", size=170, y_pct=0.40,
                  flash_bg="#0d2818"),
        PunchText("HIGH POINT, NC", 16.0, 18.5, color="#ffe24a", size=160, y_pct=0.40),
        # The shift
        PunchText("MOST IMPORTED", 20.0, 22.5, color="#ffaa50", size=170, y_pct=0.40),
        PunchText("PARTICLE BOARD", 24.0, 27.0, color="#cccccc", size=180, y_pct=0.40),
        # Hard-stop closing punch
        PunchText("PAY TWICE", 30.0, 33.5, color="#ffffff", size=240, y_pct=0.40,
                  flash_bg="#a01010"),
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_str = time.strftime("%Y%m%d-%H%M%S")
    out = OUTPUT_DIR / f"motiongraphic_{ts_str}.mp4"
    # Real B-roll override. If /tmp/newsreel.mp4 exists, use it with
    # minimal blur so the footage actually reads. Otherwise fall back to
    # the abstract Minecraft Nether wallpaper.
    newsreel = Path("/tmp/newsreel.mp4")
    if newsreel.exists():
        build_video(script, punches, out, bg_video=newsreel, bg_blur=4, bg_dim=0.15, bg_seek=0)
    else:
        bg = ROOT / "gameplay" / "minecraft_nether_parkour.mp4"
        build_video(script, punches, out, bg_video=bg, bg_blur=35, bg_dim=0.25)
    return 0


if __name__ == "__main__":
    sys.exit(main())
