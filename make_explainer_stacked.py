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
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
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
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "am_adam")


def normalize_for_tts(text: str) -> str:
    """Rewrite numeric shorthand so Kokoro/edge-tts pronounce it the way
    a human would read it aloud.

    Kokoro reads "$3B" as "dollar three bee" and "25%" as "twenty five
    percent sign". Fix by expanding the symbols before the engine sees
    them. Phrase-matching (find_phrase_start) runs the same normaliser
    so triggers stay aligned with the spoken transcript.

      $3B / $1.5B / $650-900B  -> N billion dollars (preserves "to" in ranges)
      $559M / $30.9M           -> N million dollars
      $1T / $1.05T             -> N trillion dollars
      $15,000 / $559           -> N dollars
      350M (no $)              -> 350 million
      25% / 130 percent        -> N percent (already-spelled passthrough)
    """
    s = text
    # Dollar ranges with B/M/T suffix: "$650-900B" -> "650 to 900 billion dollars"
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*-\s*([\d,]+(?:\.\d+)?)\s*[Bb]\b",
               r"\1 to \2 billion dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*-\s*([\d,]+(?:\.\d+)?)\s*[Mm]\b",
               r"\1 to \2 million dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*-\s*([\d,]+(?:\.\d+)?)\s*[Tt]\b",
               r"\1 to \2 trillion dollars", s)
    # Single-value dollar amounts with B/M/K/T suffix.
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*[Bb]\b", r"\1 billion dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*[Mm]\b", r"\1 million dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*[Tt]\b", r"\1 trillion dollars", s)
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s*[Kk]\b", r"\1 thousand dollars", s)
    # Dollar with WRITTEN-OUT unit: "$10.9 billion" -> "10.9 billion dollars".
    # Must run BEFORE bare "$NUM" so the unit stays inside the substitution.
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)\s+(billion|million|trillion|thousand|hundred)\b",
               r"\1 \2 dollars", s, flags=re.I)
    # Plain "$NUM" -> "NUM dollars" (after the suffixed forms have run).
    s = re.sub(r"\$([\d,]+(?:\.\d+)?)", r"\1 dollars", s)
    # Percent symbol.
    s = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 percent", s)
    # Bare abbreviations after a number (no $). Lookahead avoids breaking
    # acronyms like "AMD" or words starting with B/M/K/T.
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*B\b(?![A-Za-z])", r"\1 billion", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*M\b(?![A-Za-z])", r"\1 million", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*T\b(?![A-Za-z])", r"\1 trillion", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*K\b(?![A-Za-z])", r"\1 thousand", s)
    return s


def tts(text: str, out: Path) -> None:
    """Synthesize narration. Prefers local Kokoro TTS (free, unlimited,
    significantly more natural than edge-tts) if model files are
    present. Falls back to edge-tts otherwise."""
    text = normalize_for_tts(text)
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
    # Phrase has to be normalised the same way the script was before TTS,
    # otherwise a trigger like "$3B in funding" won't match the spoken
    # "three billion dollars in funding" that Whisper transcribes.
    target = [_norm(w) for w in normalize_for_tts(phrase).split()]
    n = len(target)
    transcript = [_norm(w.text) for w in words]
    for i in range(len(transcript) - n + 1):
        if words[i].start < hint_after:
            continue
        if all(_token_match(transcript[i + j], target[j]) for j in range(n)):
            return words[i].start
    return None


def _token_match(transcript_tok: str, target_tok: str) -> bool:
    """Decide if a single transcript token matches a target token.

    Numbers must match exactly — otherwise trigger '3 billion' grabs
    the first '3' digit of '350 billion', which is what caused two
    punches to fire on the same word in the Anthropic short. Words
    fall back to startswith / substring so verb tenses and similar
    morphology forgive transcription drift."""
    if not target_tok:
        return False
    if target_tok.isdigit() or transcript_tok.isdigit():
        return transcript_tok == target_tok
    return transcript_tok.startswith(target_tok) or target_tok in transcript_tok


def _norm(s: str) -> str:
    # Equivalence shims for Whisper-vs-author drift. "%" comes through as
    # its own token so "95 percent" in the script becomes ["95", "%"] in
    # the transcript and would never match the author's ["95", "percent"]
    # trigger. Normalize the symbol forms to their spelled-out forms in
    # both directions so triggers Just Work either way.
    s = s.replace("%", "percent")
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
Style: Pop,Impact,92,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,8,4,2,80,80,{margin_v},1

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
      1. `image`: a URL or local path to a still image — rendered with
         a slow Ken Burns zoom so it doesn't feel static. Use this for
         topic-specific imagery (Wikipedia, news article og:images,
         logos, screenshots) where stock footage would be too generic.
      2. `queries`: a list of stock-search queries; the shot subdivides
         its time window into one sub-cut per query.
      3. `pexels_query`: a single query — the shot fetches the top 2-3
         candidates and cycles between them as sub-cuts.
      4. `clip` + `clip_start`: a hardcoded local file.
    """
    phrase: str
    image: str | None = None
    queries: list[str] | None = None
    pexels_query: str | None = None
    clip: Path | None = None
    clip_start: float = 0.0
    # Package title used as extra context when topic_media has to
    # synthesise a topic-specific image from a generic shot query.
    topic_context: str = ""


# ---------- B-roll assembly (multi-cut) ----------

def _fetch_image(url_or_path: str, cache: Path) -> Path:
    """Resolve a shot.image value (URL or local path) to a cached file
    on disk. Local paths pass through; URLs are downloaded once and
    keyed by hash so subsequent renders re-use the same file."""
    if url_or_path.startswith(("http://", "https://")):
        import hashlib
        cache.mkdir(parents=True, exist_ok=True)
        ext = (Path(url_or_path.split("?")[0]).suffix or ".jpg").lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"
        name = hashlib.sha1(url_or_path.encode()).hexdigest()[:16] + ext
        dest = cache / name
        if not dest.exists():
            req = urllib.request.Request(
                url_or_path,
                # Wikimedia rejects the default urllib UA outright and
                # also requires a referer that looks like it came from a
                # Wikipedia page. Most news CDNs are happy with any
                # browser-shaped UA. This pair gets us through both.
                headers={
                    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko)"),
                    "Referer": "https://en.wikipedia.org/",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                dest.write_bytes(r.read())
        return dest
    p = Path(url_or_path)
    if not p.exists():
        raise FileNotFoundError(f"shot image path does not exist: {p}")
    return p


def _resolve_image(shot: Shot) -> dict | None:
    """Fetch the shot's image (URL or local path). Returns None on any
    failure so the caller can fall back to stock; raises only when the
    shot has nothing else to fall back to."""
    if not shot.image:
        return None
    try:
        img_path = _fetch_image(shot.image, Path("/tmp/shot_images"))
        print(f"      [image] {shot.image[:80]} -> {img_path.name}")
        return {"path": str(img_path), "is_image": True,
                "width": W, "height": HALF_H, "source": "image"}
    except Exception as e:  # noqa: BLE001
        print(f"      [image FAILED] {shot.image[:60]}: {e} — trying fallback")
        if not (shot.queries or shot.pexels_query or shot.clip):
            raise
        return None


_STOPWORDS = frozenset((
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at",
    "is", "are", "was", "were", "be", "been", "by", "with", "as", "it",
    "its", "this", "that", "from", "but", "not", "just", "more", "new",
))


def _shot_tokens(shot: "Shot") -> set[str]:
    """Build a bag of meaningful tokens for a shot — drawn from its
    spoken phrase + stock query so we can score each pool clip's
    filename against it. Stopwords are dropped so the score reflects
    content words ("moon", "rocket", "Mechazilla") not glue words.
    """
    bits: list[str] = [shot.phrase]
    if shot.pexels_query:
        bits.append(shot.pexels_query)
    if shot.queries:
        bits.extend(shot.queries)
    text = " ".join(bits).lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return {w for w in text.split() if len(w) > 2 and w not in _STOPWORDS}


def _score_clip(clip_title: str, shot_tokens: set[str]) -> int:
    """How well does a pool clip's filename match a shot's tokens?
    Plain token-overlap count — good enough for routing "moon" shots
    to moon clips and "engine" shots to engine clips without needing
    an LLM. Returns 0 when there's no overlap, which the caller treats
    as "fall back to round-robin."""
    title = re.sub(r"[^a-z0-9 ]+", " ", clip_title.lower())
    title_tokens = {w for w in title.split() if len(w) > 2}
    return len(shot_tokens & title_tokens)


def _scan_juicy(path: str | Path) -> list[float]:
    """Find high-motion seconds in a topic-video clip so the renderer
    can seek to one of them instead of the typical static intro /
    telemetry / coast-phase frame. Reuses `gameplay_scanner` in
    `scan_mode="center"` — center-crops to 50%x60% before the diff
    filter and scores by peak motion + frame-content richness, so a
    small rocket against a huge sky still registers as motion and
    flat-color sky pans get rejected.

    Window is short (3s) because each shot is only 3-5s and we want
    the displayed window to be all motion, not motion-then-static.
    Returns ascending list of seek offsets; caller cycles through them
    across shots so two shots that share a clip never seek to the
    same window.
    """
    try:
        import gameplay_scanner
        starts = gameplay_scanner.juicy_starts(
            Path(path), window=3.0, step=2.0, top_n=10,
            scan_mode="center")
        return starts or []
    except Exception as e:  # noqa: BLE001
        print(f"      [juicy scan failed] {Path(path).name}: {e}")
        return []


def _sub_cut_is_blank(sub_path: Path) -> bool:
    """Quick post-render sanity check: ffprobe a sampled frame from
    the rendered sub-cut. If it's mostly black (mean Y < 10) or
    visually uniform (std-dev < 5), the seek probably landed past the
    end of available frame data (common with Range-truncated webm
    where the duration metadata lies). Caller retries with the next
    juicy window or pool clip.

    Cheap: one `ffmpeg signalstats` pass on a single frame at the
    sub-cut's midpoint, ~30-50 ms.
    """
    try:
        out = subprocess.run([
            "ffprobe", "-v", "error",
            "-f", "lavfi",
            "-i", f"movie={sub_path},select=eq(n\\,15),signalstats",
            "-show_entries", "frame_tags=lavfi.signalstats.YAVG,lavfi.signalstats.YSTD",
            "-of", "default=noprint_wrappers=1",
        ], capture_output=True, text=True, timeout=10)
        text = out.stdout
        m_avg = re.search(r"YAVG=([\d.]+)", text)
        m_std = re.search(r"YSTD=([\d.]+)", text)
        if not m_avg or not m_std:
            return False  # couldn't measure → don't penalise
        return float(m_avg.group(1)) < 10.0 or float(m_std.group(1)) < 5.0
    except Exception:  # noqa: BLE001
        return False


def _supplementary_clip(shot: "Shot", existing_pool: list[dict]) -> dict | None:
    """When a shot's tokens don't overlap with any pool clip's title
    (e.g. "moon 2027" against a pure Starship pool), run a small
    Commons-only search keyed on this shot's own phrase + query.
    Cheap because it skips Archive / og:video / YouTube — Commons is
    free and ~200ms per call. If a real clip lands, it's added to the
    pool so subsequent shots can reuse it.
    """
    primary = shot.pexels_query or (shot.queries[0] if shot.queries else "")
    if not primary:
        return None
    try:
        import topic_video
    except ImportError:
        return None
    # Critical: pass *empty* context. If we passed the package title
    # here, Commons would just re-rank by overall topic and we'd get
    # the same rocket clips back. The whole point of supplementary
    # search is to find content the title-keyed pool missed — moon
    # footage for a moon shot, courtroom footage for a courtroom shot.
    seen_paths = {c["path"] for c in existing_pool}
    try:
        items = topic_video.search(primary, "", max_clips=3)
    except Exception as e:  # noqa: BLE001
        print(f"      [supplementary search error] {e}")
        return None
    # Disambiguation guard: the shot's keywords may be polysemous in
    # isolation ("Raptor" → SpaceX engine OR fighter jet, "Apple" →
    # company OR fruit). Require any supplementary clip to share at
    # least one token with the package context, so the package topic
    # constrains the result. F-22 Raptor Refuel for a SpaceX-Starship
    # package fails this check and gets dropped.
    context_tokens: set[str] = set()
    if shot.topic_context:
        ctx = re.sub(r"[^a-z0-9 ]+", " ", shot.topic_context.lower())
        context_tokens = {w for w in ctx.split()
                          if len(w) > 2 and w not in _STOPWORDS}
    for it in items:
        path_str = str(it["path"])
        if path_str in seen_paths:
            continue
        try:
            dur = ffprobe_duration(it["path"])
        except Exception:  # noqa: BLE001
            continue
        if dur < 2.0 or dur > 1800:
            continue
        title = it.get("title", "")
        if context_tokens:
            title_tokens = {w for w in re.sub(r"[^a-z0-9 ]+", " ",
                                                title.lower()).split()
                            if len(w) > 2}
            if not (context_tokens & title_tokens):
                print(f"      [supplementary skip off-topic] {title[:50]!r}")
                continue
        entry = {
            "path": path_str,
            "duration": dur,
            "title": title,
            "source": "topic_video",
            "uses": 0,
            "juicy": _scan_juicy(path_str),
            "width": W, "height": HALF_H,
        }
        existing_pool.append(entry)
        print(f"      [supplementary] '{shot.phrase[:30]}' -> "
              f"{entry['title'][:50]!r}")
        return entry
    return None


def _build_topic_video_pool(shots: list["Shot"]) -> list[dict]:
    """Pull a *pool* of topic-specific video clips once per render,
    queried by the package title rather than per-shot keywords.

    Each entry carries:
      - `title`: source filename for shot-matching scoring
      - `juicy`: list of high-motion seek offsets from
         `gameplay_scanner` so seeks land on action rather than
         intros / telemetry / coast phases
      - `uses`: counter for distributing the same clip across multiple
         shots with different seek targets
    """
    context = next((s.topic_context for s in shots if s.topic_context), "")
    if not context:
        return []
    try:
        import topic_video
    except ImportError:
        return []
    try:
        items = topic_video.search(context, "", max_clips=6)
    except Exception as e:  # noqa: BLE001
        print(f"      [topic_video pool error] {e}")
        return []
    pool: list[dict] = []
    for it in items:
        p = it["path"]
        try:
            dur = ffprobe_duration(p)
        except Exception as e:  # noqa: BLE001
            print(f"      [topic_video ffprobe fail] {p}: {e}")
            continue
        if dur < 2.0:
            continue
        if dur > 1800:  # 30 minutes
            print(f"      [topic_video skip long-form] {it['title'][:60]!r} ({dur:.0f}s)")
            continue
        juicy = _scan_juicy(p)
        pool.append({
            "path": str(p),
            "duration": dur,
            "title": it.get("title", ""),
            "source": "topic_video",
            "uses": 0,
            "juicy": juicy,
            "width": W, "height": HALF_H,
        })
    if pool:
        print(f"      [topic_video pool] {len(pool)} clips for {context[:60]!r}")
        for c in pool:
            j = c["juicy"]
            j_str = f"{len(j)} juicy@{j[0]:.0f}s..{j[-1]:.0f}s" if j else "no motion scan"
            print(f"         {c['title'][:60]} ({c['duration']:.0f}s, {j_str})")
    return pool


# Commons / news CDN thumbnail filenames prefix a resolution onto the
# real image name ("1280px-Starship_SN16.jpg", "800x600 launch.jpg",
# "thumb_launch.jpg"). Stripping the prefix gives the underlying
# stem so two thumbnails of the same source image dedup correctly.
_IMG_PREFIX_RE = re.compile(
    r"^(?:\d+px|\d+x\d+|thumb|small|medium|large)[\s_-]+",
    re.I,
)


def _image_stem(title: str) -> str:
    """Normalize a thumbnail filename for dedup. Repeatedly strips
    resolution / size prefixes ('1280px', '800x600', 'thumb', etc.),
    collapses whitespace, lowercases. Same source image at multiple
    resolutions collapses to a single stem; genuinely different
    images of the same event (different angles, different days) keep
    their distinguishing tokens and stay separate."""
    t = title.strip()
    while True:
        new = _IMG_PREFIX_RE.sub("", t).strip()
        if new == t or not new:
            break
        t = new
    return re.sub(r"\s+", " ", t).lower()


def _build_topic_image_pool(shots: list["Shot"]) -> list[dict]:
    """Pool of topic-specific *still images* (Wikipedia hero, Commons
    photos, news article og:images) built once per render. Images are
    way cheaper to fetch than videos and almost always crisply on
    topic, so we mix them into the round-robin filler to fill gaps
    where topic_video misses and to add visual variety.

    Entries are deduplicated by normalized filename stem so two
    thumbnails of the same source image at different resolutions
    can't both end up in the pool — and therefore can never get
    picked back-to-back. Each entry drops straight into the
    renderer's existing `is_image` branch (Ken Burns zoompan) and
    carries `title` from the source filename for token scoring.
    """
    context = next((s.topic_context for s in shots if s.topic_context), "")
    if not context:
        return []
    try:
        import topic_media
        urls = topic_media.search(context, "")
    except Exception as e:  # noqa: BLE001
        print(f"      [topic_image pool error] {e}")
        return []
    pool: list[dict] = []
    seen_stems: set[str] = set()
    cache = Path("/tmp/shot_images")
    for url in (urls or [])[:8]:
        try:
            path = _fetch_image(url, cache)
        except Exception as e:  # noqa: BLE001
            print(f"      [topic_image fetch fail] {url[:60]}: {e}")
            continue
        # Extract a readable title from the URL for token scoring.
        name = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
        try:
            from urllib.parse import unquote
            name = unquote(name)
        except Exception:  # noqa: BLE001
            pass
        if "." in name:
            name = name.rsplit(".", 1)[0]
        title = name.replace("_", " ").replace("-", " ").strip()
        stem = _image_stem(title)
        if stem in seen_stems:
            print(f"      [topic_image dedup] {title[:60]!r}")
            continue
        seen_stems.add(stem)
        pool.append({
            "path": str(path),
            "title": title,
            "stem": stem,
            "source": "topic_image",
            "is_image": True,
            "uses": 0,
            "width": W, "height": HALF_H,
        })
    if pool:
        print(f"      [topic_image pool] {len(pool)} images for {context[:60]!r}")
        for c in pool:
            print(f"         {c['title'][:70]}")
    return pool


def _pick_pool_image(pool: list[dict], shot: "Shot",
                     exclude_paths: set[str] | None = None) -> dict | None:
    """Score-and-pick an image from the topic_image pool. Same shape
    as `_pick_pool_clip` but for stills — no seek offset, no juicy
    windows.

    `exclude_paths` is a set of image paths the caller wants to avoid
    (typically: images already used in this shot's plan, so we never
    pick the same one back-to-back). If every pool entry is excluded
    we still return a pick — better to repeat than to leave a gap.
    Mutates `uses` so successive picks across shots prefer images
    that haven't been shown yet.
    """
    if not pool:
        return None
    excl = exclude_paths or set()
    candidates = [c for c in pool if c["path"] not in excl] or pool
    tokens = _shot_tokens(shot)
    chosen: dict | None = None
    if tokens:
        scored = [(_score_clip(c["title"], tokens), -c["uses"], idx, c)
                  for idx, c in enumerate(candidates)]
        scored.sort(reverse=True)
        best_score, _, _, best = scored[0]
        if best_score > 0:
            chosen = best
    if chosen is None:
        chosen = min(candidates, key=lambda c: c["uses"])
    chosen["uses"] += 1
    return dict(chosen)


# Per-shot memo so _pick_pool_clip's repeated calls in the
# sub-cut round-robin don't each re-run the supplementary Commons
# search. Keyed by the shot's phrase string; emptied each render.
_SUPPLEMENTARY_DONE: set[str] = set()


def _pick_pool_clip(pool: list[dict], shot: "Shot") -> dict | None:
    """Return the clip best matching this shot, plus a per-shot `seek`
    offset that lands on a high-motion window. Mutates `clip['uses']`
    so successive shots get different juicy windows instead of the
    same opening frames.

    For every shot, runs a per-shot supplementary Commons search keyed
    on that shot's own words. The results join the pool before
    scoring, so even when the title-based pool already has a
    "decent" match (e.g. "Starship landing" for a "moon landing"
    shot), a more relevant per-shot result can still win. The
    supplementary clip stays in the pool so later shots can reuse it.
    """
    if not pool:
        return None
    tokens = _shot_tokens(shot)
    # Always seed shot-specific content into the pool. Cheap (Commons
    # only, ~200ms when nothing matches; the download is cached on
    # reuse) and prevents the "moon shot got a rocket clip" failure
    # mode where the pool's coincidental token overlap beats the
    # supplementary clip's semantic fit. Memoised by shot phrase
    # because each long shot calls _pick_pool_clip several times in
    # the SUB_CUT_TARGET round-robin and we don't want to repeat the
    # search per sub-cut.
    if shot.phrase not in _SUPPLEMENTARY_DONE:
        sup = _supplementary_clip(shot, pool)
        _SUPPLEMENTARY_DONE.add(shot.phrase)
    else:
        sup = None

    chosen: dict | None = None
    if tokens:
        scored = [(_score_clip(c["title"], tokens), -c["uses"], idx, c)
                  for idx, c in enumerate(pool)]
        scored.sort(reverse=True)
        best_score, _, _, best = scored[0]
        if best_score > 0:
            chosen = best
    if chosen is None:
        # Nothing in the pool scored against the shot tokens. Prefer
        # the just-found supplementary clip (queried specifically for
        # this shot) over the least-used round-robin pick.
        chosen = sup or min(pool, key=lambda c: c["uses"])

    # Seek policy: prefer a juicy (high-motion) start. Successive uses
    # of the same clip cycle through its juicy list so two shots never
    # show the same window. Falls back to the +15s-per-use constant
    # when the motion scan returned nothing (e.g. scan crashed).
    if chosen.get("juicy"):
        starts = chosen["juicy"]
        seek = starts[chosen["uses"] % len(starts)]
    else:
        seek = min(15.0 + chosen["uses"] * 12.0,
                   max(0.0, chosen["duration"] - 5.0))
    chosen["uses"] += 1
    out = dict(chosen)
    out["seek"] = seek
    return out


def _resolve_topic_media(shot: Shot, cache: Path) -> dict | None:
    """Try to pull a topic-specific image from free sources (Wikipedia,
    Commons, GDELT news). Used only when the package didn't supply
    `image_url` for this shot. Returns the same dict shape as
    `_resolve_image` or None on miss so the caller falls back to stock.
    """
    primary = shot.pexels_query or (shot.queries[0] if shot.queries else "")
    if not primary and not shot.topic_context:
        return None
    try:
        import topic_media
    except ImportError:
        return None
    try:
        urls = topic_media.search(primary, shot.topic_context)
    except Exception as e:  # noqa: BLE001
        print(f"      [topic_media error] {e}")
        return None
    for url in urls:
        try:
            img_path = _fetch_image(url, cache)
            print(f"      [topic_media] {primary[:30]!r} -> {url[:80]}")
            return {"path": str(img_path), "is_image": True,
                    "width": W, "height": HALF_H, "source": "topic_media"}
        except Exception as e:  # noqa: BLE001
            print(f"      [topic_media FAIL] {url[:60]}: {e}")
            continue
    return None


def _resolve_stock(shot: Shot, cache: Path, n_target: int) -> list[dict]:
    """Just the stock-video resolution path (no image branch). Returns
    the downloaded clip metadata; always at least one, or raises."""
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

    # How long a still image is allowed to stay on screen before it
    # has to hand off to stock. Users find longer holds boring even
    # with Ken Burns motion — keep it short and let multiple specific
    # images carry the visual story instead of one long hold.
    IMAGE_MAX_DUR = 1.8

    # One-shot per-render calls to topic_video / topic_media. Returns
    # pools of on-topic media. Each shot picks pool entries whose
    # filenames best match its own phrase/query (semantic scoring) so
    # "moon" shots get moon media and "engine" shots get engine media
    # instead of round-robin chaos. The image pool is woven into the
    # sub-cut filler alongside the video pool — images are cheaper to
    # source and almost always crisply topical, so they fill gaps
    # where topic_video is thin and add visual variety.
    topic_video_pool = _build_topic_video_pool(shots)
    topic_image_pool = _build_topic_image_pool(shots)
    # Reset the per-shot supplementary memo so this render starts
    # fresh — across renders the cached video files are reused, but
    # the in-process "we already tried this shot" set must not leak.
    _SUPPLEMENTARY_DONE.clear()

    for i, (shot, start_t) in enumerate(zip(shots, shot_times)):
        end_t = shot_times[i + 1] if i + 1 < len(shot_times) else total_dur
        seg_dur = max(0.5, end_t - start_t)

        # Plan this shot's sub-cuts as a list of (clip, duration) pairs.
        # The plan handles three cases:
        #   1. Image + stock fallback   -> image (capped) then stock cuts
        #   2. Image only               -> image extended to full window
        #   3. Stock only               -> existing multi-cut behavior
        plan: list[tuple[dict, float]] = []
        image_clip = _resolve_image(shot)
        # Operator-supplied image wins. Otherwise pull a pool clip
        # scored against this shot's tokens. Fall through to topic_media
        # stills and then stock only when the pool is empty.
        topic_video_clip = None
        if image_clip is None and topic_video_pool:
            topic_video_clip = _pick_pool_clip(topic_video_pool, shot)
            if topic_video_clip:
                print(f"      [topic_video] shot {i+1} '{shot.phrase[:30]}' -> "
                      f"{topic_video_clip['title'][:50]!r} @ seek={topic_video_clip['seek']:.0f}s")
        if image_clip is None and topic_video_clip is None:
            image_clip = _resolve_topic_media(shot, Path("/tmp/shot_images"))
        has_stock = bool(shot.queries or shot.pexels_query or shot.clip)

        if topic_video_clip:
            # Topic-video clips claim the full shot window. The clip is
            # already on-topic; padding it with generic stock would only
            # dilute the visual continuity.
            available = max(0.0,
                            float(topic_video_clip["duration"])
                            - float(topic_video_clip.get("seek", 0.0)))
            # Cap each topic-video sub-cut at SUB_CUT_TARGET. Without
            # this, a 10s shot got 10 unbroken seconds from one source
            # clip — even when there was motion, the lack of cuts read
            # as a static frame. Capping forces the round-robin loop
            # below to pull additional pool clips and produce the same
            # rapid-cut feel the stock path already had.
            vid_dur = min(seg_dur, available, SUB_CUT_TARGET)
            plan.append((topic_video_clip, vid_dur))
            remaining = seg_dur - vid_dur
            # Fill the rest of the shot by ALTERNATING video and image
            # pool entries. Images are cheaper to source and almost
            # always on-topic, and alternating breaks up the visual
            # monotony of a single source streaming for 5+ seconds.
            # Image dur is capped at IMAGE_MAX_DUR (Ken Burns gets
            # boring past ~2s); video dur stays at SUB_CUT_TARGET.
            # Track images already used in this shot so the picker
            # never returns the same one back-to-back even if it
            # happens to be the highest-scoring pool entry.
            used_image_paths: set[str] = set()
            fill_idx = 1
            while remaining > 0.3:
                want_image = (fill_idx % 2 == 1 and topic_image_pool)
                placed = False
                if want_image:
                    img = _pick_pool_image(topic_image_pool, shot,
                                            exclude_paths=used_image_paths)
                    if img:
                        fill = min(remaining, IMAGE_MAX_DUR)
                        if fill > 0.3:
                            plan.append((img, fill))
                            remaining -= fill
                            fill_idx += 1
                            placed = True
                            used_image_paths.add(img["path"])
                            print(f"      [topic_image] shot {i+1} fill -> "
                                  f"{img['title'][:50]!r} ({fill:.1f}s)")
                if not placed and topic_video_pool:
                    nxt = _pick_pool_clip(topic_video_pool, shot)
                    if nxt:
                        nxt_avail = max(0.0,
                                        float(nxt["duration"])
                                        - float(nxt.get("seek", 0.0)))
                        fill = min(remaining, nxt_avail, SUB_CUT_TARGET)
                        if fill > 0.3:
                            plan.append((nxt, fill))
                            remaining -= fill
                            fill_idx += 1
                            placed = True
                # Last-ditch: try the image pool even if it wasn't
                # this slot's turn, so we don't bail on the round-robin
                # just because the video pool ran out of clips that
                # fit the remaining window.
                if not placed and not want_image and topic_image_pool:
                    img = _pick_pool_image(topic_image_pool, shot,
                                            exclude_paths=used_image_paths)
                    if img:
                        fill = min(remaining, IMAGE_MAX_DUR)
                        if fill > 0.3:
                            plan.append((img, fill))
                            remaining -= fill
                            fill_idx += 1
                            placed = True
                            used_image_paths.add(img["path"])
                            print(f"      [topic_image] shot {i+1} fill -> "
                                  f"{img['title'][:50]!r} ({fill:.1f}s)")
                if not placed:
                    break
        elif image_clip and has_stock:
            image_dur = min(IMAGE_MAX_DUR, seg_dur)
            plan.append((image_clip, image_dur))
            remaining = seg_dur - image_dur
        elif image_clip:
            plan.append((image_clip, seg_dur))
            remaining = 0.0
        else:
            remaining = seg_dur

        if remaining > 0.3:
            n_cuts = max(1, round(remaining / SUB_CUT_TARGET))
            cut_dur = remaining / n_cuts
            stock_clips: list[dict] = []
            try:
                stock_clips = _resolve_stock(shot, cache, n_target=n_cuts)
            except Exception as e:  # noqa: BLE001
                print(f"      [stock failed] {shot.phrase[:40]!r}: {e}")
            if stock_clips:
                for j in range(n_cuts):
                    plan.append((stock_clips[j % len(stock_clips)], cut_dur))
            else:
                # Stock provider unreachable. Never stretch the image
                # past its cap — long static holds feel dead. Use a
                # slate-blue placeholder for the remainder so the
                # timeline length is preserved. In real CI this path
                # never fires because stock keys are configured.
                placeholder = {"is_image": True, "is_placeholder": True,
                               "path": "", "width": W, "height": HALF_H,
                               "source": "placeholder"}
                plan.append((placeholder, remaining))

        # Render each planned sub-cut.
        sub_t = start_t
        for j, (clip, dur) in enumerate(plan):
            sub = workdir / f"top_{i:02d}_{j:02d}.mp4"

            if clip.get("is_placeholder"):
                # No image, no stock — just paint a slate background for
                # this segment so the timeline doesn't drift.
                run([
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i",
                    f"color=c=0x1f2a3a:s={W}x{top_h}:r={FPS}",
                    "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p",
                    str(sub),
                ])
            elif clip.get("is_image"):
                # Still image — Ken Burns it. Alternate zoom-in vs
                # zoom-out based on cut index so successive image shots
                # don't all do the same move. We work at 2x then scale
                # down inside the zoompan filter so the zoom doesn't
                # quantize to ugly stair-stepped frames.
                frames = max(2, int(dur * FPS))
                move = "zoom_in" if (i + j) % 2 == 0 else "zoom_out"
                if move == "zoom_in":
                    z_expr = f"min(zoom+0.0006,1.18)"
                else:
                    z_expr = f"if(eq(on,0),1.18,max(zoom-0.0006,1.0))"
                # Build the frame in two layers. First input is the
                # image (may have alpha → must NOT become the
                # background); second is a solid colored canvas of the
                # correct size we generate on the fly with `color=`.
                # We overlay the fitted image onto the canvas, then
                # zoompan that. This guarantees the encoded H.264
                # frame has no transparent regions even when the
                # source PNG is a logo with a transparent margin —
                # the alpha gets composited against the non-black
                # canvas instead of the H.264 void.
                bg_color = "0x1f2a3a"  # medium-dark slate blue, clearly NOT black
                filt = (
                    f"[1:v]scale={W*2}:{top_h*2}[canvas];"
                    f"[0:v]scale={W*2}:{top_h*2}:force_original_aspect_ratio=decrease[fg];"
                    f"[canvas][fg]overlay=(W-w)/2:(H-h)/2:format=auto[stage];"
                    f"[stage]zoompan=z='{z_expr}'"
                    f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                    f":d={frames}:s={W}x{top_h}:fps={FPS},"
                    f"setsar=1[out]"
                )
                run([
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-loop", "1", "-i", clip["path"],
                    "-f", "lavfi", "-i",
                    f"color=c={bg_color}:s={W*2}x{top_h*2}:r={FPS}",
                    "-t", f"{dur:.3f}",
                    "-filter_complex", filt,
                    "-map", "[out]",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    str(sub),
                ])
            else:
                clip_dur = float(clip.get("duration") or 10)
                # Topic-video clips carry their own seek offset (set by
                # _pick_pool_clip — skips past title cards, telemetry,
                # and intro dead-air so successive uses of the same
                # source clip show different moments). Stock clips just
                # use the existing "vary seek by sub-cut index" logic
                # to stop showing the same opening frames.
                # Topic-video pool clips also carry a list of
                # alternative juicy windows; if the first seek lands
                # on a black/uniform frame (Range-truncated webm
                # reporting a longer duration than its actual data),
                # we retry with the next window.
                candidates_seek: list[float]
                if "seek" in clip:
                    if clip.get("juicy"):
                        # Sort juicy windows by distance from the
                        # initially-chosen seek so the retry stays
                        # close to the requested moment when possible.
                        primary = float(clip["seek"])
                        candidates_seek = sorted(
                            clip["juicy"], key=lambda s: abs(s - primary))
                    else:
                        candidates_seek = [float(clip["seek"])]
                else:
                    candidates_seek = [0.3 + j * 1.5]

                rendered = False
                for attempt, seek in enumerate(candidates_seek[:3]):
                    seek = min(seek, max(0.0, clip_dur - dur - 0.3))
                    run([
                        "ffmpeg", "-y", "-loglevel", "error",
                        "-ss", f"{seek:.3f}", "-i", clip["path"],
                        "-t", f"{dur:.3f}",
                        "-vf", f"scale={W}:{top_h}:force_original_aspect_ratio=increase,"
                               f"crop={W}:{top_h},setsar=1,fps={FPS}",
                        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        str(sub),
                    ])
                    if _sub_cut_is_blank(sub):
                        print(f"      [sub-cut blank @ seek={seek:.1f}s, "
                              f"retry {attempt+1}/3] {Path(clip['path']).name}")
                        continue
                    rendered = True
                    break
                # If every juicy window on this clip rendered blank,
                # we keep the last attempt rather than dropping the
                # sub-cut — better a weak frame than a missing one in
                # the timeline.
                if not rendered:
                    print(f"      [sub-cut all retries blank, keeping last attempt]")
            all_segments.append(sub)
            cut_times.append(sub_t)
            sub_t += dur

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
        # Don't sys.exit here — it skips the caller's exception handler
        # and the orchestrator never logs which package failed or why.
        # Listing what IS in the dir makes the error self-diagnosing
        # ("ah, the cache restored only the sidecar json").
        existing = [p.name for p in GAMEPLAY_DIR.iterdir()] if GAMEPLAY_DIR.exists() else []
        raise RuntimeError(
            f"no gameplay clips matching {tag!r} in {GAMEPLAY_DIR}. "
            f"Existing files: {existing}. "
            f"Run seed_gameplay.py to download fresh."
        )
    src = random.choice(pool)
    dur = ffprobe_duration(src)

    # Prefer to seek into a pre-scanned high-motion window. The scanner
    # caches its result in a sidecar JSON so this only pays the scan
    # cost once per video. For short clips (< 3 min) the overhead isn't
    # worth it — fall back to random seek.
    seek = None
    if dur > 180:
        try:
            import gameplay_scanner
            # Fixed scan window of 35s — wide enough to cover any short
            # we'd render. Using a constant window keeps the sidecar
            # cache stable across renders with slightly different audio
            # lengths (otherwise every length change forces a rescan).
            scan_window = 35.0
            starts = gameplay_scanner.juicy_starts(
                src, window=scan_window, step=5.0, top_n=25,
            )
            if starts:
                # Pick a juicy window, then jitter inside it so two
                # renders that hit the same window don't show the same
                # framing.
                base = random.choice(starts)
                seek = base + random.uniform(0, max(0.1, scan_window - target - 2.0))
                print(f"      juicy seek {seek:.1f}s (from {len(starts)} candidates)")
        except Exception as e:  # noqa: BLE001
            print(f"      gameplay_scanner failed, falling back: {e}")

    if seek is None:
        # Stay away from the tail of the clip — that's where the
        # YouTuber's world-select menu / outro screens tend to sit.
        max_seek = max(0, dur - target - 25)
        seek = random.uniform(5, max(5, max_seek))

    out = workdir / "bottom_raw.mp4"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{seek:.3f}", "-i", str(src),
        "-t", f"{target:.3f}",
        # Center crop on both axes. The previous formula offset y by 70%
        # of the excess height (showing the bottom third) which was
        # cutting the player's head off on landscape sources and cutting
        # everything off on portrait sources. Centered is the safer
        # default for arbitrary parkour gameplay clips.
        "-vf", f"scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
               f"crop={W}:{HALF_H},setsar=1,fps={FPS}",
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


def synth_sfx(workdir: Path) -> dict[str, Path]:
    """Make a small SFX library. Returns a dict of named one-shots.

    The whoosh fires on every visual cut. The four impact variants are
    keyed off punch color — each color implies a tone, so the SFX
    matches: red = shock/bad → deep thump, green = positive → bright
    bell, orange = warning → mid bell, white = neutral → classic
    impact. Multiple punches in a single video stop feeling repetitive
    when each one sounds slightly different."""
    sfx: dict[str, Path] = {}

    # Whoosh: filtered brown noise, 0.22s. Fires on every B-roll cut.
    sfx["whoosh"] = workdir / "whoosh.wav"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "anoisesrc=duration=0.22:color=brown:amplitude=0.6",
        "-af", "highpass=f=400,lowpass=f=6000,volume=0.6",
        str(sfx["whoosh"]),
    ])

    # Neutral impact: low sine with sharp decay, 0.30s. Classic.
    sfx["impact_neutral"] = workdir / "impact_neutral.wav"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        "aevalsrc='0.9*sin(2*PI*70*t)*exp(-10*t)+0.4*sin(2*PI*45*t)*exp(-6*t)':d=0.30:s=44100",
        str(sfx["impact_neutral"]),
    ])

    # Shock (red): sub-bass dominant, longer decay, scarier.
    sfx["impact_shock"] = workdir / "impact_shock.wav"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        "aevalsrc='1.0*sin(2*PI*40*t)*exp(-5*t)+0.55*sin(2*PI*55*t)*exp(-8*t)+"
        "0.3*sin(2*PI*82*t)*exp(-12*t)':d=0.45:s=44100",
        "-af", "highpass=f=25,lowpass=f=2200",
        str(sfx["impact_shock"]),
    ])

    # Positive (green): bright tonal bell, two harmonics.
    sfx["impact_positive"] = workdir / "impact_positive.wav"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        "aevalsrc='0.55*sin(2*PI*880*t)*exp(-7*t)+0.30*sin(2*PI*1320*t)*exp(-9*t)+"
        "0.20*sin(2*PI*1760*t)*exp(-11*t)':d=0.40:s=44100",
        "-af", "highpass=f=400,lowpass=f=8000",
        str(sfx["impact_positive"]),
    ])

    # Warning (orange): mid-frequency bell with a quick metallic edge.
    sfx["impact_warning"] = workdir / "impact_warning.wav"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        "aevalsrc='0.6*sin(2*PI*420*t)*exp(-6*t)+0.35*sin(2*PI*660*t)*exp(-9*t)+"
        "0.18*sin(2*PI*1100*t)*exp(-14*t)':d=0.38:s=44100",
        "-af", "highpass=f=200,lowpass=f=5000",
        str(sfx["impact_warning"]),
    ])

    # Money (cash register): two quick metallic ka-chings. Plays
    # whenever the punch text contains a dollar sign, regardless of
    # color, because "$350B" lighting up with a flat blip felt wrong.
    sfx["impact_money"] = workdir / "impact_money.wav"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        "aevalsrc='"
        # First hit at t=0
        "0.5*sin(2*PI*1480*t)*exp(-12*t)+"
        "0.35*sin(2*PI*2100*t)*exp(-14*t)+"
        # Second hit ~95ms later
        "0.45*sin(2*PI*1760*max(0,t-0.095))*exp(-12*max(0,t-0.095))+"
        "0.30*sin(2*PI*2640*max(0,t-0.095))*exp(-14*max(0,t-0.095))"
        "':d=0.42:s=44100",
        "-af", "highpass=f=500,lowpass=f=8000",
        str(sfx["impact_money"]),
    ])

    return sfx


# Map punch color hex -> SFX variant. Anything not in the map falls
# through to the neutral variant. Text-pattern rules in sfx_for_punch()
# take priority over color when the text itself implies a specific tone
# (a punch with "$350B" plays the cash-register ching regardless of
# what color the author chose for it).
_PUNCH_COLOR_TO_SFX = {
    "#ff3030": "impact_shock",
    "#ff5050": "impact_shock",
    "#ff9000": "impact_warning",
    "#ff9900": "impact_warning",
    "#ffaa30": "impact_warning",
    "#50ff80": "impact_positive",
    "#30ff60": "impact_positive",
    "#80ffaa": "impact_positive",
    "#ffffff": "impact_neutral",
}


# Text-pattern overrides. (regex, sfx_name) — the first match wins. The
# author shouldn't need to hand-pick SFX; the pipeline should anticipate
# obvious cases from the punch text itself.
_PUNCH_TEXT_RULES: list[tuple[re.Pattern, str]] = [
    # Anything with a dollar sign is money — ching.
    (re.compile(r"\$"), "impact_money"),
    # Catastrophic / shock vocabulary.
    (re.compile(r"\b(RIP|DEAD|CRASH|DIES?|KILLED|GAME OVER|BANNED)\b", re.I),
     "impact_shock"),
    # Time-pressure / countdown.
    (re.compile(r"\b\d+\s*(DAYS?|HOURS?|MIN(UTES?)?|SEC(ONDS?)?)\b", re.I),
     "impact_warning"),
]


def sfx_for_punch(p: "Punch") -> str:
    # Text rules first — they catch cases the author's color choice
    # might not (e.g. "$1.2B" on a green-positive punch should still
    # ching like money).
    for pat, name in _PUNCH_TEXT_RULES:
        if pat.search(p.text or ""):
            return name
    return _PUNCH_COLOR_TO_SFX.get((p.color or "").lower(), "impact_neutral")


def mix_audio(
    voice: Path,
    music: Path,
    sfx: dict[str, Path],
    whoosh_times: list[float],
    punch_cues: list[tuple[float, str]],
    total_dur: float,
    out: Path,
) -> None:
    """Mix voice (primary), music bed (-15dB), and SFX hits at the given
    cue times. Two important details:

      * normalize=0 on amix — the default normalize=1 divides every
        input by the total input count, so with 20+ SFX cues the voice
        would land at ~1/20 of its nominal level (and feel "quiet at
        the start, loud at the end" as SFX-density shifts the per-input
        gain). We want each input to play at its own gain, period.

      * dynaudnorm on the voice — Kokoro's loudness drifts across long
        scripts; the run-end sentences land hotter than the opener.
        dynaudnorm levels that out before we mix.
    """
    inputs: list[str] = ["-i", str(voice), "-i", str(music)]
    sfx_chains: list[str] = []
    sfx_labels: list[str] = []
    idx = 2  # next input index

    for t in whoosh_times:
        if t < 0.05 or t > total_dur - 0.05:
            continue
        inputs += ["-i", str(sfx["whoosh"])]
        ms = int(t * 1000)
        lab = f"w{idx}"
        sfx_chains.append(f"[{idx}]adelay={ms}|{ms},volume=0.35[{lab}]")
        sfx_labels.append(f"[{lab}]")
        idx += 1
    for t, variant in punch_cues:
        if t < 0.05 or t > total_dur - 0.05:
            continue
        path = sfx.get(variant) or sfx["impact_neutral"]
        inputs += ["-i", str(path)]
        ms = int(t * 1000)
        lab = f"i{idx}"
        sfx_chains.append(f"[{idx}]adelay={ms}|{ms},volume=0.55[{lab}]")
        sfx_labels.append(f"[{lab}]")
        idx += 1

    chain_parts = [
        # Voice: stereo + dynaudnorm so TTS loudness drift is gone before
        # it ever hits amix. Modest gain after — dynaudnorm pulls down
        # peaks more than it pushes up quiet parts.
        "[0]aformat=channel_layouts=stereo,dynaudnorm=f=200:g=15:p=0.95,volume=1.1[v]",
        # Music sits ~15dB under the voice.
        "[1]aformat=channel_layouts=stereo,volume=0.18[m]",
        *sfx_chains,
    ]
    mix_inputs = "[v][m]" + "".join(sfx_labels)
    n = 2 + len(sfx_labels)
    # normalize=0: each input plays at its own gain, ignore input count.
    # alimiter at the end stops anything from clipping.
    chain_parts.append(
        f"{mix_inputs}amix=inputs={n}:duration=first:dropout_transition=0:normalize=0,"
        f"alimiter=limit=0.95:attack=5:release=50[mix]"
    )
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
                # Don't collapse the shot to nothing — give it at least
                # 2.5s after the prior shot so the B-roll has a fighting
                # chance of showing on screen. If a trigger fails right
                # at the start (no prior), use that as the floor too.
                prev_t = shot_times[-1] if shot_times else 0.0
                t = max(hint, prev_t + 2.5)
            shot_times.append(t)
            hint = t + 0.1
            print(f"      shot {shot.phrase[:30]:30s} -> t={t:.2f}s")

        # 4. Build timed top half (multi-cut B-roll)
        print("[4/9] top: assembling multi-cut B-roll")
        top, cut_times = build_timed_top(shots, shot_times, total_dur, HALF_H, workdir)
        print(f"      {len(cut_times)} sub-cuts")

        # 5. Pick gameplay for bottom
        print(f"[5/9] bottom: {gameplay_tag} gameplay", flush=True)
        bottom = pick_gameplay_clip(gameplay_tag, total_dur, workdir)

        # 6. Captions + punches (both ASS, one filter pass)
        print("[6/9] captions + animated punches")
        chunks = group_words(words)
        caps_path = workdir / "captions.ass"
        # Captions sit just below the top/bottom split so gameplay's
        # bottom is unobstructed. ASS MarginV is bottom margin in pixels
        # with Alignment=2 (bottom-center): text bottom at y = H - margin_v.
        # For text bottom around y~1110 (~150px below the split): 1920-1110 = 810.
        write_captions_ass(chunks, caps_path, margin_v=810)

        punches_resolved: list[tuple[Punch, float, float]] = []
        # (time, sfx_variant_name) — variant picked from the punch's
        # color so the audio matches the visual tone.
        punch_cues: list[tuple[float, str]] = []
        for p in punches:
            t = find_phrase_start(words, p.phrase, hint_after=0)
            if t is None:
                print(f"      !! punch phrase not found: {p.phrase!r}")
                continue
            punches_resolved.append((p, t, t + p.duration))
            punch_cues.append((t, sfx_for_punch(p)))

        # Prevent overlapping punches. All punches render at the same
        # screen position (top-third, centered), so two firing within
        # ~2.4s of each other would literally stack on top of each other
        # — looked like overlapping captions to the user. Truncate each
        # punch at (next_start - 0.15s) so there's a tiny breathing gap,
        # but never below 0.8s on screen so a punch always has time to
        # land.
        punches_resolved.sort(key=lambda x: x[1])
        adjusted: list[tuple[Punch, float, float]] = []
        for i, (p, t, end) in enumerate(punches_resolved):
            if i + 1 < len(punches_resolved):
                next_start = punches_resolved[i + 1][1]
                end = min(end, max(t + 0.8, next_start - 0.15))
            adjusted.append((p, t, end))
        punches_resolved = adjusted

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

        sfx = synth_sfx(workdir)
        # Whoosh on every cut EXCEPT the first (the very start doesn't
        # need a swoosh — it's already an attention grab from silence).
        whoosh_cues = [t for t in cut_times if t > 0.3]
        mixed_audio = workdir / "audio.aac"
        mix_audio(voice, music, sfx, whoosh_cues, punch_cues, total_dur, mixed_audio)

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

def build_from_package(pkg: dict, out_path: Path, *, gameplay_tag: str = "minecraft") -> None:
    """Run the renderer from a JSON package (as produced by
    script_generator.py). Schema:

      {
        "script": "...",
        "shots":  [{"phrase": "...", "query": "..."}, ...],
        "punches":[{"phrase": "...", "text": "...", "color": "#..."}, ...],
        "music_vibe": "dark" | "cinematic" | "hiphop",
      }
    """
    shots = []
    for s in pkg["shots"]:
        # Each shot is one of: image-anchored, stock-query, or local clip.
        # The package can also pass a list of queries for sub-cut variety.
        shots.append(Shot(
            phrase=s["phrase"],
            # Packages emit `image_url`; older code wrote `image`. Accept
            # both so we don't silently drop the routine's hand-picked
            # Wikipedia/news images.
            image=s.get("image_url") or s.get("image"),
            queries=s.get("queries"),
            pexels_query=s.get("query"),
            topic_context=pkg.get("title", ""),
        ))
    punches = [
        Punch(
            phrase=p["phrase"],
            text=p["text"],
            color=p.get("color", "#ffffff"),
            size=p.get("size", 240),
            duration=p.get("duration", 2.0),
        )
        for p in pkg["punches"]
    ]
    build_video(
        pkg["script"], shots, punches,
        gameplay_tag=gameplay_tag, out_path=out_path,
        music_vibe=pkg.get("music_vibe", "dark"),
    )


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", type=Path,
                    help="JSON package from script_generator.py "
                         "(if omitted, runs the hardcoded fast-furniture demo)")
    ap.add_argument("--out", type=Path, help="output mp4 path")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts_str = time.strftime("%Y%m%d-%H%M%S")
    out = args.out or (OUTPUT_DIR / f"stacked_{ts_str}.mp4")

    if args.package:
        pkg = json.loads(args.package.read_text())
        build_from_package(pkg, out)
        return 0

    # --- Hardcoded demo: fast furniture ---
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

    build_video(script, shots, punches, gameplay_tag="minecraft",
                out_path=out, music_vibe=os.environ.get("MUSIC_VIBE", "dark"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
