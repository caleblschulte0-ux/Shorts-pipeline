#!/usr/bin/env python3
"""The cinematic vocabulary — named, reusable SHOTS (CURIOSITY_BRAIN §7.5).

Operator doctrine, verbatim: "The viewer should feel like they are RIDING
THE CAMERA, not watching a presentation." Cinematography is not invented
per video; it is CHOSEN from this library, like a documentary editor
choosing proven shots. Every shot added here upgrades every future video.

A SHOT owns everything cinematic about one waypoint visit: the approach
path, the arrival choreography (including chrome in/out), the dwell motion
(never static), and it consumes exactly its narration window. The world
engine's waypoint loop is a thin dispatcher over this registry.

Shot signature:  SHOTS[name](scene, ctx) -> None
ctx keys: frame, anchor (np.array), fw, dur, group, arrival_anims,
          chrome_factory (callable -> pinned mobject), idx, is_scale,
          anchors_all (for multi-level shots), prev_rot (accumulated frame
          rotation — shots that rotate must unwind by dwell end).

Travel:  fly_to · dive · pull_back · track · follow_path
Dwell:   orbit · push_in · drift_hold · parallax_sweep
Reveal:  reveal (Restore from pre-shrunk state as the camera arrives)
         counter_surge (zoom emphasis while the number races)
Story:   comparison_race (builder-driven) · stack_build · timeline_travel
Special: zoom_rush (the cold open — the WHOLE ride in seconds)
"""
from __future__ import annotations

import math

import numpy as np
from manim import FadeIn, FadeOut, Restore, rate_functions

SHOTS = {}


def shot(name):
    def reg(fn):
        SHOTS[name] = fn
        return fn
    return reg


# Default cycles per world template — un-annotated stories still get varied
# cinematography, and the dispatcher never repeats a shot back-to-back.
DEFAULT_TRAVEL = {
    "depth": ["dive", "fly_to", "dive", "follow_path"],
    "scale": ["pull_back", "pull_back", "pull_back", "pull_back"],
    "system": ["track", "fly_to", "track", "follow_path"],
}
DEFAULT_DWELL = {
    "depth": ["orbit", "drift_hold", "push_in", "parallax_sweep"],
    "scale": ["drift_hold", "orbit", "push_in", "parallax_sweep"],
    "system": ["push_in", "drift_hold", "orbit", "parallax_sweep"],
}

CHROME_SECONDS = 3.5      # text diet: chrome leaves after this
EVENT_GAP = 5.5           # escalation law: a new visual event this often


# ---------------------------------------------------------------------------
# THE LEDGER — the engine KNOWS what happened (§7.5 v4). Every travel,
# reveal, event, payoff, reaction and discovery logs a row; the world
# engine writes the ledger to disk and scripts/qa_escalation.py validates
# the escalation laws against it. Design QA runs on rules, not pixels.
# ---------------------------------------------------------------------------
LEDGER: list[dict] = []


def _now(scene) -> float:
    return round(float(getattr(scene.renderer, "time", 0.0)), 2)


def log_event(scene, kind: str, **detail):
    LEDGER.append({"t": _now(scene), "kind": kind, **detail})


# ---------------------------------------------------------------------------
# INTENSITY — the world has a state machine (§7.5 v5: WORLD CONSEQUENCE).
# calm(0) → fast(1) → extreme(2) → cosmic(3), set at every beat start and
# MONOTONIC: the world remembers it is accelerating and never calms back
# down. Intensity drives, automatically: the STANDING star-streak factor,
# the dust layer's drift velocity (read live by its updater), dwell-leg
# energy, punch magnitude, and the auto reaction cadence.
# ---------------------------------------------------------------------------
INTENSITY = {"level": 0, "stretch": 1.0}

# CAPABILITIES (§7.5 v8 — the NO-DOWNGRADE LAW): visual capabilities the
# world has gained (environment:space, environment:depth, ...). Granted
# by hero breaches, NEVER revoked; every later beat logs that it runs
# with the granted layers in frame. Cleared per render by the engine.
CAPS: set = set()

EMOTION_INTENSITY = {"wonder": 1, "mystery": 1, "speed": 2, "scale": 2,
                     "heat": 2, "force": 2, "danger": 3, "awe": 3}

_STREAK = [1.0, 1.35, 1.85, 2.5]      # standing star-stretch per level


def _energy() -> float:
    return 1.0 + 0.35 * INTENSITY["level"]


def set_intensity(scene, ctx, level: int) -> float:
    """Raise the world state (never lowers). Plays the standing streak
    change on the backdrop, logs a `state` ledger row, returns seconds
    consumed."""
    level = max(0, min(3, int(level)))
    if level <= INTENSITY["level"]:
        return 0.0
    INTENSITY["level"] = level
    log_event(scene, "state", beat=ctx.get("idx"), what="intensity",
              to=level)
    bg = ctx.get("backdrop")
    target = _STREAK[level]
    factor = target / INTENSITY["stretch"]
    INTENSITY["stretch"] = target
    if bg is None or len(bg) == 0 or abs(factor - 1.0) < 1e-3:
        return 0.0
    rt = 0.6
    scene.play(bg.animate.stretch(factor, 0), run_time=rt,
               rate_func=rate_functions.ease_in_out_sine)
    return rt


# ---------------------------------------------------------------------------
# REACTIONS — narration changes the world ("Every fact should change the
# world"). World-level effects: they touch the backdrop/camera/frame, not
# the exhibit. All geometry/position based (gate-safe).
# ---------------------------------------------------------------------------
def _fx_star_streak(scene, ctx, rt=1.5):
    """Speed: the backdrop stars stretch into streaks, then relax."""
    bg = ctx.get("backdrop")
    if bg is None or len(bg) == 0:
        return _fx_shake(scene, ctx, rt)
    scene.play(bg.animate.stretch(2.4, 0), run_time=rt * 0.45,
               rate_func=rate_functions.ease_in_quad)
    scene.play(bg.animate.stretch(1 / 2.4, 0), run_time=rt * 0.55,
               rate_func=rate_functions.ease_out_sine)
    return rt


def _fx_shake(scene, ctx, rt=0.9):
    """Force/impact: camera micro-jitter, always returned to centre."""
    frame = ctx["frame"]
    fw = frame.width
    c = frame.get_center().copy()
    jolts = ((1.0, 0.6), (-0.9, -1.0), (0.7, -0.5), (-0.4, 0.8))
    leg = rt / (len(jolts) + 1)
    for dx, dy in jolts:
        scene.play(frame.animate.move_to(
            c + np.array([fw * 0.007 * dx, fw * 0.006 * dy, 0.0])),
            run_time=leg, rate_func=rate_functions.linear)
    scene.play(frame.animate.move_to(c), run_time=leg,
               rate_func=rate_functions.ease_out_sine)
    return rt


def _fx_glow_pulse(scene, ctx, rt=1.6):
    """Heat/energy: the backdrop warms, then cools."""
    bg = ctx.get("backdrop")
    if bg is None or len(bg) == 0:
        return _fx_shake(scene, ctx, rt)
    orig = bg[0].get_color()
    scene.play(bg.animate.set_color("#ffb27a"), run_time=rt * 0.4,
               rate_func=rate_functions.ease_in_sine)
    scene.play(bg.animate.set_color(orig), run_time=rt * 0.6,
               rate_func=rate_functions.ease_out_sine)
    return rt


def _fx_still(scene, ctx, rt=2.0):
    """Awe/silence: the world holds its breath — one near-still breath."""
    frame = ctx["frame"]
    scene.play(frame.animate.set(width=frame.width * 0.985),
               run_time=rt, rate_func=rate_functions.ease_in_out_sine)
    return rt


REACTIONS = {"star_streak": _fx_star_streak, "shake": _fx_shake,
             "glow_pulse": _fx_glow_pulse, "slow_drift_stop": _fx_still}

# Emotion seed (§7.5 v4): an emotion tag picks a default reaction when the
# author didn't name one. Full emotion system comes later.
EMOTION_FX = {"speed": "star_streak", "scale": "star_streak",
              "danger": "shake", "force": "shake",
              "heat": "glow_pulse", "wonder": "glow_pulse",
              "awe": "slow_drift_stop", "mystery": "slow_drift_stop"}


def _reactions_for(ctx) -> list[dict]:
    declared = list(ctx.get("react") or [])
    if not declared and ctx.get("emotion") in EMOTION_FX:
        # Auto cadence scales with the window: long beats get several
        # emotion-mapped reactions, not one (the engine applies the
        # reaction layer; authors only override for narration-causal
        # timing).
        n = 1 + int(float(ctx.get("dur", 0)) // 14)
        fx = EMOTION_FX[ctx["emotion"]]
        declared = [{"fx": fx,
                     "at": 0.42 + 0.45 * k / max(1, n - 1) if n > 1
                     else 0.55}
                    for k in range(n)]
    return [r for r in declared if r.get("fx") in REACTIONS]


def _fire_reaction(scene, ctx, spec) -> float:
    rt = REACTIONS[spec["fx"]](scene, ctx)
    log_event(scene, "reaction", beat=ctx.get("idx"), fx=spec["fx"], rt=rt)
    return rt


def _echo(scene, ctx) -> float:
    """FACT PROPAGATION (§7.5 v6): 'Every major fact must create a chain
    reaction.' The instant a payoff lands, the whole engine answers —
    stars jolt, dust surges (its updater reads intensity live), the
    camera recoils a breath — automatically, with no authoring. One
    fact; the world reacts."""
    frame = ctx["frame"]
    bg = ctx.get("backdrop")
    rt = 0.7
    jolt = [frame.animate.set(width=frame.width * 1.02)]
    if bg is not None and len(bg):
        jolt.append(bg.animate.stretch(1.16, 0))
    scene.play(*jolt, run_time=rt * 0.4,
               rate_func=rate_functions.ease_out_quad)
    relax = [frame.animate.set(width=frame.width / 1.012)]
    if bg is not None and len(bg):
        relax.append(bg.animate.stretch(1 / 1.16, 0))
    scene.play(*relax, run_time=rt * 0.6,
               rate_func=rate_functions.ease_in_out_sine)
    log_event(scene, "reaction", beat=ctx.get("idx"), fx="echo",
              cause="payoff", rt=rt)
    return rt


# ---------------------------------------------------------------------------
# DISCOVERIES — found, not navigated. An unexpected object crosses the
# frame during the approach; it is never narrated before it is seen.
# ---------------------------------------------------------------------------
def _play_discovery(scene, ctx) -> float:
    d = ctx.get("discovery")
    if not d:
        return 0.0
    from data_learning.world_builders import ASSETS
    make = ASSETS.get(str(d.get("asset", "comet")))
    if make is None:
        return 0.0
    frame = ctx["frame"]
    fw, fh = frame.width, frame.height
    m = make(1.0)
    m.scale(fw * 0.13 / max(m.width, 1e-6))
    c = frame.get_center()
    if d.get("cross", "lr") == "rl":
        start = c + np.array([fw * 0.62, -fh * 0.16, 0.0])
        end = c + np.array([-fw * 0.62, fh * 0.14, 0.0])
    else:
        start = c + np.array([-fw * 0.62, fh * 0.16, 0.0])
        end = c + np.array([fw * 0.62, -fh * 0.14, 0.0])
    m.move_to(start)
    scene.add(m)
    rt = 1.3
    scene.play(m.animate(path_arc=-0.22).move_to(end).scale(1.6),
               run_time=rt, rate_func=rate_functions.ease_in_out_sine)
    scene.remove(m)
    log_event(scene, "discovery", beat=ctx.get("idx"),
              asset=str(d.get("asset", "comet")), rt=rt)
    return rt


# ---------------------------------------------------------------------------
# The visit scaffold — the ESCALATION ENGINE. A beat is an event timeline:
#   approach -> [discovery] -> [reveal] -> chrome in -> reveal bundle ->
#   dwell leg -> event -> dwell leg -> reaction -> ... -> payoff -> tail
# ALL bundles beyond the first are scheduled across the whole window at
# EVENT_GAP, so a beat mechanically cannot sit still. Time bookkeeping
# keeps the visit EXACTLY ctx["dur"] seconds.
# ---------------------------------------------------------------------------
def _play_bundle(scene, ctx, b) -> float:
    rt = getattr(b, "run_time", 1.0)
    anims = list(b.anims) if hasattr(b, "anims") else [b]
    cam = getattr(b, "cam", None)
    if cam is not None:
        # CONSEQUENCE bundle: the event steers the camera (follow the
        # winner, get pulled along the orbit) — the fact happens TO the
        # viewer, not beside them. Dwell legs re-centre afterwards.
        anims.extend(cam(ctx) or [])
    elif getattr(b, "punch", False):
        # Payoff pop, scaled by world intensity.
        frame = ctx["frame"]
        anims.append(frame.animate.set(
            width=frame.width * (0.96 - 0.012 * INTENSITY["level"])))
    scene.play(*anims, run_time=rt)
    if getattr(b, "state", False):
        # this bundle PERMANENTLY changed the world (bars stay landed,
        # ticks stay lit, the fill stays past the marker)
        log_event(scene, "state", beat=ctx.get("idx"), what="entity",
                  rt=0.0)
    if getattr(b, "sem", None):
        # SEMANTIC PROGRESSION (§7.5 v8): this bundle introduced a new
        # visual idea — a counter merely climbing or a bar merely
        # extending never carries a sem tag.
        dim, what = b.sem
        log_event(scene, "semantic", beat=ctx.get("idx"), dim=dim,
                  what=what, rt=0.0)
    # DOMINANT-SUBJECT CONTRACT (§7.5 v8): who owns the frame now. A
    # punch owns it by definition (it pops the camera) — authored tags
    # refine the name.
    foc = getattr(b, "focus", None) or (
        "payoff" if getattr(b, "punch", False) else None)
    if foc:
        log_event(scene, "focus", beat=ctx.get("idx"), what=foc, rt=0.0)
    return rt


BREACH_RT = 1.1


def _breach_and_cover(scene, ctx, plan) -> float:
    """THE HERO-INTEGRATION CONTRACT (§7.5 v8). Setup already played
    (approach + reveal + arrival). This function plays stages 2-4:

    BREACH — an ACCELERATING push INTO the hero object (a push that
    never decelerates reads as 'we're going through it'). The logged
    breach row's t+rt IS the splice cut: the engine decides when, the
    assembler obeys the ledger.

    COVERED SPAN — the 2D take keeps rendering underneath the premium
    splice; that hidden time is spent MUTATING the world (intensity up,
    capability grant, the persistent consequence object, camera pulled
    farther out) so the return frame is already the changed world. A
    hero you could delete without changing later footage is decorative —
    this makes deletion structurally impossible."""
    from data_learning import world_builders as wb
    frame, fw, idx = ctx["frame"], ctx["fw"], ctx.get("idx")
    obj = wb.STATE.get(str(plan.get("object") or ""))
    if obj is None:
        obj = ctx.get("group")
    target = (np.array(obj.get_center()) if obj is not None
              else np.array(ctx["anchor"]))
    scene.play(frame.animate.move_to(target).set(width=fw * 0.28),
               run_time=BREACH_RT, rate_func=rate_functions.ease_in_quad)
    log_event(scene, "breach", beat=idx, hero=plan.get("id"),
              rt=BREACH_RT, splice=float(plan.get("splice", 7.0)))
    log_event(scene, "semantic", beat=idx, dim="camera", what="3d-breach",
              rt=0.0)
    cover = float(plan.get("splice", 7.0))
    used = set_intensity(scene, ctx,
                         INTENSITY["level"] + int(plan.get("intensity", 1)))
    grants = list(plan.get("grants") or [])
    if grants:
        CAPS.update(grants)
        log_event(scene, "capability", beat=idx, grant=grants,
                  by=plan.get("id"))
        fx = ctx.get("grant_fx")
        if fx is not None:
            used += fx(scene, ctx, grants)
    maker = getattr(wb, "CONSEQUENCES", {}).get(
        str(plan.get("consequence") or ""))
    if maker is not None:
        used += maker(scene, ctx, plan)
        log_event(scene, "state", beat=idx, what="hero_consequence",
                  hero=plan.get("id"),
                  consequence=plan.get("consequence"), rt=0.0)
    # Ride the rest of the covered span out to the resume frame — wider
    # than we left it: the world keeps the hero's altitude.
    left = cover - used
    out_w = fw * float(plan.get("camera_out", 1.18))
    if left > 0.3:
        scene.play(frame.animate.move_to(ctx["anchor"]).set(width=out_w),
                   run_time=left, rate_func=rate_functions.ease_in_out_sine)
    else:
        frame.move_to(ctx["anchor"]).set(width=out_w)
    log_event(scene, "semantic", beat=idx, dim="camera", what="3d-return",
              rt=0.0)
    return BREACH_RT + max(cover, used)


def _visit(scene, ctx, approach, dwell, approach_frac=0.28,
           reveal_target=None):
    frame, dur = ctx["frame"], ctx["dur"]
    idx = ctx.get("idx")
    t_approach = min(2.8, max(0.8, dur * approach_frac))
    # travel metrics feed the payoff grade: did the camera reveal new
    # space this beat?
    w0 = float(frame.width)
    moved = float(np.linalg.norm(
        np.array(frame.get_center()) - np.array(ctx["anchor"])))
    log_event(scene, "travel", beat=idx, shot=ctx.get("shot_name"),
              rt=round(t_approach, 2), w0=round(w0, 2),
              w1=round(float(ctx["fw"]), 2),
              moved=round(moved / max(float(ctx["fw"]), 1e-9), 3))
    if ctx.get("emotion"):
        log_event(scene, "emotion", beat=idx, tag=ctx["emotion"])
    # SEMANTIC PROGRESSION (§7.5 v8): what this arrival changes in the
    # viewer's understanding — new scale band, new environment, new
    # metaphor — prepared by the engine, logged as facts.
    for srow in ctx.get("semantics") or []:
        log_event(scene, "semantic", beat=idx, rt=0.0, **srow)
    # NO-DOWNGRADE LAW (§7.5 v8): once capabilities are granted, every
    # later beat runs with the granted layers literally in frame (the
    # persistent star sub-layer, the consequence objects, the intensity
    # machinery) — the row records that inheritance.
    if CAPS:
        consumed = sorted(CAPS)
        if ctx.get("in_world"):
            consumed.append("in_world")
        log_event(scene, "capability", beat=idx, consumed=consumed)
    spent = set_intensity(scene, ctx, int(ctx.get("intensity", 0)))
    approach(scene, ctx, t_approach)
    spent += t_approach
    spent += _play_discovery(scene, ctx)
    if reveal_target is not None:                       # the subject is BORN
        scene.play(Restore(reveal_target), run_time=0.7,
                   rate_func=rate_functions.ease_out_back)
        spent += 0.7
        log_event(scene, "reveal", beat=idx, rt=0.7)
    # Live counters (become+next_to updaters) must only run once the
    # subject is at full size — resuming before the reveal would pin a
    # full-size number to a shrunken ghost.
    g = ctx.get("group")
    if g is not None:
        g.resume_updating()
    chrome = ctx["chrome_factory"]()
    if chrome is not None:
        scene.add(chrome)
        scene.play(FadeIn(chrome), run_time=0.3)
        spent += 0.3

    bundles = list(ctx.get("arrival_anims") or [])
    if bundles:                       # the subject's arrival plays NOW …
        b = bundles.pop(0)
        rt = getattr(b, "run_time", 1.0)
        if spent + rt <= dur - 0.4:
            spent += _play_bundle(scene, ctx, b)
            log_event(scene, "reveal", beat=idx, rt=round(rt, 2))

    # HERO BREACH (§7.5 v8): Setup has played — if the director gave
    # this beat premium seconds, dive through the subject NOW. The
    # scheduler below then lands the beat's punch AFTER the return, so
    # the hero can never be a deletable cutaway. A window the plan
    # doesn't fit is a loud ledger fact the -ql gate fails on.
    plan = ctx.get("hero_plan")
    if plan:
        if dur - spent >= float(plan.get("splice", 7.0)) + BREACH_RT + 3.0:
            spent += _breach_and_cover(scene, ctx, plan)
        else:
            log_event(scene, "skipped", beat=idx, what="hero",
                      hero=plan.get("id"))

    # … and EVERYTHING else is scheduled across the window: events with
    # ADAPTIVE spacing (breathe at EVENT_GAP when time is generous,
    # compress when the window is tight — the payoff MUST land),
    # reactions at their authored fractions, chrome exit at its diet
    # time. Dwell legs are the filler between items.
    reactions = _reactions_for(ctx)

    def _fit_gap():
        n = len(bundles) + len(reactions)
        n_punch = sum(1 for b in bundles if getattr(b, "punch", False))
        need = (sum(getattr(b, "run_time", 1.0) for b in bundles)
                + 1.6 * len(reactions) + 0.7 * n_punch   # payoff echoes
                + 0.6 + 0.5 * n)                         # incl. min gaps
        avail = (dur - spent) - need
        return avail, max(0.5, min(EVENT_GAP,
                                   0.5 + avail / max(1, n)))

    avail, gap = _fit_gap()
    while avail < 0 and any(not getattr(b, "punch", False)
                            for b in bundles):
        # window physically too small — drop trailing non-payoffs first,
        # NEVER the punch (every beat must land its payoff)
        for k in range(len(bundles) - 1, -1, -1):
            if not getattr(bundles[k], "punch", False):
                log_event(scene, "skipped", beat=idx, what="event")
                del bundles[k]
                break
        avail, gap = _fit_gap()

    items = []
    if chrome is not None:
        items.append((spent + CHROME_SECONDS, "chrome_out", None))
    for r in reactions:
        items.append((dur * float(r.get("at", 0.55)), "react", r))
    t_cursor = spent
    prev_ends = {}
    for b in bundles:
        prev_ends[len(items)] = t_cursor      # end of what came before
        t_cursor += gap
        items.append((t_cursor, "event", b))
        t_cursor += getattr(b, "run_time", 1.0)
    # The beat must END STRONGER than it starts (payoff grade): pin the
    # last punch toward ~0.7 of the window — capped at 7.5s after the
    # PREVIOUS happening's END so the pin can never open a >9s hole,
    # and always fitting before the window closes.
    punch_ix = max((i for i, it in enumerate(items)
                    if it[1] == "event" and getattr(it[2], "punch", False)),
                   default=None)
    if punch_ix is not None:
        t_nat, _, pb = items[punch_ix]
        rt_p = getattr(pb, "run_time", 1.0)
        cap = prev_ends.get(punch_ix, t_nat) + 7.5
        items[punch_ix] = (max(t_nat, min(0.68 * dur, cap,
                                          dur - rt_p - 0.6)), "event", pb)
    items.sort(key=lambda x: x[0])

    for target, kind, payload in items:
        left = dur - spent
        need = (0.4 if kind == "chrome_out" else
                getattr(payload, "run_time", 1.0) if kind == "event" else 1.6)
        if need > left - 0.05:
            if kind != "chrome_out":
                log_event(scene, "skipped", beat=idx, what=kind)
            continue
        gap = min(target - spent, left - need - 0.05)
        if gap > 0.15:
            dwell(scene, ctx, gap)
            spent += gap
        if kind == "chrome_out":
            scene.play(FadeOut(chrome), run_time=0.4)
            spent += 0.4
            chrome = None
        elif kind == "event":
            rt = _play_bundle(scene, ctx, payload)
            spent += rt
            is_punch = getattr(payload, "punch", False)
            log_event(scene, "payoff" if is_punch else "event",
                      beat=idx, rt=round(rt, 2))
            if is_punch and dur - spent > 1.0:
                spent += _echo(scene, ctx)   # the chain reaction
        else:
            spent += _fire_reaction(scene, ctx, payload)

    left = dur - spent
    if left > 0.05:
        dwell(scene, ctx, left)
    if chrome is not None:
        scene.remove(chrome)


# ---------------------------------------------------------------------------
# Travel moves.
# ---------------------------------------------------------------------------
def _mv_fly(scene, ctx, rt):
    scene.play(ctx["frame"].animate(path_arc=0.35)
               .move_to(ctx["anchor"]).set(width=ctx["fw"]),
               run_time=rt, rate_func=rate_functions.ease_in_out_sine)


def _mv_dive(scene, ctx, rt):
    a, fw = ctx["anchor"], ctx["fw"]
    over = a + np.array([0.0, -fw * 0.035, 0.0])
    scene.play(ctx["frame"].animate.move_to(over).set(width=fw * 0.94),
               run_time=rt * 0.72, rate_func=rate_functions.ease_in_quad)
    scene.play(ctx["frame"].animate.move_to(a).set(width=fw),
               run_time=rt * 0.28, rate_func=rate_functions.ease_out_sine)


def _mv_pull_back(scene, ctx, rt):
    scene.play(ctx["frame"].animate.move_to(ctx["anchor"])
               .set(width=ctx["fw"]),
               run_time=rt, rate_func=rate_functions.ease_in_out_cubic)


def _mv_track(scene, ctx, rt):
    scene.play(ctx["frame"].animate.move_to(ctx["anchor"])
               .set(width=ctx["fw"]),
               run_time=rt, rate_func=rate_functions.linear)


def _mv_follow(scene, ctx, rt):
    scene.play(ctx["frame"].animate(path_arc=-0.6)
               .move_to(ctx["anchor"]).set(width=ctx["fw"]),
               run_time=rt, rate_func=rate_functions.ease_in_out_sine)


# ---------------------------------------------------------------------------
# Dwell moves — the frame breathes; never static, always unwound.
#
# LOOPED, not single eased plays: a narration beat can run 35 s, and one
# 10%-width ease spread across 25 s is sub-pixel per frame — a locked
# camera by the motion gate's (and the operator's) standard. Every dwell
# splits its time into ~5.5 s legs that alternate direction/zoom, so the
# frame visibly lives for however long the beat holds.
# ---------------------------------------------------------------------------
DWELL_LEG = 5.5


def _leg_times(rt: float) -> list[float]:
    n = max(1, round(rt / DWELL_LEG))
    return [rt / n] * n


def _dw_phase(ctx) -> int:
    """Dwell leg counter that persists ACROSS fragments within a visit.
    The scheduler calls a dwell several times (gap fillers, tail); if
    each call restarted at leg 0, two consecutive fragments would target
    the same point — a frozen no-op play (the motion gate caught exactly
    this after reactions that don't move the frame)."""
    i = ctx.get("_dw_i", 0)
    ctx["_dw_i"] = i + 1
    return i


def _dw_orbit(scene, ctx, rt):
    frame, a, fw = ctx["frame"], ctx["anchor"], ctx["fw"]
    e = _energy()          # dwell amplitude rises with world intensity
    for L in _leg_times(rt):
        i = _dw_phase(ctx)
        sgn = 1 if i % 2 == 0 else -1
        off = np.array([fw * 0.026 * sgn, fw * 0.012 * -sgn, 0.0]) * e
        scene.play(frame.animate(path_arc=0.5 * sgn).move_to(a + off)
                   .set(width=fw * (0.975 - 0.025 * (i % 2))),
                   run_time=L, rate_func=rate_functions.ease_in_out_sine)


def _dw_push(scene, ctx, rt):
    # Every leg pairs its width target with an ALTERNATING positional
    # offset — a pure width-set leg is a frozen frame whenever the
    # camera already sits at that width (e.g. right after a punch pop).
    frame, a, fw = ctx["frame"], ctx["anchor"], ctx["fw"]
    e = _energy()
    for L in _leg_times(rt):
        i = _dw_phase(ctx)
        off = np.array([fw * 0.013 * (1 if i % 2 else -1),
                        fw * 0.007 * (-1 if i % 2 else 1), 0.0]) * e
        scene.play(frame.animate.move_to(a + off)
                   .set(width=fw * (0.90 if i % 2 == 0 else 0.935)),
                   run_time=L, rate_func=rate_functions.ease_in_out_sine)


_DRIFT_PATH = [(0.022, -0.012), (-0.016, -0.020), (0.026, 0.009),
               (-0.020, 0.016)]


def _dw_drift(scene, ctx, rt):
    frame, a, fw = ctx["frame"], ctx["anchor"], ctx["fw"]
    e = _energy()
    for L in _leg_times(rt):
        i = _dw_phase(ctx)
        dx, dy = _DRIFT_PATH[i % len(_DRIFT_PATH)]
        scene.play(frame.animate
                   .move_to(a + np.array([fw * dx, fw * dy, 0.0]) * e)
                   .set(width=fw * (0.965 - 0.015 * (i % 2))),
                   run_time=L, rate_func=rate_functions.ease_in_out_sine)


def _dw_sweep(scene, ctx, rt):
    frame, a, fw = ctx["frame"], ctx["anchor"], ctx["fw"]
    e = _energy()
    for L in _leg_times(rt):
        i = _dw_phase(ctx)
        sgn = 1 if i % 2 == 0 else -1
        scene.play(frame.animate
                   .move_to(a + np.array([fw * 0.032 * sgn,
                                          fw * 0.006 * -sgn, 0.0]) * e),
                   run_time=L, rate_func=rate_functions.ease_in_out_sine)


_DWELLS = {"orbit": _dw_orbit, "push_in": _dw_push, "drift_hold": _dw_drift,
           "parallax_sweep": _dw_sweep}
_TRAVELS = {"fly_to": _mv_fly, "dive": _mv_dive, "pull_back": _mv_pull_back,
            "track": _mv_track, "follow_path": _mv_follow}


def _make(travel_name, dwell_name):
    def run(scene, ctx, travel=travel_name, dwell=dwell_name):
        dw = _DWELLS[ctx.get("dwell") or dwell]
        reveal_target = ctx.get("reveal_target")
        _visit(scene, ctx, _TRAVELS[travel], dw,
               reveal_target=reveal_target)
    return run


# Register the travel/dwell matrix under travel names (dwell overridable
# per-waypoint via "dwell"), plus named specials below.
for _t, _d in (("fly_to", "drift_hold"), ("dive", "orbit"),
               ("pull_back", "drift_hold"), ("track", "push_in"),
               ("follow_path", "parallax_sweep")):
    SHOTS[_t] = _make(_t, _d)


@shot("counter_surge")
def _s_counter_surge(scene, ctx):
    """Arrive hard, let the number race while the camera pushes past
    comfort, then settle — the 'speed counter explodes' beat."""
    frame, a, fw = ctx["frame"], ctx["anchor"], ctx["fw"]

    def approach(sc, c, rt):
        sc.play(frame.animate.move_to(a).set(width=fw * 1.08),
                run_time=rt, rate_func=rate_functions.ease_in_quad)

    def dwell(sc, c, rt):
        sgn = 1 if _dw_phase(c) % 2 == 0 else -1   # never repeat a target
        t1 = min(4.0, rt * 0.45)
        sc.play(frame.animate.move_to(
            a + sgn * np.array([fw * 0.008, -fw * 0.005, 0.0]))
            .set(width=fw * 0.88),
            run_time=t1, rate_func=rate_functions.ease_in_out_sine)
        t2 = min(3.0, (rt - t1) * 0.5)
        if t2 > 0.05:
            sc.play(frame.animate.move_to(
                a - sgn * np.array([fw * 0.008, -fw * 0.005, 0.0]))
                .set(width=fw * 0.94), run_time=t2,
                rate_func=rate_functions.ease_in_out_sine)
        if rt - t1 - t2 > 0.05:
            _dw_drift(sc, c, rt - t1 - t2)   # looped — long beats stay alive

    _visit(scene, ctx, approach, dwell,
           reveal_target=ctx.get("reveal_target"))


@shot("cross_section")
def _s_cross_section(scene, ctx):
    """Dive in tight, then pull to reveal the whole interior — for
    cutaway/layered subjects."""
    frame, a, fw = ctx["frame"], ctx["anchor"], ctx["fw"]

    def approach(sc, c, rt):
        sc.play(frame.animate.move_to(a).set(width=fw * 0.62),
                run_time=rt, rate_func=rate_functions.ease_in_out_sine)

    def dwell(sc, c, rt):
        t1 = min(4.5, rt * 0.6)
        sc.play(frame.animate.set(width=fw),
                run_time=t1, rate_func=rate_functions.ease_in_out_sine)
        if rt - t1 > 0.05:
            _dw_drift(sc, c, rt - t1)

    _visit(scene, ctx, approach, dwell,
           reveal_target=ctx.get("reveal_target"))


@shot("scale_up")
def _s_scale_up(scene, ctx):
    """Start too close (subject overwhelms the frame), pull to compare."""
    frame, a, fw = ctx["frame"], ctx["anchor"], ctx["fw"]

    def approach(sc, c, rt):
        sc.play(frame.animate.move_to(a).set(width=fw * 0.45),
                run_time=rt, rate_func=rate_functions.ease_out_quad)

    def dwell(sc, c, rt):
        t1 = min(5.0, rt * 0.7)
        sc.play(frame.animate.set(width=fw),
                run_time=t1, rate_func=rate_functions.ease_in_out_sine)
        if rt - t1 > 0.05:
            _dw_sweep(sc, c, rt - t1)

    _visit(scene, ctx, approach, dwell,
           reveal_target=ctx.get("reveal_target"))


# Story shots ride the standard visit; their drama lives in the builders
# (comparison_race, stack_build, timeline_travel animate their own objects).
SHOTS["comparison_race"] = _make("track", "parallax_sweep")
SHOTS["stack_build"] = _make("fly_to", "push_in")
SHOTS["timeline_travel"] = _make("follow_path", "parallax_sweep")


def cold_open_rush(scene, ctx):
    """The hook is a RIDE: sprint through the entire world in seconds —
    title riding the frame, counter surging — then reset to the start.
    Show the whole ride first; explain it second.

    ctx: frame, anchors_all [(pos, fw)...], dur, surge (optional
    (ValueTracker, target) — winds back to 0 on the reset).

    Consumes EXACTLY ctx["dur"] seconds: the body is one continuous take,
    so an intro overrun would desync every later beat from narration.
    Per-segment rate funcs chain ease-in -> linear -> ease-out so the
    sprint reads as ONE accelerating move, not a stutter of stops."""
    frame = ctx["frame"]
    anchors = ctx["anchors_all"]
    dur = ctx["dur"]
    log_event(scene, "cold_open", rt=round(dur, 2))
    reset = min(1.4, dur * 0.18)
    rush = min(8.0, dur - reset - 0.3)
    settle = max(0.05, dur - rush - reset)
    surge = ctx.get("surge")
    n = len(anchors)
    per = rush / max(1, n - 1)
    last = n - 1
    for j, (pos, fw) in enumerate(anchors[1:], start=1):
        rf = (rate_functions.ease_in_sine if j == 1 else
              rate_functions.ease_out_sine if j == last else
              rate_functions.linear)
        anims = [frame.animate.move_to(np.array(pos)).set(width=fw)]
        if surge is not None:
            v, target = surge
            anims.append(v.animate.set_value(target * j / max(1, last)))
        scene.play(*anims, run_time=per, rate_func=rf)
    a0, fw0 = anchors[0]
    reset_anims = [frame.animate.move_to(np.array(a0)).set(width=fw0 * 1.6)]
    if surge is not None:
        reset_anims.append(surge[0].animate.set_value(0))
    scene.play(*reset_anims, run_time=reset,
               rate_func=rate_functions.ease_in_out_cubic)
    scene.play(frame.animate.set(width=fw0 * 1.35), run_time=settle,
               rate_func=rate_functions.ease_in_out_sine)
    # end marker: the rush is surprise-class for its WHOLE span — the
    # cadence gate should measure from where the ride ended
    log_event(scene, "cold_open", rt=0.0)
