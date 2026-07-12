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
if os.environ.get("CURIO_REGRESSION"):
    # The 15-minute contract tier: the FULL pipeline (director, world
    # take, evidence, sound, gates' ledger) at low quality with Blender
    # skipped — the ledger it produces is identical in shape to the
    # premium run's, so every v8 gate verdict is known before a single
    # Cycles frame is paid for.
    W, H, FPS = 854, 480, 15
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


def synth_narration(sentences, workdir: Path, voice: str, holds=None):
    """Per-sentence wavs -> one narration track + (start, end) windows.

    holds: optional per-sentence extra silence (seconds) appended AFTER
    the sentence — BREATHING GAPS (§7.5 v7) where narration stops and
    music + visuals carry the moment (the sidechained bed swells on its
    own). The sentence's window stretches to include its hold, so the
    escalation scheduler fills the gap with events and dwell."""
    if KOKORO_MODEL.exists() and KOKORO_VOICES.exists():
        wavs = _synth_kokoro(sentences, workdir, voice)
    else:
        print("[longform] Kokoro models missing — falling back to edge-tts "
              f"({EDGE_VOICE})", file=sys.stderr)
        wavs = _synth_edge(sentences, workdir)
    holds = list(holds or [])
    holds += [0.0] * (len(wavs) - len(holds))
    windows, t = [], 0.0
    for w, hold in zip(wavs, holds):
        d = _dur(w) + SENT_GAP + max(0.0, float(hold))
        windows.append((t, t + d))
        t += d
    listf = workdir / "list.txt"
    listf.write_text("\n".join(
        f"file '{w}'\nduration {_dur(w) + SENT_GAP + max(0.0, float(h)):.3f}"
        for w, h in zip(wavs, holds)) + "\n")
    # concat with per-file padding so audio timing matches the windows
    padded = []
    for i, (w, hold) in enumerate(zip(wavs, holds)):
        p = workdir / f"p{i}.wav"
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(w),
              "-af",
              f"apad=pad_dur={SENT_GAP + max(0.0, float(hold)):.3f}",
              "-ar", "48000", "-c:a", "pcm_s16le", str(p)])
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


def _heading_overlay(seg, theme: dict, out: Path,
                     bottom: bool = False) -> Path:
    """Transparent 1920x1080 PNG with the beat's role/topic/rule/footer —
    laid over Blender hero and b-roll clips so every beat shares one
    chrome system. `bottom=True` anchors the heading lower-left (hero
    scenes keep their 3D labels along the top — never collide with them)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    M = 90
    accent = _rgb(theme.get("accent", "#60A5FA"))
    rf = _font(38)
    tf, tlines = _fit_text(d, (seg.topic or "").title(), 66, 760, 3)
    block_h = 65 + len(tlines) * int(tf.size * 1.18) + 34
    y0 = (H - 150 - block_h) if bottom else 120
    d.text((M, y0), (seg.role or "").upper(), font=rf, fill=(*accent, 255))
    y = y0 + 65
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
    from data_learning.curiosity_scenes import SCENE_BY_NAME, SCENE_FOR_KIND
    kind = seg_cfg.get("insight_type", "rank")
    # A story can request a named storytelling primitive per beat
    # ("scene": "descent" | "zoomout" | "cutaway"); otherwise the chart
    # scene for the data shape.                         KeyError -> fallback
    scene_cls = (SCENE_BY_NAME[seg_cfg["scene"]] if seg_cfg.get("scene")
                 else SCENE_FOR_KIND[kind])
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
    overlay = _heading_overlay(seg, theme, work / f"hover{idx}.png",
                               bottom=True)
    out = work / f"herobeat{idx}.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error",
          "-framerate", str(hero_fps), "-i", str(frames_dir / "hero_%04d.png"),
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
# B-roll — real footage between the data payoffs. Documentary grammar:
# stock clips play while the narration sets the beat up, then the cut lands
# on the chart/hero exactly when the number does. Providers via the repo's
# stock_search (Pexels/Pixabay when keys exist, keyless Mixkit always).
# --------------------------------------------------------------------------
BROLL_MAX_SHARE = 0.45      # never let footage eat the data payoff
BROLL_CLIP_SECONDS = 4.5    # per-clip cap (playbook: a cut every 1-4s)


def _broll_part(query: str, want: float, overlay: Path, work: Path,
                tag: str) -> Path | None:
    """Fetch one stock clip, grade it into the channel look (crop to
    1920x1080, slight desaturated-dark grade, vignette, heading chrome),
    trimmed to `want` seconds. None on any failure — b-roll is a bonus,
    never a blocker."""
    try:
        import stock_search
        c = stock_search.fetch_top(query, work / f"broll_{tag}_dl",
                                   min_duration=4, max_duration=30)
        raw = Path(c["path"])          # fetch_top's dest is a DIRECTORY
        out = work / f"broll_{tag}.mp4"
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={FPS},"
              f"eq=saturation=1.05:brightness=-0.04,vignette=PI/5")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
              "-i", str(overlay), "-filter_complex",
              f"[0:v]{vf}[v];[v][1:v]overlay=0:0,"
              f"fade=t=in:st=0:d=0.3,format=yuv420p[o]",
              "-map", "[o]", "-t", f"{want:.3f}", "-r", str(FPS), "-an",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
              str(out)])
        return out if _dur(out) >= 1.5 else None
    except Exception as e:  # noqa: BLE001
        print(f"[longform] b-roll {tag} ({query!r}) skipped: {e}",
              file=sys.stderr)
        return None


def _broll_parts(seg_cfg: dict, seg, theme: dict, dur: float, work: Path,
                 idx: int) -> tuple[list[Path], float]:
    """Up to 2 graded b-roll clips for this beat, within the share cap.
    Returns (clips, seconds_used)."""
    queries = list(seg_cfg.get("broll") or [])[:2]
    if not queries or dur < 16:
        return [], 0.0
    budget = min(dur * BROLL_MAX_SHARE, BROLL_CLIP_SECONDS * len(queries))
    overlay = _heading_overlay(seg, theme, work / f"bover{idx}.png")
    parts, used = [], 0.0
    for j, q in enumerate(queries):
        want = min(BROLL_CLIP_SECONDS, budget - used)
        if want < 2.5:
            break
        clip = _broll_part(q, want, overlay, work, f"{idx}_{j}")
        if clip:
            parts.append(clip)
            used += _dur(clip)
    return parts, used


# --------------------------------------------------------------------------
# The simulation engine path — one place, one camera, one take
# (world_engine.WorldScene), with Blender heroes spliced over their
# waypoint windows behind a luminance dip. Falls back LOUDLY to the
# clip-per-beat renderer below if anything in here fails.
# --------------------------------------------------------------------------
def _hex_grad0(theme: dict) -> str:
    g = (theme.get("grad") or ("0x080A14",))[0]
    return "#" + str(g).replace("0x", "").replace("#", "")


# Templates that are pure visual journeys — no data points required
# (premium budget law: entering/exiting things, impossible transitions).
_VISUAL_TEMPLATES = {"earth_spin", "orbit_fly", "cosmic_exit"}
# Templates that draw THE Earth and need the continent silhouettes.
_EARTH_TEMPLATES = {"earth_spin", "orbit_fly", "cosmic_exit", "earth_dive"}


def _hero_spec(template: str, seg_cfg: dict, theme: dict,
               seconds: float = HERO_SECONDS, breach: bool = False) -> dict:
    # Interpolation-suitability triage (§7.5 v8): fps class per template
    # — crossing objects and fast edges warp at 10fps minterpolate.
    from data_learning.render_director import FPS_CLASS
    # Cycles cost knobs (§7.5 v8) — the render is upscaled to 1080p by the
    # minterpolate pass, and toon shading (flat emission + diffuse, no
    # textures) upscales cleanly, so a slower host (a 4-core CI runner
    # under a hard job cap) can trade a little hero sharpness for FINISHING
    # inside its window. Defaults keep full quality; env overrides let CI
    # fit the 6h GitHub cap. "960x540" heroes render ~3x faster than 1440.
    _res = os.environ.get("CURIO_HERO_RES", "1440x810")
    _rx, _ry = (int(v) for v in _res.lower().split("x"))
    _samples = int(os.environ.get("CURIO_HERO_SAMPLES", "32"))
    spec = {
        "template": template,
        "accent": theme.get("highlight", "#4FD1C5"),
        "seconds": seconds, "fps": int(FPS_CLASS.get(template, HERO_FPS)),
        "samples": _samples,
        "res_x": _rx, "res_y": _ry,
        "style": 3,     # visual language version — busts the hero
    }                   # cache when the brand look changes
    if breach:
        # hero-integration contract: open inside the 2D push-in target,
        # end wide enough to match the mutated return frame
        spec["entry"] = "breach"
        spec["exit"] = "wide"
    if template in _EARTH_TEMPLATES:
        # v8: THE continents ride in the spec (blender_hero never imports
        # pipeline code) — and being part of the md5 cache key, editing
        # the silhouettes re-renders every earth shot automatically.
        from data_learning.continents import LANDMASSES
        spec["continents"] = {k: [list(p) for p in v]
                              for k, v in LANDMASSES.items()}
    if template in _VISUAL_TEMPLATES:
        return spec
    points, unit = _seg_points(seg_cfg)
    vals = [abs(float(p["value"])) or 1e-9 for p in points]
    vmax = max(vals) if vals else 1.0
    if template == "earth_dive":
        spec["markers"] = [
            {"label": p["label"], "display": _disp(p["value"], unit),
             "frac": abs(float(p["value"])) / vmax} for p in points]
    else:
        spec["points"] = [{"label": p["label"], "value": p["value"],
                           "display": _disp(p["value"], unit)}
                          for p in points]
        spec["invert"] = bool(seg_cfg.get("hero_invert"))
        spec["log_scale"] = (max(vals) / min(vals)) > 50 if vals else False
    return spec


def _hero_clip(template: str, seg_cfg: dict, theme: dict, dur: float,
               work: Path, idx, seconds: float = HERO_SECONDS,
               breach: bool = False) -> Path:
    """Render a Blender hero and dress it for splicing: minterpolated to
    30fps, scaled, luminance-dip fades at both ends (the simple splice —
    no motion matching, per doctrine)."""
    spec = _hero_spec(template, seg_cfg, theme, seconds, breach=breach)
    spec_path = work / f"whspec{idx}.json"
    spec_path.write_text(json.dumps(spec))
    # Cycles frames are the expensive asset — cache them outside the
    # tempdir (CURIO_HERO_CACHE) keyed by the spec, so a failed splice
    # or a re-run never re-pays the render.
    cache_root = os.environ.get("CURIO_HERO_CACHE")
    hero_fps = int(spec.get("fps", HERO_FPS))
    expected = max(4, int(round(hero_fps * seconds)))
    if cache_root:
        import hashlib
        key = hashlib.md5(json.dumps(spec, sort_keys=True)
                          .encode()).hexdigest()[:16]
        frames_dir = Path(cache_root) / f"{template}_{key}"
    else:
        frames_dir = work / f"whero{idx}"
    frames_dir.mkdir(parents=True, exist_ok=True)
    if len(list(frames_dir.glob("hero_*.png"))) < expected:
        res = subprocess.run(
            ["blender", "-b", "--factory-startup", "--python",
             str(PKG_DIR / "blender_hero.py"), "--", str(spec_path),
             str(frames_dir)],
            check=False, capture_output=True, text=True, timeout=7200)
        if "HERO_DONE" not in (res.stdout or ""):
            raise RuntimeError(f"hero failed: {(res.stderr or '')[-300:]}")
    else:
        print(f"[longform] hero cache hit: {frames_dir.name}")
    out = work / f"wherobeat{idx}.mp4"
    # Fill the WHOLE splice with real motion: stretch playback (slow-mo)
    # to the splice duration, then motion-interpolate to 30fps. Never a
    # frozen hold — the motion gate fails static frames.
    factor = max(1.0, dur / seconds)
    fade_out_st = max(0.0, dur - 0.3)
    _run(["ffmpeg", "-y", "-loglevel", "error",
          "-framerate", str(hero_fps), "-i", str(frames_dir / "hero_%04d.png"),
          "-vf",
          f"setpts={factor:.4f}*PTS,minterpolate=fps={FPS}:mi_mode=mci,"
          f"scale={W}:{H},"
          f"fade=t=in:st=0:d=0.3,fade=t=out:st={fade_out_st:.3f}:d=0.3,"
          f"format=yuv420p",
          "-t", f"{dur:.3f}", "-r", str(FPS),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
          str(out)])
    return out


def _splice(body: Path, hero: Path, t0: float, t1: float, out: Path) -> Path:
    """Replace body[t0:t1] with the hero clip.

    Memory-frugal: encode the head/tail parts as separate sequential
    passes and join with the concat DEMUXER (stream copy) — the old
    single-pass 3-branch concat FILTER buffered whole branches and got
    OOM-killed on long bodies, and a zero-length first trim (t0=0) made
    it buffer without bound."""
    total = _dur(body)
    enc = ["-an", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "18", "-pix_fmt", "yuv420p"]
    parts = []
    if t0 > 0.05:
        pa = out.with_name(out.stem + "_a.mp4")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(body),
              "-t", f"{t0:.3f}", *enc, str(pa)])
        parts.append(pa)
    parts.append(hero)
    if t1 < total - 0.05:
        pc = out.with_name(out.stem + "_c.mp4")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t1:.3f}",
              "-i", str(body), *enc, str(pc)])
        parts.append(pc)
    lst = out.with_name(out.stem + "_list.txt")
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe",
          "0", "-i", str(lst), "-c", "copy", str(out)])
    return out


def _body_world(story_cfg: dict, cfg: dict, st, theme: dict, windows,
                work: Path) -> Path:
    """Render the whole video body as ONE take through the story's world,
    then splice Blender heroes over their waypoint windows."""
    world = story_cfg["world"]
    seg_cfgs = list(story_cfg.get("segments", []))
    wps = []
    for i, wp in enumerate(world.get("waypoints", [])):
        wp = dict(wp)
        seg = seg_cfgs[i] if i < len(seg_cfgs) else {}
        wp.setdefault("params", {})
        if "file" not in wp["params"] and seg.get("params", {}).get("file"):
            wp["params"]["file"] = seg["params"]["file"]
        if "emotion" not in wp and seg.get("emotion"):
            wp["emotion"] = seg["emotion"]     # emotion seed (§7.5 v4)
        wps.append(wp)
    # THE DIRECTOR (§7.5 v8): premium frames are allocated by narrative
    # value BEFORE the world spec is written — the engine executes the
    # plan (breach, consequence, grants) and its ledger tells us where
    # to cut. Chart beats after the first environment grant physicalize
    # (mode=in_world). Every decision is on the record.
    from data_learning.render_director import plan_heroes
    hero_plans, dreport = plan_heroes(world, wps, windows)
    for i, plan in hero_plans.items():
        wps[i]["hero_plan"] = plan
    for i in dreport.get("in_world_beats", []):
        wps[i].setdefault("params", {})["mode"] = "in_world"
    (work / "director_report.json").write_text(json.dumps(dreport,
                                                          indent=1))
    spec = {
        "title": st.title,
        # On-screen closing is the takeaway line ONLY (text diet) — the
        # narration still speaks the engagement question over the exit.
        "closing": st.closing,
        "theme": {"bg": _hex_grad0(theme),
                  "highlight": theme.get("highlight", "#4FD1C5"),
                  "accent": theme.get("accent", "#60A5FA")},
        "windows": [[round(a, 3), round(b, 3)] for a, b in windows],
        # Questions engine (§7.5 v6): a beat's chrome shows the QUESTION
        # it answers (while its payoff plants the next one) — the story
        # is a chain of questions, not a sequence of scenes.
        "chrome": [{"role": s.role,
                    "topic": (seg_cfgs[j].get("question", s.topic)
                              if j < len(seg_cfgs) else s.topic)}
                   for j, s in enumerate(st.segments)],
        "world": {"template": world.get("template", "depth"),
                  "story_template": world.get("story_template", ""),
                  "cold_open": world.get("cold_open"),
                  "waypoints": wps},
    }
    spec_path = work / "world_spec.json"
    spec_path.write_text(json.dumps(spec))
    media = work / "worldmedia"
    env = dict(os.environ, CURIO_WORLD_SPEC=str(spec_path),
               CURIO_WORLD_LOG=str(work / "world_ledger.json"))
    subprocess.run(
        [sys.executable, "-m", "manim", "render",
         "-ql" if os.environ.get("CURIO_REGRESSION") else "-qm",
         "--fps", str(FPS),
         "-r", f"{W},{H}", "--media_dir", str(media), "-o", "body.mp4",
         "-v", "ERROR", str(PKG_DIR / "world_engine.py"), "WorldScene"],
        check=True, env=env, capture_output=True, text=True)
    hits = list(media.glob("videos/**/body.mp4"))
    if not hits:
        raise FileNotFoundError("world engine produced no body.mp4")
    body = hits[0]
    # Conform to the narration length exactly.
    total = windows[-1][1]
    conformed = work / "body_conformed.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(body),
          "-vf", f"fps={FPS},tpad=stop_mode=clone:stop_duration=2,"
                 f"format=yuv420p",
          "-t", f"{total:.3f}", "-r", str(FPS),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
          str(conformed)])
    body = conformed
    # Blender heroes: the director chose them; the ENGINE chose when.
    # Each planned beat hero has a `breach` ledger row — its t+rt is the
    # splice cut (the fade lands mid-dive, never on an unrelated cut).
    # No breach row means the engine logged skipped:hero; we drop the
    # job and the QA gate decides whether that's fatal.
    world_rows = json.loads(
        (work / "world_ledger.json").read_text()).get("rows", [])
    jobs = []
    if os.environ.get("CURIO_REGRESSION"):
        hero_plans = {}          # Cycles is the premium tier's bill
    for i, plan in sorted(hero_plans.items()):
        br = next((r for r in world_rows if r.get("kind") == "breach"
                   and r.get("hero") == plan["id"]), None)
        if br is None:
            print(f"[longform] hero {plan['id']} not breached by the "
                  "engine — window too small; the gate will judge")
            continue
        t0 = float(br["t"]) + float(br.get("rt", 0.0))
        h_end = min(t0 + float(plan["splice"]), total - 0.5)
        wp = wps[i]
        seg = {**(seg_cfgs[i] if i < len(seg_cfgs) else {}), **wp}
        # stamp overlay: the beat's number stays on screen during its
        # premium window (mute test holds through the hero)
        params = wp.get("params") or {}
        hc = (wp.get("hero_candidate")
              or (wp.get("hero") if isinstance(wp.get("hero"), dict)
                  else None) or {})
        stamp = (hc.get("stamp") or params.get("display"),
                 hc.get("stamp_label") or params.get("label"))
        jobs.append((f"beat {i + 1}", plan["template"],
                     float(plan["seconds"]), seg, t0, h_end, i,
                     stamp, False))
    # World heroes: the hook and the ending get premium windows too
    # (window: "cold_open" | "ending"; end_offset keeps the vector
    # layer's finale — the returning counter — on screen after it).
    for j, hz in enumerate([] if os.environ.get("CURIO_REGRESSION")
                           else (world.get("heroes", []) or [])):
        template = str(hz.get("template", "monoliths"))
        secs = float(hz.get("seconds", HERO_SECONDS))
        if hz.get("window") == "cold_open":
            t0 = windows[0][0]
            h_end = min(windows[0][1], t0 + secs * 1.1)
        elif hz.get("window") == "ending":
            h_end = total - float(hz.get("end_offset", 0.0))
            t0 = max(windows[-1][0] - 8.0, h_end - secs * 1.1)
        else:
            continue
        # the cold-open hero carries the TITLE; the ending hero stays
        # clean (the returning counter follows it in the vector layer)
        stamp = ((st.title, None) if hz.get("window") == "cold_open"
                 else (hz.get("stamp"), hz.get("stamp_label")))
        jobs.append((f"{hz.get('window')}", template, secs,
                     dict(hz), t0, h_end, f"w{j}", stamp,
                     hz.get("window") == "cold_open"))
    for name, template, secs, seg, t0, h_end, idx, stamp, as_title in jobs:
        for attempt in (1, 2):
            try:
                hero = _hero_clip(template, seg, theme, h_end - t0, work,
                                  idx, seconds=secs,
                                  breach=isinstance(idx, int))
                if stamp and stamp[0]:
                    png = work / f"stamp{idx}.png"
                    _stamp_png(str(stamp[0]), stamp[1], theme, png,
                               title=as_title)
                    stamped = work / f"herostamped{idx}.mp4"
                    _run(["ffmpeg", "-y", "-loglevel", "error",
                          "-i", str(hero), "-i", str(png),
                          "-filter_complex",
                          "[0:v][1:v]overlay=0:0,format=yuv420p",
                          "-r", str(FPS), "-c:v", "libx264", "-preset",
                          "veryfast", "-crf", "18", "-an", str(stamped)])
                    hero = stamped
                body = _splice(body, hero, t0, h_end,
                               work / f"spliced{idx}.mp4")
                print(f"[longform] world hero '{template}' ({secs:.0f}s) "
                      f"spliced over {name}")
                break
            except Exception as e:  # noqa: BLE001 — a hero is never fatal
                print(f"[longform] hero splice {name} attempt {attempt} "
                      f"FAILED ({e})"
                      + ("" if attempt == 1 else
                         " — world take keeps its own window"),
                      file=sys.stderr)

    # EVIDENCE SHOTS (§7.5 v7): real imagery cuts the hero moments —
    # animation explains, evidence grounds. NASA-first with the on-topic
    # gate; a beat whose evidence can't pass keeps its animation.
    from data_learning.evidence import fetch_evidence
    ev_rows, ev_credits, ev_tiles = [], [], []
    for i, wp in enumerate(wps):
        for j, ev in enumerate((wp.get("evidence") or [])[:2]):
            t0w, t1w = windows[i + 1]
            secs = min(4.0, max(2.0, float(ev.get("seconds", 3.0))))
            e0 = max(t0w + 1.0,
                     min(t0w + (t1w - t0w) * float(ev.get("at", 0.5)),
                         t1w - secs - 1.0))
            label = str(ev.get("nasa_id") or ev.get("query") or "?")
            try:
                kind, src, credit = fetch_evidence(ev, work, f"{i}_{j}")
                if kind == "image":
                    norm = work / f"evnorm{i}_{j}.jpg"
                    _run(["ffmpeg", "-y", "-loglevel", "error", "-i",
                          str(src), "-vf",
                          "scale=2400:1350:force_original_aspect_ratio="
                          "increase,crop=2400:1350", str(norm)])
                    kb = _kenburns_clip(norm, secs, i + j,
                                        work / f"evkb{i}_{j}.mp4")
                else:
                    kb = work / f"evkb{i}_{j}.mp4"
                    _run(["ffmpeg", "-y", "-loglevel", "error", "-i",
                          str(src), "-t", f"{secs:.2f}", "-vf",
                          f"scale={W}:{H}:force_original_aspect_ratio="
                          f"increase,crop={W}:{H},fps={FPS}", "-an",
                          "-c:v", "libx264", "-preset", "veryfast",
                          "-crf", "18", str(kb)])
                clip = work / f"evclip{i}_{j}.mp4"
                _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(kb),
                      "-vf", f"fade=t=in:st=0:d=0.25,fade=t=out:"
                      f"st={secs - 0.25:.2f}:d=0.25,format=yuv420p",
                      "-t", f"{secs:.2f}", "-r", str(FPS),
                      "-c:v", "libx264", "-preset", "veryfast",
                      "-crf", "18", "-an", str(clip)])
                body = _splice(body, clip, e0, e0 + secs,
                               work / f"evsp{i}_{j}.mp4")
                ev_rows.append({"t": round(e0, 2), "kind": "evidence",
                                "beat": i, "rt": secs, "what": label})
                ev_credits.append(credit)
                if kind == "image":
                    ev_tiles.append((src, label, e0))
                print(f"[longform] evidence '{label}' cut into "
                      f"beat {i + 1} at {e0:.1f}s")
            except Exception as e:  # noqa: BLE001 — never fatal
                print(f"[longform] evidence '{label}' beat {i + 1} "
                      f"skipped ({e}) — a wrong picture is worse than "
                      "no picture", file=sys.stderr)
    if ev_rows:
        lp = work / "world_ledger.json"
        if lp.exists():
            led = json.loads(lp.read_text())
            led["rows"].extend(ev_rows)
            led["rows"].sort(key=lambda r: r.get("t", 0))
            lp.write_text(json.dumps(led, indent=1))
        (work / "evidence_credits.json").write_text(
            json.dumps(ev_credits, indent=1))
        _evidence_sheet(ev_tiles, work / "evidence_sheet.png")
    return body


def _stamp_png(big: str, small, theme: dict, out: Path,
               title: bool = False) -> None:
    """Brand-font overlay for hero windows: the number (or title) rides
    the premium shot so the mute test never dips (§7.5 v7). Stroked for
    readability over bright 3D frames."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    hi = theme.get("highlight", "#4FD1C5")
    stroke = dict(stroke_width=4, stroke_fill=(8, 10, 20, 230))
    if title:
        fb = _font(76)
        tw = d.textlength(big, font=fb)
        d.text(((W - tw) / 2, H * 0.08), big, font=fb, fill="#ffffff",
               **stroke)
    else:
        fb, fs = _font(72), _font(34)
        tw = d.textlength(big, font=fb)
        x, y = W - max(tw, 200) - 90, H - 190
        if small:
            d.text((x, y - 48), str(small), font=fs, fill="#c7cede",
                   **stroke)
        d.text((x, y), big, font=fb, fill=hi, **stroke)
    im.save(out)


def _evidence_sheet(tiles, out: Path) -> None:
    """Eye-QA contact sheet: every accepted evidence image with its
    query and landing timestamp — wrong imagery dies at preview."""
    if not tiles:
        return
    from PIL import Image, ImageDraw
    tw, th, cap = 640, 360, 44
    cols = min(3, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, (th + cap) * rows), "#101626")
    draw = ImageDraw.Draw(sheet)
    font = _font(26)
    for k, (src, label, t0) in enumerate(tiles):
        x, y = (k % cols) * tw, (k // cols) * (th + cap)
        try:
            im = Image.open(src).convert("RGB")
            im.thumbnail((tw, th))
            sheet.paste(im, (x + (tw - im.width) // 2,
                             y + (th - im.height) // 2))
        except Exception:  # noqa: BLE001
            pass
        draw.text((x + 12, y + th + 8), f"{label}  @ {t0:.0f}s",
                  fill="#e8ecf4", font=font)
    sheet.save(out)


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


def _srt_ts(t: float) -> str:
    ms = int(round(t * 1000))
    return (f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:"
            f"{ms // 1000 % 60:02d},{ms % 1000:03d}")


def write_srt(sentences: list[str], windows, out: Path) -> Path:
    """Uploadable captions: each sentence's window is split into ~8-word
    cues, time allocated proportional to character count (no word-level
    timestamps needed — proportional split tracks TTS pacing closely)."""
    cues = []
    for sent, (t0, t1) in zip(sentences, windows):
        words = sent.split()
        chunks = [" ".join(words[i:i + 8]) for i in range(0, len(words), 8)]
        total_chars = sum(len(c) for c in chunks) or 1
        t = t0
        for c in chunks:
            d = (t1 - t0 - 0.15) * len(c) / total_chars
            cues.append((t, min(t + d, t1), c))
            t += d
    lines = []
    for i, (a, b, text) in enumerate(cues, 1):
        lines += [str(i), f"{_srt_ts(a)} --> {_srt_ts(b)}", text, ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


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
        # breathing gaps (§7.5 v7): hook and closing never hold; segments
        # may declare "hold": N seconds of narration silence after them
        holds = [0.0] + [float(s.get("hold", 0.0))
                         for s in story_cfg.get("segments", [])] + [0.0]
        narration, windows = synth_narration(sentences, work, voice,
                                             holds=holds)
        total = windows[-1][1]
        write_srt(sentences, windows, out_path.with_suffix(".srt"))

        # THE SIMULATION ENGINE (one place, one camera, one take) is the
        # primary body renderer; the clip-per-beat path below is the loud
        # fallback so a world failure can never mean no video.
        video = None
        if story_cfg.get("world"):
            try:
                video = _body_world(story_cfg, cfg, st, theme, windows, work)
                print("[longform] body: world engine (one take)")
                lg = work / "world_ledger.json"
                if lg.exists():   # for scripts/qa_escalation.py
                    shutil.copy(lg, out_path.with_suffix(".ledger.json"))
                es = work / "evidence_sheet.png"
                if es.exists():   # eye-QA: on-topic check before publish
                    shutil.copy(es, out_path.with_suffix(".evidence.png"))
                dr = work / "director_report.json"
                if dr.exists():   # the premium-budget decision record
                    shutil.copy(dr, out_path.with_suffix(".director.json"))
            except Exception as e:  # noqa: BLE001
                print(f"[longform] WORLD ENGINE FAILED ({e}) — falling back "
                      "to clip-per-beat renderer", file=sys.stderr)
        if video is not None:
            return _finish(out_path, st, theme, cfg, work, video, narration,
                           windows, total)

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
            # Real footage plays while the narration sets the beat up...
            broll, used = _broll_parts(seg_cfg, seg, theme, dur, work, i)
            payoff_dur = dur - used
            # ...then the cut lands on the data payoff with the number.
            clip = None
            if seg_cfg.get("hero") and have_blender:
                try:
                    clip = _fit_clip(_hero_beat(seg_cfg, seg, theme, work, i),
                                     payoff_dur, work / f"c{i + 1}.mp4")
                    print(f"[longform] beat {i + 1}: blender hero"
                          + (f" (+{used:.1f}s b-roll)" if used else ""))
                except Exception as e:  # noqa: BLE001
                    print(f"[longform] beat {i + 1}: hero FAILED ({e}) — "
                          "degrading to manim/still", file=sys.stderr)
            if clip is None and seg_cfg and have_manim:
                try:
                    clip = _fit_clip(_manim_beat(seg_cfg, seg, theme, work, i),
                                     payoff_dur, work / f"c{i + 1}.mp4")
                    print(f"[longform] beat {i + 1}: manim "
                          f"{seg_cfg.get('insight_type')}"
                          + (f" (+{used:.1f}s b-roll)" if used else ""))
                except Exception as e:  # noqa: BLE001
                    print(f"[longform] beat {i + 1}: manim FAILED ({e}) — "
                          "degrading to still", file=sys.stderr)
            if clip is None:
                clip = _still_beat(seg, theme, i + 1, len(st.segments),
                                   payoff_dur, work)
                print(f"[longform] beat {i + 1}: still fallback")
            clips.extend(broll)
            clips.append(clip)

        clips.append(_kenburns_clip(close_frame,
                                    windows[-1][1] - windows[-1][0],
                                    len(clips), work / "c_close.mp4"))
        listf = work / "clips.txt"
        listf.write_text("\n".join(f"file '{c}'" for c in clips) + "\n")
        video = work / "video.mp4"
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
              "-safe", "0", "-i", str(listf), "-c", "copy", str(video)])
        return _finish(out_path, st, theme, cfg, work, video, narration,
                       windows, total)


def _finish(out_path: Path, st, theme: dict, cfg: dict, work: Path,
            video: Path, narration: Path, windows, total: float) -> Path:
    """Shared tail for both body renderers: soundtrack, mux, chapters."""
    # Ledger-driven sound design (§7.5 v7): whooshes/impacts/shimmers on
    # the engine's own event timestamps + a sidechain-ducked bed that
    # swells in breathing gaps. Falls back to the plain mix when there is
    # no ledger (clip-per-beat path).
    audio = work / "mix.wav"
    ledger_path = work / "world_ledger.json"
    if ledger_path.exists():
        try:
            from data_learning.sound_design import build_soundtrack
            stk = build_soundtrack(
                json.loads(ledger_path.read_text()), narration, total,
                work, cfg.get("music_vibe", "cinematic"), st.slug)
            _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(stk),
                  "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000",
                  str(audio)])
        except Exception as e:  # noqa: BLE001 — sound is never fatal
            print(f"[longform] sound design FAILED ({e}) — plain mix",
                  file=sys.stderr)
            audio = work / "mix.wav"
        else:
            return _finish_mux(out_path, st, theme, work, video, audio,
                               windows, total)
    track = _music_track(cfg.get("music_vibe", "cinematic"), st.slug)
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
    return _finish_mux(out_path, st, theme, work, video, audio, windows,
                       total)


def _finish_mux(out_path: Path, st, theme: dict, work: Path, video: Path,
                audio: Path, windows, total: float) -> Path:
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
    sources = list(st.sources)
    evc = work / "evidence_credits.json"
    if evc.exists():   # image credits ride the description like data does
        sources += [f"Image: {c}" for c in json.loads(evc.read_text())]
    meta = {"slug": st.slug, "duration": round(total, 2),
            "chapters": chapters, "sources": sources}
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
