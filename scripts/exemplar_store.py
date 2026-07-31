#!/usr/bin/env python3
"""The 90 CLUB + reject library (review Phase 9).

Every video/scene that scores >= EXEMPLAR_BAR gets its PLAN saved (scene plans,
performance specs, metrics, verdict, and why it worked) under
``quality/exemplars/``; recurring hard failures get their plan + failure class
saved under ``quality/rejects/``. Small JSON only — renders live on the
preview-renders branch, referenced by run id, never committed here.

Generation RETRIEVES before inventing: scene_repair consults the exemplar
store for plans matching the scene's shape+relationships and seeds the
candidate list with the best match, so wins compound and known failures are
not re-attempted.

Usage:
    python scripts/exemplar_store.py harvest [--bar 90]   # scan output/ verdicts
    python scripts/exemplar_store.py list
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EX_DIR = REPO / "quality" / "exemplars"
REJ_DIR = REPO / "quality" / "rejects"
EXEMPLAR_BAR = 90


def _scene_records(slug: str) -> list[dict]:
    out = []
    sdir = REPO / "output" / "scenes" / slug
    if sdir.exists():
        for seg in sorted(sdir.glob("segment_*")):
            m = seg / "metrics.json"
            if m.exists():
                out.append(json.loads(m.read_text()))
    return out


def harvest(bar: int = EXEMPLAR_BAR) -> dict:
    """Scan the canonical verdicts; bank exemplars and rejects."""
    saved, rejected = [], []
    for vp in sorted((REPO / "output").glob("story_*.showrunner.json")):
        v = json.loads(vp.read_text())
        slug = vp.name[len("story_"):-len(".showrunner.json")]
        scenes = _scene_records(slug)
        plan_p = REPO / "state" / "scene_plans" / f"{slug}.json"
        plan = json.loads(plan_p.read_text()) if plan_p.exists() else {}
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        if (v.get("score") or 0) >= bar and not v.get("auto_fails"):
            rec = {"slug": slug, "ts": stamp, "score": v.get("score"),
                   "dimensions": v.get("dimensions"),
                   "temporal": v.get("temporal"),
                   "scene_plan": plan,
                   "scenes": [{"id": s.get("id"), "kind": s.get("kind"),
                               "performance": s.get("performance")}
                              for s in scenes],
                   "why_it_worked": v.get("one_line", ""),
                   "render_ref": "preview-renders branch @ " + stamp}
            EX_DIR.mkdir(parents=True, exist_ok=True)
            (EX_DIR / f"{slug}_{stamp}.json").write_text(
                json.dumps(rec, indent=1))
            saved.append(slug)
        for af in v.get("auto_fails") or []:
            cls = af.split(":", 1)[0].strip()
            ws = v.get("weakest_scene") or {}
            rec = {"slug": slug, "ts": stamp, "failure_class": cls,
                   "evidence": af[:300], "weakest_scene": ws,
                   "scene_plan": plan,
                   "scenes": [{"id": s.get("id"), "kind": s.get("kind"),
                               "performance": (s.get("performance") or {}).get(
                                   "action")} for s in scenes]}
            REJ_DIR.mkdir(parents=True, exist_ok=True)
            (REJ_DIR / f"{slug}_{cls}_{stamp}.json").write_text(
                json.dumps(rec, indent=1))
            rejected.append(f"{slug}:{cls}")
    return {"exemplars_saved": saved, "rejects_saved": rejected}


def retrieve(shape: str, relationships: list[str]) -> dict | None:
    """The best banked exemplar scene plan matching this shape+relationships
    (highest score wins). Returns {viz, perf} or None."""
    best, best_score = None, -1
    if not EX_DIR.exists():
        return None
    for p in EX_DIR.glob("*.json"):
        try:
            rec = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        for sc in rec.get("scenes", []):
            perf = sc.get("performance") or {}
            sel = perf.get("selection_input") or {}
            if sel.get("shape") != shape:
                continue
            if relationships and not (set(sel.get("relationships", []))
                                      & set(relationships)):
                continue
            if (rec.get("score") or 0) > best_score:
                best_score = rec.get("score") or 0
                best = {"viz": sc.get("kind"), "perf": perf.get("action"),
                        "from_exemplar": p.name, "score": best_score}
    return best


def rejected_pairs(shape: str) -> set:
    """(viz, perf) pairs that produced hard failures for this shape — the
    negative knowledge generation should not re-attempt first."""
    out = set()
    if not REJ_DIR.exists():
        return out
    for p in REJ_DIR.glob("*.json"):
        try:
            rec = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        for sc in rec.get("scenes", []):
            if sc.get("kind") and sc.get("performance"):
                out.add((sc["kind"], sc["performance"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["harvest", "list"])
    ap.add_argument("--bar", type=int, default=EXEMPLAR_BAR)
    args = ap.parse_args()
    if args.cmd == "harvest":
        print(json.dumps(harvest(args.bar), indent=1))
    else:
        ex = sorted(p.name for p in EX_DIR.glob("*.json")) \
            if EX_DIR.exists() else []
        rj = sorted(p.name for p in REJ_DIR.glob("*.json")) \
            if REJ_DIR.exists() else []
        print(json.dumps({"exemplars": ex, "rejects": rj}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
