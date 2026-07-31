"""Word-timed karaoke captions — shared ASS builder + burn helper.

Takes whisper-style word timestamps (any channel already produces these via
openai-whisper) and emits an .ass subtitle track where the active word
highlights as it is spoken — the retention-standard Shorts caption look.
Rendering is ffmpeg's subtitles filter; no new dependencies.

This module never imports whisper. It consumes plain data:

    words = [{"word": "we", "start": 0.00, "end": 0.18}, ...]
    # from whisper: transcribe(..., word_timestamps=True) then
    # words = [w for seg in result["segments"] for w in seg["words"]]

    from shared import captions
    ass = captions.build_ass(words, play_res=(1080, 1920))
    captions.write_ass(ass, "subs.ass")
    captions.burn("in.mp4", "subs.ass", "out.mp4")   # -> out path or None

Styling defaults match the pipeline's vertical format (bottom-center block,
heavy outline, highlight color pop). All overridable per call — channels own
their look; this owns the timing math.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Karaoke highlight style. ASS colors are &HAABBGGRR (alpha first).
DEFAULT_STYLE = {
    "fontname": "DejaVu Sans",
    "fontsize": 88,
    "bold": -1,                       # ASS: -1 = true
    "primary": "&H00FFFFFF",         # spoken-word base: white
    "highlight": "&H0000D7FF",       # active word: amber (BGR: FFD700)
    "outline_color": "&H00000000",
    "outline": 7,
    "shadow": 0,
    "margin_v": 260,                  # pixels up from the bottom edge
    "align": 2,                       # bottom-center
}


def group_words(words, *, max_words: int = 4, max_gap: float = 0.6,
                max_span: float = 3.5) -> list[list[dict]]:
    """Split a flat word stream into caption lines: break on long pauses,
    line length, or total on-screen span. Pure function, easy to test."""
    lines: list[list[dict]] = []
    cur: list[dict] = []
    for w in words:
        if not str(w.get("word", "")).strip():
            continue
        if cur:
            gap = w["start"] - cur[-1]["end"]
            span = w["end"] - cur[0]["start"]
            if len(cur) >= max_words or gap > max_gap or span > max_span:
                lines.append(cur)
                cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return lines


def _ts(t: float) -> str:
    """ASS timestamp h:mm:ss.cc"""
    t = max(0.0, float(t))
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")
            .replace("\n", " ").strip())


def build_ass(words, *, play_res: tuple[int, int] = (1080, 1920),
              style: dict | None = None, max_words: int = 4,
              max_gap: float = 0.6, uppercase: bool = True) -> str:
    """Build a karaoke .ass document from word timestamps. Each line's words
    carry \\k durations so the active word flips to the highlight color in
    sync with speech."""
    st = dict(DEFAULT_STYLE, **(style or {}))
    w, h = play_res
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Karaoke,{st['fontname']},{st['fontsize']},{st['highlight']},{st['primary']},{st['outline_color']},&H96000000,{st['bold']},0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},{st['align']},60,60,{st['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for line in group_words(words, max_words=max_words, max_gap=max_gap):
        start, end = line[0]["start"], line[-1]["end"]
        parts = []
        for i, wd in enumerate(line):
            # \k units are centiseconds; measure from word start to the
            # NEXT word's start so pauses inside a line stay highlighted
            # on the word being finished rather than flickering.
            until = line[i + 1]["start"] if i + 1 < len(line) else wd["end"]
            k = max(1, int(round((until - wd["start"]) * 100)))
            token = _esc(str(wd["word"]))
            if uppercase:
                token = token.upper()
            parts.append(f"{{\\k{k}}}{token}")
        events.append(
            f"Dialogue: 0,{_ts(start)},{_ts(end)},Karaoke,,0,0,0,,"
            + " ".join(parts))
    return head + "\n".join(events) + "\n"


def write_ass(ass_text: str, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ass_text, encoding="utf-8")
    return path


def _subtitles_filter_path(p: str) -> str:
    """Escape a filesystem path for ffmpeg's subtitles= filter argument."""
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def burn(video_in, ass_path, out_path, *, crf: int = 20,
         timeout: int = 600) -> Path | None:
    """Burn the .ass onto the video. Returns the output path or None —
    never raises (a failed burn falls back to the unsubtitled render)."""
    try:
        if not shutil.which("ffmpeg"):
            return None
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        vf = f"subtitles='{_subtitles_filter_path(str(ass_path))}'"
        run = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(video_in), "-vf", vf,
             "-c:v", "libx264", "-crf", str(crf), "-preset", "veryfast",
             "-c:a", "copy", str(out_path)],
            capture_output=True, text=True, timeout=timeout)
        if run.returncode == 0 and out_path.exists() and out_path.stat().st_size:
            return out_path
        return None
    except Exception:
        return None
