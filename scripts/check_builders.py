#!/usr/bin/env python3
"""Builder-contract compliance (CURIOSITY_BRAIN §7.5 v4).

Every registered builder must return an ESCALATING TIMELINE: at least 3
animation bundles, at least one of them a payoff (punch=True). A builder
that arrives and then sits still is a design bug the library must make
impossible — this check keeps every future builder honest.

    python3 scripts/check_builders.py

Exits 1 if any builder falls short.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from data_learning.world_builders import BUILDERS  # noqa: E402

THEME = {"bg": "#080a14", "highlight": "#4FD1C5", "accent": "#60A5FA"}
POINTS = [
    {"label": "Alpha runner", "value": 45, "asset": "human",
     "period": "1970"},
    {"label": "Beta cruiser", "value": 900, "asset": "jet",
     "period": "1985"},
    {"label": "Gamma station", "value": 28000, "asset": "iss",
     "period": "2008"},
]
PARAMS = {
    "marker": {"label": "Sample stop"},
    "scalelevel": {"tableau": "earth", "label": "Earth spin",
                   "display": "1,670 km/h"},
}


def main() -> int:
    fails = []
    # in-world variants (§7.5 v8 no-downgrade law) obey the same contract
    variants = [(name, dict(PARAMS.get(name,
                                       {"points": POINTS, "unit": "km/h"})))
                for name in sorted(BUILDERS)]
    variants.append(("rank", {"points": POINTS, "unit": "km/h",
                              "mode": "in_world"}))
    for name, params in variants:
        build = BUILDERS[name]
        if params.get("mode"):
            name = f"{name}[{params['mode']}]"
        wp = {"builder": name, "params": params}
        try:
            _g, anims = build(wp, THEME, 1.0, np.array([0.0, 0.0, 0.0]),
                              post_scale=1.0)
        except Exception as e:  # noqa: BLE001 — report, don't crash the sweep
            fails.append(f"{name}: crashed on sample data ({e})")
            print(f"{name:18s} CRASH  {e}")
            continue
        n = len(anims)
        punches = sum(1 for a in anims if getattr(a, "punch", False))
        ok = n >= 3 and punches >= 1
        print(f"{name:18s} bundles={n:2d}  payoffs={punches}  "
              f"{'ok' if ok else 'FAIL'}")
        if not ok:
            fails.append(f"{name}: {n} bundles / {punches} payoffs "
                         "(need >=3 incl. >=1 punch)")
    if fails:
        print(f"\nFAIL — {len(fails)} builder(s) below the escalation "
              "contract:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print(f"\nOK: all {len(BUILDERS)} builders return escalating timelines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
