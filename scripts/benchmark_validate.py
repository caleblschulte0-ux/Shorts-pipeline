#!/usr/bin/env python3
"""Benchmark suite validator (ChatGPT review §3): checks every suite story
against its STRUCTURAL requirements — offline, free, deterministic — using the
chart build artifacts (frames + attachment sidecars), not judge scores.

Per story, per segment it renders a short build and verifies:

  hook.visual_present_at_frame_1  frame 1 carries real content (opaque fraction)
  hook.primary_action_before_s    the opening burst moves the chart by 0.4s
  mascot.contact_required         the attach sidecar shows grip contact EVERY frame
  mascot.state_changes >= 3       the selected performance has >= 3 distinct beats
  mascot.causes_data_change       the performance declares cause + consequence
  ending.new_information          the final frame lands value labels (anchors)
  ending.payoff_action            the timeline contains a payoff phase/event

Prints a table and exits non-zero if any suite story fails a requirement.
A renderer change should improve the MEDIAN across the suite, not one slug.

Usage: python scripts/benchmark_validate.py [--frames 18] [--slugs a b ...]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import os
os.environ.setdefault("STRICT_CONTACT", "1")   # suite = contact-verified kinds

import matplotlib  # noqa: E402
matplotlib.use("Agg")

from data_learning import charts, story  # noqa: E402
from data_learning.scene_timeline import HOOK_BURST_T  # noqa: E402


def _opaque_fraction(png: Path) -> float:
    from PIL import Image
    im = Image.open(png).convert("RGBA")
    a = im.getchannel("A")
    hist = a.histogram()
    opaque = sum(hist[40:])
    return opaque / max(1, im.size[0] * im.size[1])


def _frame_diff(p1: Path, p2: Path) -> float:
    from PIL import Image, ImageChops
    a = Image.open(p1).convert("L")
    b = Image.open(p2).convert("L")
    d = ImageChops.difference(a, b).histogram()
    return sum(d[12:]) / max(1, a.size[0] * a.size[1])


def validate_story(slug: str, story_cfg: dict, cfg: dict, req: dict,
                   frames: int) -> dict:
    """Render each segment's build into a temp dir and check the requirements."""
    res = {"slug": slug, "checks": {}, "pass": True, "families": []}

    def _set(name, ok, detail=""):
        res["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            res["pass"] = False

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        try:
            st = story.build(story_cfg, cfg, tdp, REPO)
        except Exception as e:  # noqa: BLE001
            _set("builds", False, str(e)[:120])
            return res
        segs = [s for s in st.segments if getattr(s, "insight", None)]
        _set("builds", bool(segs), f"{len(segs)} segments")
        for i, seg in enumerate(segs):
            tag = f"seg{i}"
            try:
                pat, anchors = charts.render_story_build(
                    seg.insight, tdp / "b", f"{slug}_{i}", frames=frames,
                    hook_lead=(i == 0))
            except Exception as e:  # noqa: BLE001
                _set(f"{tag}.renders", False, str(e)[:120])
                continue
            fs = sorted((tdp / "b").glob(f"{slug}_{i}_build*.png"))
            attach_p = tdp / "b" / f"{slug}_{i}_attach.json"
            attach = (json.loads(attach_p.read_text())
                      if attach_p.exists() else {})
            if i == 0:
                # HOOK: frame 1 carries content; the burst moves it by 0.4s
                _set("hook.visual_present_at_frame_1",
                     fs and _opaque_fraction(fs[0]) > 0.30,
                     f"opaque {_opaque_fraction(fs[0]):.2f}" if fs else "no frames")
                # 0.4s at 30fps = frame 12 of a real render; on this short proxy
                # build compare frame1 -> the burst-window frame.
                bi = max(1, min(len(fs) - 1, int(round(HOOK_BURST_T * frames))))
                _set("hook.primary_action_before_s",
                     len(fs) > bi and _frame_diff(fs[0], fs[bi]) > 0.01,
                     f"diff f1->f{bi + 1} = "
                     f"{_frame_diff(fs[0], fs[bi]):.3f}" if len(fs) > bi else "short")
            # MASCOT: contact every frame; >=3 beats; cause+consequence declared
            gp = attach.get("grip_path", [])
            _set(f"{tag}.mascot.contact_required",
                 attach.get("contact_frames", 0) >= len(fs) and len(gp) >= len(fs),
                 f"{attach.get('contact_frames', 0)}/{len(fs)} frames gripped")
            beats = (attach.get("performance") or {}).get("beats", [])
            _set(f"{tag}.mascot.state_changes",
                 len({b.get('phase') for b in beats}) >= 3,
                 f"{len(beats)} beats")
            perf = attach.get("performance") or {}
            res["families"].append(perf.get("family") or perf.get("action")
                                   or "?")
            # HONEST causal labels (review 4.2) — four separate claims, not one:
            _set(f"{tag}.mascot_contacts_data",
                 len(gp) >= len(fs),
                 "grip recorded every frame (metadata; visual check separate)")
            # review 4.2: the scene must declare at least ONE causal direction
            # (data drives him, or he drives/transforms the visual)
            _set(f"{tag}.causal_interaction_declared",
                 bool(perf.get("data_affects_mascot")
                      or perf.get("mascot_affects_data")),
                 perf.get("consequence", "")[:60])
            res["checks"][f"{tag}.data_affects_mascot"] = {
                "ok": True, "informational": True,
                "detail": str(bool(perf.get("data_affects_mascot")))}
            # mascot_affects_data is INFORMATIONAL (not every scene needs it) —
            # recorded, never failed on:
            res["checks"][f"{tag}.mascot_affects_data"] = {
                "ok": True, "informational": True,
                "detail": str(bool(perf.get("mascot_affects_data")))}
            # readability is PERCEPTUAL — deferred to the visual benchmark,
            # never credited structurally:
            res["checks"][f"{tag}.cause_consequence_readable"] = {
                "ok": True, "deferred_to": "benchmark_visual",
                "detail": "perceptual — graded by the vision benchmark"}
            # ENDING: labels land (anchors) + a payoff phase exists
            if i == len(segs) - 1:
                _set("ending.new_information", bool(anchors),
                     f"{len(anchors)} anchors")
                tl = attach.get("timeline") or {}
                _set("ending.payoff_action",
                     "payoff" in (tl.get("phases") or {}),
                     str((tl.get("phases") or {}).get("payoff")))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=18)
    ap.add_argument("--slugs", nargs="*")
    args = ap.parse_args()
    suite = json.loads(
        (REPO / "data_learning" / "benchmarks" / "suite.json").read_text())
    cfg = json.loads(
        (REPO / "data_learning" / "niche.config.json").read_text())
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    req = suite["requirements"]
    slugs = args.slugs or [s["slug"] for s in suite["stories"]]
    results, all_ok = [], True
    for slug in slugs:
        if slug not in stories:
            print(f"[{slug}] NOT IN CONFIG — skipping")
            continue
        r = validate_story(slug, stories[slug], cfg, req, args.frames)
        results.append(r)
        all_ok &= r["pass"]
        print(f"[{slug}] {'PASS' if r['pass'] else 'FAIL'}")
        for name, c in r["checks"].items():
            print(f"   {'ok  ' if c['ok'] else 'FAIL'} {name}"
                  f"{(' — ' + c['detail']) if c['detail'] else ''}")
    # FAMILY DIVERSITY (review Phase 5 acceptance): within a story <=50% of
    # scenes may share a performance family; across the suite no family may
    # exceed 25% of scenes (rounded up allowance for small suites).
    fam_all = []
    for r in results:
        fams = r.get("families") or []
        if fams:
            top = max(fams.count(f) for f in set(fams))
            if top > max(1, len(fams) // 2):
                r["pass"] = False
                r["checks"]["mascot.family_diversity"] = {
                    "ok": False, "detail": f"{fams} (family >50% of story)"}
            fam_all += fams
    if fam_all:
        import math as _m
        cap = max(1, _m.ceil(0.25 * len(fam_all)))
        worst = max(set(fam_all), key=fam_all.count)
        div_ok = fam_all.count(worst) <= cap
        if not div_ok:
            all_ok = False
        print(f"suite family spread: {sorted(set(fam_all))} "
              f"(dominant '{worst}' {fam_all.count(worst)}/{len(fam_all)}, "
              f"cap {cap}) {'ok' if div_ok else 'FAIL'}")
    all_ok = all_ok and all(r["pass"] for r in results)
    out = REPO / "state" / "benchmark_structural.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"results": results, "all_pass": all_ok}, indent=1))
    # merged summary: structural + (separate) visual — a story is only FULLY
    # passing when BOTH pass; visual not-run keeps fully_passing false.
    vis_p = REPO / "state" / "benchmark_visual.json"
    vis = json.loads(vis_p.read_text()) if vis_p.exists() else {
        "all_pass": False, "status": "not_run"}
    (REPO / "state" / "benchmark_validation.json").write_text(json.dumps(
        {"structural": {"all_pass": all_ok},
         "visual": {"all_pass": bool(vis.get("all_pass")),
                    "status": vis.get("status", "ran")},
         "fully_passing": all_ok and bool(vis.get("all_pass"))}, indent=1))
    print(f"\nstructural: {'ALL PASS' if all_ok else 'FAILURES'} -> {out}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
