#!/usr/bin/env python3
"""Script-aligned stacked explainer — energy edition.

Newsreel B-roll on top, Minecraft brain-rot gameplay on bottom, big
punch-text overlays + standard captions. Timings are derived from the
actual TTS audio via whisper word-level timestamps.

Energy upgrades vs the previous version:
  * Multi-cut shots: each beat fetches 2-3 different stock clips and
    cuts between them every ~2s instead of holding one shot for 6s.
  * Animated punches: scale-bounce in via ASS animation tags (was a
    static drawtext fade).
  * Synthesized music bed: a dark, kick-driven loop generated with
    ffmpeg lavfi, ducked under the voice.
  * SFX hits: whoosh on every visual cut, impact thump on every punch.
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

# Target seconds per sub-cut. ~2s feels fast without being epileptic.
SUB_CUT_TARGET = 2.0


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


# ---------- captions ----------

def _ass_time(t: float) -> str:
    if t < 0: t = 0
    h = int(t // 3600); m = int((t % 3600) // 60); s = t - h * 3600 - m * 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def group_words(words: list[Word], max_chars: int = 22, max_words: int = 5) -> list[Word]:
    """Group whisper words into caption chunks, flushing on punctuation
    boundaries so phrases like NORTH CAROLINA or FALL APART stay together."""
    chunks: list[Word] = []
    bucket: list[Word] = []
    for w in words:
        bucket.append(w)
        joined = " ".join(b.text for b in bucket)
        tail = w.text.rstrip()
        boundary = tail.endswith((".", ",", "!", "?", ":", ";"))
        if boundary or len(joined) >= max_chars or len(bucket) >= max_words:
            chunks.append(Word(bucket[0].start, bucket[-1].end, joined))
            bucket = []
    if bucket:
        chunks.append(Word(bucket[0].start, bucket[-1].end, " ".join(b.text for b in bucket)))
    return chunks


def write_captions_ass(chunks: list[Word], path: Path, margin_v: int) -> None:
    """Write the rolling caption track. Bottom-half center, large
    Impact-style with thick black outline so it reads over busy bg."""
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


# ---------- punches (animated) ----------

def _rgb_to_ass(hex_color: str) -> str:
    """#RRGGBB -> &HBBGGRR& (ASS uses BGR ordering)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        h = "ffffff"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{b}{g}{r}&".upper()


@dataclass
class Punch:
    """Big text that bounces on at a trigger phrase. Rendered via ASS
    animation: 50% -> 130% -> 100% scale over the first ~250ms, then
    holds, then fades out at the end."""
    phrase: str
    text: str
    color: str = "#ffffff"
    size: int = 200
    duration: float = 2.4
    y_frac: float = 0.28  # vertical position as fraction of full height


def write_punches_ass(
    punches_resolved: list[tuple[Punch, float, float]],
    path: Path,
) -> None:
    """Write each punch as an ASS Dialogue with a scale-bounce keyframe
    chain. `punches_resolved` is (Punch, start, end) tuples in seconds."""
    # One style per default; per-punch font size is overridden inline
    # via \fs because ASS styles can't be parameterised cheaply per cue.
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Punch,Impact,200,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,12,4,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for p, t, end in punches_resolved:
        # Auto-shrink font if the phrase would overflow the frame at the
        # nominal size. ~0.65 is a rough Impact-Bold aspect heuristic.
        size = p.size
        est_w = len(p.text) * size * 0.65
        if est_w > 920:
            size = max(80, int(920 / (len(p.text) * 0.65)))

        x = W // 2
        y = int(H * p.y_frac)
        col = _rgb_to_ass(p.color)
        # Animation tags:
        #   \pos(x,y)            - explicit center anchor
        #   \fs{size}            - font size
        #   \c, \3c              - fill and outline colours
        #   \fad(60,200)         - 60ms fade in, 200ms fade out
        #   \fscx50 \fscy50      - start at half size
        #   \t(0,150,...130)     - scale to 130% over first 150ms
        #   \t(150,250,...100)   - settle to 100% over next 100ms
        body = (
            f"{{\\an5\\pos({x},{y})\\fs{size}\\c{col}\\3c&H000000&"
            f"\\fad(60,200)\\fscx50\\fscy50"
            f"\\t(0,150,\\fscx130\\fscy130)"
            f"\\t(150,250,\\fscx100\\fscy100)}}"
            f"{_ass_escape(p.text.upper())}"
        )
        lines.append(f"Dialogue: 0,{_ass_time(t)},{_ass_time(end)},Punch,,0,0,0,,{body}\n")
    path.write_text("".join(lines), encoding="utf-8")


# ---------- shot list ----------

@dataclass
class Shot:
    """Anchor a B-roll segment to a script phrase. The segment plays from
    when the phrase starts until the next shot's phrase starts.

    Source modes (checked in order):
      1. `queries`: a list of stock-search queries; the shot subdivides
         its time window into one sub-cut per query.
      2. `pexels_query`: a single query — the shot fetches the top 2-3
         candidates and cycles between them as sub-cuts.
      3. `clip` + `clip_start`: a hardcoded local file.
    """
    phrase: str
    queries: list[str] | None = None
    pexels_query: str | None = None
    clip: Path | None = None
    clip_start: float = 0.0


# ---------- B-roll assembly (multi-cut) ----------

def _resolve_clips(shot: Shot, cache: Path, n_target: int) -> list[dict]:
    """Return up to n_target downloaded clip metadata dicts for this
    shot. Always returns at least one (or raises)."""
    import stock_search
    clips: list[dict] = []

    if shot.queries:
        for q in shot.queries:
            try:
                m = stock_search.fetch_top(q, cache)
                clips.append(m)
                print(f"      [{m.get('source','?')}] {q!r} -> "
                      f"{m.get('url','?')} ({m['width']}x{m['height']}, {m['duration']}s)")
            except Exception as e:  # noqa: BLE001
                print(f"      !! {q!r}: {e}")
        if not clips:
            raise RuntimeError(f"no clips resolved for queries {shot.queries!r}")
        return clips

    if shot.pexels_query:
        cands = stock_search.list_candidates(shot.pexels_query, top_n=max(3, n_target))
        for c in cands:
            try:
                p = stock_search._download(c, cache)
                c["path"] = str(p)
                c["source"] = c["provider"]
                clips.append(c)
                print(f"      [{c['source']}] {shot.pexels_query!r} #{c['rank']} -> "
                      f"{c.get('url','?')} ({c['width']}x{c['height']}, {c['duration']}s)")
                if len(clips) >= n_target:
                    break
            except Exception:
                continue
        if not clips:
            raise RuntimeError(f"no candidates downloadable for {shot.pexels_query!r}")
        return clips

    if shot.clip:
        return [{"path": str(shot.clip), "duration": ffprobe_duration(shot.clip),
                 "width": W, "height": HALF_H, "source": "local"}]

    raise RuntimeError(f"shot {shot.phrase!r} has no source")


def build_timed_top(
    shots: list[Shot],
    shot_times: list[float],
    total_dur: float,
    top_h: int,
    workdir: Path,
) -> tuple[Path, list[float]]:
    """Build the top-half video with multiple sub-cuts inside each shot's
    time window. Returns (path, cut_times) where cut_times is every
    sub-cut's start time in seconds (used for SFX placement)."""
    cache = Path("/tmp/pexels")
    cache.mkdir(exist_ok=True)

    all_segments: list[Path] = []
    cut_times: list[float] = []

    for i, (shot, start_t) in enumerate(zip(shots, shot_times)):
        end_t = shot_times[i + 1] if i + 1 < len(shot_times) else total_dur
        seg_dur = max(0.5, end_t - start_t)

        # Decide how many sub-cuts fit in this window.
        n_cuts = max(1, round(seg_dur / SUB_CUT_TARGET))
        cut_dur = seg_dur / n_cuts

        clips = _resolve_clips(shot, cache, n_target=n_cuts)

        for j in range(n_cuts):
            clip = clips[j % len(clips)]
            clip_dur = float(clip.get("duration") or 10)
            # If we're reusing a clip for a second cut, seek further in.
            repeat = j // len(clips)
            seek_start = 0.3
            seek_step = max(1.5, (clip_dur - cut_dur - 1.0) / max(1, n_cuts))
            seek = min(seek_start + repeat * seek_step, max(0.0, clip_dur - cut_dur - 0.3))

            sub = workdir / f"top_{i:02d}_{j:02d}.mp4"
            run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-ss", f"{seek:.3f}", "-i", clip["path"],
                "-t", f"{cut_dur:.3f}",
                "-vf", f"scale={W}:{top_h}:force_original_aspect_ratio=increase,"
                       f"crop={W}:{top_h},setsar=1,fps={FPS}",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                str(sub),
            ])
            all_segments.append(sub)
            cut_times.append(start_t + j * cut_dur)

    list_file = workdir / "top_list.txt"
    list_file.write_text("\n".join(f"file '{s}'" for s in all_segments))
    top_out = workdir / "top.mp4"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy", str(top_out),
    ])
    return top_out, cut_times


def pick_gameplay_clip(tag: str, target: float, workdir: Path) -> Path:
    pool = [p for p in GAMEPLAY_DIR.iterdir()
            if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm")
            and tag.lower() in p.stem.lower()]
    if not pool:
        sys.exit(f"no gameplay clips matching {tag!r} in {GAMEPLAY_DIR}")
    src = random.choice(pool)
    dur = ffprobe_duration(src)
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


# ---------- audio: music + SFX ----------

def synth_music(duration: float, out: Path, vibe: str = "dark") -> None:
    """Synthesize a placeholder music bed with ffmpeg lavfi. Not great,
    but adds perceptible energy under the narration. Swap for a real
    track by setting the MUSIC_FILE env var."""
    if vibe == "dark":
        # Sub-bass drone (55Hz) + kick pulse at 90bpm (0.667s) + mid pad.
        drone = "0.32*sin(2*PI*55*t)+0.18*sin(2*PI*110*t)"
        kick = "0.55*sin(2*PI*58*t)*exp(-7*mod(t,0.667))"
        pad = "0.12*sin(2*PI*220*t)*sin(2*PI*0.125*t)"
    elif vibe == "hiphop":
        # Faster kick (120bpm = 0.5s), brighter bass.
        drone = "0.20*sin(2*PI*82*t)"
        kick = "0.55*sin(2*PI*65*t)*exp(-9*mod(t,0.5))"
        pad = "0.10*sin(2*PI*440*t)*sin(2*PI*0.25*t)"
    else:  # cinematic
        drone = "0.30*sin(2*PI*49*t)+0.12*sin(2*PI*98*t)"
        kick = "0.45*sin(2*PI*55*t)*exp(-5*mod(t,1.0))"
        pad = "0.10*sin(2*PI*196*t)*sin(2*PI*0.0625*t)"

    d = max(8.0, duration + 1.0)
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"aevalsrc='{drone}':d={d}:s=44100",
        "-f", "lavfi", "-i", f"aevalsrc='{kick}':d={d}:s=44100",
        "-f", "lavfi", "-i", f"aevalsrc='{pad}':d={d}:s=44100",
        "-filter_complex",
        "[0][1][2]amix=inputs=3:duration=longest:weights=1 1.4 0.5,"
        "highpass=f=30,lowpass=f=4500,acompressor=threshold=0.4:ratio=4[m]",
        "-map", "[m]", "-ac", "2", "-ar", "44100",
        "-c:a", "libmp3lame", "-q:a", "4",
        str(out),
    ])


def synth_sfx(workdir: Path) -> tuple[Path, Path]:
    """Make whoosh and impact SFX files. Returns (whoosh_path, impact_path)."""
    whoosh = workdir / "whoosh.wav"
    impact = workdir / "impact.wav"
    # Whoosh: filtered brown noise, 0.22s.
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "anoisesrc=duration=0.22:color=brown:amplitude=0.6",
        "-af", "highpass=f=400,lowpass=f=6000,volume=0.6",
        str(whoosh),
    ])
    # Impact: low sine with sharp decay, 0.30s.
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        "aevalsrc='0.9*sin(2*PI*70*t)*exp(-10*t)+0.4*sin(2*PI*45*t)*exp(-6*t)':d=0.30:s=44100",
        str(impact),
    ])
    return whoosh, impact


def mix_audio(
    voice: Path,
    music: Path,
    whoosh: Path,
    impact: Path,
    whoosh_times: list[float],
    impact_times: list[float],
    total_dur: float,
    out: Path,
) -> None:
    """Mix voice (primary), music bed (-13dB), and SFX hits at the given
    cue times. Uses adelay to schedule each SFX instance, then amix."""
    inputs: list[str] = ["-i", str(voice), "-i", str(music)]
    # Each SFX cue becomes an additional input + adelay'd label.
    sfx_chains: list[str] = []
    sfx_labels: list[str] = []
    idx = 2  # next input index

    for t in whoosh_times:
        if t < 0.05 or t > total_dur - 0.05:
            continue  # skip cues outside the speech window
        inputs += ["-i", str(whoosh)]
        ms = int(t * 1000)
        lab = f"w{idx}"
        sfx_chains.append(f"[{idx}]adelay={ms}|{ms},volume=0.45[{lab}]")
        sfx_labels.append(f"[{lab}]")
        idx += 1
    for t in impact_times:
        if t < 0.05 or t > total_dur - 0.05:
            continue
        inputs += ["-i", str(impact)]
        ms = int(t * 1000)
        lab = f"i{idx}"
        sfx_chains.append(f"[{idx}]adelay={ms}|{ms},volume=0.7[{lab}]")
        sfx_labels.append(f"[{lab}]")
        idx += 1

    # Voice is primary; music ducked under it.
    chain_parts = [
        "[0]volume=1.0,aformat=channel_layouts=stereo[v]",
        "[1]volume=0.18,aformat=channel_layouts=stereo[m]",
        *sfx_chains,
    ]
    mix_inputs = "[v][m]" + "".join(sfx_labels)
    n = 2 + len(sfx_labels)
    chain_parts.append(f"{mix_inputs}amix=inputs={n}:duration=first:dropout_transition=0,"
                       f"alimiter=limit=0.95[mix]")
    filter_complex = ";".join(chain_parts)

    run([
        "ffmpeg", "-y", "-loglevel", "error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[mix]",
        "-t", f"{total_dur:.3f}",
        "-c:a", "aac", "-b:a", "192k",
        str(out),
    ])


# ---------- compose ----------

def build_video(
    script: str,
    shots: list[Shot],
    punches: list[Punch],
    gameplay_tag: str,
    out_path: Path,
    music_vibe: str = "dark",
) -> None:
    workdir = Path(tempfile.mkdtemp(prefix="exps_"))
    print(f"workdir: {workdir}")
    try:
        # 1. TTS
        print("[1/9] tts")
        voice = workdir / "voice.mp3"
        tts(script, voice)
        total_dur = ffprobe_duration(voice)
        print(f"      voice {total_dur:.2f}s")

        # 2. Whisper transcribe for timing + captions
        print("[2/9] whisper transcribe")
        words = transcribe(voice)
        print(f"      {len(words)} words")

        # 3. Resolve trigger times for each shot
        print("[3/9] resolving shot timings")
        shot_times: list[float] = []
        hint = 0.0
        for shot in shots:
            t = find_phrase_start(words, shot.phrase, hint_after=hint)
            if t is None:
                print(f"      !! trigger phrase not found: {shot.phrase!r}")
                t = hint
            shot_times.append(t)
            hint = t + 0.1
            print(f"      shot {shot.phrase[:30]:30s} -> t={t:.2f}s")

        # 4. Build timed top half (multi-cut B-roll)
        print("[4/9] top: assembling multi-cut B-roll")
        top, cut_times = build_timed_top(shots, shot_times, total_dur, HALF_H, workdir)
        print(f"      {len(cut_times)} sub-cuts")

        # 5. Pick gameplay for bottom
        print(f"[5/9] bottom: {gameplay_tag} gameplay")
        bottom = pick_gameplay_clip(gameplay_tag, total_dur, workdir)

        # 6. Captions + punches (both ASS, one filter pass)
        print("[6/9] captions + animated punches")
        chunks = group_words(words)
        caps_path = workdir / "captions.ass"
        write_captions_ass(chunks, caps_path, margin_v=380)

        punches_resolved: list[tuple[Punch, float, float]] = []
        punch_times: list[float] = []
        for p in punches:
            t = find_phrase_start(words, p.phrase, hint_after=0)
            if t is None:
                print(f"      !! punch phrase not found: {p.phrase!r}")
                continue
            punches_resolved.append((p, t, t + p.duration))
            punch_times.append(t)
        punches_path = workdir / "punches.ass"
        write_punches_ass(punches_resolved, punches_path)

        def _esc(p: Path) -> str:
            return str(p).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\\'")

        # 7. Audio: music + SFX, mixed under the voice
        print("[7/9] audio: music + SFX mix")
        music_file_env = os.environ.get("MUSIC_FILE")
        if music_file_env and Path(music_file_env).exists():
            music = Path(music_file_env)
            print(f"      using MUSIC_FILE={music}")
        else:
            music = workdir / "music.mp3"
            synth_music(total_dur, music, vibe=music_vibe)
            print(f"      synthesized {music_vibe} music bed")

        whoosh, impact = synth_sfx(workdir)
        # Whoosh on every cut EXCEPT the first (the very start doesn't
        # need a swoosh — it's already an attention grab from silence).
        whoosh_cues = [t for t in cut_times if t > 0.3]
        mixed_audio = workdir / "audio.aac"
        mix_audio(voice, music, whoosh, impact, whoosh_cues, punch_times, total_dur, mixed_audio)

        # 8. Stack top + bottom, burn in captions + punches.
        print("[8/9] compose video")
        graph = (
            f"[0:v]format=yuv420p[topf];"
            f"[1:v]format=yuv420p[botf];"
            f"[topf][botf]vstack=inputs=2[stacked];"
            f"[stacked]ass='{_esc(punches_path)}'[withpunch];"
            f"[withpunch]ass='{_esc(caps_path)}'[v]"
        )

        run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(top),
            "-i", str(bottom),
            "-i", str(mixed_audio),
            "-filter_complex", graph,
            "-map", "[v]", "-map", "2:a",
            "-t", f"{total_dur:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_path),
        ])
        print(f"[9/9] done -> {out_path}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------- main ----------

def main() -> int:
    # Script notes:
    #   * Whisper rewrites numbers as digits, so triggers below use "12"
    #     and "25", not "twelve" and "twenty five".
    #   * "Wayfair" gets transcribed as "wafer" so it's dropped from the
    #     copy; captions would otherwise misspell it.
    #   * "Once to buy / once to throw" gets heard as "wants to buy",
    #     so we use different wording.
    script = (
        "Your couch is garbage. Literally. "
        "Americans dump twelve million tons of furniture every year. "
        "In 1950, sofas were solid wood, real upholstery, built to last twenty five years. "
        "Today's couch is particle board, hot glue, and vinyl wrap. "
        "Designed to fall apart in one move. "
        "IKEA and Amazon trained you to treat furniture like fast fashion. "
        "Now millennials pay twice. First to buy it. Then to throw it out."
    )

    # Multi-cut shots. Pure single `pexels_query` shots fetch the top-3
    # candidates and cycle between them, which gives variety without us
    # hand-curating every angle. Explicit `queries` only where we want
    # specific different visuals.
    shots = [
        Shot(phrase="Your couch",   pexels_query="couch dumpster"),
        Shot(phrase="12 million",   queries=["landfill aerial", "garbage truck", "trash pile"]),
        Shot(phrase="In 1950",      queries=["vintage workshop", "wood carving", "upholstery"]),
        Shot(phrase="Today's couch",pexels_query="furniture assembly"),
        Shot(phrase="Designed to",  pexels_query="broken sofa"),
        Shot(phrase="IKEA",         queries=["warehouse boxes", "retail store aisle"]),
        Shot(phrase="millennials",  queries=["moving boxes", "dumpster trash"]),
    ]

    # Punches: triggers match whisper's actual transcription, so "twelve"
    # becomes "12" and "twenty five" becomes "25".
    punches = [
        Punch(phrase="garbage",      text="TRASH",            color="#ff3030", size=300, duration=1.4),
        Punch(phrase="12 million",   text="12 MILLION TONS",  color="#ff3030", size=180, duration=2.2),
        Punch(phrase="last 25",      text="25 YEARS",         color="#50ff80", size=260, duration=2.0),
        Punch(phrase="particle",     text="PARTICLE BOARD",   color="#cccccc", size=200, duration=2.0),
        Punch(phrase="fall apart",   text="ONE MOVE",         color="#ff3030", size=280, duration=2.0),
        Punch(phrase="trained you",  text="TRAINED YOU",      color="#ffffff", size=240, duration=2.0),
        Punch(phrase="pay twice",    text="PAY TWICE",        color="#ff3030", size=280, duration=2.2),
    ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_str = time.strftime("%Y%m%d-%H%M%S")
    out = OUTPUT_DIR / f"stacked_{ts_str}.mp4"
    build_video(script, shots, punches, gameplay_tag="minecraft",
                out_path=out, music_vibe=os.environ.get("MUSIC_VIBE", "dark"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
