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
    """Read JSON, returning `default` when missing or corrupt.

    This is the TOLERANT loader — for expendable caches, quota counters and
    reports, where the worst case of "corrupt read as empty" is a re-fetch
    or a noisier report. It must NEVER read authoritative state: a posted
    log or ledger that reads as empty means duplicate uploads or a bypassed
    gate. Those callers use `load_state_json`, which keeps default-on-missing
    (first runs must work) but fails CLOSED on corruption."""
    path = Path(path)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:  # noqa: BLE001 — a corrupt CACHE must not break a run
            pass
    return default


class CorruptStateError(RuntimeError):
    """An AUTHORITATIVE state file exists but cannot be read as what it
    claims to be. Deliberately NOT caught anywhere in the pipeline: the only
    correct handler is the operator restoring the file."""


def load_state_json(path: str | Path, default, *, expect_type: type | None = None):
    """Read AUTHORITATIVE state: absence returns `default`, corruption RAISES.

    The distinction this module's header warns about (corrupt log -> dedupe
    blind -> duplicate upload) is exactly the one `load_json` erases: it
    returns the caller's empty default for a missing file AND for a
    truncated/mangled one. A missing posted-log is a first run and the
    default is honest; a corrupt posted-log is an emergency, and treating it
    as empty re-uploads the catalogue and then lets the writer replace 100+
    real entries with this run's handful. So:

    - file missing            -> `default` (first runs keep working)
    - unreadable / unparseable / wrong top-level type (`expect_type`)
                              -> the bad bytes are preserved as
                                 `<name>.corrupt` beside the file and
                                 CorruptStateError is raised, naming the
                                 file, the reason, and the repair.

    Do not catch CorruptStateError to "keep the run going" — a run without
    its dedupe state must not run. Fix the file (usually
    `git checkout <last-good-commit> -- <path>`), then re-run.
    """
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return default
    except OSError as e:
        # Exists-but-unreadable (permissions, path is a directory, I/O
        # error) is NOT absence — returning `default` here would be the
        # exact corrupt-reads-as-empty bug this loader exists to close.
        raise CorruptStateError(
            f"REFUSING to run: authoritative state {path} exists but cannot "
            f"be read ({e}). A ledger that cannot be read must not be "
            f"treated as empty — fix the file or its permissions, then "
            f"re-run.")
    reason = None
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001 — any parse failure is corruption
        obj, reason = None, f"not valid JSON: {e}"
    if reason is None and expect_type is not None \
            and not isinstance(obj, expect_type):
        reason = (f"wrong shape: expected {expect_type.__name__}, "
                  f"got {type(obj).__name__}")
    if reason is None:
        return obj
    # Preserve the evidence BEFORE refusing: the operator (or a later
    # session) repairs from the bad bytes plus git history, and the next
    # run must not find them already overwritten by a "fix". Best-effort —
    # failing to write the sidecar must not mask the refusal itself.
    sidecar = path.with_name(path.name + ".corrupt")
    try:
        sidecar.write_bytes(raw)
        preserved = f"the bad bytes are preserved at {sidecar}"
    except OSError:
        preserved = "the bad bytes could not be copied aside — do not edit in place"
    raise CorruptStateError(
        f"REFUSING to run: authoritative state {path} is corrupt "
        f"({reason}). Reading it as empty would mean duplicate uploads or "
        f"a bypassed gate, so this fails CLOSED. {preserved}. Restore the "
        f"file from git history (git log --oneline -- {path.name}; "
        f"git checkout <good-commit> -- <path>) and re-run. A genuinely "
        f"missing file would have returned the default — only corruption "
        f"refuses.")
