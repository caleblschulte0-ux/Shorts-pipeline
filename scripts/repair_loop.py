#!/usr/bin/env python3
"""Bounded self-repair loop: render -> judge -> fix the weakest thing -> re-render
-> KEEP the better cut -> stop after a small budget.

The showrunner is a sovereign veto but it is not, by itself, a fixer. This loop
is the thin autonomous driver around it: it renders a story, reads the gate's
verdict, and if the gate BLOCKS it makes ONE bounded, whitelisted change aimed
at the weakest dimension, re-renders, and keeps whichever cut the gate scored
higher. It never ships a worse cut, it never edits code, and it stops after a
fixed number of attempts — so it can run headless without running away.

It is deliberately conservative:
  - Remedies come from a WHITELIST of render-time env knobs (never code edits).
  - It KEEPS-BEST by the gate's own score — a repair that made things worse is
    discarded, so the loop is monotone in quality.
  - It is BOUNDED (default 2 repair attempts) and stops immediately on a ship.

The pure decision logic (weakest dimension, remedy pick, better-of) is factored
out and unit-tested in data_learning/tests/test_repair_loop.py so the control
flow is trustworthy without spending render minutes.

CLI:
    python scripts/repair_loop.py --slug world-power-mix [--max-iters 2]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _load_showrunner():
    spec = importlib.util.spec_from_file_location(
        "showrunner_review", REPO / "scripts" / "showrunner_review.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SR = _load_showrunner()

# WHITELIST of remedies: weakest dimension / auto-fail -> env knobs to try next
# render. Remedies are SCENE-ADDRESSABLE STRUCTURAL CHANGES (scripts/
# scene_repair.py): three structurally different plans for the failing scene,
# blind-scored, keep-best, persisted to state/scene_plans/{slug}.json which the
# renderer applies. NO variance rerolls, NO env nudges, NO MASCOT_BRAIN=1 —
# every attempt renders a deliberately different scene, deterministically.
REMEDIES = {
    "mascot": {"scene_repair": True},
    "decorative_mascot": {"scene_repair": True},
    "empty_void": {"scene_repair": True},
    "temporal_craft": {"scene_repair": True},
    "temporal_gate": {"scene_repair": True},
    "dead_air": {"scene_repair": True},
    "craft": {"scene_repair": True},
    "pace": {"scene_repair": True},
}


def weakest_dimension(dims: dict) -> str | None:
    """The dimension furthest from its ceiling (biggest headroom). Ties break to
    the higher-weighted dimension so the loop spends its one shot where it moves
    the score most."""
    worst, worst_key = 2.0, None
    for k, (w, ceil) in SR.WEIGHTS.items():
        g = max(0, min(ceil, int(dims.get(k, 0))))
        frac = g / ceil
        # rank by (fraction filled, then -weight) ascending
        key = (frac, -w)
        if worst_key is None or key < worst:
            worst, worst_key = key, k
    return worst_key


def pick_remedy(verdict: dict, already: set) -> dict | None:
    """Choose the next STRUCTURAL remedy: address a hard auto-fail first, else
    the weakest dimension. The remedy is a scene-repair pass (a deliberately
    different scene plan for the failing scene), never an env nudge or a reroll.
    Returns None when there is no un-tried remedy class left (the loop then
    stops, honestly)."""
    # auto_fails look like ["dead_air: <evidence>", ...]; take the check name.
    for af in verdict.get("auto_fails", []) or []:
        name = af.split(":", 1)[0].strip()
        if name in REMEDIES and name not in already:
            return {"target": name, "env": REMEDIES[name]}
    weak = weakest_dimension(verdict.get("dimensions", {}) or {})
    if weak in REMEDIES and weak not in already:
        return {"target": weak, "env": REMEDIES[weak]}
    return None


def _cmp_key(v: dict) -> tuple:
    """Total-order key for the comparison HIERARCHY (higher = better):
    1. ship beats block
    2. no hard failures beats hard failures
    3. higher total score
    4. higher lowest dimension
    5. better temporal (higher effective fps)
    6. lower duplicate ratio
    """
    dims = v.get("dimensions") or {}
    temporal = v.get("temporal") or {}
    return (
        1 if v.get("verdict") == "ship" else 0,
        0 - len(v.get("auto_fails") or []),
        v.get("score") or 0,
        min(dims.values()) if dims else 0,
        temporal.get("effective_fps") or 0.0,
        0.0 - (temporal.get("duplicate_ratio")
               if temporal.get("duplicate_ratio") is not None else 1.0),
    )


def better(a: dict | None, b: dict | None) -> dict | None:
    """The better of two verdicts under the full comparison hierarchy. None is
    worst. Used to KEEP-BEST across attempts; ties keep the INCUMBENT (a)."""
    if a is None:
        return b
    if b is None:
        return a
    return a if _cmp_key(a) >= _cmp_key(b) else b


def _default_render(slug: str, env: dict) -> dict:
    """Render + judge one story via the real pipeline (dry-run, never uploads),
    then read the showrunner verdict it wrote. Returns the verdict dict."""
    run_env = {**os.environ, **env}
    subprocess.run(
        [sys.executable, "scripts/post_stories.py", "--dry-run", "--force",
         "--slugs", slug],
        cwd=REPO, env=run_env, check=False)
    vpath = REPO / "output" / f"story_{slug}.showrunner.json"
    if not vpath.exists():
        return {"verdict": "unknown", "score": None,
                "note": "no verdict written (gate did not run)"}
    return json.loads(vpath.read_text())


# ---------------------------------------------------------------------------
# TRANSACTIONAL attempts. Every attempt snapshots its full state (scene plan,
# rendered mp4, verdict, per-scene artifacts) into its own directory; the
# winner is explicitly PROMOTED back to the canonical outputs + plan afterward.
# A worse repair can therefore never leave the repo configured to reproduce it:
# "keep best" restores the best SYSTEM STATE, not just a remembered score.
# ---------------------------------------------------------------------------
def _plan_path(slug: str, repo: Path) -> Path:
    return repo / "state" / "scene_plans" / f"{slug}.json"


def _canon_paths(slug: str, repo: Path) -> dict:
    out = repo / "output"
    return {"video": out / f"story_{slug}.mp4",
            "verdict": out / f"story_{slug}.showrunner.json",
            "scenes": out / "scenes" / slug}


def snapshot_attempt(slug: str, attempt_dir: Path, verdict: dict,
                     repo: Path = REPO) -> None:
    """Copy the attempt's full state into its isolated directory."""
    attempt_dir.mkdir(parents=True, exist_ok=True)
    pp = _plan_path(slug, repo)
    (attempt_dir / "scene_plan.json").write_text(
        pp.read_text() if pp.exists() else "{}")
    (attempt_dir / "verdict.json").write_text(json.dumps(verdict, indent=1))
    cp = _canon_paths(slug, repo)
    if cp["video"].exists():
        shutil.copy2(cp["video"], attempt_dir / "video.mp4")
    if cp["scenes"].exists():
        shutil.copytree(cp["scenes"], attempt_dir / "scenes",
                        dirs_exist_ok=True)


def promote_attempt(attempt_dir: Path, slug: str, repo: Path = REPO) -> None:
    """Make an attempt's snapshot the CANONICAL state: scene plan, promoted
    video, verdict-of-record and scene artifacts all restored from it."""
    pp = _plan_path(slug, repo)
    plan_text = (attempt_dir / "scene_plan.json").read_text() \
        if (attempt_dir / "scene_plan.json").exists() else "{}"
    if plan_text.strip() in ("", "{}"):
        if pp.exists():
            pp.unlink()                      # winner had NO plan -> none active
    else:
        pp.parent.mkdir(parents=True, exist_ok=True)
        pp.write_text(plan_text)
    cp = _canon_paths(slug, repo)
    if (attempt_dir / "video.mp4").exists():
        cp["video"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(attempt_dir / "video.mp4", cp["video"])
    if (attempt_dir / "verdict.json").exists():
        cp["verdict"].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(attempt_dir / "verdict.json", cp["verdict"])
    if (attempt_dir / "scenes").exists():
        if cp["scenes"].exists():
            shutil.rmtree(cp["scenes"])
        shutil.copytree(attempt_dir / "scenes", cp["scenes"])


def _default_scene_repair(slug: str, verdict: dict) -> None:
    """Run the real scene-addressable repair (3 structural candidates for the
    failing scene, keep-best, plan persisted for the next render)."""
    sys.path.insert(0, str(REPO / "scripts"))
    import scene_repair as _sr
    _sr.propose(slug, verdict, apply_plan=True)


def repair(slug: str, max_iters: int = 2, render_fn=_default_render,
           scene_repair_fn=_default_scene_repair, run_root: Path | None = None,
           repo: Path = REPO) -> dict:
    """Drive render -> judge -> fix-weakest -> re-render, keeping the best cut.

    TRANSACTIONAL: every attempt snapshots its plan + video + verdict + scene
    artifacts into output/repair_runs/{slug}/{run_id}/attempt_N/ and the best
    attempt is explicitly PROMOTED to the canonical state at the end — a worse
    repair can never leave its plan or outputs active.

    render_fn(slug, env) -> verdict dict is injected so the control flow is
    testable without rendering. Returns a summary: the best verdict, the trail
    of attempts, why it stopped, and the promoted attempt directory."""
    import time as _t
    run_id = _t.strftime("%Y%m%dT%H%M%SZ", _t.gmtime())
    root = run_root or (repo / "output" / "repair_runs" / slug / run_id)
    trail = []
    tried_remedies: set = set()
    env: dict = {}
    best, best_dir = None, None
    stop = "exhausted"
    for i in range(max_iters + 1):          # 1 baseline + up to max_iters repairs
        verdict = render_fn(slug, env)
        adir = root / f"attempt_{i}"
        try:
            snapshot_attempt(slug, adir, verdict, repo)
        except Exception as e:  # noqa: BLE001 — snapshot failure is loud but
            print(f"[repair] snapshot failed: {e}")           # not fatal
        trail.append({"iter": i, "env": dict(env), "dir": str(adir),
                      "verdict": verdict.get("verdict"),
                      "score": verdict.get("score")})
        prev_best = best
        best = better(best, verdict)
        if best is verdict or prev_best is None:
            best_dir = adir
        if verdict.get("verdict") == "ship":
            stop = "shipped"
            break
        if i == max_iters:
            stop = "budget_exhausted"
            break
        remedy = pick_remedy(verdict, tried_remedies)
        if remedy is None:
            stop = "no_remedy_left"
            break
        tried_remedies.add(remedy["target"])
        if remedy["env"].get("scene_repair"):
            # SCENE-ADDRESSABLE: pick the failing scene, render 3 structurally
            # different candidates, keep-best, persist the plan — the next
            # render applies it. Never a reroll of the same video.
            try:
                scene_repair_fn(slug, verdict)
            except Exception as e:  # noqa: BLE001 — a failed proposal just
                print(f"[repair] scene repair failed: {e}")   # ends the loop
                stop = "scene_repair_failed"
                break
        else:
            env = {**env, **remedy["env"]}
    # PROMOTE the winner: canonical plan + video + verdict + scenes = best
    # attempt's snapshot. This is the rollback guarantee — even if the LAST
    # render was worse, the repo state now reproduces the BEST one.
    if best_dir is not None:
        try:
            promote_attempt(best_dir, slug, repo)
            (root / "winner.json").parent.mkdir(parents=True, exist_ok=True)
            (root / "winner.json").write_text(json.dumps(
                {"attempt": best_dir.name, "score": (best or {}).get("score"),
                 "verdict": (best or {}).get("verdict")}, indent=1))
            print(f"[repair] promoted {best_dir.name} "
                  f"(score={(best or {}).get('score')})")
        except Exception as e:  # noqa: BLE001
            print(f"[repair] promotion failed: {e}")
    return {"slug": slug, "best": best, "attempts": trail, "stopped": stop,
            "run_dir": str(root), "promoted": str(best_dir or ""),
            "shipped": (best or {}).get("verdict") == "ship"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--max-iters", type=int, default=2,
                    help="repair attempts after the baseline render (default 2)")
    args = ap.parse_args()
    summary = repair(args.slug, max_iters=args.max_iters)
    print(json.dumps(summary, indent=2))
    # Exit 0 if we ended on a shippable cut, else 2 (matches showrunner CLI).
    return 0 if summary["shipped"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
