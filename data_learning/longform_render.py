#!/usr/bin/env python3
"""Long-form 16:9 renderer — the curiosity channel's production renderer.

Renders a STORY as a 4-5 minute 1920x1080 watch-page video (NOT a Short):
a title card, then one documentary-style "exhibit" frame per beat (the
segment's chart/viz-scene PNG composed with a heading column), each with a
slow Ken Burns push, calm narration, a ducked music bed, and a closing card.
Alongside the mp4 it writes:

    <out>.jpg          1920x1080 custom thumbnail
    <out>.meta.json    chapters (>=3, first at 00:00, each >=10s) + duration

It is an add-on in the spirit of studio_render: it reuses story.build, the
per-slug theme, the TTS text normalizer and the music picker, and never
modifies any base module. Everything runs headless (ffmpeg + Pillow +
matplotlib + ONNX TTS) per the channel's tools doctrine (CURIOSITY_BRAIN.md
§13): desktop tools only when fully CLI-scriptable.

Voice: Kokoro (the pipeline's QA'd voice) when the model files are present,
falling back LOUDLY to edge-tts — the same fallback the base pipeline uses —
so a missing model download never kills a render.

Usage:
    python -m data_learning.longform_render --slug kola-deepest-hole \
        --out output/curiosity_kola.mp4 \
        --config data_learning/curiosity.config.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
REPO = PKG_DIR.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from data_learning import charts, story                          # noqa: E402
from data_learning.demo_render import _dur, _run                 # noqa: E402
from data_learning.studio_render import (                        # noqa: E402
    KOKORO_MODEL, KOKORO_VOICES, _font, _headline_number, _music_track,
    _theme_for, _tts_text)

W, H, FPS = 1920, 1080, 30
EDGE_VOICE = "en-US-GuyNeural"       # fallback narrator (calm US male)
SENT_GAP = 0.35                      # documentary breathing between beats
MUSIC_VOL = 0.09
DATA_DIR = PKG_DIR / "data"

# Beat treatments, best first (CURIOSITY_BRAIN.md §13 tools rule):
#   hero  -> Blender Cycles monolith lineup (blender_hero.py), one per video
#   manim -> animated data scene (curiosity_scenes.py)
#   still -> Pillow exhibit frame + Ken Burns (always available)
HERO_SECONDS, HERO_FPS = 7.0, 10     # Cycles frames are the CI cost centre


def _have_blender() -> bool:
    return shutil.which("blender") is not None


def _have_manim() -> bool:
    try:
        import manim  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------
# Narration — Kokoro primary (speed 1.0: watch-page pace, not Shorts pace),
# edge-tts fallback.
# --------------------------------------------------------------------------
def _synth_kokoro(sentences, workdir: Path, voice: str):
    import soundfile as sf
    from kokoro_onnx import Kokoro
    k = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    try:
        k.create("test", voice=voice, lang="en-us")
    except Exception:  # noqa: BLE001
        voice = "am_fenrir"
    wavs = []
    for i, sent in enumerate(sentences):
        samples, sr = k.create(_tts_text(sent), voice=voice, speed=1.0,
                               lang="en-us")
        w = workdir / f"s{i}.wav"
        sf.write(str(w), samples, sr)
        wavs.append(w)
    return wavs


def _synth_edge(sentences, workdir: Path):
    import asyncio
    import edge_tts

    async def one(i, sent):
        c = edge_tts.Communicate(_tts_text(sent), EDGE_VOICE)
        await c.save(str(workdir / f"s{i}.mp3"))

    async def all_():
        for i, s in enumerate(sentences):
            await one(i, s)

    asyncio.run(all_())
    wavs = []
    for i in range(len(sentences)):
        w = workdir / f"s{i}.wav"
        _run(["ffmpeg", "-y", "-loglevel", "error",
              "-i", str(workdir / f"s{i}.mp3"),
              "-ar", "48000", "-ac", "1", str(w)])
        wavs.append(w)
    return wavs


def synth_narration(sentences, workdir: Path, voice: str):
    """Per-sentence wavs -> one narration track + (start, end) windows."""
    if KOKORO_MODEL.exists() and KOKORO_VOICES.exists():
        wavs = _synth_kokoro(sentences, workdir, voice)
    else:
        print("[longform] Kokoro models missing — falling back to edge-tts "
              f"({EDGE_VOICE})", file=sys.stderr)
        wavs = _synth_edge(sentences, workdir)
    windows, t = [], 0.0
    for w in wavs:
        d = _dur(w) + SENT_GAP
        windows.append((t, t + d))
        t += d
    listf = workdir / "list.txt"
    listf.write_text("\n".join(
        f"file '{w}'\nduration {_dur(w) + SENT_GAP:.3f}" for w in wavs) + "\n")
    # concat with per-file padding so audio timing matches the windows
    padded = []
    for i, w in enumerate(wavs):
        p = workdir / f"p{i}.wav"
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(w),
              "-af", f"apad=pad_dur={SENT_GAP}", "-ar", "48000",
              "-c:a", "pcm_s16le", str(p)])
        padded.append(p)
    lf = workdir / "plist.txt"
    lf.write_text("\n".join(f"file '{p}'" for p in padded) + "\n")
    narration = workdir / "narration.wav"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", str(lf), "-c:a", "pcm_s16le", str(narration)])
    return narration, windows


# --------------------------------------------------------------------------
# Frames (PIL) — dark documentary canvas, exhibit image right, heading left.
# --------------------------------------------------------------------------
def _rgb(h: str):
    h = h.lstrip("#").replace("0x", "")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _gradient(theme: dict):
    """Vertical gradient through the theme's grad stops (2-4 of them),
    darkest stop on top so the heading column stays legible."""
    from PIL import Image
    stops = [_rgb(g) for g in (theme.get("grad")
                               or ("0x080A14", "0x0e2444"))]
    stops = sorted(stops, key=sum)                  # darkest first (top)
    col = Image.new("RGB", (1, H))
    n = len(stops) - 1
    for y in range(H):
        f = y / (H - 1) * n
        i = min(int(f), n - 1)
        u = f - i
        a, b = stops[i], stops[i + 1]
        col.putpixel((0, y), tuple(int(a[k] + (b[k] - a[k]) * u)
                                   for k in range(3)))
    return col.resize((W, H))


def _wrap_text(draw, text: str, font, maxw: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if draw.textlength(trial, font=font) > maxw and line:
            lines.append(line)
            line = w
        else:
            line = trial
    if line:
        lines.append(line)
    return lines


def _fit_text(draw, text: str, size: int, maxw: int, max_lines: int):
    f = _font(size)
    lines = _wrap_text(draw, text, f, maxw)
    while len(lines) > max_lines and f.size > 30:
        f = _font(f.size - 6)
        lines = _wrap_text(draw, text, f, maxw)
    return f, lines


def _title_card(theme: dict, kicker: str, title: str, sub: str,
                out: Path) -> Path:
    from PIL import ImageDraw
    img = _gradient(theme)
    d = ImageDraw.Draw(img)
    M = 140
    kf = _font(40)
    d.text((M, 200), kicker.upper(), font=kf,
           fill=_rgb(theme.get("accent", "#60A5FA")))
    tf, tlines = _fit_text(d, title, 118, W - 2 * M, 3)
    y = 280
    for ln in tlines:
        d.text((M + 5, y + 5), ln, font=tf, fill=(0, 0, 0))
        d.text((M, y), ln, font=tf, fill=(255, 255, 255))
        y += int(tf.size * 1.15)
    d.rectangle([M, y + 30, M + 220, y + 44],
                fill=_rgb(theme.get("highlight", "#4FD1C5")))
    if sub:
        sf, slines = _fit_text(d, sub, 52, W - 2 * M, 4)
        y += 110
        for ln in slines:
            d.text((M, y), ln, font=sf, fill=(200, 208, 220))
            y += int(sf.size * 1.3)
    img.save(out)
    return out


def _chart_still(chart_path: str | None) -> Path | None:
    """story.build returns a printf frame-sequence pattern
    ("..._build%02d.png"); the exhibit still is the LAST frame (== the
    final static chart). Also accepts a plain PNG path."""
    if not chart_path:
        return None
    p = Path(chart_path)
    if "%" not in p.name:
        return p if p.exists() else None
    frames = sorted(p.parent.glob(p.name.replace("%02d", "*")))
    return frames[-1] if frames else None


def _beat_frame(seg, theme: dict, idx: int, n: int, out: Path) -> Path:
    from PIL import Image, ImageDraw
    img = _gradient(theme)
    d = ImageDraw.Draw(img)
    M = 90
    col_w = 640

    # Exhibit image (chart or viz scene), right side, fit inside its box.
    still = _chart_still(seg.chart_path)
    if still:
        art = Image.open(still).convert("RGB")
        box_w, box_h = W - col_w - 2 * M - 40, H - 2 * M
        sc = min(box_w / art.width, box_h / art.height)
        art = art.resize((max(1, int(art.width * sc)),
                          max(1, int(art.height * sc))))
        ax = W - M - art.width
        ay = (H - art.height) // 2
        # Soft plinth shadow so the exhibit sits IN the frame, not on it.
        d.rectangle([ax - 14, ay - 14, ax + art.width + 14,
                     ay + art.height + 14], fill=_rgb("#05070d"))
        img.paste(art, (ax, ay))

    # Heading column, left.
    accent = _rgb(theme.get("accent", "#60A5FA"))
    highlight = _rgb(theme.get("highlight", "#4FD1C5"))
    rf = _font(38)
    d.text((M, 170), (seg.role or f"{idx} of {n}").upper(), font=rf,
           fill=accent)
    tf, tlines = _fit_text(d, (seg.topic or "").title(), 74, col_w, 4)
    y = 240
    for ln in tlines:
        d.text((M + 4, y + 4), ln, font=tf, fill=(0, 0, 0))
        d.text((M, y), ln, font=tf, fill=(255, 255, 255))
        y += int(tf.size * 1.18)
    d.rectangle([M, y + 26, M + 170, y + 38], fill=highlight)

    # Source footer — honesty on every frame.
    if seg.source_footer:
        sf = _font(26)
        d.text((M, H - 70), seg.source_footer[:110], font=sf,
               fill=(150, 158, 172))
    img.save(out)
    return out


def make_thumbnail(st: "story.Story", theme: dict, out_path: Path) -> Path:
    """1920x1080 packaging card: claim (title) + the biggest on-chart
    number, in the video's theme palette — same language as the channel."""
    from PIL import ImageDraw
    img = _gradient(theme)
    d = ImageDraw.Draw(img)
    M = 110
    big = _headline_number(st)
    if big:
        nf = _font(430)
        nb = d.textbbox((0, 0), big, font=nf)
        nw = nb[2] - nb[0]
        if nw > W * 0.62:
            nf = _font(int(430 * (W * 0.62) / nw))
            nb = d.textbbox((0, 0), big, font=nf)
            nw = nb[2] - nb[0]
        nx, ny = W - M - nw - nb[0], M - nb[1]
        d.text((nx + 8, ny + 8), big, font=nf, fill=(0, 0, 0))
        d.text((nx, ny), big, font=nf,
               fill=_rgb(theme.get("highlight", "#4FD1C5")))
    claim = (st.title or "").strip()
    cf, lines = _fit_text(d, claim, 150, W - 2 * M, 3)
    lh = int(cf.size * 1.1)
    y = H - M - lh * len(lines)
    d.rectangle([M, y - 40, M + 230, y - 22],
                fill=_rgb(theme.get("accent", "#60A5FA")))
    for ln in lines:
        d.text((M + 6, y + 6), ln, font=cf, fill=(0, 0, 0))
        d.text((M, y), ln, font=cf, fill=(255, 255, 255))
        y += lh
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, quality=92)
    return out_path


# --------------------------------------------------------------------------
# Beat treatments — Blender hero, Manim motion, Pillow still (fallback).
# --------------------------------------------------------------------------
def _disp(v: float, unit: str) -> str:
    n = f"{v:,.0f}" if abs(v) >= 1000 or float(v).is_integer() else f"{v:,.1f}"
    return f"{n} {unit}".strip()


def _seg_points(seg_cfg: dict) -> tuple[list[dict], str]:
    data = json.loads((DATA_DIR / seg_cfg["params"]["file"]).read_text())
    return data.get("points", []), data.get("unit", "")


def _fit_clip(src: Path, dur: float, out: Path) -> Path:
    """Normalize a beat clip to 1920x1080@30 and EXACTLY `dur` seconds:
    trim if long, hold the final frame if short (the animation plays, then
    the finished exhibit sits while the narration lands)."""
    have = _dur(src)
    pad = max(0.0, dur - have)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},"
          f"tpad=stop_mode=clone:stop_duration={pad:.3f},"
          f"fade=t=in:st=0:d=0.4,format=yuv420p")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
          "-vf", vf, "-t", f"{dur:.3f}", "-r", str(FPS), "-an",
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    return out


def _heading_overlay(seg, theme: dict, out: Path) -> Path:
    """Transparent 1920x1080 PNG with the beat's role/topic/rule/footer —
    laid over Blender hero clips so every beat shares one chrome system."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    M = 90
    accent = _rgb(theme.get("accent", "#60A5FA"))
    rf = _font(38)
    d.text((M, 120), (seg.role or "").upper(), font=rf, fill=(*accent, 255))
    tf, tlines = _fit_text(d, (seg.topic or "").title(), 66, 760, 3)
    y = 185
    for ln in tlines:
        d.text((M + 4, y + 4), ln, font=tf, fill=(0, 0, 0, 200))
        d.text((M, y), ln, font=tf, fill=(255, 255, 255, 255))
        y += int(tf.size * 1.18)
    d.rectangle([M, y + 22, M + 170, y + 34],
                fill=(*_rgb(theme.get("highlight", "#4FD1C5")), 255))
    if seg.source_footer:
        sf = _font(26)
        d.text((M, H - 70), seg.source_footer[:95], font=sf,
               fill=(180, 188, 200, 235))
    img.save(out)
    return out


def _manim_beat(seg_cfg: dict, seg, theme: dict, work: Path,
                idx: int) -> Path:
    """Render one animated data beat with Manim (curiosity_scenes.py)."""
    from data_learning.curiosity_scenes import SCENE_FOR_KIND
    kind = seg_cfg.get("insight_type", "rank")
    scene_cls = SCENE_FOR_KIND[kind]                    # KeyError -> fallback
    points, unit = _seg_points(seg_cfg)
    spec = {
        "kind": kind, "role": seg.role, "topic": seg.topic, "unit": unit,
        "source": seg.source_footer,
        "bg": "#0a0e14", "accent": theme.get("accent", "#60A5FA"),
        "highlight": theme.get("highlight", "#4FD1C5"),
        "points": points,
    }
    spec_path = work / f"mspec{idx}.json"
    spec_path.write_text(json.dumps(spec))
    media = work / f"manim{idx}"
    env = dict(os.environ, CURIO_SPEC=str(spec_path))
    subprocess.run(
        [sys.executable, "-m", "manim", "render", "-qm", "--fps", str(FPS),
         "-r", f"{W},{H}", "--media_dir", str(media),
         "-o", f"beat{idx}.mp4", "-v", "ERROR",
         str(PKG_DIR / "curiosity_scenes.py"), scene_cls],
        check=True, env=env, capture_output=True, text=True)
    hits = list(media.glob(f"videos/**/beat{idx}.mp4"))
    if not hits:
        raise FileNotFoundError(f"manim produced no beat{idx}.mp4")
    return hits[0]


def _hero_beat(seg_cfg: dict, seg, theme: dict, work: Path,
               idx: int) -> Path:
    """Render the video's one Blender Cycles hero shot and dress it with
    the shared heading chrome. Rendered at 810p/10fps for the CI budget,
    motion-interpolated to 30fps and upscaled."""
    points, unit = _seg_points(seg_cfg)
    vals = [abs(float(p["value"])) or 1e-9 for p in points]
    spec = {
        "points": [{"label": p["label"], "value": p["value"],
                    "display": _disp(p["value"], unit)} for p in points],
        "title": seg.topic, "accent": theme.get("highlight", "#4FD1C5"),
        "seconds": HERO_SECONDS, "fps": HERO_FPS, "samples": 32,
        "invert": bool(seg_cfg.get("hero_invert")),
        "log_scale": (max(vals) / min(vals)) > 50,
        "res_x": 1440, "res_y": 810,
    }
    spec_path = work / f"hspec{idx}.json"
    spec_path.write_text(json.dumps(spec))
    frames_dir = work / f"hero{idx}"
    frames_dir.mkdir(exist_ok=True)
    res = subprocess.run(
        ["blender", "-b", "--factory-startup", "--python",
         str(PKG_DIR / "blender_hero.py"), "--", str(spec_path),
         str(frames_dir)],
        check=False, capture_output=True, text=True, timeout=3600)
    if "HERO_DONE" not in (res.stdout or ""):
        raise RuntimeError(f"blender hero failed: {(res.stderr or '')[-400:]}")
    overlay = _heading_overlay(seg, theme, work / f"hover{idx}.png")
    out = work / f"herobeat{idx}.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error",
          "-framerate", str(HERO_FPS), "-i", str(frames_dir / "hero_%04d.png"),
          "-i", str(overlay), "-filter_complex",
          f"[0:v]minterpolate=fps={FPS}:mi_mode=mci,scale={W}:{H}[v];"
          f"[v][1:v]overlay=0:0,format=yuv420p[o]",
          "-map", "[o]", "-c:v", "libx264", "-preset", "veryfast",
          "-crf", "18", str(out)])
    return out


def _still_beat(seg, theme: dict, idx: int, n: int, dur: float,
                work: Path) -> Path:
    """Fallback: composed exhibit still + Ken Burns (always available)."""
    frame = _beat_frame(seg, theme, idx, n, work / f"sframe{idx}.png")
    return _kenburns_clip(frame, dur, idx, work / f"sbeat{idx}.mp4")


# --------------------------------------------------------------------------
# Assembly.
# --------------------------------------------------------------------------
def _kenburns_clip(frame: Path, dur: float, idx: int, out: Path) -> Path:
    """A slow push (alternating in/out) over a still — upscale first so
    zoompan doesn't jitter at small zoom factors."""
    frames = max(2, int(round(dur * FPS)))
    zmax = 1.07
    if idx % 2 == 0:
        z = f"min(1.0+{(zmax - 1.0) / frames:.7f}*on,{zmax})"
    else:
        z = f"max({zmax}-{(zmax - 1.0) / frames:.7f}*on,1.0)"
    vf = (f"scale={W * 2}:{H * 2},"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"d=1:s={W}x{H}:fps={FPS},fade=t=in:st=0:d=0.4,format=yuv420p")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1",
          "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(frame),
          "-vf", vf, "-t", f"{dur:.3f}", "-r", str(FPS),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
          "-an", str(out)])
    return out


def _chapter_name(role: str, topic: str) -> str:
    name = (role or "").split("·", 1)[-1].strip() or (topic or "").strip()
    return name.title() if name else "Chapter"


def render(slug: str, out_path: Path, voice: str | None = None,
           config_path: Path | None = None) -> Path:
    config_path = (Path(config_path) if config_path
                   else PKG_DIR / "curiosity.config.json")
    cfg = json.loads(config_path.read_text())
    story_cfg = next((s for s in cfg.get("stories", [])
                      if s["slug"] == slug), None)
    if not story_cfg:
        raise KeyError(f"no story with slug {slug!r} in {config_path.name}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    theme = _theme_for(slug)
    charts.HIGHLIGHT, charts.ACCENT, charts.WARN = (
        theme["highlight"], theme["accent"], theme["warn"])
    if voice is None:
        voice = theme["voice"]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        st = story.build(story_cfg, cfg, work, REPO)
        try:
            make_thumbnail(st, theme, out_path.with_suffix(".jpg"))
        except Exception as e:  # noqa: BLE001 — never fail a render on a thumb
            print(f"[longform] thumbnail skipped: {e}", file=sys.stderr)

        sentences = st.sentences()
        narration, windows = synth_narration(sentences, work, voice)
        total = windows[-1][1]

        # Title + closing cards (Pillow + Ken Burns).
        title_frame = _title_card(theme, cfg.get("channel_name", "Visualized"),
                                  st.title, st.hook, work / "f_title.png")
        close_frame = _title_card(theme, "one more thing", st.closing,
                                  st.question, work / "f_close.png")
        clips = [_kenburns_clip(title_frame, windows[0][1] - windows[0][0],
                                0, work / "c_title.mp4")]

        # One MOTION beat per segment: Blender hero for the story's marked
        # reveal, Manim for the data beats, Pillow still as the loud
        # fallback (a missing tool degrades the look, never kills a video).
        # Treatments assume config order == story order, which the
        # keep_order flag guarantees for curiosity stories.
        seg_cfgs = list(story_cfg["segments"])
        ordered = (len(seg_cfgs) == len(st.segments)
                   and story_cfg.get("keep_order"))
        have_manim, have_blender = _have_manim(), _have_blender()
        for i, (seg, (t0, t1)) in enumerate(zip(st.segments, windows[1:-1])):
            dur = t1 - t0
            seg_cfg = seg_cfgs[i] if ordered else {}
            clip = None
            if seg_cfg.get("hero") and have_blender:
                try:
                    clip = _fit_clip(_hero_beat(seg_cfg, seg, theme, work, i),
                                     dur, work / f"c{i + 1}.mp4")
                    print(f"[longform] beat {i + 1}: blender hero")
                except Exception as e:  # noqa: BLE001
                    print(f"[longform] beat {i + 1}: hero FAILED ({e}) — "
                          "degrading to manim/still", file=sys.stderr)
            if clip is None and seg_cfg and have_manim:
                try:
                    clip = _fit_clip(_manim_beat(seg_cfg, seg, theme, work, i),
                                     dur, work / f"c{i + 1}.mp4")
                    print(f"[longform] beat {i + 1}: manim "
                          f"{seg_cfg.get('insight_type')}")
                except Exception as e:  # noqa: BLE001
                    print(f"[longform] beat {i + 1}: manim FAILED ({e}) — "
                          "degrading to still", file=sys.stderr)
            if clip is None:
                clip = _still_beat(seg, theme, i + 1, len(st.segments),
                                   dur, work)
                print(f"[longform] beat {i + 1}: still fallback")
            clips.append(clip)

        clips.append(_kenburns_clip(close_frame,
                                    windows[-1][1] - windows[-1][0],
                                    len(clips), work / "c_close.mp4"))
        listf = work / "clips.txt"
        listf.write_text("\n".join(f"file '{c}'" for c in clips) + "\n")
        video = work / "video.mp4"
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
              "-safe", "0", "-i", str(listf), "-c", "copy", str(video)])

        # Soundtrack: narration + ducked music bed (skip music gracefully).
        track = _music_track(cfg.get("music_vibe", "cinematic"), slug)
        audio = work / "mix.wav"
        if track:
            _run(["ffmpeg", "-y", "-loglevel", "error",
                  "-i", str(narration), "-stream_loop", "-1",
                  "-i", str(track), "-filter_complex",
                  f"[1:a]volume={MUSIC_VOL},atrim=0:{total:.3f},"
                  f"afade=t=out:st={max(0.0, total - 3):.3f}:d=3[m];"
                  f"[0:a][m]amix=inputs=2:duration=first:normalize=0,"
                  f"loudnorm=I=-14:TP=-1.5:LRA=11[a]",
                  "-map", "[a]", "-ar", "48000", str(audio)])
        else:
            print("[longform] no music bed found — narration only",
                  file=sys.stderr)
            _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(narration),
                  "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
                  str(audio)])

        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
              "-i", str(audio), "-map", "0:v", "-map", "1:a",
              "-c:v", "copy", "-c:a", "aac", "-b:a", "384k", "-ar", "48000",
              "-movflags", "+faststart", str(out_path)])

        # Chapters sidecar: first at 00:00, names from segment roles. Beats
        # run 20-40s each so the >=10s chapter rule holds by construction.
        chapters = [{"t": 0.0, "label": "Intro"}]
        for seg, (t0, _) in zip(st.segments, windows[1:-1]):
            chapters.append({"t": round(t0, 2),
                             "label": _chapter_name(seg.role, seg.topic)})
        chapters.append({"t": round(windows[-1][0], 2), "label": "Takeaway"})
        meta = {"slug": slug, "duration": round(total, 2),
                "chapters": chapters, "sources": st.sources}
        out_path.with_suffix(".meta.json").write_text(
            json.dumps(meta, indent=2) + "\n")

    print(f"[longform] {out_path}  ({total:.0f}s, "
          f"{len(st.segments)} beats)")
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--voice", default=None,
                    help="Kokoro voice id (default: per-slug theme voice)")
    ap.add_argument("--config", type=Path, default=None,
                    help="story config JSON (default: data_learning/"
                         "curiosity.config.json)")
    args = ap.parse_args()
    render(args.slug, args.out, voice=args.voice, config_path=args.config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
