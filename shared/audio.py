"""Audio mixing stage — duck source under the voiceover, or pass source through.

Lifted verbatim from make_short.py.
"""
from __future__ import annotations

from pathlib import Path

from .shell import run


def mix_audio(source: Path, voice: Path | None, workdir: Path) -> Path:
    """Return a wav with source audio (ducked) + voiceover, or just source audio."""
    mixed = workdir / "audio.wav"
    if voice is None:
        run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(source),
            "-vn", "-ac", "2", "-ar", "44100",
            str(mixed),
        ])
        return mixed
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(source),
        "-i", str(voice),
        "-filter_complex",
        "[0:a]volume=0.25[src];[1:a]volume=1.6[vo];[src][vo]amix=inputs=2:duration=longest:dropout_transition=0[a]",
        "-map", "[a]",
        "-ac", "2", "-ar", "44100",
        str(mixed),
    ])
    return mixed
