"""Cross-video media usage ledger — stops the same photo airing in video
after video.

Until now nothing tracked which media appeared in PREVIOUS videos: the
entity cache pinned one Wikipedia photo per subject forever and the news
cache returned identical candidates for 48h, so repeat subjects (recurring
animals, ongoing stories) kept opening on the same image. This ledger
records every funnel-chosen URL and lets scorers penalize recent reuse —
a soft penalty, not a hard ban, so a genuinely-only photo still beats a
placeholder slate.

State lives in state/media_usage.json (committed by the daily persist
step like the rest of state/), capped FIFO so it can't grow unbounded.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from fsutil import atomic_write_json, load_json

ROOT = Path(__file__).resolve().parent
LEDGER_PATH = ROOT / "state" / "media_usage.json"

MAX_ENTRIES = 3000
RECENT_DAYS = 14
REUSE_PENALTY = 0.25


def _key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8", "ignore")).hexdigest()[:16]


def _load() -> dict:
    d = load_json(LEDGER_PATH, {})
    return d if isinstance(d, dict) else {}


def record(url: str, slug: str = "") -> None:
    """Mark `url` as aired (call when a candidate is actually chosen,
    not merely fetched). Best-effort — never raises."""
    if not url:
        return
    try:
        d = _load()
        used = d.setdefault("used", {})
        used[_key(url)] = {"slug": slug, "at": time.time()}
        if len(used) > MAX_ENTRIES:
            for k in sorted(used, key=lambda k: used[k].get("at", 0))[
                    :len(used) - MAX_ENTRIES]:
                del used[k]
        atomic_write_json(LEDGER_PATH, d, sort_keys=True)
    except Exception as e:  # noqa: BLE001 — bookkeeping must never kill a render
        print(f"  [media_usage] record failed: {e}")


def used_recently(url: str, days: int = RECENT_DAYS) -> bool:
    if not url:
        return False
    try:
        rec = _load().get("used", {}).get(_key(url))
        return bool(rec) and (time.time() - rec.get("at", 0)) < days * 86400
    except Exception:  # noqa: BLE001
        return False


def penalty(url: str) -> float:
    """Score penalty for scorers: REUSE_PENALTY if aired in the last
    RECENT_DAYS, else 0. Soft — a repeat still beats junk/placeholder."""
    return REUSE_PENALTY if used_recently(url) else 0.0
