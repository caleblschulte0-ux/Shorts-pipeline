#!/usr/bin/env python3
"""THE EXTRA DIRECTOR — its whole job is to be extra.

Every purpose-built animation is fine. This director asks the one question that
turns "fine" into "fun": *what if we did MORE?* It layers CHARACTER and PHYSICS
onto the base animation, so the thing on screen reacts and has personality:

  - the hidden-motion figure STUMBLES back and catches its balance as the ground
    accelerates ("stuff's getting so fast");
  - a hero number OVERSHOOTS its target and SLAMS back with an impact shake;
  - the winning comparison bar BOUNCES past the line and celebrates;
  - the spinning globe SPINS UP and the 'you are here' marker gets flung;
  - the orbit and the galaxy zoom ACCELERATE toward the reveal.

This is charm and character — anticipation, overshoot, follow-through, secondary
action, exaggeration (the animation principles) — NOT random jitter. It is a
first-class director in the pipeline: after the planner picks each beat's
animation, `apply()` attaches an `extra` spec that the flat2d builders act on.

INTENSITY escalates across the video (a gentle open, a wild payoff) so the energy
builds instead of being flat — the last animation should be the most alive.

    from data_learning import extra_director
    shots = extra_director.apply(planner.plan_story(beats, durs))
"""
from __future__ import annotations

# the repertoire of "extra" moves each animation kind can perform. The builder
# implements them; this director decides to turn them on and how hard.
EXTRA_MOVES = {
    "flat_hidden_motion": {"accelerate_ground": True, "stumble": True},
    "flat_number":        {"overshoot": True, "impact_shake": True},
    "flat_compare":       {"bar_overshoot": True, "winner_celebrate": True},
    "flat_spin":          {"spin_accelerate": True, "marker_fling": True},
    "flat_orbit":         {"orbit_accelerate": True},
    "flat_zoom":          {"zoom_accelerate": True},
    "flat_shrinking_years": {"bar_overshoot": True},
    "composite":          {"impact_shake": True},
}

# THE CHARACTER SCENES WERE NOT IN THE LIST ABOVE, AND THAT IS THE WHOLE POINT.
#
# Every key in EXTRA_MOVES is a CHART. The director whose stated job is to add
# "CHARACTER and personality" was attaching it to the bar graphs and skipping
# the person. On `shared-air` — 10 scene shots, 0 flat shots — `apply()` did
# literally nothing, and the blind taste judge said NO_SOUL three times:
# "nothing on screen has personality: no character, no living scene, NO ACTING".
#
# The acting engine already existed. `data_learning/expression.py` renders
# seven emotions as pose deltas, `scenes._expr_delta` resolves them per frame,
# and it fires on `{"express": true}` — for which the scene supplies its own
# emotion. Nothing ever set that flag except seven hand-authored beats in
# `money-goes`, which is the one story that scored personality 3 and PASSED.
# A capability nothing calls is not a capability (CLAUDE.md, rule zero).
#
# Each scene names the mood its staging is ABOUT, so this is not an arbitrary
# mapping — waiting in a queue is resignation, being on hold is exhaustion,
# work is weight. A beat that authors its own `expression` still wins.
SCENE_EMOTIONS = {
    "scene_queue":     "resignation",
    "scene_hold":      "exhaustion",
    "scene_work":      "burden",
    "scene_screen":    "exhaustion",
    "scene_sleep":     "resignation",
    "scene_free":      "joy",
    "scene_walkout":   "relief",
    "scene_treadmill": "exhaustion",
    "scene_money":     "burden",
    "scene_paycheck":  "burden",
    "scene_tax":       "frustration",
}


def extra_for(kind: str, beat_index: int = 0, total: int = 1) -> dict:
    """The extra spec for one animation, with an intensity that RAMPS across the
    video so the payoff is the most alive beat. Returns {} for kinds with no
    repertoire (footage, plain text) — the extra director only escalates
    animations."""
    moves = dict(EXTRA_MOVES.get(kind, {}))
    if not moves and kind in SCENE_EMOTIONS:
        # A CHARACTER SCENE ACTS. `express` is the legacy flag `_expr_delta`
        # reads, and it deliberately lets the SCENE choose the emotion rather
        # than naming one here — the staging knows what it is about, and a
        # mapping in this module would be a second place to keep it. The
        # intensity ramps with everything else, so the last scene is the most
        # felt. An authored `expression` block overrides this in `apply()`.
        moves = {"express": True,
                 "expression": {"emotion": SCENE_EMOTIONS[kind],
                                "intensity": round(
                                    0.45 + 0.35 * (beat_index /
                                                   max(1, total - 1)), 2)}}
        return moves
    if moves:
        # a stronger floor so even the opening is lively; ramps to a wild payoff.
        moves["intensity"] = round(0.8 + 0.5 * (beat_index / max(1, total - 1)),
                                   2)
        # FRONT-LOAD the very first animation: a hook wins attention in the first
        # second, so its character must react INSTANTLY, not 6s in.
        if beat_index == 0:
            moves["front_load"] = True
    return moves


def apply(shots: list[dict]) -> list[dict]:
    """Attach an escalating `extra` spec to every designed-animation shot in a
    plan. Footage/plain shots are left untouched. Mutates and returns the list."""
    n = len(shots)
    for i, s in enumerate(shots):
        moves = extra_for(str(s.get("kind", "")), i, n)
        if moves:
            # MERGE, don't clobber: an author may have set deliberate keys on the
            # shot (e.g. a full-frame `hero` opening) that the director must keep.
            merged = dict(moves)
            merged.update(s.get("extra") or {})
            s["extra"] = merged
        elif s.get("extra"):
            pass                              # leave author extra as-is
    return shots
