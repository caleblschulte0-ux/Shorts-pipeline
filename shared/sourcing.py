"""Source acquisition stage — yt-dlp download or local file copy.

Lifted verbatim from make_short.py.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from .constants import VIDEO_EXTS
from .shell import run


def is_url(s: str) -> bool:
    return bool(re.match(r"^https?://", s))


def download_source(url_or_file: str, workdir: Path) -> Path:
    if not is_url(url_or_file):
        src = Path(url_or_file).expanduser().resolve()
        if not src.exists():
            sys.exit(f"input not found: {src}")
        dst = workdir / f"source{src.suffix}"
        shutil.copy2(src, dst)
        return dst

    out_tmpl = str(workdir / "source.%(ext)s")
    run([
        "yt-dlp",
        "--no-playlist",
        "--quiet", "--no-warnings",
        "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", out_tmpl,
        url_or_file,
    ])
    for p in workdir.iterdir():
        if p.stem == "source" and p.suffix.lower() in VIDEO_EXTS:
            return p
    sys.exit("yt-dlp did not produce a source video")
