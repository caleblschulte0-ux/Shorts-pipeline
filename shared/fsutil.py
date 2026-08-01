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


def write_json_if_changed(path: str | Path, obj, *, indent: int = 2,
                          sort_keys: bool = False,
                          ensure_ascii: bool = True) -> bool:
    """Write only when the serialised content actually differs. Returns
    whether it wrote.

    `data_learning/niche.config.json` is 719 KB and every explainer run
    rewrote the whole thing, whether or not anything in it had changed. That
    is what made it a merge-conflict magnet: two concurrent runs that BOTH
    changed nothing still produced two conflicting 719 KB diffs, and
    `explainer.yml` had to carry a `--autostash -X ours` retry loop to ride
    it out.

    A no-op write is not free anywhere in this repo — it is a commit, a
    push, a potential conflict, and a line of noise in every future `git
    log -p`. Same principle as `ask_fingerprint`: identity is the content,
    not the timestamp of the last time something looked at it.
    """
    path = Path(path)
    body = json.dumps(obj, indent=indent, sort_keys=sort_keys,
                      ensure_ascii=ensure_ascii) + "\n"
    try:
        if path.read_text(encoding="utf-8") == body:
            return False
    except (OSError, UnicodeDecodeError):
        pass                        # missing or unreadable — write it
    atomic_write_json(path, obj, indent=indent, sort_keys=sort_keys,
                      ensure_ascii=ensure_ascii)
    return True


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
