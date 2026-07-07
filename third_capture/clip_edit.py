#!/usr/bin/env python3
"""Clip pillar — Twitch/Kick clip -> edited 9:16 Short.

Pipeline per clip:
  1. discover(channel) — yt-dlp reads the channel's top clips of the last
     24h (no API key needed; Twitch Helix can slot in later).
  2. download(url) — grabs the source mp4 + metadata.
  3. edit(...) — reframe to 1080x1920 (blurred fill + centered clip),
     whisper word-timed captions in 1-3 word pops, streamer credit
     banner, optional hook card over the first seconds, loudness
     normalize. One ffmpeg pass for the visual chain.

Credit doctrine (THIRD_BRAIN.md): streamer name burned on screen the
whole video + source link in the description. Only channels on the
allowlist in the package are used.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

CANVAS_W, CANVAS_H = 1080, 1920
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True,
                                   stderr=subprocess.STDOUT)


# ---------- 1. discover ----------

def discover(channel: str, *, top: int = 8, range_: str = "24hr") -> list[dict]:
    """Top clips for a channel in the window, best-first. No API key."""
    url = f"https://www.twitch.tv/{channel}/clips?filter=clips&range={range_}"
    out = _run(["yt-dlp", "--flat-playlist", "--playlist-items", f"1-{top}",
                "--print", "%(url)s\t%(view_count)s\t%(title)s", url])
    clips = []
    for line in out.strip().splitlines():
        try:
            u, views, title = line.split("\t", 2)
            clips.append({"url": u, "views": int(views or 0),
                          "title": title, "channel": channel})
        except ValueError:
            continue
    return clips


# ---------- 2. download ----------

def download(url: str, work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    raw = work / "raw_clip.mp4"
    meta = work / "raw_clip.meta"
    _run(["yt-dlp", "-q", "--force-overwrites",
          "-o", str(work / "raw_clip.%(ext)s"),
          "--print-to-file",
          "%(id)s\t%(title)s\t%(uploader)s\t%(view_count)s\t%(duration)s",
          str(meta), url])
    cid, title, clipper, views, dur = \
        meta.read_text().strip().split("\t")
    return {"path": raw, "clip_id": cid, "title": title,
            "clipper": clipper, "views": int(float(views or 0)),
            "duration": float(dur), "url": url}


# ---------- 3. captions ----------

def transcribe_words(video: Path, model_name: str = "base") -> list[dict]:
    import whisper
    model = whisper.load_model(model_name)
    res = model.transcribe(str(video), word_timestamps=True, fp16=False)
    words = []
    for seg in res["segments"]:
        for w in seg.get("words", []):
            token = w["word"].strip()
            if token:
                words.append({"w": token, "s": w["start"], "e": w["end"]})
    return words


_ASS_HEADER = """[Script Info]
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Pop,DejaVu Sans,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,7,0,5,60,60,760,1
Style: Credit,DejaVu Sans,44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,2,40,40,64,1

[Events]
Format: Layer, Start, End, Style, Text
"""


def _ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _clean(token: str) -> str:
    return re.sub(r"[{}\\]", "", token).upper()


def build_ass(words: list[dict], credit: str, dur: float, out: Path,
              max_group: int = 3) -> Path:
    """1-3 word caption pops, centered mid-low, plus a permanent credit
    line. Groups split on gaps > 0.6s or punctuation."""
    lines = [_ASS_HEADER]
    group: list[dict] = []

    def flush():
        if not group:
            return
        s, e = group[0]["s"], max(group[-1]["e"], group[0]["s"] + 0.35)
        text = " ".join(_clean(g["w"]) for g in group)
        lines.append(f"Dialogue: 1,{_ts(s)},{_ts(e)},Pop,{text}\n")
        group.clear()

    for w in words:
        if group and (w["s"] - group[-1]["e"] > 0.6
                      or len(group) >= max_group
                      or group[-1]["w"][-1:] in ".?!,"):
            flush()
        group.append(w)
    flush()
    lines.append(
        f"Dialogue: 0,{_ts(0)},{_ts(dur)},Credit,"
        f"twitch.tv/{credit}\n")
    out.write_text("".join(lines))
    return out


# ---------- 4. edit ----------

def edit(raw: Path, out_path: Path, *, credit: str, hook: str = "",
         start: float = 0.0, end: float = 0.0,
         whisper_model: str = "base") -> dict:
    """Compose the 9:16 edit. Returns the edit ledger."""
    probe = json.loads(_run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(raw)]))
    src_dur = float(probe["format"]["duration"])
    t0 = max(0.0, start)
    t1 = min(src_dur, end) if end else src_dur
    dur = t1 - t0

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        cut = tmp / "cut.mp4"
        if t0 > 0.01 or t1 < src_dur - 0.01:
            _run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t0}",
                  "-to", f"{t1}", "-i", str(raw), "-c:v", "libx264",
                  "-preset", "veryfast", "-crf", "18", "-c:a", "aac",
                  str(cut)])
        else:
            cut = raw

        words = transcribe_words(cut, whisper_model)
        ass = build_ass(words, credit, dur, tmp / "caps.ass")

        # visual chain: blurred fill + centered source + captions
        vf = (
            "[0:v]split=2[bg][fg];"
            f"[bg]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio="
            "increase,crop=1080:1920,gblur=sigma=24,"
            "eq=brightness=-0.12:saturation=1.15[bgd];"
            "[fg]scale=1080:-2[fgs];"
            "[bgd][fgs]overlay=(W-w)/2:(H-h)/2[base];"
            f"[base]ass={ass}[capped]"
        )
        if hook:
            safe = hook.replace(":", r"\:").replace("'", r"\\\'")
            chain = (vf + ";[capped]"
                     f"drawtext=fontfile={FONT_BOLD}:text='{safe}'"
                     ":fontsize=64:fontcolor=white:box=1:boxcolor=black@0.72"
                     ":boxborderw=26:x=(w-text_w)/2:y=230"
                     ":enable='between(t,0,3.0)'[vout]")
        else:
            chain = vf.replace("[capped]", "[vout]")

        _run(["ffmpeg", "-y", "-v", "error", "-i", str(cut),
              "-filter_complex", chain, "-map", "[vout]", "-map", "0:a",
              "-af", "loudnorm=I=-14:TP=-1.5",
              "-c:v", "libx264", "-preset", "medium", "-crf", "19",
              "-pix_fmt", "yuv420p", "-r", "30",
              "-c:a", "aac", "-b:a", "160k", str(out_path)])

    return {"kind": "twitch_clip", "credit": credit,
            "cut": [t0, t1], "duration_s": round(dur, 2),
            "caption_words": len(words), "hook": hook}
