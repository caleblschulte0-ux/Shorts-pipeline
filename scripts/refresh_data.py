#!/usr/bin/env python3
"""Replace bundled 'Illustrative' dataset snapshots with REAL, source-backed
numbers pulled live from FRED / BLS.

Why this exists
---------------
The data channel's whole premise is "data." But most files in
``data_learning/data/*.json`` are marked ``"notes": "Illustrative"`` while
being attributed to a real agency with ``"officiality": "official"`` — e.g.
loan rates credited to the Federal Reserve over numbers the Fed never
published. The first time a video gets traction, someone fact-checks a
figure, finds the agency doesn't say that, and the channel earns a "fake
stats" reputation that's very hard to undo. Accuracy IS the brand.

This tool closes that gap. For every key in ``data_sources.map.json`` it
pulls the live series, normalises it into the bundled offline format
(preserving the human title/geography/topic), stamps honest provenance, and
overwrites the snapshot. The offline file then doubles as a reproducible
cache so renders stay deterministic.

SAFETY — defaults to dry-run
----------------------------
Nothing is written unless you pass ``--write``. The dry run prints the real
numbers so you can eyeball them against the live series page
(fred.stlouisfed.org/series/<SERIES>) before committing. A live pull that
returns too few points or non-finite values aborts that key rather than
shipping garbage.

Usage
-----
  FRED_API_KEY=... python3 scripts/refresh_data.py --check        # what's stale
  FRED_API_KEY=... python3 scripts/refresh_data.py --key savings_rate
  FRED_API_KEY=... python3 scripts/refresh_data.py --write        # persist all
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data_learning" / "data"
MAP_PATH = ROOT / "data_learning" / "data_sources.map.json"


def _is_illustrative(d: dict) -> bool:
    return str(d.get("notes", "")).strip().lower().startswith("illustrative")


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text()).get("mappings", {})


def snapshot_from_dataset(ds, existing: dict, m: dict) -> dict:
    """Pure transform: a fetched Dataset + the existing on-disk snapshot +
    its mapping entry -> the new offline-format dict. Kept side-effect free
    so it's unit-testable without any network."""
    scale = float(m.get("scale", 1.0))
    unit = m.get("unit") or existing.get("unit") or ds.unit
    label_mode = m.get("label")

    points = []
    for p in ds.points:
        val = p.value * scale
        if not math.isfinite(val):
            continue
        label = p.label
        if label_mode == "year":
            # FRED labels look like "2026-01"; trend charts use "2026".
            label = (p.period or label)[:4]
        points.append({"label": label, "value": round(val, 4),
                       "period": p.period or label})

    if len(points) < 2:
        raise ValueError(
            f"{ds.key}: live pull returned {len(points)} usable points "
            f"(need >=2) — refusing to overwrite a snapshot with garbage")

    # Preserve the human-authored framing; replace only the numbers + honest
    # provenance. title/geography/topic carry the writer's intent.
    return {
        "key": existing.get("key", ds.key),
        "title": existing.get("title", ds.title),
        "unit": unit,
        "geography": existing.get("geography", ds.geography),
        "time_coverage": f"{points[0]['period']} to {points[-1]['period']}",
        "source": {
            "name": ds.source.name,
            "publisher": ds.source.publisher,
            "url": ds.source.url,
            "officiality": "official",
            "access_date": date.today().isoformat(),
        },
        "notes": f"Live pull from {m['adapter'].upper()} series "
                 f"{m['series']} ({m.get('frequency', 'a')}).",
        "points": points,
    }


def refresh_key(key: str, m: dict, *, write: bool) -> dict | None:
    """Pull one key live and (optionally) write it. Returns the new snapshot
    dict, or None if the key has no on-disk file to update."""
    from data_learning.sources import get_source

    path = DATA_DIR / f"{key}.json"
    if not path.exists():
        print(f"[skip] {key}: no data file at {path}", file=sys.stderr)
        return None
    existing = json.loads(path.read_text())

    src = get_source(m["adapter"])
    params = {"observations": m.get("observations", 7),
              "frequency": m.get("frequency", "a")}
    ds = src.fetch(m["series"], params)
    snap = snapshot_from_dataset(ds, existing, m)

    vals = ", ".join(f"{p['label']}={p['value']}" for p in snap["points"])
    print(f"[{key}] {m['adapter']}:{m['series']}  unit={snap['unit']}")
    print(f"   {vals}")
    print(f"   source: {snap['source']['publisher']} -> {snap['source']['url']}")

    if write:
        path.write_text(json.dumps(snap, indent=2) + "\n")
        print(f"   WROTE {path}")
    else:
        print("   (dry-run — re-run with --write to persist)")
    return snap


def check() -> int:
    """Report how many bundled files are still illustrative and which of those
    already have a live mapping ready to pull."""
    mapping = _load_map()
    files = sorted(DATA_DIR.glob("*.json"))
    illus = [json.loads(f.read_text()).get("key", f.stem)
             for f in files if _is_illustrative(json.loads(f.read_text()))]
    ready = [k for k in illus if k in mapping]
    print(f"{len(files)} data files; {len(illus)} still illustrative.")
    print(f"{len(mapping)} live mappings defined; "
          f"{len(ready)} of the illustrative files can be refreshed now:")
    for k in sorted(ready):
        print(f"   - {k}  ({mapping[k]['adapter']}:{mapping[k]['series']})")
    todo = sorted(set(illus) - set(mapping))
    if todo:
        print(f"\n{len(todo)} illustrative files still need a verified mapping "
              f"(extend data_sources.map.json):")
        print("   " + ", ".join(todo))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--key", help="refresh a single key (default: all mapped)")
    ap.add_argument("--write", action="store_true",
                    help="persist changes (default is dry-run)")
    ap.add_argument("--check", action="store_true",
                    help="report illustrative vs. mapped, then exit")
    args = ap.parse_args()

    if args.check:
        return check()

    mapping = _load_map()
    keys = [args.key] if args.key else list(mapping)
    if args.key and args.key not in mapping:
        sys.exit(f"no mapping for {args.key!r}; add it to {MAP_PATH.name}")

    failures = 0
    for key in keys:
        try:
            refresh_key(key, mapping[key], write=args.write)
        except Exception as e:  # noqa: BLE001 — keep going, report at the end
            print(f"[fail] {key}: {e}", file=sys.stderr)
            failures += 1
    if failures:
        print(f"\n{failures}/{len(keys)} keys failed", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
