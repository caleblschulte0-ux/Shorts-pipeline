"""Caption stage — Whisper word-timestamp transcription + ASS authoring.

Lifted verbatim from make_short.py. write_ass exposes the caption style
(font size + vertical margin) as parameters defaulting to the main app's
exact values, so localize can re-author captions for a translated track
without altering the main app's look.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .constants import H, HALF_H, W


@dataclass
class Word:
    start: float
    end: float
    text: str


def transcribe(audio: Path) -> list[Word]:
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


def write_ass(
    words: list[Word],
    path: Path,
    *,
    w: int = W,
    h: int = H,
    font_size: int = 96,
    margin_v: int | None = None,
) -> None:
    # TikTok-style: large white, thick black outline, centered, near vertical middle.
    # MarginV is from the bottom in ASS, so put it just below the stack seam.
    if margin_v is None:
        margin_v = (h // 2) - 140
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,Impact,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,6,2,2,80,80,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for c in words:
        lines.append(
            f"Dialogue: 0,{_ass_time(c.start)},{_ass_time(c.end)},Pop,,0,0,0,,{_ass_escape(c.text.upper())}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
