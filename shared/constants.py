"""Shared constants for the video pipeline.

Values are lifted verbatim from make_short.py so that code importing them
reproduces the exact same render math. Do not change these without re-running
tools/verify_identical.py — the daily money-maker depends on byte-identical
output.
"""
from __future__ import annotations

from pathlib import Path

# Repo root = parent of this shared/ package.
ROOT = Path(__file__).resolve().parent.parent
GAMEPLAY_DIR = ROOT / "gameplay"
OUTPUT_DIR = ROOT / "output"

# 9:16 canvas, split into two equal halves for the stacked layout.
W, H = 1080, 1920
HALF_H = H // 2

TTS_VOICE = "en-US-GuyNeural"

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".m4v", ".avi"}
