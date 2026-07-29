#!/usr/bin/env python3
"""Hash-chained append-only run ledger (PR#173 adoption D, adapted).

The reference execution_ledger.py models a multi-worker orchestration ledger
with leases; production is single-worker, so the adaptation keeps the two
properties that solve REAL pain here:

1. DURABILITY — every producer phase appends an event to
   ``state/curiosity_run_ledger.jsonl``. When a container dies mid-run (it
   happened twice on 2026-07-25), the ledger shows exactly how far the run
   got, and the resume path in produce.py can prove whether the on-disk
   render is complete and identical instead of re-rendering for an hour.
2. TAMPER-EVIDENCE — events are hash-chained (each event carries the hash of
   the previous one), so the history of what was rendered, judged, and held
   can be verified end-to-end. verify_chain() names the first broken link.

Events are small JSON lines; renders/artifacts never go in the ledger — only
their hashes ride along via the package manifest.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO / "state" / "curiosity_run_ledger.jsonl"
GENESIS = "0" * 64


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                out.append({"_corrupt": line})
    return out


def append(event_type: str, slug: str, payload: dict | None = None,
           path: Path = LEDGER_PATH) -> dict:
    """Append one hash-chained event. Returns the event as written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    events = _read_lines(path)
    prev = events[-1].get("event_hash", GENESIS) if events else GENESIS
    event = {
        "sequence": len(events),
        "event_type": event_type,
        "slug": slug,
        "at": datetime.now(timezone.utc).isoformat(),
        "payload": payload or {},
        "previous_hash": prev,
    }
    event["event_hash"] = sha256(
        prev.encode() + _canonical({k: v for k, v in event.items()
                                    if k != "event_hash"})).hexdigest()
    with path.open("a") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def verify_chain(path: Path = LEDGER_PATH) -> tuple[bool, str | None]:
    """Walk the chain; returns (ok, first_problem)."""
    events = _read_lines(path)
    prev = GENESIS
    for i, e in enumerate(events):
        if "_corrupt" in e:
            return False, f"line {i}: not valid JSON"
        if e.get("previous_hash") != prev:
            return False, f"seq {i}: previous_hash broken (chain edited?)"
        expect = sha256(prev.encode() + _canonical(
            {k: v for k, v in e.items() if k != "event_hash"})).hexdigest()
        if e.get("event_hash") != expect:
            return False, f"seq {i}: event_hash mismatch (event edited?)"
        prev = e["event_hash"]
    return True, None


def tail(n: int = 10, slug: str | None = None,
         path: Path = LEDGER_PATH) -> list[dict]:
    events = _read_lines(path)
    if slug:
        events = [e for e in events if e.get("slug") == slug]
    return events[-n:]


def main(argv) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Inspect the curiosity run ledger.")
    ap.add_argument("--slug", default=None)
    ap.add_argument("-n", type=int, default=10)
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args(argv)
    if a.verify:
        ok, why = verify_chain()
        print("chain OK" if ok else f"chain BROKEN: {why}")
        return 0 if ok else 1
    for e in tail(a.n, a.slug):
        print(f"{e['at']}  #{e['sequence']:<4} {e['event_type']:<18} "
              f"{e['slug']:<18} {json.dumps(e['payload'])[:90]}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
