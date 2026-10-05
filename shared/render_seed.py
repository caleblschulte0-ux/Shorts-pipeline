"""Deterministic, attributable randomness for the renderers.

Doctor finding 66d90578bc9b: the three renderers called the module-global
``random`` for gameplay file / seek choices, so a re-render after a
showrunner block changed the background footage independently of the repair
and nothing recorded what was chosen.

Contract: ``begin(identity, attempt)`` opens a render context.  Every choice
goes through ``rng(purpose)`` (a fresh ``random.Random`` seeded from
identity + attempt + purpose, so the same package and attempt always make the
same choices, and a new attempt changes them deliberately).  ``note()``
records what was picked; ``manifest()`` is written into the audit sidecar.

``attempt`` defaults to env ``RENDER_ATTEMPT`` (0 when unset).
"""
from __future__ import annotations

import hashlib
import json
import os
import random

VERSION = 1
_state: dict = {"identity": "", "attempt": 0, "choices": []}


def identity_of(obj) -> str:
    """Stable hash of a package/script (dicts are key-sorted)."""
    if isinstance(obj, str):
        raw = obj
    else:
        raw = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def begin(identity, attempt: int | None = None) -> None:
    if attempt is None:
        try:
            attempt = int(os.environ.get("RENDER_ATTEMPT", "0") or 0)
        except ValueError:
            attempt = 0
    _state.update(identity=identity_of(identity), attempt=int(attempt),
                  choices=[])


def rng(purpose: str) -> random.Random:
    seed = hashlib.sha256(
        f"{_state['identity']}|{_state['attempt']}|{purpose}".encode()
    ).digest()
    return random.Random(int.from_bytes(seed[:8], "big"))


def note(purpose: str, **fields) -> None:
    _state["choices"].append({"purpose": purpose, **fields})


def manifest() -> dict:
    return {"version": VERSION, "identity": _state["identity"],
            "attempt": _state["attempt"], "choices": list(_state["choices"])}
