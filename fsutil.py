"""Atomic file helpers shared by every state writer (audit Ticket 2).

A crash mid-`write_text()` leaves a truncated JSON file — fatal when the
file is a posted-log (corrupt log -> dedupe blind -> duplicate upload).
`atomic_write_json` writes to a temp file in the SAME directory and
`os.replace`s it into place: readers see the old bytes or the new bytes,
never a torn write. Modeled on media_funnel._save_json, the one writer in
the repo that already did this correctly.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: str | Path, obj, *, indent: int = 2,
                      sort_keys: bool = False, ensure_ascii: bool = True) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent),
                               prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=indent, sort_keys=sort_keys,
                      ensure_ascii=ensure_ascii)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_json(path: str | Path, default):
    """Read JSON, returning `default` when missing or corrupt — the loader
    every posted-log already implements ad hoc."""
    path = Path(path)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:  # noqa: BLE001 — corrupt state must not break a run
            pass
    return default
