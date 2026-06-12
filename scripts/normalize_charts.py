#!/usr/bin/env python3
"""Self-healing guard against un-renderable chart specs.

The daily-packages generator sometimes authors story segments using an
``insight_type: "comparison"`` with a single data point plus a ``baseline``
field in the data file. The studio renderer can't draw that shape — it produces
a broken chart (both bars the same value, mislabelled, formatted as a bogus
percent) and in some cases hangs. Rather than hand-patch each occurrence, this
script normalises any such segment into the proven two-point ``rank`` chart
(baseline + value as two labelled bars) that the renderer draws reliably.

It is idempotent and safe to run before every render: stories that are already
fine are left untouched. Wire it into the workflow ahead of post_stories so the
channel can never ship a broken comparison chart again.

  python scripts/normalize_charts.py            # normalise in place
  python scripts/normalize_charts.py --check     # report only, exit 1 if any found
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "data_learning" / "niche.config.json"
DATA = ROOT / "data_learning" / "data"


def _normalise_datafile(path: Path) -> bool:
    """Turn a {baseline + single point} data file into two ranked points.
    Returns True if the file was changed."""
    if not path.exists():
        return False
    d = json.loads(path.read_text())
    base = d.get("baseline")
    pts = d.get("points", [])
    if base and len(pts) >= 1:
        merged = [
            {"label": base["label"], "value": base["value"]},
            {"label": pts[0]["label"], "value": pts[0]["value"]},
        ]
        merged.sort(key=lambda p: p["value"], reverse=True)
        d["points"] = merged
        d.pop("baseline", None)
        path.write_text(json.dumps(d, indent=2, ensure_ascii=True) + "\n")
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report only; exit 1 if any un-renderable spec found")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text())
    fixed: list[str] = []
    for s in cfg.get("stories", []):
        for seg in s.get("segments", []):
            key = seg.get("key", "")
            datafile = DATA / ((seg.get("params") or {}).get("file") or f"{key}.json")
            pts = []
            if datafile.exists():
                pts = json.loads(datafile.read_text()).get("points", [])
            needs = seg.get("insight_type") == "comparison" or len(pts) < 2
            if not needs:
                continue
            fixed.append(f"{s['slug']}/{key}")
            if not args.check:
                _normalise_datafile(datafile)
                seg["insight_type"] = "rank"
                seg["ascending"] = False

    if args.check:
        if fixed:
            print("un-renderable chart specs found:\n  " + "\n  ".join(fixed))
            return 1
        print("all chart specs renderable")
        return 0

    if fixed:
        CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")
        print(f"normalised {len(fixed)} segment(s) to 2-point rank:\n  "
              + "\n  ".join(fixed))
    else:
        print("nothing to normalise")
    return 0


if __name__ == "__main__":
    sys.exit(main())
