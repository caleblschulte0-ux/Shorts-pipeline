#!/usr/bin/env python3
"""Validate the `scene` depictions the BRAIN wrote for the given story slugs.

Offline + fast: builds a light stub insight from each segment's data-file points
(no photo fetches) and checks the scene against the SAME validators the renderer
uses — the element-kit `viz_scene.validate` or, for a procedural mechanic,
`validate_mechanic` + a one-frame dry render. Prints PASS/FAIL per segment and
exits non-zero if anything is invalid, so the brain can iterate until clean.

    python scripts/validate_scenes.py bite-force-champions hottest-planets-surface
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_learning import viz_scene            # noqa: E402
from data_learning.insights import Insight     # noqa: E402

DATA = REPO / "data_learning" / "data"
CFG = REPO / "data_learning" / "niche.config.json"


class _P:
    def __init__(self, label, value, period=None):
        self.label = label
        self.value = float(value)
        self.unit = ""
        self.period = period


def _stub_insight(seg: dict) -> Insight:
    pts = []
    f = (seg.get("params") or {}).get("file")
    if f and (DATA / f).exists():
        d = json.load(open(DATA / f, encoding="utf-8"))
        pts = [_P(p["label"], p["value"], p.get("period"))
               for p in d.get("points", [])]
    ins = Insight.__new__(Insight)
    ins.items = pts or [_P("A", 1.0)]
    ins.kind = "scene"
    ins.topic = seg.get("topic", "")
    ins.unit = ""
    ins.baseline = None
    ins.highlight_label = ins.items[0].label
    ins.main_insight = ""
    ins.slug = "validate"
    return ins


def _check(seg: dict) -> tuple[bool, str]:
    sc = seg.get("scene")
    if not isinstance(sc, dict):
        return False, "no scene"
    ins = _stub_insight(seg)
    if "code" in sc or "mechanic" in sc:                       # procedural mechanic
        if not viz_scene.validate_mechanic(sc):
            return False, "mechanic failed structural validation (unsafe/no-subject/syntax)"
        if not viz_scene.mechanic_dry_ok(sc, ins):
            return False, "mechanic failed dry-render (raised or drew nothing)"
        return True, f"mechanic '{sc.get('mechanic','?')}'"
    if viz_scene.validate(sc, ins):                            # element-kit scene
        kinds = ",".join(e.get("type", "?") for e in sc.get("elements", []))
        return True, f"scene [{kinds}]"
    return False, "scene failed validation (abstract-only / bad type / unresolvable value_from)"


def main(argv: list[str]) -> int:
    slugs = set(argv)
    cfg = json.load(open(CFG, encoding="utf-8"))
    stories = [s for s in cfg["stories"] if not slugs or s["slug"] in slugs]
    if slugs:
        missing = slugs - {s["slug"] for s in cfg["stories"]}
        for m in sorted(missing):
            print(f"[MISS] unknown slug: {m}")
    bad = 0
    for st in stories:
        for i, seg in enumerate(st.get("segments", [])):
            ok, msg = _check(seg)
            tag = "PASS" if ok else "FAIL"
            if not ok:
                bad += 1
            print(f"[{tag}] {st['slug']} seg{i}: {msg}")
    print(f"\n{'OK' if not bad else 'FAILURES: ' + str(bad)}")
    return 1 if (bad or (slugs and (slugs - {s['slug'] for s in cfg['stories']}))) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
