#!/usr/bin/env python3
"""Run a REAL command and record everything: the Proof Mode CLI capture.

This is the truthfulness layer (THIRD_BRAIN.md §0, §7): the video's
terminal replay, stopwatch, and before/after numbers all come from the
artifacts this module records — never from narration.

capture(cmd, ...) executes the command in a pseudo-terminal, records
timestamped output chunks, wall time, exit code, and sha256 hashes of
the input/output files, and writes a proof ledger JSON next to the
recording. The composer replays the recorded bytes at their true
timestamps; nothing on screen is invented.
"""
from __future__ import annotations

import hashlib
import json
import os
import pty
import select
import subprocess
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Capture:
    argv: list[str]
    cwd: str
    started_utc: str
    wall_time_s: float = 0.0
    exit_code: int = -1
    # [(t_offset_seconds, utf8_text_chunk), ...]
    events: list = field(default_factory=list)
    files: dict = field(default_factory=dict)   # label -> {path, sha256, bytes, rows}
    notes: dict = field(default_factory=dict)   # measured claims (row counts etc.)


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for blk in iter(lambda: fh.read(65536), b""):
            h.update(blk)
    return h.hexdigest()


def _csv_rows(p: Path) -> int:
    with p.open("rb") as fh:
        return max(0, sum(1 for _ in fh) - 1)   # minus header


def capture(argv: list[str], *, cwd: Path, shell_line: str | None = None) -> Capture:
    """Run argv in a pty, recording timestamped output. `shell_line` is the
    exact line shown being typed in the replay; it must be the same command
    (cosmetic path shortening only)."""
    cap = Capture(
        argv=argv, cwd=str(cwd),
        started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    cap.notes["shell_line"] = shell_line or " ".join(argv)
    master, slave = pty.openpty()
    t0 = time.monotonic()
    proc = subprocess.Popen(
        argv, cwd=str(cwd), stdin=slave, stdout=slave, stderr=slave,
        close_fds=True,
    )
    os.close(slave)
    while True:
        r, _, _ = select.select([master], [], [], 0.05)
        if r:
            try:
                data = os.read(master, 65536)
            except OSError:
                data = b""
            if data:
                cap.events.append(
                    (round(time.monotonic() - t0, 4),
                     data.decode("utf-8", "replace")))
            else:
                break
        if proc.poll() is not None and not r:
            break
    os.close(master)
    proc.wait()
    cap.wall_time_s = round(time.monotonic() - t0, 3)
    cap.exit_code = proc.returncode
    return cap


def record_file(cap: Capture, label: str, path: Path) -> None:
    entry = {"path": str(path), "sha256": _sha256(path),
             "bytes": path.stat().st_size}
    if path.suffix.lower() == ".csv":
        entry["rows"] = _csv_rows(path)
    cap.files[label] = entry


def save_ledger(cap: Capture, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asdict(cap), indent=2) + "\n")
    return out


def load_ledger(path: Path) -> dict:
    return json.loads(path.read_text())
