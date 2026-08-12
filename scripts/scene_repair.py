#!/usr/bin/env python3
"""SCENE-ADDRESSABLE repair (ChatGPT review §"Repair system"): when a video
fails, do not reroll the whole video — fix the failing SCENE.

    1. Select the failing scene (from the verdict's auto-fail text / weakest
       dimension mapped onto segments).
    2. Generate THREE structurally different scene plans (different chart kind
       x performance — not parameter jitter).
    3. Render all three as scene-only chart builds (offline, free).
    4. Score them BLINDLY with code metrics (cadence + frame fullness + label
       presence + contact coverage).
    5. Keep the winner only if it beats the incumbent by a meaningful margin.
    6. Persist the choice to state/scene_plans/{slug}.json — the renderer
       applies it (insight.plan_locked) on the next render of that slug.

No variance rerolls. No env nudges. No MASCOT_BRAIN=1.

Usage:
    python scripts/scene_repair.py --slug world-power-mix \
        [--verdict output/story_world-power-mix.showrunner.json] [--apply]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import matplotlib  # noqa: E402
matplotlib.use("Agg")

PLANS_DIR = REPO / "state" / "scene_plans"

# Chart-kind options per data shape; the PERFORMANCE for each candidate is
# selected SEMANTICALLY from the claim (mascot_director.performance_for with a
# rotating anti-repetition set), so the three candidates are three genuinely
# different scenes: different depiction × different performance family, all
# compatible with the scene's meaning.
KIND_OPTIONS = {
    "part_to_whole": ["stack", "stack", "pictorial_race"],
    "two_value": ["comparison", "stack", "pictorial_race"],
    "ranking": ["pictorial_race", "rank", "stack"],
    "trend": ["trend", "trend", "pictorial_race"],
}


def semantic_candidates(insight, shape: str) -> list[dict]:
    """Three structurally different (viz, perf) plans, each SEMANTICALLY
    compatible with the scene's claim (review 3.2): the performance's
    supported shapes/relationships must fit the scene intent — an incompatible
    combination is rejected before any rendering."""
    sys.path.insert(0, str(REPO))
    from data_learning import mascot_director as md
    claim = getattr(insight, "main_insight", "") or ""
    intent = md.analyze_claim(claim)
    target = insight.items[0].label if getattr(insight, "items", None) else ""
    cands, used = [], set()
    # RETRIEVE BEFORE INVENTING (review Phase 9): seed with the best banked
    # exemplar for this shape+relationships; drop pairs the reject library
    # already saw hard-fail.
    try:
        import exemplar_store as _ex
        seed_plan = _ex.retrieve(shape, intent["relationships"])
        bad_pairs = _ex.rejected_pairs(shape)
    except Exception:  # noqa: BLE001
        seed_plan, bad_pairs = None, set()
    if seed_plan and seed_plan.get("viz") and seed_plan.get("perf"):
        cands.append({"viz": seed_plan["viz"], "perf": seed_plan["perf"],
                      "family": "exemplar",
                      "performance_meaning":
                          f"banked exemplar ({seed_plan['from_exemplar']})",
                      "intent": {"shape": shape,
                                 "relationships": intent["relationships"],
                                 "direction": intent["direction"]}})
    for j, viz in enumerate(KIND_OPTIONS.get(shape, KIND_OPTIONS["ranking"])):
        spec = md.performance_for(viz, claim, target,
                                  used_families=used, seed=j)
        # SEMANTIC GATE: the selected performance must genuinely support this
        # shape (performance_for enforces it) — record the declaration.
        used.add(spec.get("family", spec["action"]))
        if (viz, spec["action"]) in bad_pairs:
            print(f"[scene_repair] skipping rejected pair {viz}+{spec['action']}"
                  " (reject library)", flush=True)
            continue
        cands.append({"viz": viz, "perf": spec["action"],
                      "family": spec.get("family"),
                      "performance_meaning": spec.get("goal", ""),
                      "intent": {"shape": shape,
                                 "relationships": intent["relationships"],
                                 "direction": intent["direction"]}})
    # dedupe identical (viz, perf) pairs while keeping order
    seen, out = set(), []
    for c in cands:
        k = (c["viz"], c["perf"])
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def shape_of(insight) -> str:
    if insight.kind in ("trend", "timeline"):
        return "trend"
    if len(insight.items) == 2:
        return "two_value"
    if insight.kind in ("share", "waffle_grid", "stack"):
        return "part_to_whole"
    return "ranking"


def measured_failures(slug: str, n_segs: int) -> list[tuple[int, float]]:
    """Segments whose OWN measured temporal gate failed, worst first.

    `studio_render._scene_metrics` already encodes every scene and grades it
    with the reviewer's own detector, writing
    `output/scenes/<slug>/segment_<i>/metrics.json`. That evidence existed on
    disk and nothing read it: on 2026-08-11 all four explainer stories were
    blocked BEFORE vision review (so there is no `weakest_scene` and no
    `segN` prose to parse), the repair fell through to its last-segment
    default, and every one of them "repaired" segment 2 — which was passing
    at 24.0 fps — while segment 0, measuring 0.8-1.4, was never touched.
    A measurement beats a default.
    """
    out: list[tuple[int, float]] = []
    d = REPO / "output" / "scenes" / slug
    for i in range(n_segs):
        f = d / f"segment_{i}" / "metrics.json"
        if not f.exists():
            continue
        try:
            m = json.loads(f.read_text())
        except Exception:  # noqa: BLE001 — a junk sidecar is not a diagnosis
            continue
        gate = m.get("gate") or (m.get("verdict") or {}).get("gate")
        fps = (m.get("effective_fps")
               if m.get("effective_fps") is not None
               else (m.get("temporal") or {}).get("effective_fps"))
        if gate and gate != "pass":
            out.append((i, float(fps or 0.0)))
    return sorted(out, key=lambda t: t[1])


def failing_scene(verdict: dict, n_segs: int, slug: str = "") -> int:
    """The scene to repair. PRIMARY source: the scene's OWN MEASUREMENT when
    a scene actually failed its temporal gate — that is evidence, and it is
    the only source available at all when the video was blocked before vision
    review. Then the judge's STRUCTURED weakest_scene diagnosis (id/index
    emitted directly by the showrunner). Prose parsing ('segN' in auto-fail
    text) and the last-segment default are EMERGENCY fallbacks only, and are
    loudly logged as such."""
    if slug:
        meas = measured_failures(slug, n_segs)
        if meas:
            i, fps = meas[0]
            print(f"[scene_repair] measured failure: seg{i} at {fps} "
                  f"effective fps — repairing the scene that FAILED", flush=True)
            return i
    ws = verdict.get("weakest_scene")
    if isinstance(ws, dict):
        idx = ws.get("index")
        if isinstance(idx, int) and 0 <= idx < n_segs:
            return idx
        sid = str(ws.get("id", ""))
        m = re.search(r"(\d+)", sid)
        if m and int(m.group(1)) < n_segs:
            return int(m.group(1))
    text = " ".join(verdict.get("auto_fails", []) or [])
    hits = [int(m) for m in re.findall(r"seg(\d+)", text)]
    if hits:
        print("[scene_repair] EMERGENCY fallback: no structured weakest_scene; "
              "parsed segment from prose", flush=True)
        return max(set(hits), key=hits.count) % max(1, n_segs)
    print("[scene_repair] EMERGENCY fallback: no scene identified anywhere; "
          "defaulting to the final segment", flush=True)
    return n_segs - 1


def _ffmpeg() -> str | None:
    import shutil
    ff = shutil.which("ffmpeg")
    if ff:
        return ff
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


def score_candidate(build_dir: Path, tag: str, frames: int) -> dict:
    """BLIND code score for one scene candidate: cadence (effective fps via the
    real reviewer detector), frame fullness, label anchors, contact coverage."""
    from PIL import Image
    fs = sorted(build_dir.glob(f"{tag}_build*.png"))
    if not fs:
        return {"score": 0.0, "detail": "no frames"}
    # fullness of the mid frame (empty_void proxy)
    im = Image.open(fs[len(fs) // 2]).convert("RGBA")
    hist = im.getchannel("A").histogram()
    fullness = sum(hist[40:]) / max(1, im.size[0] * im.size[1])
    # contact coverage from the attach sidecar
    ap = build_dir / f"{tag}_attach.json"
    attach = json.loads(ap.read_text()) if ap.exists() else {}
    contact = attach.get("contact_frames", 0) / max(1, len(fs))
    # cadence: encode tiny mp4 and run the reviewer's own temporal detector
    # CADENCE IS MEASURED ON THE COMPOSITED SCENE, NOT THE RAW BUILD.
    # Candidates are rendered at ~60 frames while the real beat is up to
    # 1200, so a raw-build cadence score was measuring something the shipped
    # video never is: every candidate scored fps_score 1.0 on 2026-08-11 and
    # then shipped at 1.0 effective fps. The camera float is duration-
    # independent (shared/camera_float.py), so including it makes the short
    # proxy honest about the long beat.
    fps_score = 0.5
    ff = _ffmpeg()
    if ff:
        try:
            from shared import camera_float as _cf
            _A = round(_cf.FLOAT_A / 2)          # 540-wide proxy = half scale
            _fx, _fy = _cf.overlay_xy(-_A, -_A, amp=_A)
            mp4 = build_dir / f"{tag}.mp4"
            subprocess.run(
                [ff, "-y", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=c=0x10131C:s=540x960:r=30",
                 "-framerate", "30", "-i", str(build_dir / f"{tag}_build%02d.png"),
                 "-filter_complex",
                 f"[1:v]scale={540 + 2 * _A}:-1,format=rgba[c];"
                 f"[0:v][c]overlay=x='{_fx}':y='{_fy}':shortest=1,"
                 f"format=yuv420p",
                 "-pix_fmt", "yuv420p", str(mp4)], check=True, timeout=120)
            from scripts.showrunner_review import _temporal_evidence
            with tempfile.TemporaryDirectory() as td:
                ev = _temporal_evidence(mp4, Path(td))
            fps = ev.get("effective_fps") or 0.0
            fps_score = min(1.0, fps / 24.0)
        except Exception:  # noqa: BLE001
            pass
    # safe-margin / clipping proxy: opaque pixels crowding the canvas border of
    # the FINAL frame (content or mascot running off the card)
    last = Image.open(fs[-1]).convert("RGBA")
    a = last.getchannel("A")
    w, h = last.size
    px = a.load()
    border = sum((px[x, 0] > 40) + (px[x, h - 1] > 40) for x in range(w)) + \
        sum((px[0, y] > 40) + (px[w - 1, y] > 40) for y in range(h))
    clipping = border / max(1, 2 * (w + h))
    total = 0.45 * fps_score + 0.35 * min(1.0, fullness / 0.5) + 0.20 * contact
    return {"score": round(total, 4), "fps_score": round(fps_score, 3),
            "fullness": round(fullness, 3), "contact": round(contact, 3),
            "clipping": round(clipping, 4),
            "objective_pass": bool(fps_score >= 0.45 and fullness >= 0.15
                                   and contact >= 0.9 and clipping < 0.05)}


_RANK_PROMPT = """You are the channel's strict scene-repair judge. These frames \
show {n} CANDIDATE scenes (labelled candidate_0, candidate_1, ...) for the SAME \
beat of a data short. The narration claim: "{claim}".

Rank the candidates by which makes the best SCENE — judge what a viewer sees: \
does the visual action EXPLAIN the claim, is the mascot's bit readable (goal, \
effort, consequence), is the composition clean, is it interesting rather than \
repetitive or busy? Technical smoothness is already filtered — do not reward it.

Return ONLY JSON:
{{"winner":str,"ranking":[str],"reasons":{{}},"confidence":float}}"""


def vision_rank(bdir: Path, survivors: list[dict], claim: str) -> dict | None:
    """Rank surviving candidates with the SHOWRUNNER's own vision judge
    (review 3.1): creative evaluation, not alpha statistics. Returns the
    ranking dict, or None when no vision backend is available (logged; the
    caller then proceeds objective-only in DEGRADED mode)."""
    try:
        import importlib.util as _il
        spec = _il.spec_from_file_location(
            "showrunner_review", REPO / "scripts" / "showrunner_review.py")
        sr = _il.module_from_spec(spec)
        spec.loader.exec_module(sr)
        labeled = []
        for c in survivors:
            tag = c["tag"]
            fs = sorted(bdir.glob(f"{tag}_build*.png"))
            for pick, ph in ((0, "start"), (len(fs) // 2, "mid"),
                             (len(fs) - 1, "end")):
                if fs:
                    # (path, label, seconds) — the SAME shape the judge
                    # unpacks (`for p, lab, ts in labeled`). This used to
                    # append (label, path): two items, reversed, so every
                    # call died on "not enough values to unpack (expected
                    # 3, got 2)" and vision ranking NEVER ran. Every repair
                    # in production fell to "DEGRADED: objective-only", and
                    # the objective score saturates at exactly 1.0 for all
                    # three candidates — so repair was picking blind, and
                    # picked the same trend+drag_line every single time.
                    labeled.append((fs[pick],
                                    f"candidate_{c['index']}@{ph}",
                                    pick / 30.0))
        grades, backend = sr._judge(
            _RANK_PROMPT.format(n=len(survivors), claim=claim[:200]), labeled)
        if grades.get("winner"):
            grades["judge"] = backend
            return grades
    except Exception as e:  # noqa: BLE001
        print(f"[scene_repair] DEGRADED: vision ranking unavailable "
              f"({str(e)[:90]}) — objective-only selection", flush=True)
    return None


def propose(slug: str, verdict: dict, frames: int = 60,
            apply_plan: bool = False) -> dict:
    from data_learning import story, charts
    cfg = json.loads((REPO / "data_learning" / "niche.config.json").read_text())
    story_cfg = next(s for s in cfg["stories"] if s["slug"] == slug)
    with tempfile.TemporaryDirectory() as td:
        st = story.build(story_cfg, cfg, Path(td), REPO)
        segs = [s for s in st.segments if getattr(s, "insight", None)]
        idx = failing_scene(verdict, len(segs), slug=slug)
        base = segs[idx].insight
        shape = shape_of(base)
        cands = semantic_candidates(base, shape)
        claim = getattr(base, "main_insight", "") or ""
        print(f"[scene_repair] {slug}: failing scene = seg{idx} "
              f"(shape {shape}); {len(cands)} structural candidates")
        results = []
        bdir = Path(td) / "cands"
        for ci, cand in enumerate(cands):
            import copy
            ins = copy.deepcopy(base)
            ins.kind = cand["viz"]
            ins.plan_locked = True
            ins.perf_override = cand["perf"]
            if hasattr(ins, "perf_spec"):
                ins.perf_spec = None
            tag = f"c{ci}"
            try:
                charts.render_story_build(ins, bdir, tag, frames=frames)
                sc = score_candidate(bdir, tag, frames)
            except Exception as e:  # noqa: BLE001
                sc = {"score": 0.0, "objective_pass": False,
                      "detail": str(e)[:80]}
            results.append({**cand, **sc, "tag": tag, "index": ci})
            print(f"  cand{ci} {cand['viz']}+{cand['perf']}: {sc}")
        # TWO-GATE selection (review 3.1): objective checks REJECT, they do not
        # pick. Survivors go to the vision judge; the creative ranking chooses.
        survivors = [r for r in results if r.get("objective_pass")]
        if not survivors:
            survivors = sorted(results, key=lambda r: -r["score"])[:1]
            print("[scene_repair] no candidate passed the objective gate — "
                  "keeping the least-bad for diagnosis")
        ranking = vision_rank(bdir, survivors, claim) if len(survivors) > 1 \
            else None
        if ranking:
            try:
                w_i = int(str(ranking["winner"]).split("_")[-1])
                chosen = next(r for r in results if r["index"] == w_i)
                selection_mode = f"vision ({ranking.get('judge', '?')}, " \
                                 f"conf {ranking.get('confidence')})"
            except Exception:  # noqa: BLE001
                chosen = max(survivors, key=lambda r: r["score"])
                selection_mode = "objective (vision output unparseable)"
        else:
            chosen = max(survivors, key=lambda r: r["score"])
            selection_mode = ("objective-only DEGRADED (no vision backend)"
                             if len(survivors) > 1 else "single survivor")
        # incumbent = candidate matching the CURRENT (routed) kind, if present
        inc = next((r for r in results if r["viz"] == base.kind), None)
        margin = chosen["score"] - (inc["score"] if inc else 0.0)
        if ranking is None and inc is not None and margin <= 0.08:
            chosen = inc                # objective-only: hold without margin
        plan = {"slug": slug, "seg": idx, "shape": shape,
                "candidates": [{k: v for k, v in r.items() if k != "tag"}
                               for r in results],
                "chosen": {k: v for k, v in chosen.items() if k != "tag"},
                "selection_mode": selection_mode,
                "vision_ranking": ranking,
                "won_by_margin": round(margin, 4)}
        if apply_plan:
            PLANS_DIR.mkdir(parents=True, exist_ok=True)
            pf = PLANS_DIR / f"{slug}.json"
            existing = json.loads(pf.read_text()) if pf.exists() else {}
            existing[str(idx)] = {"viz": chosen["viz"], "perf": chosen["perf"]}
            pf.write_text(json.dumps(existing, indent=1))
            print(f"[scene_repair] plan applied -> {pf}")
        return plan


# ---------------------------------------------------------------------------
# HOOK + ENDING candidates (review Phase 7): three structurally different
# hooks / two endings, objective-gated, vision-ranked, winner persisted through
# the SAME scene-plan mechanism (segment 0 / last segment overrides).
# ---------------------------------------------------------------------------
HOOK_STRUCTURES = [
    # immediate consequence: the value moves violently from frame 1 and Data is
    # already being dragged by it
    {"name": "immediate_consequence", "perf": "drag_line"},
    # failed mascot attempt: he takes the hit and recovers — instant empathy
    {"name": "failed_attempt", "perf": "fail_recover"},
    # scale reveal: he is dwarfed/overwhelmed by the size of the thing
    {"name": "scale_reveal", "perf": "overwhelmed"},
]

ENDING_STRUCTURES = [
    # resolve with a transformation ta-da (new synthesis + visual consequence)
    {"name": "transform_payoff", "perf": "transform_reveal"},
    # resolve with the discovery/double-take presenting the final number
    {"name": "discover_payoff", "perf": "discover"},
]


def candidate_bout(slug: str, seg_idx: int, structures: list[dict],
                   frames: int, apply_plan: bool, label: str) -> dict:
    """Render structurally different candidates for ONE scene (hook or ending),
    objective-gate them, vision-rank survivors, persist the winner's plan."""
    from data_learning import story, charts
    cfg = json.loads((REPO / "data_learning" / "niche.config.json").read_text())
    story_cfg = next(s for s in cfg["stories"] if s["slug"] == slug)
    with tempfile.TemporaryDirectory() as td:
        st = story.build(story_cfg, cfg, Path(td), REPO)
        segs = [s for s in st.segments if getattr(s, "insight", None)]
        idx = seg_idx if 0 <= seg_idx < len(segs) else len(segs) - 1
        base = segs[idx].insight
        claim = getattr(base, "main_insight", "") or ""
        bdir = Path(td) / label
        results = []
        for ci, cand in enumerate(structures):
            import copy
            ins = copy.deepcopy(base)
            ins.plan_locked = True
            ins.perf_override = cand["perf"]
            if hasattr(ins, "perf_spec"):
                ins.perf_spec = None
            tag = f"c{ci}"
            try:
                charts.render_story_build(ins, bdir, tag, frames=frames,
                                          hook_lead=(label == "hook"))
                sc = score_candidate(bdir, tag, frames)
            except Exception as e:  # noqa: BLE001
                sc = {"score": 0.0, "objective_pass": False,
                      "detail": str(e)[:80]}
            results.append({**cand, "viz": base.kind, **sc,
                            "tag": tag, "index": ci})
            print(f"  {label} cand{ci} {cand['name']}: {sc}")
        survivors = [r for r in results if r.get("objective_pass")] or \
            sorted(results, key=lambda r: -r["score"])[:1]
        ranking = vision_rank(bdir, survivors, claim) \
            if len(survivors) > 1 else None
        if ranking:
            try:
                w_i = int(str(ranking["winner"]).split("_")[-1])
                chosen = next(r for r in results if r["index"] == w_i)
                mode = f"vision ({ranking.get('judge', '?')})"
            except Exception:  # noqa: BLE001
                chosen = max(survivors, key=lambda r: r["score"])
                mode = "objective (vision unparseable)"
        else:
            chosen = max(survivors, key=lambda r: r["score"])
            mode = "objective-only DEGRADED" if len(survivors) > 1 \
                else "single survivor"
        out = {"slug": slug, "seg": idx, "label": label,
               "candidates": [{k: v for k, v in r.items() if k != "tag"}
                              for r in results],
               "chosen": {k: v for k, v in chosen.items() if k != "tag"},
               "selection_mode": mode, "vision_ranking": ranking}
        if apply_plan:
            PLANS_DIR.mkdir(parents=True, exist_ok=True)
            pf = PLANS_DIR / f"{slug}.json"
            existing = json.loads(pf.read_text()) if pf.exists() else {}
            existing[str(idx)] = {"viz": chosen["viz"],
                                  "perf": chosen["perf"],
                                  "structure": chosen.get("name")}
            pf.write_text(json.dumps(existing, indent=1))
            print(f"[{label}_candidates] plan applied -> {pf}")
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--verdict")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--hooks", action="store_true",
                    help="run the 3-way hook candidate bout instead")
    ap.add_argument("--endings", action="store_true",
                    help="run the ending candidate bout instead")
    args = ap.parse_args()
    if args.hooks:
        out = candidate_bout(args.slug, 0, HOOK_STRUCTURES, args.frames,
                             args.apply, "hook")
        print(json.dumps({k: out[k] for k in ("chosen", "selection_mode")},
                         indent=1))
        return 0
    if args.endings:
        out = candidate_bout(args.slug, 10 ** 6, ENDING_STRUCTURES,
                             args.frames, args.apply, "ending")
        print(json.dumps({k: out[k] for k in ("chosen", "selection_mode")},
                         indent=1))
        return 0
    verdict = {}
    vp = Path(args.verdict) if args.verdict else \
        REPO / "output" / f"story_{args.slug}.showrunner.json"
    if vp.exists():
        verdict = json.loads(vp.read_text())
    plan = propose(args.slug, verdict, frames=args.frames,
                   apply_plan=args.apply)
    print(json.dumps({k: plan[k] for k in ("seg", "shape", "chosen",
                                           "won_by_margin")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
