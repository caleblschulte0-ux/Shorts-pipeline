"""Shell + ffprobe helpers, lifted verbatim from make_short.py."""
from __future__ import annotations

import subprocess
from pathlib import Path


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command, streaming output unless capture=True."""
    if capture:
        return subprocess.run(cmd, check=True, capture_output=True, text=True)
    return subprocess.run(cmd, check=True)


def ffprobe_duration(path: Path) -> float:
    out = run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1",
            str(path),
        ],
        capture=True,
    ).stdout.strip()
    return float(out)
