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


#: Sentence-ish characters a caption chunk may end on.
BREAK_CHARS = ".!?,"


def word_text(w) -> str:
    """The text of a word, whichever shape the caller's whisper wrapper uses.

    The repo has two: plain dicts (`{"word": ..., "start": ..., "end": ...}`)
    and the `Word` objects in `make_explainer_stacked` (`.text/.start/.end`).
    Supporting both is what lets every renderer share ONE grouper instead of
    keeping five.
    """
    if isinstance(w, dict):
        for k in ("word", "text", "w"):
            if k in w:
                return str(w[k])
        return ""
    return str(getattr(w, "text", getattr(w, "word", "")))


def word_start(w) -> float:
    if isinstance(w, dict):
        return float(w["start"] if "start" in w else w["s"])
    return float(w.start)


def word_end(w) -> float:
    if isinstance(w, dict):
        return float(w["end"] if "end" in w else w["e"])
    return float(w.end)


def group_words(words, *, max_words: int = 4, max_gap: float = 0.6,
                max_span: float = 3.5, max_chars: int | None = None,
                break_on_punct: bool = False,
                break_chars: str = BREAK_CHARS,
                drop_empty: bool = True,
                strip_join: bool = True,
                blank_breaks: bool = False) -> list[list]:
    """Split a flat word stream into caption lines. Pure function.

    This is THE caption grouper for the whole pipeline. Five renderers had
    grown their own near-identical copy (`_chunk_words`, `_chunks`, …) with
    slightly different break rules, which is why the rule set here is a
    superset rather than an opinion — a caller reproduces its old behaviour
    exactly by setting the limits it used and disabling the rest:

        reddit_story  max_words=3, max_chars=22, break_on_punct=True,
                      max_gap=inf, max_span=inf

    Break rules, all optional:
      * `max_words`      — words per line
      * `max_chars`      — rendered length of the joined line
      * `max_gap`        — silence between two words (a pause is a line break)
      * `max_span`       — total time a line may stay on screen
      * `break_on_punct` — end a line after a char in `break_chars`
      * `break_chars`    — which trailing chars count (explainer also breaks
                           on `:` and `;`, reddit_story does not)
      * `drop_empty`     — skip blank words. `make_explainer_stacked` keeps
                           them, because they land in its joined line text.
      * `strip_join`     — whether `max_chars` measures stripped word text

    Accepts dicts or objects (see `word_text`).
    """
    lines: list[list] = []
    cur: list = []
    for w in words:
        raw = word_text(w)
        text = raw.strip()
        if not text and drop_empty:
            continue
        if cur:
            gap = word_start(w) - word_end(cur[-1])
            span = word_end(w) - word_start(cur[0])
            if len(cur) >= max_words or gap > max_gap or span > max_span:
                lines.append(cur)
                cur = []
        cur.append(w)
        # Post-append rules (length of the line INCLUDING this word, and
        # punctuation on this word) — these close the current line rather
        # than pushing the word to the next one.
        if max_chars is not None:
            joined = " ".join((word_text(x).strip() if strip_join
                               else word_text(x)) for x in cur)
            if len(joined) >= max_chars:
                lines.append(cur)
                cur = []
                continue
        # `text` is empty only when drop_empty=False let a blank word
        # through. A blank word is not a sentence boundary — except in
        # `third_capture/clip_edit.py`, whose test was `w[-1:] in ".?!,"`,
        # and in Python `"" in ".?!,"` is True, so a blank word DID break a
        # line there. That is a latent bug, not a design choice, but this
        # consolidation is a refactor: it reproduces the behaviour exactly
        # and `blank_breaks` names it so it can be fixed deliberately later.
        if break_on_punct and not text and blank_breaks:
            lines.append(cur)
            cur = []
            continue
        if break_on_punct and text and text[-1] in break_chars:
            lines.append(cur)
            cur = []
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
        start, end = word_start(line[0]), word_end(line[-1])
        parts = []
        for i, wd in enumerate(line):
            # \k units are centiseconds; measure from word start to the
            # NEXT word's start so pauses inside a line stay highlighted
            # on the word being finished rather than flickering.
            until = (word_start(line[i + 1]) if i + 1 < len(line)
                     else word_end(wd))
            k = max(1, int(round((until - word_start(wd)) * 100)))
            token = _esc(word_text(wd))
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
