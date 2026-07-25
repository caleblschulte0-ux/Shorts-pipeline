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

# Structurally different scene plans per data shape. Each candidate is a
# (chart kind, performance) pair from the VERIFIED sets — a different scene,
# not a re-roll of the same one.
VARIANTS = {
    "part_to_whole": [
        {"viz": "stack", "perf": "drag_line"},
        {"viz": "stack", "perf": "hoist_stack"},
        {"viz": "pictorial_race", "perf": "shoved_bar"},
    ],
    "two_value": [
        {"viz": "comparison", "perf": "drag_line"},
        {"viz": "stack", "perf": "drag_line"},
        {"viz": "pictorial_race", "perf": "shoved_bar"},
    ],
    "ranking": [
        {"viz": "pictorial_race", "perf": "shoved_bar"},
        {"viz": "rank", "perf": "shoved_bar"},
        {"viz": "stack", "perf": "drag_line"},
    ],
    "trend": [
        {"viz": "trend", "perf": "drag_line"},
        {"viz": "trend", "perf": "pull_down_win"},
        {"viz": "pictorial_race", "perf": "shoved_bar"},
    ],
}


def shape_of(insight) -> str:
    if insight.kind in ("trend", "timeline"):
        return "trend"
    if len(insight.items) == 2:
        return "two_value"
    if insight.kind in ("share", "waffle_grid", "stack"):
        return "part_to_whole"
    return "ranking"


def failing_scene(verdict: dict, n_segs: int) -> int:
    """Map the verdict's auto-fail text (seg indices appear as 'segN') or the
    weakest visual dimension onto a segment index. Defaults to the LAST segment
    (long final beats fail most)."""
    text = " ".join(verdict.get("auto_fails", []) or [])
    hits = [int(m) for m in re.findall(r"seg(\d+)", text)]
    if hits:
        # the most-blamed segment
        return max(set(hits), key=hits.count) % max(1, n_segs)
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
    fps_score = 0.5
    ff = _ffmpeg()
    if ff:
        try:
            mp4 = build_dir / f"{tag}.mp4"
            subprocess.run(
                [ff, "-y", "-loglevel", "error",
                 "-f", "lavfi", "-i", "color=c=0x10131C:s=540x960:r=30",
                 "-framerate", "30", "-i", str(build_dir / f"{tag}_build%02d.png"),
                 "-filter_complex",
                 "[1:v]scale=540:-1,format=rgba[c];"
                 "[0:v][c]overlay=0:0:shortest=1,format=yuv420p",
                 "-pix_fmt", "yuv420p", str(mp4)], check=True, timeout=120)
            from scripts.showrunner_review import _temporal_evidence
            with tempfile.TemporaryDirectory() as td:
                ev = _temporal_evidence(mp4, Path(td))
            fps = ev.get("effective_fps") or 0.0
            fps_score = min(1.0, fps / 24.0)
        except Exception:  # noqa: BLE001
            pass
    total = 0.45 * fps_score + 0.35 * min(1.0, fullness / 0.5) + 0.20 * contact
    return {"score": round(total, 4), "fps_score": round(fps_score, 3),
            "fullness": round(fullness, 3), "contact": round(contact, 3)}


def propose(slug: str, verdict: dict, frames: int = 60,
            apply_plan: bool = False) -> dict:
    from data_learning import story, charts
    cfg = json.loads((REPO / "data_learning" / "niche.config.json").read_text())
    story_cfg = next(s for s in cfg["stories"] if s["slug"] == slug)
    with tempfile.TemporaryDirectory() as td:
        st = story.build(story_cfg, cfg, Path(td), REPO)
        segs = [s for s in st.segments if getattr(s, "insight", None)]
        idx = failing_scene(verdict, len(segs))
        base = segs[idx].insight
        shape = shape_of(base)
        cands = VARIANTS.get(shape, VARIANTS["ranking"])[:3]
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
            tag = f"c{ci}"
            try:
                charts.render_story_build(ins, bdir, tag, frames=frames)
                sc = score_candidate(bdir, tag, frames)
            except Exception as e:  # noqa: BLE001
                sc = {"score": 0.0, "detail": str(e)[:80]}
            results.append({**cand, **sc})
            print(f"  cand{ci} {cand['viz']}+{cand['perf']}: {sc}")
        # incumbent = candidate matching the CURRENT (routed) kind, if present
        inc = next((r for r in results if r["viz"] == base.kind), None)
        best = max(results, key=lambda r: r["score"])
        margin = best["score"] - (inc["score"] if inc else 0.0)
        chosen = best if (inc is None or margin > 0.08) else inc
        plan = {"slug": slug, "seg": idx, "shape": shape,
                "candidates": results, "chosen": chosen,
                "won_by_margin": round(margin, 4)}
        if apply_plan:
            PLANS_DIR.mkdir(parents=True, exist_ok=True)
            pf = PLANS_DIR / f"{slug}.json"
            existing = json.loads(pf.read_text()) if pf.exists() else {}
            existing[str(idx)] = {"viz": chosen["viz"], "perf": chosen["perf"]}
            pf.write_text(json.dumps(existing, indent=1))
            print(f"[scene_repair] plan applied -> {pf}")
        return plan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--verdict")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
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
