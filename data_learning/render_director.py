#!/usr/bin/env python3
"""THE RENDER-BUDGET DIRECTOR (CURIOSITY_BRAIN §7.5 v8).

Permanent law: premium time is allocated by NARRATIVE VALUE, not by beat
count. "A seven-second Blender payoff for every beat" sounds fair and is
bad directing — some beats deserve no Blender at all; major reveals
deserve 12-15 seconds.

This module decides, BEFORE a single Cycles frame is paid for:
  - which authored hero candidates render at all (low-value ones are
    ZEROED and their beats physicalize in the 2D world instead),
  - how many seconds each survivor gets (uneven, value-weighted),
  - the whole hero-integration plan the world engine executes (breach
    object, persistent consequence, capability grants, camera-out) —
    the engine decides exactly WHEN; the director decides WHAT.

The budget is denominated in Cycles FRAMES, not seconds: the per-template
fps class (interpolation-suitability triage) makes seconds lie about
cost. Everything here is authoring-time fact — emotion tag, template
class, discovery, window length. The ledger verifies the plan later; it
never allocates. Pure stdlib: unit-testable without manim or Blender.

Every decision lands in an auditable report (<out>.director.json).
"""
from __future__ import annotations

import math
import os

# ~20s per CPU-Cycles frame at 1440x810 s32 → a 4-hour cap is ~720 frames.
DEFAULT_BUDGET_FRAMES = 720

# Interpolation-suitability triage (v8): slow pullbacks and gradual depth
# interpolate cleanly from 10fps; crossing objects and fast foreground
# edges need 15. Priced here so the budget math stays honest.
FPS_CLASS = {"monoliths": 10, "earth_spin": 10, "earth_dive": 10,
             "orbit_fly": 15, "cosmic_exit": 15}

# How much a template can do that the 2D engine cannot (impossible-camera
# value) vs how nearly a flat exhibit could say the same thing (flat_2d
# penalty — a monolith lineup is a bar chart wearing lighting).
IMPOSSIBLE_CAMERA = {"earth_dive": 3, "cosmic_exit": 3, "orbit_fly": 2,
                     "earth_spin": 2, "monoliths": 1}
FLAT_2D_PENALTY = {"monoliths": 2, "earth_spin": 1}

# Mirrors shots.EMOTION_INTENSITY (this module must stay import-light).
EMOTION_VALUE = {"wonder": 1, "mystery": 1, "speed": 2, "scale": 2,
                 "heat": 2, "force": 2, "danger": 3, "awe": 3}

# Hero-integration defaults per template: what the camera breaches
# through, what stays changed in the 2D world afterwards, and which
# capability the premium window grants to every later beat.
# STATE keys as builders actually register them (scalelevel uses
# "level:<tableau>"); the engine falls back to the beat's group.
TEMPLATE_OBJECT = {"earth_spin": "level:earth", "earth_dive": "level:earth",
                   "orbit_fly": "level:earth", "cosmic_exit": "level:earth"}
TEMPLATE_CONSEQUENCE = {"earth_spin": "orbit_ring",
                        "monoliths": "standing_trail",
                        "earth_dive": "depth_mark"}
TEMPLATE_GRANTS = {"earth_spin": ["environment:space"],
                   "orbit_fly": ["environment:space"],
                   "cosmic_exit": ["environment:space"],
                   "earth_dive": ["environment:depth"],
                   "monoliths": ["object:monolith"]}

# Builders with a physicalized in-world mode (grown per iteration).
SUPPORTS_IN_WORLD = {"rank"}

MIN_HERO_SECONDS = 6.0
MAX_HERO_SECONDS = 15.0
MAX_BEAT_HEROES = 3
SPLICE_FACTOR = 1.3          # minterpolate slow-mo stretch ceiling
WINDOW_SHARE = 0.55          # a hero may cover at most this much window


def _fps(template: str) -> int:
    return int(FPS_CLASS.get(template, 10))


def _candidate(wp: dict) -> dict | None:
    """hero_candidate is the v8 authoring shape; a legacy `hero` entry
    (True / str / dict with fixed seconds) is auto-wrapped so old stories
    still render — but through the director, like everything else."""
    c = wp.get("hero_candidate")
    if c is None and wp.get("hero") is not None:
        h = wp["hero"]
        if h is True:
            c = {"template": "monoliths"}
        elif isinstance(h, str):
            c = {"template": h}
        else:
            c = dict(h)
            c.setdefault("max_seconds", c.pop("seconds", MAX_HERO_SECONDS))
    return c


def _value(cand: dict, wp: dict) -> tuple[int, dict]:
    t = cand.get("template", "monoliths")
    s = dict(cand.get("scores") or {})
    s.setdefault("mental_model", 2 if wp.get("discovery") else 1)
    s.setdefault("emotion", EMOTION_VALUE.get(wp.get("emotion"), 1))
    s.setdefault("impossible_camera", IMPOSSIBLE_CAMERA.get(t, 1))
    s.setdefault("flat_2d", FLAT_2D_PENALTY.get(t, 0))
    v = (2 * s["mental_model"] + s["emotion"]
         + s["impossible_camera"] - s["flat_2d"])
    return v, s


def plan_heroes(world: dict, waypoints: list[dict],
                windows: list[tuple[float, float]],
                budget_frames: int | None = None):
    """Returns (plans, report): plans maps beat index -> hero_plan dict
    (baked into the world spec; the engine breaches, mutates, and logs),
    report is the auditable record. windows[i+1] is beat i's narration
    window (windows[0] = title, windows[-1] = closing)."""
    if budget_frames is None:
        budget_frames = int(os.environ.get(
            "CURIO_PREMIUM_FRAMES", DEFAULT_BUDGET_FRAMES))

    # Fixed structural heroes (cold open / ending) come off the top:
    # they are the flagship bookends, never rationed against beats.
    fixed = []
    fixed_frames = 0
    for hz in world.get("heroes", []) or []:
        t = hz.get("template", "orbit_fly")
        fr = int(round(float(hz.get("seconds", 7.0)) * _fps(t)))
        fixed.append({"window": hz.get("window"), "template": t,
                      "frames": fr})
        fixed_frames += fr
    beat_frames = max(0, budget_frames - fixed_frames)

    cands = []
    for i, wp in enumerate(waypoints):
        c = _candidate(wp)
        if not c:
            continue
        t = c.get("template", "monoliths")
        v, scores = _value(c, wp)
        w0, w1 = windows[i + 1] if i + 1 < len(windows) else (0.0, 0.0)
        win = max(0.0, w1 - w0)
        hi = min(MAX_HERO_SECONDS, float(c.get("max_seconds",
                                               MAX_HERO_SECONDS)),
                 WINDOW_SHARE * win / SPLICE_FACTOR)
        cands.append({
            "beat": i, "id": f"h{i}", "template": t, "value": v,
            "scores": scores, "fps": _fps(t), "hi": hi,
            "object": c.get("object", TEMPLATE_OBJECT.get(t, "")),
            "consequence": c.get("consequence",
                                 TEMPLATE_CONSEQUENCE.get(t, "orbit_ring")),
            "grants": c.get("grants", TEMPLATE_GRANTS.get(t, [])),
            "camera_out": float(c.get("camera_out", 1.18)),
            "intensity": int(c.get("intensity", 1)),
        })

    report = {"budget_frames": budget_frames, "fixed": fixed,
              "beat_frames": beat_frames, "candidates": [], "plan": [],
              "in_world_beats": []}

    # --- selection: zero-out, then cap the count -------------------------
    top = max((c["value"] for c in cands), default=0)
    floor = max(4, 0.5 * top)
    live, dead = [], []
    for c in cands:
        if c["value"] < floor or c["hi"] < MIN_HERO_SECONDS:
            why = ("window too small for a hero"
                   if c["hi"] < MIN_HERO_SECONDS else
                   f"zeroed: value {c['value']} under floor {floor:g}")
            dead.append((c, why))
        else:
            live.append(c)
    live.sort(key=lambda c: -c["value"])
    for c in live[MAX_BEAT_HEROES:]:
        dead.append((c, f"zeroed: beat-hero cap is {MAX_BEAT_HEROES}"))
    live = live[:MAX_BEAT_HEROES]

    # --- allocation: value²-weighted water-fill in FRAMES ----------------
    def cost(cs, secs):
        return sum(int(round(secs[c["id"]] * c["fps"])) for c in cs)

    secs = {}
    while live:
        lo = {c["id"]: MIN_HERO_SECONDS for c in live}
        if live[0]["value"] >= 7:                    # the flagship reveal
            lo[live[0]["id"]] = min(12.0, live[0]["hi"])
        wsum = sum(c["value"] ** 2 for c in live)
        pool = beat_frames / max(1, sum(c["fps"] for c in live)) * len(live)
        secs = {c["id"]: max(lo[c["id"]],
                             min(c["hi"], pool * c["value"] ** 2 / wsum))
                for c in live}
        for _ in range(6):                # clamped proportional refine
            over = cost(live, secs) - beat_frames
            if over <= 0:
                break
            shrink = [c for c in live if secs[c["id"]] > lo[c["id"]]]
            if not shrink:
                break
            cut = over / sum(c["fps"] for c in shrink)
            for c in shrink:
                secs[c["id"]] = max(lo[c["id"]], secs[c["id"]] - cut)
        if cost(live, secs) <= beat_frames:
            break
        dropped = live.pop()              # lowest value pays first
        dead.append((dropped, "zeroed: over frame budget"))

    # Nobody outranks the flagship: seconds must be monotonic in value,
    # or a mid-value beat ends up with the biggest premium window.
    cap = float("inf")
    for c in live:
        secs[c["id"]] = cap = min(secs[c["id"]], cap)

    for c, why in dead:
        report["candidates"].append({**{k: c[k] for k in
                                        ("beat", "id", "template", "value",
                                         "scores")},
                                     "seconds": 0, "reason": why})

    plans = {}
    for c in live:
        s = round(secs[c["id"]], 1)
        w0, w1 = windows[c["beat"] + 1]
        splice = round(min(SPLICE_FACTOR * s, WINDOW_SHARE * (w1 - w0)), 2)
        plans[c["beat"]] = {
            "id": c["id"], "template": c["template"], "seconds": s,
            "fps": c["fps"], "splice": splice, "object": c["object"],
            "consequence": c["consequence"], "camera_out": c["camera_out"],
            "grants": c["grants"], "intensity": c["intensity"],
        }
        report["candidates"].append(
            {**{k: c[k] for k in ("beat", "id", "template", "value",
                                  "scores")},
             "seconds": s, "splice": splice,
             "reason": ("flagship reveal — floored at 12s"
                        if c is live[0] and c["value"] >= 7 and s >= 12
                        else "value-weighted fill")})
        report["plan"].append(c["id"])

    # --- no-downgrade: physicalize charts after the first grant ----------
    first_env = min((c["beat"] for c in live
                     if any(g.startswith("environment:")
                            for g in c["grants"])), default=None)
    if first_env is not None:
        for i, wp in enumerate(waypoints):
            if i > first_env and wp.get("builder") in SUPPORTS_IN_WORLD:
                report["in_world_beats"].append(i)

    report["frames_spent"] = fixed_frames + cost(live, secs)
    report["candidates"].sort(key=lambda c: c["beat"])
    return plans, report
