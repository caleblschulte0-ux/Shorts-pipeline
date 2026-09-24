"""WHICH LOOK A VIDEO IS DRAWN IN — the explainer's A/B split.

Operator, 2026-09-23: *"that 2D animation, I want to start A/B testing that
on the mascot channel."* The split is POLICY, so it lives where every other
piece of channel policy lives: `config/channel_registry.json`, as
`style_arms` on the explainer's `data_story` format — a weight per arm.

    "style_arms": {"current": <weight>, "illustrated": <weight>}

`choose(slug)` is deterministic per slug (a re-render of the same story is
the same arm, so a held story that is repaired stays in its arm), and
`EXPLAINER_STYLE=<arm>` overrides it for a preview. Every render writes the
arm it used beside the mp4 (`<mp4>.style.json`), and the posting step copies
it into the posted-log entry and the verdict ledger, so the retro can compare
the arms by outcome.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ARMS = ("current", "illustrated")
DEFAULT = "current"
REPO = Path(__file__).resolve().parent.parent


def weights(reg: dict | None = None) -> dict:
    """{arm: weight} from the registry; {'current': 1.0} when absent."""
    try:
        if reg is None:
            reg = json.loads((REPO / "config" / "channel_registry.json").read_text())
        fmt = reg["channels"]["explainer"]["formats"]["data_story"]
        raw = fmt.get("style_arms") or {}
    except Exception:  # noqa: BLE001 — no registry: the current look, always
        raw = {}
    out = {a: float(raw[a]) for a in ARMS
           if isinstance(raw.get(a), (int, float)) and raw[a] > 0}
    return out or {DEFAULT: 1.0}


def problems(raw) -> list[str]:
    """What is wrong with a `style_arms` block. Empty means usable."""
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return ["style_arms must be an object of {arm: weight}"]
    out = []
    for k, v in raw.items():
        if k == "note":
            continue
        if k not in ARMS:
            out.append(f"style_arms: unknown arm {k!r} (known: {ARMS})")
        elif not isinstance(v, (int, float)) or v < 0:
            out.append(f"style_arms.{k}: weight must be a number >= 0")
    if not any(isinstance(v, (int, float)) and v > 0
               for k, v in raw.items() if k in ARMS):
        out.append("style_arms: every weight is 0 — no arm could be chosen")
    return out


def choose(slug: str, reg: dict | None = None) -> str:
    forced = os.environ.get("EXPLAINER_STYLE", "").strip().lower()
    if forced in ARMS:
        return forced
    w = weights(reg)
    total = sum(w.values())
    u = int(hashlib.sha1(f"style:{slug}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    acc = 0.0
    for arm in ARMS:
        if arm in w:
            acc += w[arm] / total
            if u <= acc:
                return arm
    return next(iter(w))


def quota(per_day: int, reg: dict | None = None) -> dict:
    """{arm: videos a day} — the split applied to the SLATE, not only to the
    queue. Assigning arms per story was not enough: the old look was held by
    the gate all day, so the new look filled every slot and "50/50" shipped
    4-0 (operator, 2026-09-23: "two of A, two of B"). Largest remainder, so
    the counts always add up to per_day."""
    w = weights(reg)
    total = sum(w.values()) or 1.0
    raw = {a: per_day * w[a] / total for a in w}
    out = {a: int(v) for a, v in raw.items()}
    for a in sorted(raw, key=lambda a: (raw[a] - out[a], a), reverse=True):
        if sum(out.values()) >= per_day:
            break
        out[a] += 1
    return out


def sidecar(mp4: Path) -> Path:
    return Path(mp4).with_suffix(".style.json")


def read(mp4: Path) -> dict:
    """What the render recorded about its arm; {} when nothing was written."""
    try:
        return json.loads(sidecar(mp4).read_text())
    except Exception:  # noqa: BLE001
        return {}
