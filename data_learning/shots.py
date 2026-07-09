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


# ---------------------------------------------------------------------------
# The visit scaffold — shared skeleton every shot composes:
#   approach -> [reveal] -> chrome in -> arrivals -> chrome out -> dwell
# Time bookkeeping keeps the visit EXACTLY ctx["dur"] seconds.
# ---------------------------------------------------------------------------
def _play_arrivals(scene, ctx, budget: float) -> float:
    spent = 0.0
    for a in ctx.get("arrival_anims") or []:
        rt = getattr(a, "run_time", 1.0)
        if spent + rt > budget:
            break
        if hasattr(a, "anims"):
            scene.play(*a.anims, run_time=rt)
        else:
            scene.play(a, run_time=rt)
        spent += rt
    return spent


def _visit(scene, ctx, approach, dwell, approach_frac=0.28,
           reveal_target=None):
    frame, dur = ctx["frame"], ctx["dur"]
    t_approach = min(2.8, max(0.8, dur * approach_frac))
    approach(scene, ctx, t_approach)
    spent = t_approach
    if reveal_target is not None:                       # the subject is BORN
        scene.play(Restore(reveal_target), run_time=0.7,
                   rate_func=rate_functions.ease_out_back)
        spent += 0.7
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
    arr_budget = max(0.0, dur - spent - max(1.2, dur * 0.25))
    spent += _play_arrivals(scene, ctx, arr_budget)
    remaining = max(0.05, dur - spent)
    if chrome is not None and remaining > CHROME_SECONDS:
        dwell(scene, ctx, CHROME_SECONDS - 0.4)
        scene.play(FadeOut(chrome), run_time=0.4)
        remaining -= CHROME_SECONDS
        dwell(scene, ctx, remaining)
    else:
        dwell(scene, ctx, remaining)
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
# ---------------------------------------------------------------------------
def _dw_orbit(scene, ctx, rt):
    frame, a, fw = ctx["frame"], ctx["anchor"], ctx["fw"]
    half = rt / 2
    off = np.array([fw * 0.02, fw * 0.008, 0.0])
    scene.play(frame.animate(path_arc=0.5).move_to(a + off)
               .set(width=fw * 0.97),
               run_time=half, rate_func=rate_functions.ease_in_out_sine)
    scene.play(frame.animate(path_arc=0.5).move_to(a).set(width=fw * 0.95),
               run_time=half, rate_func=rate_functions.ease_in_out_sine)


def _dw_push(scene, ctx, rt):
    scene.play(ctx["frame"].animate.set(width=ctx["fw"] * 0.90),
               run_time=rt, rate_func=rate_functions.ease_in_out_sine)


def _dw_drift(scene, ctx, rt):
    a, fw = ctx["anchor"], ctx["fw"]
    scene.play(ctx["frame"].animate
               .move_to(a + np.array([fw * 0.018, -fw * 0.012, 0.0]))
               .set(width=fw * 0.95),
               run_time=rt, rate_func=rate_functions.ease_in_out_sine)


def _dw_sweep(scene, ctx, rt):
    a, fw = ctx["anchor"], ctx["fw"]
    scene.play(ctx["frame"].animate
               .move_to(a + np.array([fw * 0.03, 0.0, 0.0])),
               run_time=rt, rate_func=rate_functions.ease_in_out_sine)


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
        sc.play(frame.animate.move_to(a).set(width=fw * 0.88),
                run_time=rt * 0.45, rate_func=rate_functions.ease_in_out_sine)
        sc.play(frame.animate.set(width=fw * 0.94),
                run_time=rt * 0.55, rate_func=rate_functions.ease_in_out_sine)

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
        sc.play(frame.animate.set(width=fw),
                run_time=rt * 0.6, rate_func=rate_functions.ease_in_out_sine)
        _dw_drift(sc, c, rt * 0.4)

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
        sc.play(frame.animate.set(width=fw),
                run_time=rt * 0.7, rate_func=rate_functions.ease_in_out_sine)
        _dw_sweep(sc, c, rt * 0.3)

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
