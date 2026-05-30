#!/usr/bin/env python3
"""Build a themed, seamless background loop for a 24/7 livestream and hand it
off to an always-on encoder.

WEEKLY, low-frequency. Visuals are generated abstract gradients (no external
media, no APIs). Fully isolated from the main app: writes only under
livestream/outbox/, never touches make_short.py / the daily orchestrator /
state/ / the catalog / the PAUSED switch.

Usage:
    python livestream/build_loop.py                      # seasonal theme, 30s base
    python livestream/build_loop.py --theme holiday
    python livestream/build_loop.py --base-seconds 60    # -> 120s seamless loop
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
from shared.visualgen import generate_abstract_clip, make_seamless_loop  # noqa: E402

from livestream.handoff import TARGET, handoff  # noqa: E402
from livestream.themes import THEMES, Theme, theme_for_date  # noqa: E402

OUTBOX = HERE / "outbox"


def build(theme: Theme, base_seconds: float, fps: int, now: datetime) -> tuple[Path, Path]:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d")
    base = OUTBOX / f".base_{theme.name}_{stamp}.mp4"
    loop_path = OUTBOX / f"loop_{theme.name}_{stamp}.mp4"

    print(f"[1/3] generating abstract clip: {theme.name} — {theme.label}")
    generate_abstract_clip(
        base, base_seconds, colors=theme.colors, speed=theme.speed, fps=fps
    )
    print(f"[2/3] assembling seamless loop -> {loop_path.name}")
    make_seamless_loop(base, loop_path, fps=fps)
    base.unlink(missing_ok=True)

    dur = ffprobe_duration(loop_path)
    manifest = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "theme": theme.name,
        "label": theme.label,
        "colors": list(theme.colors),
        "speed": theme.speed,
        "loop_file": loop_path.name,
        "duration_seconds": round(dur, 3),
        "fps": fps,
        "resolution": f"{W}x{H}",
        "size_bytes": loop_path.stat().st_size,
        "seamless": True,
        "handoff_target": TARGET,
        "note": (
            "Encoder must repeat this file 24/7 (e.g. ffmpeg -stream_loop -1) "
            "and push RTMP to YouTube. GitHub/cron cannot hold the stream open."
        ),
    }
    manifest_path = OUTBOX / f"loop_{theme.name}_{stamp}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"      loop: {dur:.1f}s, {manifest['size_bytes']} bytes, {W}x{H}@{fps}")
    return loop_path, manifest_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a themed seamless livestream loop.")
    ap.add_argument("--theme", choices=sorted(THEMES),
                    help="override the seasonal theme")
    ap.add_argument("--base-seconds", type=float, default=30.0,
                    help="base clip length in seconds; the seamless loop is 2x this")
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    theme = THEMES[args.theme] if args.theme else theme_for_date(now.date())

    loop_path, manifest_path = build(theme, args.base_seconds, args.fps, now)

    print("[3/3] handoff")
    handoff(loop_path, manifest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
