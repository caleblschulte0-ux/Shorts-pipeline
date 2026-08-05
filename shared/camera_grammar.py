"""CAMERA GRAMMAR — decide the move instead of defaulting it.

WHY. Same defect shape as `cut_rhythm`, found the same way. Of the 39 shots in
the shared-air plan, all 14 image shots carried `push: 1.1` and NOT ONE shot
set `direction` or `pan`. The renderer has supported `direction` in/out and
`pan` left/right/up/down since `footage_hybrid.image_beat` was written; the
planner never passed either, so every shot in every film pushed in, at the same
rate, with the same auto drift. A film where the camera does one thing for two
minutes reads as LOW_ENERGY and BORING, which is what the taste judge said —
twice and four times respectively, across four renders.

THE MOVE IS PART OF THE MEANING, so this is not an alternation:

    REVEAL, CLOSE     pull OUT — the thing you were looking at turns out to be
                      part of something larger. That is what a reveal IS.
    HOOK, PAYOFF      push IN — commit, land it.
    DEVELOP, DATA     no inherent direction, so vary it, because fourteen
                      consecutive identical develops is the actual problem.

AND ADJACENT SHOTS MUST NOT SHARE A MOVE. Two cuts in a row drifting left read
as one continuous camera with a hiccup in it, not as two shots. This is the one
rule here that is a rule rather than a preference, and `plan_moves` enforces it
across the whole shot list rather than deciding each shot alone.

SHARED ON PURPOSE. Takes roles and indices, returns move parameters. No slug,
no channel, no topic.
"""
from __future__ import annotations

# Roles whose meaning fixes the direction. Everything else is free to vary.
PULLS_OUT = frozenset({"REVEAL", "CLOSE", "WIDEN"})
PUSHES_IN = frozenset({"HOOK", "PAYOFF", "PUNCH"})

PANS = ("left", "right", "up", "down")

# Total zoom for a free shot, cycled. The old constants (1.14 for stills, 1.06
# for footage) sit inside this range — this widens around them rather than
# replacing them, so no shot moves less than it used to.
PUSH_CYCLE = (1.14, 1.06, 1.22, 1.10, 1.30, 1.08)


def move_for(index: int, role: str = "", *, still: bool = False) -> dict:
    """The camera for one shot, before the no-repeat pass.

    `still` marks a Ken Burns shot over a photograph, which needs more movement
    than footage does — a frozen photo is the canonical slideshow tell, so its
    push floor is higher. That distinction already existed as two hardcoded
    defaults; it is preserved, not invented.
    """
    r = str(role or "").upper()
    i = int(index)
    if r in PULLS_OUT:
        direction = "out"
    elif r in PUSHES_IN:
        direction = "in"
    else:
        direction = "in" if i % 2 == 0 else "out"
    push = PUSH_CYCLE[i % len(PUSH_CYCLE)]
    if still:
        push = max(push, 1.14)
    return {"direction": direction, "pan": PANS[i % len(PANS)],
            "push": round(push, 3)}


def plan_moves(shots: list[dict], roles: list[str] | None = None) -> list[dict]:
    """Assign a move to every shot, with no two neighbours matching.

    Returns a NEW list; the input is not mutated. A shot that already carries
    an authored `direction` or `pan` keeps it — an author who specified the
    camera outranks a cycle, and silently overriding them is how the scene
    library ended up staging a subject the film never had.
    """
    out: list[dict] = []
    prev = None
    for i, sh in enumerate(shots or []):
        s = dict(sh)
        role = (roles[i] if roles and i < len(roles) else s.get("role")) or ""
        kind = str(s.get("kind") or "")
        mv = move_for(i, role, still=kind.startswith("image"))
        # An authored camera wins outright.
        if s.get("direction"):
            mv["direction"] = s["direction"]
        if s.get("pan"):
            mv["pan"] = s["pan"]
        if s.get("push"):
            mv["push"] = s["push"]
        # ...but a repeat of the previous shot's move is a defect either way:
        # nudge the pan, which carries no meaning, before touching direction,
        # which does.
        if prev and mv["pan"] == prev["pan"] and mv["direction"] == prev["direction"]:
            mv["pan"] = PANS[(PANS.index(mv["pan"]) + 1) % len(PANS)]
        s.update(mv)
        out.append(s)
        prev = mv
    return out


def repeated_moves(shots: list[dict]) -> int:
    """How many adjacent pairs share a move. Zero is the target."""
    n = 0
    for a, b in zip(shots or [], (shots or [])[1:]):
        if (a.get("direction"), a.get("pan")) == (b.get("direction"), b.get("pan")) \
                and a.get("direction") is not None:
            n += 1
    return n
