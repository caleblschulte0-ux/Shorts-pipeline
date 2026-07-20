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
    "composite":          {"impact_shake": True},
}


def extra_for(kind: str, beat_index: int = 0, total: int = 1) -> dict:
    """The extra spec for one animation, with an intensity that RAMPS across the
    video so the payoff is the most alive beat. Returns {} for kinds with no
    repertoire (footage, plain text) — the extra director only escalates
    animations."""
    moves = dict(EXTRA_MOVES.get(kind, {}))
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
            s["extra"] = moves
    return shots
