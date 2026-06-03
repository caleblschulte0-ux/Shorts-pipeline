#!/usr/bin/env python3
"""Studio renderer — the data channel's own production renderer.

Unlike the base pipeline (gameplay-stacked) and the bare demo renderer, this
is purpose-built for data shorts and is meant to produce a finished,
publishable 9:16 video:

  * a calming, flowing ambient background (satisfying, not a game);
  * a consistent code-drawn mascot host (idle bob + blink), identical every
    render;
  * MULTIPLE graphs that build the story across the narration (progressive
    reveal, 3-4 states);
  * narration via the pipeline's Kokoro voice (the good one);
  * burned kinetic captions + colored punch stingers.

It is an *add-on* — it imports from data_learning and reuses the base
pipeline's Kokoro model files, but never modifies any base module.

Usage:
    python -m data_learning.studio_render --slug inflation-pain-points \
        --out output/inflation_studio.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO = PKG_DIR.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import charts, insights, mascot, packager      # noqa: E402
from data_learning.demo_render import (                            # noqa: E402
    _ass_time, _chunks, _dur, _hex_to_ass, _run, _sentences)
from data_learning.sources import get_source                      # noqa: E402
from data_learning.sources.offline import OfflineSource           # noqa: E402

W, H, FPS = 1080, 1920, 30
KOKORO_MODEL = REPO / "kokoro_models" / "kokoro-v1.0.onnx"
KOKORO_VOICES = REPO / "kokoro_models" / "voices-v1.0.bin"

# Layout (1080x1920). Card sits high; a clear band below it holds the punch
# stinger, then the mascot host, then captions at the bottom.
GRAPH_W, GRAPH_H = 1000, 920
GRAPH_X, GRAPH_Y = (W - GRAPH_W) // 2, 70
MASCOT_SIZE = 270
MASCOT_X, MASCOT_Y = (W - MASCOT_SIZE) // 2, 1150
PUNCH_Y = 1055


# --------------------------------------------------------------------------
# Insight + package (rebuilt from the niche config, like generate.py).
# --------------------------------------------------------------------------
def _load_spec(cfg: dict, slug: str) -> dict:
    for v in cfg.get("videos", []):
        if v.get("slug") == slug:
            return v
    raise KeyError(f"no video with slug {slug!r} in config")


def build_insight_and_package(spec: dict, cfg: dict):
    src = get_source(spec["source"])
    ds = src.fetch(spec["key"], spec.get("params"))
    baseline = None
    if spec.get("use_baseline"):
        baseline = (src.baseline(spec["key"], spec.get("params"))
                    if isinstance(src, OfflineSource)
                    else (spec.get("params") or {}).get("baseline"))
    ins = insights.build(ds, insight_type=spec.get("insight_type", "auto"),
                         baseline=baseline,
                         ascending=bool(spec.get("ascending", False)))
    if spec.get("topic"):
        ins.topic = spec["topic"]
    pkg = packager.build_package(
        ins, slug=spec["slug"], chart_path=None,
        hashtags=spec.get("hashtags", []),
        music_vibe=spec.get("music_vibe", cfg.get("music_vibe", "cinematic")),
        query_theme=spec.get("query_theme", cfg.get("query_theme", "data")))
    return ins, pkg


# --------------------------------------------------------------------------
# Kokoro narration (the pipeline voice).
# --------------------------------------------------------------------------
def _normalize(text: str) -> str:
    return text.replace("$", " dollars ").replace("%", " percent ")


def synth_narration(sentences: list[str], workdir: Path, voice: str
                    ) -> tuple[Path, list[tuple[float, float]]]:
    import soundfile as sf
    from kokoro_onnx import Kokoro

    k = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    wavs, windows, t = [], [], 0.0
    for i, sent in enumerate(sentences):
        samples, sr = k.create(_normalize(sent), voice=voice, speed=1.05,
                               lang="en-us")
        w = workdir / f"s{i}.wav"
        sf.write(str(w), samples, sr)
        # Small trailing pause between sentences for pacing.
        d = _dur(w) + 0.15
        windows.append((t, t + d))
        t += d
        wavs.append((w, 0.15))
    listf = workdir / "list.txt"
    lines = []
    for w, pause in wavs:
        lines.append(f"file '{w}'")
    listf.write_text("\n".join(lines) + "\n")
    raw = workdir / "raw.wav"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
          "-af", "apad=pad_dur=0.15", "-c:a", "pcm_s16le", str(raw)])
    narration = workdir / "narration.wav"
    _run(["ffmpeg", "-y", "-i", str(raw),
          "-af", "loudnorm=I=-16:LRA=11:TP=-1.5", str(narration)])
    return narration, windows


# --------------------------------------------------------------------------
# Map sentences -> graph states (progressive story).
# --------------------------------------------------------------------------
def assign_state_windows(windows, n_states: int):
    """Return [(state_index, start, end)] — distinct graph states across the
    narration, ending on the final (full) state."""
    n_sent = len(windows)
    last = n_states - 1
    # Advance the reveal so the FULL chart lands on the last *proof* sentence
    # (the one that introduces the final number) and holds through the
    # takeaway — otherwise a spoken final value can precede its bar/point.
    if n_sent <= 2:
        per_sentence = [min(i, last) for i in range(n_sent)]
    else:
        denom = n_sent - 2  # index of the last proof sentence
        per_sentence = [min(last, max(0, round(i * last / denom)))
                        for i in range(n_sent)]
    # Collapse consecutive identical states into windows.
    out = []
    i = 0
    while i < n_sent:
        s = per_sentence[i]
        start = windows[i][0]
        j = i
        while j + 1 < n_sent and per_sentence[j + 1] == s:
            j += 1
        end = windows[j][1]
        out.append((s, start, end))
        i = j + 1
    return out


# --------------------------------------------------------------------------
# ASS captions + punches.
# --------------------------------------------------------------------------
def build_ass(sentences, windows, punches, out: Path) -> None:
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,62,&HFFFFFF&,&H000000&,&H66000000&,1,1,4,1,2,80,80,250,1
Style: Punch,DejaVu Sans,150,&HFFFFFF&,&H000000&,&H000000&,1,1,6,3,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for sent, (s0, s1) in zip(sentences, windows):
        chunks = _chunks(sent, 3)
        if not chunks:
            continue
        step = (s1 - s0) / len(chunks)
        for j, ch in enumerate(chunks):
            cs, ce = s0 + j * step, s0 + (j + 1) * step
            lines.append(f"Dialogue: 0,{_ass_time(cs)},{_ass_time(ce)},Cap,,0,0,0,,"
                         f"{ch.strip()}")
    for p in punches:
        phrase = p.get("phrase", "").lower()
        win = next(((a, b) for sent, (a, b) in zip(sentences, windows)
                    if phrase in sent.lower()), None)
        if not win:
            continue
        dur = float(p.get("duration", 2.0))
        ps = win[0] + max(0.0, (win[1] - win[0]) - dur) * 0.45
        pe = min(win[1], ps + dur)
        color = _hex_to_ass(p.get("color", "#ffffff"))
        # Anchor punches just below the graph card (between chart and mascot)
        # so they never cover the on-screen source citation.
        styled = ("{\\fad(150,150)\\pos(540," + str(PUNCH_Y) + ")\\fs104\\c"
                  + color + "}" + p.get("text", ""))
        lines.append(f"Dialogue: 1,{_ass_time(ps)},{_ass_time(pe)},Punch,,0,0,0,,"
                     f"{styled}")
    out.write_text(head + "\n".join(lines) + "\n")


# --------------------------------------------------------------------------
# Composite.
# --------------------------------------------------------------------------
def _ambient(total: float) -> str:
    return (
        f"gradients=s={W}x{H}:c0=0x0B1020:c1=0x14365e:c2=0x1f6f6a:c3=0x0e1230:"
        f"x0=160:y0=220:x1=920:y1=1680:nb_colors=4:speed=0.010:"
        f"duration={total:.2f}:rate={FPS}")


def render(slug: str, out_path: Path, voice: str = "am_adam") -> Path:
    cfg = json.loads((PKG_DIR / "niche.config.json").read_text())
    spec = _load_spec(cfg, slug)
    insight, pkg = build_insight_and_package(spec, cfg)
    sentences = _sentences(pkg["script"])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        # 1. Narration (Kokoro) + windows.
        narration, windows = synth_narration(sentences, work, voice)
        total = _dur(narration) + 0.3

        # 2. Graph series + mascot + captions.
        states = charts.render_series(insight, work / "charts", slug)
        if not states:
            raise RuntimeError("chart series empty (matplotlib missing?)")
        state_windows = assign_state_windows(windows, len(states))
        mascot_mov = mascot.build_mascot_loop(work / "mascot.mov",
                                              size=MASCOT_SIZE)
        ass = work / "cap.ass"
        build_ass(sentences, windows, pkg.get("punches", []), ass)
        ass_esc = str(ass).replace("\\", "/").replace(":", "\\:")

        # 3. Build ffmpeg inputs + filtergraph.
        inputs = ["-f", "lavfi", "-i", _ambient(total)]            # 0: ambient
        state_input_idx = {}
        idx = 1
        for s, _, _ in state_windows:
            if s not in state_input_idx:
                inputs += ["-loop", "1", "-i", str(states[s])]      # graph PNG
                state_input_idx[s] = idx
                idx += 1
        inputs += ["-stream_loop", "-1", "-i", str(mascot_mov)]    # mascot
        mascot_idx = idx
        idx += 1
        inputs += ["-i", str(narration)]                           # audio
        audio_idx = idx

        fc = [f"[0:v]format=yuv420p,scale={W}:{H}[bg]"]
        prev = "bg"
        # Overlay each graph state during its window with an alpha fade.
        for n, (s, start, end) in enumerate(state_windows):
            gi = state_input_idx[s]
            fdur = 0.35
            lbl = f"g{n}"
            fc.append(
                f"[{gi}:v]scale={GRAPH_W}:{GRAPH_H}:force_original_aspect_ratio=decrease,"
                f"format=rgba,"
                f"fade=t=in:st={start:.2f}:d={fdur}:alpha=1,"
                f"fade=t=out:st={max(start, end - fdur):.2f}:d={fdur}:alpha=1[{lbl}]")
            out_lbl = f"b{n}"
            fc.append(
                f"[{prev}][{lbl}]overlay=x={GRAPH_X}:y={GRAPH_Y}:"
                f"enable='between(t,{start:.2f},{end:.2f})'[{out_lbl}]")
            prev = out_lbl
        # Mascot (always on), then captions.
        fc.append(f"[{mascot_idx}:v]format=rgba,scale={MASCOT_SIZE}:{MASCOT_SIZE}[masc]")
        fc.append(f"[{prev}][masc]overlay=x={MASCOT_X}:y={MASCOT_Y}:shortest=0[withm]")
        fc.append(f"[withm]ass='{ass_esc}'[v]")

        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
               "-filter_complex", ";".join(fc),
               "-map", "[v]", "-map", f"{audio_idx}:a",
               "-t", f"{total:.2f}", "-r", str(FPS),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
               "-crf", "20", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(out_path)]
        _run(cmd)

    print(f"[studio] {slug}: {len(state_windows)} graph states, "
          f"{len(sentences)} beats, {total:.1f}s -> {out_path}")
    print(f"[studio] title: {pkg['title']}")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--voice", default="am_adam",
                    help="Kokoro voice id (default am_adam, the pipeline voice)")
    args = ap.parse_args()
    render(args.slug, args.out, voice=args.voice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
