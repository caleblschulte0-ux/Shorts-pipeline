#!/usr/bin/env python3
"""Studio renderer — the data channel's own production renderer.

Renders a STORY: a punchy hook, then several *distinct* charts (each from its
own data pull) that build a narrative, then a sources card. Over the top: a
calming flowing-bokeh background, a humanoid mascot host that points at the
data, the pipeline's Kokoro voice, and burned kinetic captions + punch
stingers.

It is an add-on — it imports from data_learning and reuses the base
pipeline's Kokoro model files, but never modifies any base module.

Usage:
    python -m data_learning.studio_render --slug us-economy-squeeze \
        --out output/economy_story.mp4
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tempfile
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO = PKG_DIR.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import ambient, mascot, story                  # noqa: E402
from data_learning.demo_render import (                            # noqa: E402
    _ass_time, _chunks, _dur, _hex_to_ass, _run)

W, H, FPS = 1080, 1920, 30
KOKORO_MODEL = REPO / "kokoro_models" / "kokoro-v1.0.onnx"
KOKORO_VOICES = REPO / "kokoro_models" / "voices-v1.0.bin"

# Layout (1080x1920): chart up top, mascot roams the band below it (pointing
# up at the chart), punch in the open band, captions at the bottom — the
# lower third stays mostly ambient so there's something calming to rest on.
# A left GUTTER is reserved for the mascot so it can stand right beside the
# label words and point at them without covering the chart. The chart PNG
# (1000x920) is scaled by CHART_SCALE into the area to the right of the
# gutter; datum pixels map to screen via that scale.
CHART_X, CHART_Y = 196, 70
CHART_SCALE = 0.86
CHART_W, CHART_H = int(1000 * CHART_SCALE), int(920 * CHART_SCALE)   # 860x791
MASCOT_SIZE = 184
MASCOT_ANGLE = 8                 # points RIGHT (slightly up) at the labels
GUTTER_X = 12                    # mascot's resting x in the gutter
PUNCH_X, PUNCH_Y = 540, 1380
CAP_MARGINV = 170

# Voice: a warm *male* "dude monster" Kokoro voice, pitched DOWN slightly
# (never up) so it reads as the monster, not a chirpy narrator.
VOICE_PITCH = 0.95


# --------------------------------------------------------------------------
# Kokoro narration (the pipeline voice).
# --------------------------------------------------------------------------
_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
         "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
         "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety"]


def _card(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")
    if n < 1000:
        r = n % 100
        return _ONES[n // 100] + " hundred" + (" " + _card(r) if r else "")
    r = n % 1000
    return _card(n // 1000) + " thousand" + (" " + _card(r) if r else "")


def _year(n: int) -> str:
    if 2000 <= n <= 2009:
        return "two thousand" + (" " + _ONES[n % 10] if n % 10 else "")
    hi, lo = n // 100, n % 100
    if lo == 0:
        return _card(hi) + " hundred"
    if lo < 10:
        return _card(hi) + " oh " + _ONES[lo]
    return _card(hi) + " " + _card(lo)


def _spell_numbers(text: str) -> str:
    """Spell every number out in words so the TTS pronounces it correctly
    (e.g. '5.3' -> 'five point three', '2023' -> 'twenty twenty three').
    Applied to the spoken audio ONLY — captions keep the digits."""
    def _dec(m):
        whole, frac = m.group(0).split(".")
        return (_card(int(whole)) + " point "
                + " ".join(_ONES[int(d)] for d in frac))
    text = re.sub(r"\d+\.\d+", _dec, text)

    def _int(m):
        n = int(m.group(0))
        return _year(n) if 1900 <= n <= 2099 else _card(n)
    return re.sub(r"\d+", _int, text)


def _tts_text(text: str) -> str:
    text = text.replace("$", " dollars ").replace("%", " percent ")
    return _spell_numbers(text)


def synth_narration(sentences, workdir: Path, voice: str):
    import soundfile as sf
    from kokoro_onnx import Kokoro

    k = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    wavs, windows, t = [], [], 0.0
    for i, sent in enumerate(sentences):
        samples, sr = k.create(_tts_text(sent), voice=voice, speed=1.04,
                               lang="en-us")
        w = workdir / f"s{i}.wav"
        sf.write(str(w), samples, sr)
        d = _dur(w) + 0.18           # small breath between lines
        windows.append((t, t + d))
        t += d
        wavs.append(w)
    listf = workdir / "list.txt"
    listf.write_text("\n".join(f"file '{w}'" for w in wavs) + "\n")
    raw = workdir / "raw.wav"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(listf), "-af", "apad=pad_dur=0.18", "-c:a", "pcm_s16le",
          str(raw)])
    narration = workdir / "narration.wav"
    # Pitch the voice up slightly (asetrate shifts pitch+tempo; atempo undoes
    # the tempo) so it sounds like the cute mascot, then loudness-normalize.
    sr0 = 24000
    af = (f"asetrate={int(sr0 * VOICE_PITCH)},aresample={sr0},"
          f"atempo={1 / VOICE_PITCH:.4f},loudnorm=I=-16:LRA=11:TP=-1.5")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
          "-af", af, str(narration)])
    return narration, windows


# --------------------------------------------------------------------------
# ASS: hook card, kinetic captions, punches, sources card.
# --------------------------------------------------------------------------
def _wrap(text: str, width: int = 22) -> str:
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return "\\N".join(out)


def build_story_ass(st: story.Story, windows, out: Path) -> None:
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,60,&HFFFFFF&,&H000000&,&H66000000&,1,1,4,1,2,90,90,{CAP_MARGINV},1
Style: Hook,DejaVu Sans,96,&H4FD1F5&,&H000000&,&H000000&,1,1,6,3,8,70,70,360,1
Style: Punch,DejaVu Sans,150,&HFFFFFF&,&H000000&,&H000000&,1,1,6,3,5,40,40,0,1
Style: Src,DejaVu Sans,40,&HA5B4C7&,&H000000&,&H000000&,0,1,3,1,5,120,120,0,1
Style: Chip,DejaVu Sans,38,&HFFFFFF&,&H6A5C7C&,&H000000&,1,3,0,0,8,60,60,26,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    sentences = st.sentences()

    def kinetic(sent, s0, s1):
        chunks = _chunks(sent, 3)
        if not chunks:
            return
        step = (s1 - s0) / len(chunks)
        for j, ch in enumerate(chunks):
            cs, ce = s0 + j * step, s0 + (j + 1) * step
            lines.append(f"Dialogue: 0,{_ass_time(cs)},{_ass_time(ce)},Cap,,0,0,0,,"
                         f"{ch.strip()}")

    # 0: HOOK — big kinetic text up top (mascot points up at it).
    h0, h1 = windows[0]
    hook_txt = "{\\fad(200,150)}" + _wrap(st.hook, 20)
    lines.append(f"Dialogue: 0,{_ass_time(h0)},{_ass_time(h1)},Hook,,0,0,0,,{hook_txt}")

    # 1..N: each segment — bottom kinetic captions + its punches.
    for i, seg in enumerate(st.segments):
        s0, s1 = windows[1 + i]
        # Step chip up top labels this chart's role in the argument.
        if seg.role:
            chip = "{\\fad(150,150)} " + seg.role + " "
            lines.append(f"Dialogue: 2,{_ass_time(s0)},{_ass_time(s1)},Chip,,0,0,0,,"
                         f"{chip}")
        kinetic(seg.sentence, s0, s1)
        # Stagger multiple punches across the segment so they never stack.
        np = len(seg.punches)
        for j, p in enumerate(seg.punches):
            slot0 = s0 + (s1 - s0) * (j / np)
            slot1 = s0 + (s1 - s0) * ((j + 1) / np)
            dur = min(float(p.get("duration", 1.8)), slot1 - slot0)
            ps = slot0 + (slot1 - slot0 - dur) * 0.5
            pe = ps + dur
            color = _hex_to_ass(p.get("color", "#ffffff"))
            styled = ("{\\fad(120,120)\\pos(" + str(PUNCH_X) + "," + str(PUNCH_Y)
                      + ")\\fs104\\c" + color + "}" + p.get("text", ""))
            lines.append(f"Dialogue: 1,{_ass_time(ps)},{_ass_time(pe)},Punch,,0,0,0,,"
                         f"{styled}")

    # Last: CLOSING — bottom caption + a sources card up top.
    c0, c1 = windows[-1]
    kinetic(sentences[-1], c0, c1)
    src_lines = "\\N".join(["{\\b1}Sources{\\b0}"] + st.sources)
    src_txt = "{\\fad(200,0)\\pos(540,520)}" + src_lines
    lines.append(f"Dialogue: 0,{_ass_time(c0)},{_ass_time(c1)},Src,,0,0,0,,{src_txt}")

    out.write_text(head + "\n".join(lines) + "\n")


# --------------------------------------------------------------------------
# Mascot motion — it lives in the left gutter and GLIDES (never stops) so it
# sits right beside whatever label/point the narration is on, pointing right
# at it. A single right-pointing pose works because every target is to its
# right; a continuous smoothstep path keeps it constantly moving.
# --------------------------------------------------------------------------
def _label_screen(hl):
    """Chart-PNG pixel -> screen pixel (through the gutter + scale)."""
    return (CHART_X + hl[0] * CHART_SCALE, CHART_Y + hl[1] * CHART_SCALE)


def _mascot_targets(st: story.Story, windows):
    """Keyframes (t, x, y) for the gutter mascot — beside each beat's label."""
    n = len(windows)
    kfs = []
    for i in range(n):
        t0 = windows[i][0]
        if i == 0 or i == n - 1:                  # hook / closing
            x, y = GUTTER_X, 470.0
        else:
            seg = st.segments[i - 1]
            hl = seg.highlight_px or (300, 460)
            _sx, sy = _label_screen(hl)
            x = GUTTER_X
            # Align the pointing hand (~0.42 down the sprite) with the label.
            y = max(40.0, min(1480.0, sy - 0.42 * MASCOT_SIZE))
        kfs.append((t0, float(x), float(y)))
    return kfs


def _piecewise(kfs, axis: int) -> str:
    """Smoothstep ffmpeg expression interpolating x/y across keyframes."""
    ts = [k[0] for k in kfs]
    vs = [k[axis] for k in kfs]
    expr = f"{vs[-1]:.1f}"
    for i in range(len(kfs) - 2, -1, -1):
        t0, t1, v0, v1 = ts[i], ts[i + 1], vs[i], vs[i + 1]
        dt = max(0.001, t1 - t0)
        u = f"clip((t-{t0:.3f})/{dt:.3f},0,1)"
        s = f"({u})*({u})*(3-2*({u}))"
        expr = f"if(lt(t,{t1:.3f}),({v0:.1f}+({v1:.1f}-{v0:.1f})*{s}),{expr})"
    return f"if(lt(t,{ts[0]:.3f}),{vs[0]:.1f},{expr})"


# --------------------------------------------------------------------------
# Composite.
# --------------------------------------------------------------------------
def render(slug: str, out_path: Path, voice: str = "am_michael") -> Path:
    cfg = json.loads((PKG_DIR / "niche.config.json").read_text())
    story_cfg = next((s for s in cfg.get("stories", []) if s["slug"] == slug), None)
    if not story_cfg:
        raise KeyError(f"no story with slug {slug!r} in niche.config.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        st = story.build(story_cfg, cfg, work, REPO)
        sentences = st.sentences()
        narration, windows = synth_narration(sentences, work, voice)
        total = _dur(narration) + 0.3

        bokeh = ambient.make_bokeh_strip(work / "bokeh.png")
        ass = work / "cap.ass"
        build_story_ass(st, windows, ass)
        ass_esc = str(ass).replace("\\", "/").replace(":", "\\:")

        # One gliding right-pointing mascot for the whole video.
        mascot_mov = mascot.build_mascot_loop(work / "mascot.mov",
                                              size=MASCOT_SIZE, seconds=2.4,
                                              point_angle=float(MASCOT_ANGLE))
        kfs = _mascot_targets(st, windows)
        x_expr = _piecewise(kfs, 1)
        # gentle continuous sway so it's never perfectly still
        y_expr = f"({_piecewise(kfs, 2)})+8*sin(2.2*t)"

        # Inputs: 0 gradient, 1 bokeh, charts, mascot, narration.
        inputs = ["-f", "lavfi", "-i", ambient.gradient_lavfi(total)]
        inputs += ["-loop", "1", "-i", str(bokeh)]
        seg_idx = {}
        idx = 2
        for i, seg in enumerate(st.segments):
            if seg.chart_path:
                inputs += ["-loop", "1", "-i", seg.chart_path]
                seg_idx[i] = idx
                idx += 1
        inputs += ["-stream_loop", "-1", "-i", str(mascot_mov)]
        mascot_idx = idx
        idx += 1
        inputs += ["-i", str(narration)]
        audio_idx = idx

        fc = ambient.bg_filter(1, fps=FPS)        # -> [bg]
        prev = "bg"
        # Charts: each its own, scaled into the gutter layout, during its window.
        for i, seg in enumerate(st.segments):
            if i not in seg_idx:
                continue
            gi = seg_idx[i]
            s0, s1 = windows[1 + i]
            fd = 0.3
            fc.append(
                f"[{gi}:v]scale={CHART_W}:{CHART_H},format=rgba,"
                f"fade=t=in:st={s0:.2f}:d={fd}:alpha=1,"
                f"fade=t=out:st={max(s0, s1 - fd):.2f}:d={fd}:alpha=1[g{i}]")
            fc.append(
                f"[{prev}][g{i}]overlay=x={CHART_X}:y={CHART_Y}:"
                f"enable='between(t,{s0:.2f},{s1:.2f})'[b{i}]")
            prev = f"b{i}"
        # Mascot glides continuously beside the active label, pointing right.
        fc.append(f"[{mascot_idx}:v]format=rgba,scale={MASCOT_SIZE}:{MASCOT_SIZE}[masc]")
        fc.append(f"[{prev}][masc]overlay=x='{x_expr}':y='{y_expr}':"
                  f"eval=frame:shortest=0[withm]")
        fc.append(f"[withm]ass='{ass_esc}'[v]")

        cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs,
               "-filter_complex", ";".join(fc),
               "-map", "[v]", "-map", f"{audio_idx}:a",
               "-t", f"{total:.2f}", "-r", str(FPS),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
               "-crf", "20", "-c:a", "aac", "-b:a", "192k",
               "-movflags", "+faststart", str(out_path)]
        _run(cmd)

    print(f"[studio] story '{slug}': {len(st.segments)} charts, "
          f"{len(sentences)} beats, {total:.1f}s -> {out_path}")
    print(f"[studio] title: {st.title}")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="story slug from niche.config.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--voice", default="am_michael",
                    help="Kokoro voice id (default am_michael, the dude-monster voice)")
    args = ap.parse_args()
    render(args.slug, args.out, voice=args.voice)
    return 0


if __name__ == "__main__":
    sys.exit(main())
