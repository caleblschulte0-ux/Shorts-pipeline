"""Gameplay-loop selection + trim stage.

Lifted verbatim from make_short.py. The gameplay directory is a parameter
(defaulting to the repo's gameplay/ folder) so other entry points can point
at their own loop libraries without changing the main app's behavior.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from .constants import GAMEPLAY_DIR, VIDEO_EXTS
from .shell import ffprobe_duration, run


def list_gameplay(tag: str, gameplay_dir: Path = GAMEPLAY_DIR) -> list[Path]:
    if not gameplay_dir.exists():
        return []
    files = [p for p in gameplay_dir.iterdir() if p.suffix.lower() in VIDEO_EXTS]
    if tag == "random":
        return files
    return [p for p in files if tag.lower() in p.stem.lower()]


def pick_gameplay(
    tag: str,
    target_seconds: float,
    workdir: Path,
    gameplay_dir: Path = GAMEPLAY_DIR,
) -> Path:
    pool = list_gameplay(tag, gameplay_dir)
    if not pool:
        sys.exit(
            f"no gameplay clips matching '{tag}' in {gameplay_dir}. "
            f"Run: python seed_gameplay.py"
        )
    clip = random.choice(pool)
    clip_dur = ffprobe_duration(clip)
    if clip_dur <= target_seconds + 0.1:
        return clip
    start = random.uniform(0, clip_dur - target_seconds)
    trimmed = workdir / "gameplay_trim.mp4"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.3f}",
        "-i", str(clip),
        "-t", f"{target_seconds:.3f}",
        "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        str(trimmed),
    ])
    return trimmed
