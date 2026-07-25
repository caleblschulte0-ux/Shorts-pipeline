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


def better(a: dict | None, b: dict | None) -> dict | None:
    """The better of two verdicts: a ship beats a block; among same class, the
    higher score wins. None is worst. Used to KEEP-BEST across attempts."""
    if a is None:
        return b
    if b is None:
        return a
    ax = (a.get("verdict") == "ship", a.get("score") or 0)
    bx = (b.get("verdict") == "ship", b.get("score") or 0)
    return a if ax >= bx else b


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


def _default_scene_repair(slug: str, verdict: dict) -> None:
    """Run the real scene-addressable repair (3 structural candidates for the
    failing scene, keep-best, plan persisted for the next render)."""
    sys.path.insert(0, str(REPO / "scripts"))
    import scene_repair as _sr
    _sr.propose(slug, verdict, apply_plan=True)


def repair(slug: str, max_iters: int = 2, render_fn=_default_render,
           scene_repair_fn=_default_scene_repair) -> dict:
    """Drive render -> judge -> fix-weakest -> re-render, keeping the best cut.

    render_fn(slug, env) -> verdict dict is injected so the control flow is
    testable without rendering. Returns a summary: the best verdict, the trail
    of attempts, and why it stopped."""
    trail = []
    tried_remedies: set = set()
    env: dict = {}
    best = None
    stop = "exhausted"
    for i in range(max_iters + 1):          # 1 baseline + up to max_iters repairs
        verdict = render_fn(slug, env)
        trail.append({"iter": i, "env": dict(env),
                      "verdict": verdict.get("verdict"),
                      "score": verdict.get("score")})
        best = better(best, verdict)
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
    return {"slug": slug, "best": best, "attempts": trail, "stopped": stop,
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
