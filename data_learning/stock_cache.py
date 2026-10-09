"""stock_cache — remember what a provider ANSWERED, so a blocked network can
still render.

The problem this solves is not a bad key. Pexels returns HTTP 200 to the same
key from a normal host and HTTP 403 from GitHub Actions runners: it refuses the
datacenter IP range, not the credential. Five consecutive films were therefore
built from Pixabay alone, and the beats whose subjects Pixabay does not serve
("open window curtain wind", "child running outdoors sunlight") found no moving
clip, fell back to a card, and left the stale spans the director then flagged.

A key cannot fix that, and neither can putting one in the repo — the credential
already arrives intact. What fixes it is doing the SEARCH somewhere the provider
answers, and letting the render reuse that answer.

Only the candidate LIST is cached — titles, licences and CDN urls, a few KB of
JSON. No media: the storage audit forbids committing binaries, and the clips
themselves come from the CDN, which is a different host from the API that does
the blocking.

Strictly a FALLBACK. A live call that succeeds is always preferred and refreshes
the cache, so a healthy provider behaves exactly as it did before this existed —
this can only ever add answers, never substitute stale ones for fresh.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "stock_cache"

SCHEMA = 2
# A fallback answer older than this is a guess about a CDN, not a fact. Live
# results always outrank it; this only bounds how long it may stand in.
MAX_AGE_S = 30 * 86400
# A candidate whose download failed this many times is evicted from its slot.
DEAD_AFTER = 2


def _slot(provider: str, query: str) -> Path:
    q = re.sub(r"[^a-z0-9]+", "-", str(query).lower()).strip("-")[:64]
    return ROOT / f"{provider}__{q or 'empty'}.json"


def load(provider: str, query: str, now: float | None = None) -> list[dict] | None:
    """Cached candidates for this query, or None if never fetched, expired, or
    written before records carried a fetch time (age unknown = not trusted)."""
    p = _slot(provider, query)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
        fetched = d.get("fetched_at")
        if d.get("schema") != SCHEMA or not isinstance(fetched, (int, float)):
            return None
        if (time.time() if now is None else now) - fetched > MAX_AGE_S:
            return None
        dead = d.get("failures") or {}
        c = [x for x in d.get("candidates") or []
             if isinstance(x, dict) and dead.get(x.get("url"), 0) < DEAD_AFTER]
        return c or None
    except Exception:  # noqa: BLE001 — a corrupt slot is a miss, never a crash
        return None


def save(provider: str, query: str, candidates: list[dict],
         now: float | None = None) -> None:
    """Record a LIVE answer. Empty answers are not cached — a provider that
    genuinely has nothing for a query should be re-asked later, not frozen.
    A fresh live answer resets the fetch time and the failure counts."""
    if not candidates:
        return
    try:
        ROOT.mkdir(parents=True, exist_ok=True)
        _slot(provider, query).write_text(json.dumps(
            {"schema": SCHEMA, "provider": provider, "query": query,
             "fetched_at": time.time() if now is None else now,
             "failures": {}, "candidates": candidates}, indent=2) + "\n")
    except Exception:  # noqa: BLE001 — caching is best-effort by definition
        pass


def report_dead(url: str) -> int:
    """A download of `url` failed: count it against every slot holding it, so
    a dead CDN link is evicted after DEAD_AFTER failures. Returns slots touched."""
    n = 0
    if not url or not ROOT.exists():
        return n
    for p in ROOT.glob("*.json"):
        try:
            d = json.loads(p.read_text())
            if not any(isinstance(x, dict) and x.get("url") == url
                       for x in d.get("candidates") or []):
                continue
            f = d.setdefault("failures", {})
            f[url] = int(f.get(url, 0)) + 1
            p.write_text(json.dumps(d, indent=2) + "\n")
            n += 1
        except Exception:  # noqa: BLE001
            continue
    return n


def wrap(provider: str, query: str, live) -> list[dict]:
    """Run `live()`, preferring its answer and caching it; fall back to the
    cache only when the call fails or returns nothing.

    The failure this exists for is a network refusal, which raises. Returning
    the cached answer there is the difference between a beat getting the clip it
    asked for and the film degrading to a card."""
    try:
        got = live() or []
    except Exception as e:  # noqa: BLE001 — the whole point is surviving this
        got = []
        err = str(e)[:60]
    else:
        err = ""
    if got:
        save(provider, query, got)
        return got
    cached = load(provider, query)
    if cached:
        print(f"[stock] {provider} {'failed (' + err + ')' if err else 'empty'} "
              f"for {query!r} — using {len(cached)} pre-fetched candidate(s)")
        return cached
    return []
