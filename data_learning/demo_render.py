#!/usr/bin/env python3
"""Self-contained DEMO renderer for the data_learning add-on.

This is NOT the production renderer — the base pipeline's
``make_explainer_stacked`` is. It exists only so the add-on can produce a
watchable example MP4 in environments that lack the production stack
(Pexels/Pixabay keys, gameplay clips, Whisper, Kokoro). It faithfully shows
the *format*: data chart on the top half, an animated placeholder on the
bottom half, offline narration (espeak-ng), and burned kinetic captions +
colored punch stingers driven straight from the package JSON.

Dependencies: ffmpeg + espeak-ng (both apt-installable, fully offline).

Usage:
    python -m data_learning.demo_render \
        --package data_learning/review/<date>/01_inflation-pain-points.json \
        --out output/inflation_demo.mp4
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO = PKG_DIR.parent

W, HALF_H, H, FPS = 1080, 960, 1920, 30


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.PIPE)


def _dur(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def _sentences(script: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", script.strip())
    return [p.strip() for p in parts if p.strip()]


def _chunks(sentence: str, n: int = 3) -> list[str]:
    words = sentence.split()
    return [" ".join(words[i:i + n]) for i in range(0, len(words), n)]


def _hex_to_ass(hex_color: str) -> str:
    """#RRGGBB -> ASS &HBBGGRR&."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "&HFFFFFF&"
    rr, gg, bb = h[0:2], h[2:4], h[4:6]
    return f"&H{bb}{gg}{rr}&".upper()


def _ass_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def synth_narration(sentences: list[str], workdir: Path) -> tuple[Path, list[tuple[float, float]]]:
    """espeak-ng each sentence, concat to one wav, return (wav, windows)
    where windows[i] = (start, end) of sentence i."""
    wavs: list[Path] = []
    windows: list[tuple[float, float]] = []
    t = 0.0
    for i, sent in enumerate(sentences):
        w = workdir / f"s{i}.wav"
        _run(["espeak-ng", "-v", "en-us", "-s", "150", "-g", "6",
              sent, "-w", str(w)])
        d = _dur(w)
        windows.append((t, t + d))
        t += d
        wavs.append(w)
    # Concatenate.
    listf = workdir / "list.txt"
    listf.write_text("".join(f"file '{w}'\n" for w in wavs))
    narration = workdir / "narration.wav"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
          "-c", "copy", str(narration)])
    return narration, windows


def build_ass(sentences, windows, punches, script, out: Path) -> None:
    """Write an ASS with kinetic 3-word captions near the stack seam and
    big colored punch stingers, timed to the sentences that contain them."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Impact,72,&HFFFFFF&,&H000000&,&H000000&,1,1,5,2,2,40,40,420,1
Style: Punch,Impact,150,&HFFFFFF&,&H000000&,&H000000&,1,1,6,3,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: list[str] = []

    # Kinetic captions: split each sentence into 3-word chunks evenly across
    # its measured audio window.
    for sent, (s0, s1) in zip(sentences, windows):
        chunks = _chunks(sent, 3)
        if not chunks:
            continue
        step = (s1 - s0) / len(chunks)
        for j, ch in enumerate(chunks):
            cs = s0 + j * step
            ce = cs + step
            txt = ch.replace("\n", " ").strip()
            lines.append(f"Dialogue: 0,{_ass_time(cs)},{_ass_time(ce)},Cap,,0,0,0,,{txt}")

    # Punch stingers: find the sentence window containing each punch phrase.
    for p in punches:
        phrase = p.get("phrase", "").lower()
        text = p.get("text", "")
        color = _hex_to_ass(p.get("color", "#ffffff"))
        dur = float(p.get("duration", 2.0))
        win = None
        for sent, (s0, s1) in zip(sentences, windows):
            if phrase in sent.lower():
                win = (s0, s1)
                break
        if win is None:
            continue
        ps = win[0] + max(0.0, (win[1] - win[0]) - dur) * 0.4
        pe = min(win[1], ps + dur)
        styled = "{\\c" + color + "}" + text
        lines.append(f"Dialogue: 1,{_ass_time(ps)},{_ass_time(pe)},Punch,,0,0,0,,{styled}")

    out.write_text(head + "\n".join(lines) + "\n")


def resolve_chart(pkg: dict) -> Path | None:
    for s in pkg.get("shots", []):
        img = s.get("image_url") or s.get("image")
        if img:
            p = (REPO / img) if not Path(img).is_absolute() else Path(img)
            if p.exists():
                return p
    return None


def render(pkg: dict, out_path: Path) -> Path:
    sentences = _sentences(pkg["script"])
    chart = resolve_chart(pkg)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        narration, windows = synth_narration(sentences, work)
        total = _dur(narration)

        ass = work / "captions.ass"
        build_ass(sentences, windows, pkg.get("punches", []),
                  pkg["script"], ass)
        # ffmpeg needs the ass path escaped for the filtergraph.
        ass_esc = str(ass).replace("\\", "/").replace(":", "\\:")

        chart_note = chart.name if chart else "(dark card — no chart)"
        _run(_assemble(chart, narration, ass_esc, total, out_path))
    print(f"[demo_render] chart: {chart_note}")
    print(f"[demo_render] duration: {total:.1f}s -> {out_path}")
    return out_path


def _assemble(chart, narration, ass_esc, total, out_path) -> list[str]:
    """Build the ffmpeg command with stable input indices."""
    inputs = ["-f", "lavfi", "-i",
              f"mandelbrot=size={W}x{HALF_H}:rate={FPS}"]      # 0: bottom bg
    if chart:
        inputs += ["-loop", "1", "-i", str(chart)]             # 1: chart
        audio_idx = 2
        top = (f"[1:v]scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
               f"crop={W}:{HALF_H},setsar=1[top];")
    else:
        audio_idx = 1
        top = f"color=c=0x0B1020:s={W}x{HALF_H}:r={FPS}[top];"
    inputs += ["-i", str(narration)]                            # last: audio

    bottom = (f"[0:v]drawtext=text='GAMEPLAY PLACEHOLDER':fontcolor=white@0.45:"
              f"fontsize=34:x=(w-text_w)/2:y=h-70,setsar=1[bottom];")
    fc = (f"{top}{bottom}"
          f"[top][bottom]vstack=inputs=2[stacked];"
          f"[stacked]ass='{ass_esc}'[v]")
    return [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", fc,
        "-map", "[v]", "-map", f"{audio_idx}:a",
        "-t", f"{total:.2f}", "-r", str(FPS),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(out_path),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    pkg = json.loads(args.package.read_text())
    render(pkg, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
