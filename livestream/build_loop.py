#!/usr/bin/env python3
"""Build a themed, seamless, branded background loop for a 24/7 livestream and
hand it off to an always-on encoder.

WEEKLY, low-frequency. Visuals are generated "semi-abstract scenes" (sky + sun/
moon glow + horizon silhouette + seasonal particles) from ffmpeg only — no
external media, no APIs — with the channel logo pinned on every frame. Fully
isolated from the main app: writes only under livestream/outbox/, never touches
make_short.py / the daily orchestrator / state/ / the catalog / the PAUSED switch.

Usage:
    python livestream/build_loop.py                      # seasonal theme, 30s loop
    python livestream/build_loop.py --theme holiday
    python livestream/build_loop.py --loop-seconds 60
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from shared.constants import H, W  # noqa: E402
from shared.shell import ffprobe_duration  # noqa: E402
from shared.visualgen import generate_scene_clip, overlay_logo  # noqa: E402

from livestream.branding import CHANNEL, ensure_logo  # noqa: E402
from livestream.handoff import TARGET, handoff  # noqa: E402
from livestream.themes import THEMES, Theme, theme_for_date  # noqa: E402

OUTBOX = HERE / "outbox"


def build(theme: Theme, loop_seconds: float, fps: int, now: datetime,
          render_scale: float = 1.0) -> tuple[Path, Path]:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d")
    scene = OUTBOX / f".scene_{theme.name}_{stamp}.mp4"
    loop_path = OUTBOX / f"loop_{theme.name}_{stamp}.mp4"

    print(f"[1/4] generating scene: {theme.name} — {theme.label} (render_scale={render_scale})")
    generate_scene_clip(scene, loop_seconds, theme.scene, fps=fps, workdir=OUTBOX,
                        render_scale=render_scale)

    print("[2/4] branding with channel logo")
    logo = ensure_logo()
    overlay_logo(
        scene, loop_path, logo,
        corner=CHANNEL.logo_corner, scale_w=CHANNEL.logo_scale_w,
        opacity=CHANNEL.logo_opacity, fps=fps,
    )
    scene.unlink(missing_ok=True)

    dur = ffprobe_duration(loop_path)
    print(f"[3/4] loop ready: {dur:.1f}s, {loop_path.stat().st_size} bytes, {W}x{H}@{fps}")
    manifest = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "channel": CHANNEL.name,
        "theme": theme.name,
        "label": theme.label,
        "scene": {
            "sky": [theme.scene.sky_top, theme.scene.sky_bottom],
            "glow_color": theme.scene.glow_color if theme.scene.glow else None,
            "particles": theme.scene.particles,
        },
        "loop_file": loop_path.name,
        "duration_seconds": round(dur, 3),
        "fps": fps,
        "resolution": f"{W}x{H}",
        "size_bytes": loop_path.stat().st_size,
        "seamless": True,
        "logo": logo.name,
        "handoff_target": TARGET,
        "note": (
            "Encoder must repeat this file 24/7 (e.g. ffmpeg -stream_loop -1) "
            "and push RTMP to YouTube. GitHub/cron cannot hold the stream open."
        ),
    }
    manifest_path = OUTBOX / f"loop_{theme.name}_{stamp}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return loop_path, manifest_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a themed seamless branded livestream loop.")
    ap.add_argument("--theme", choices=sorted(THEMES),
                    help="override the seasonal theme")
    ap.add_argument("--loop-seconds", type=float, default=60.0,
                    help="loop length in seconds (seamless by construction). Longer "
                         "= slower, calmer particle fall (one screen-height per loop).")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--render-scale", type=float, default=1.0,
                    help="composite the moving layers at this fraction of 1080x1920, "
                         "then upscale (1.0 = full quality; static layers prebaked so "
                         "full res is already ~2.4x faster, lower = extra speed, softer).")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    theme = THEMES[args.theme] if args.theme else theme_for_date(now.date())

    loop_path, manifest_path = build(theme, args.loop_seconds, args.fps, now,
                                     render_scale=args.render_scale)

    print("[4/4] handoff")
    handoff(loop_path, manifest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
