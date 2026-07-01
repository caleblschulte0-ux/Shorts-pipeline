#!/usr/bin/env python3
"""Render ONE viz kind to PNG frames for eyeballing — no ffmpeg, no keys.

    python scripts/preview_viz.py timeline --out /tmp/tl
    python scripts/preview_viz.py --all --out /tmp/viz

Handy for iterating on a depiction locally (the full video only builds in CI).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_learning import charts                       # noqa: E402
from data_learning.insights import Insight             # noqa: E402


class _P:
    def __init__(self, label, value, period=None):
        self.label, self.value, self.unit, self.period = label, value, "", period


class _S:
    def footer(self):
        return "Source: illustrative"


SAMPLES = {
    "timeline": dict(items=[("First humans", 300000)], unit="years ago",
                     vp={"timeline_start": 0, "timeline_end": 4_500_000_000}),
    "fill_vessel": dict(items=[("Ocean water", 97)], unit="percent", vp={}),
    "waffle_grid": dict(items=[("Saltwater", 97), ("Ice", 2), ("Fresh", 1)],
                        unit="percent", vp={}),
    "pictorial_race": dict(items=[("Cheetah", 75), ("Lion", 50), ("Human", 28)],
                           unit="mph", vp={}),
    "orbit": dict(items=[("Neptune", 4500), ("Jupiter", 778), ("Earth", 150),
                         ("Mercury", 58)], unit="M km", vp={}),
    "pictograph": dict(items=[("Dogs", 48), ("Cats", 30), ("Birds", 12)],
                       unit="million", vp={}),
    "bubbles": dict(items=[("A", 80), ("B", 55), ("C", 30)], unit="", vp={}),
}


def _mk(kind: str, s: dict) -> Insight:
    ins = Insight.__new__(Insight)
    ins.items = [_P(lbl, v) for lbl, v in s["items"]]
    ins.kind = kind
    ins.topic = kind.replace("_", " ").title() + " sample"
    ins.unit = s["unit"]
    ins.baseline = None
    ins.highlight_label = s["items"][0][0]
    ins.main_insight = s["items"][0][0] + " tops the list"
    ins.source = _S()
    ins.viz_params = s["vp"]
    return ins


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kind", nargs="?", choices=sorted(SAMPLES))
    ap.add_argument("--all", action="store_true", help="render every sample kind")
    ap.add_argument("--out", default="preview_viz")
    ap.add_argument("--frames", type=int, default=16)
    a = ap.parse_args()
    if not a.kind and not a.all:
        ap.error("give a kind or --all")
    kinds = sorted(SAMPLES) if a.all else [a.kind]
    for kind in kinds:
        ins = _mk(kind, SAMPLES[kind])
        out = Path(a.out) / kind
        out.mkdir(parents=True, exist_ok=True)
        pat, anc = charts.render_story_build(ins, out, "preview", frames=a.frames)
        print(f"{kind:15} -> final kind={ins.kind:14} frames={'ok' if pat else 'NONE'} "
              f"anchors={len(anc)}  ({out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
