"""Render stage.

Two renderers live here:

1. compose()        — the MAIN APP'S renderer, lifted VERBATIM from
                      make_short.py. A single ffmpeg pass that stacks source
                      over gameplay, burns captions, and muxes audio. The
                      daily money-maker uses this and its output must remain
                      byte-identical (proven by tools/verify_identical.py).
                      Do not touch.

2. render_layered() — a NEW, additive renderer that produces the same kind of
                      stacked Short but as SEPARATE LAYERS in distinct passes:
                          background (silent stacked video)
                          -> caption burn
                          -> audio mux
                      It is NOT used by the main app and is NOT claimed to be
                      byte-identical to compose(). It exists so the livestream
                      and localize modules can reuse a background/timing and
                      re-run only the layer they need (e.g. localize re-runs
                      only captions + audio over a finished video's background).
"""
from __future__ import annotations

from pathlib import Path

from .constants import HALF_H, W
from .shell import run


# ---------- main app renderer (verbatim) ----------

def compose(source: Path, gameplay: Path, audio: Path, subs: Path, out: Path, duration: float) -> None:
    # Top half (source): scale-to-fit with a blurred zoomed copy filling any
    # leftover space — source aspect varies and we don't want to crop news /
    # sports / talking-head content.
    # Bottom half (gameplay): scale-to-fill + bias-low crop, no blur. For
    # landscape gameplay (e.g. Minecraft 16:9) the scaled height equals the
    # slot height so the y bias is a no-op and we get a clean fill. For
    # portrait gameplay (e.g. Subway Surfers 9:16) the player character
    # lives at ~75% from the top of the original frame, so a default center
    # crop chops it out — biasing y to 0.7 of the available range keeps the
    # character in frame and matches the standard brain-rot Shorts layout.
    subs_path = str(subs).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    vf = (
        f"[0:v]split=2[s0a][s0b];"
        f"[s0a]scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{HALF_H},boxblur=24:2,setsar=1[topbg];"
        f"[s0b]scale={W}:{HALF_H}:force_original_aspect_ratio=decrease,"
        f"setsar=1[topfg];"
        f"[topbg][topfg]overlay=(W-w)/2:(H-h)/2[top];"
        f"[1:v]scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{HALF_H}:0:'(ih-{HALF_H})*0.7',setsar=1[bot];"
        f"[top][bot]vstack=inputs=2[stacked];"
        f"[stacked]ass='{subs_path}'[v]"
    )
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(source),
        "-i", str(gameplay),
        "-i", str(audio),
        "-filter_complex", vf,
        "-map", "[v]", "-map", "2:a",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ])


# ---------- new layered renderer (additive, for livestream/localize) ----------

def render_background(source: Path, gameplay: Path, out: Path, duration: float) -> None:
    """Stacked source-over-gameplay visual with NO captions and NO audio.

    This is the reusable "background + timing" layer. localize keeps this byte
    for byte from a finished video and only re-runs the caption + audio layers.
    """
    vf = (
        f"[0:v]split=2[s0a][s0b];"
        f"[s0a]scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{HALF_H},boxblur=24:2,setsar=1[topbg];"
        f"[s0b]scale={W}:{HALF_H}:force_original_aspect_ratio=decrease,"
        f"setsar=1[topfg];"
        f"[topbg][topfg]overlay=(W-w)/2:(H-h)/2[top];"
        f"[1:v]scale={W}:{HALF_H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{HALF_H}:0:'(ih-{HALF_H})*0.7',setsar=1[bot];"
        f"[top][bot]vstack=inputs=2[v]"
    )
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(source),
        "-i", str(gameplay),
        "-filter_complex", vf,
        "-map", "[v]",
        "-an",
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out),
    ])


def burn_captions(visual: Path, subs: Path, out: Path) -> None:
    """Caption layer: burn an ASS file onto an existing (silent) visual."""
    subs_path = str(subs).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(visual),
        "-vf", f"ass='{subs_path}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        str(out),
    ])


def mux_audio_track(visual: Path, audio: Path, out: Path, duration: float) -> None:
    """Audio layer: mux an audio track onto a finished (silent) visual."""
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(visual),
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-t", f"{duration:.3f}",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ])


def render_layered(
    source: Path,
    gameplay: Path,
    audio: Path,
    subs: Path,
    out: Path,
    duration: float,
    workdir: Path,
) -> None:
    """Layer-separate equivalent of compose(): background -> captions -> audio,
    each in its own pass. Used by the new modules; NOT byte-identical to
    compose() and deliberately not used by the main app."""
    bg = workdir / "_layer_bg.mp4"
    capped = workdir / "_layer_caps.mp4"
    render_background(source, gameplay, bg, duration)
    burn_captions(bg, subs, capped)
    mux_audio_track(capped, audio, out, duration)
