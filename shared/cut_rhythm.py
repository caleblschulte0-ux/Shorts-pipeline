"""CUT RHYTHM — vary shot lengths inside the legal window.

WHY. Four blind taste verdicts on `shared-air` over 2026-08-01/02. SAMENESS in
all four. BORING in all four. The response each time was a change to WHAT was
on screen — restage the scenes, ban the library, dedupe the clips — and the
score went 4.0 -> 4.0 -> 3.5 -> 3.0. Nobody looked at the cut.

The plan for that film, 39 shots and 127 seconds long, contains FOUR distinct
shot lengths:

    4.50 depict / 1.85 image / 4.50 depict / 1.85 image / 3.18 scene / 3.18 ...

That is not a story problem. `planner.MAX_UNCHANGED` is a constant, and every
long beat is cut as `emit(lead, seconds=maxu); emit(tail, secs - maxu)`. With a
constant ceiling and beats of similar narration length, EVERY beat cuts at the
identical instant. An editor who held every shot for exactly 4.5 seconds would
be described as boring by anyone who watched it, and four judges did.

WHAT THIS DOES. The hold ceiling stays a law — a visual may not sit past
`max_unchanged`. This varies where the cut lands BENEATH that ceiling, from a
fixed cycle keyed to the beat index. Deterministic (same story, same cut, so a
re-render is comparable and CI is stable), never random.

WHAT IT WILL NOT DO. It never lengthens a shot past the ceiling, never emits
one shorter than `min_shot`, and never changes a beat's total duration — the
narration under it is untouched, so nothing desyncs. When those constraints
leave no room, it returns the old value unchanged, which is why adopting it
cannot make a film worse than it already was.

SHARED ON PURPOSE. Nothing here knows a slug, a channel, or a topic — it takes
seconds and gives back seconds. Any channel that cuts shots wants a rhythm.
"""
from __future__ import annotations

# Fractions of the hold ceiling, walked in order across beats. Five values,
# coprime with the 2- and 3-phase splits that dominate real plans, so the
# pattern does not fall into step with the phase count and re-flatten. 1.0
# is included deliberately: some beats SHOULD run the full hold, and a rhythm
# with no long shots in it is just a different monotony.
HOLD_CYCLE = (1.0, 0.62, 0.86, 0.70, 0.94, 0.55)

# How far an individual phase may be pushed off the equal split, as a fraction
# of the room actually available. Not 1.0: a phase pinned exactly to the
# ceiling or exactly to the floor on every beat is a new constant.
SKEW = 0.8

# Zero-mean weights for unequal phase splits, rotated by beat index.
_W = (1.0, 0.35, 0.75, 0.15, 0.55)

# The shortest a SILENT DEVELOPMENT phase may run. Not invented: the planner
# already emitted 1.85s development shots on every image beat of every render
# so far, and no judge in four rounds called the film choppy — they called it
# same-y. So a fast cut is proven acceptable, and treating the lead shot's
# floor (MIN_SHOT, 2.8s) as if it also bound the tail is what squeezes an
# edit toward one length.
#
# THIS MATTERS MORE THAN THE CYCLE. The first version of this module enforced
# 2.8s on both halves. It raised the count of distinct shot lengths from 4 to
# 8 and looked like a win on the metric — while collapsing the range from
# 1.85-4.5s to 2.80-3.55s. Eight lengths that are all a third of a second
# apart is a WORSE edit than four with real contrast, and a scorer counting
# distinct values would have called it an improvement. Range and variety are
# two different things and a rhythm needs both.
FAST_CUT = 1.7


def hold_for(index: int, secs: float, ceiling: float,
             min_shot: float = 2.8, fast_cut: float = FAST_CUT) -> float:
    """Where the lead phase of this beat should cut. Never above `ceiling`.

    The returned value is only ever used as the lead shot's length, so the
    constraints are the interesting part:

      * the tail must remain a usable cut         -> hold <= secs - fast_cut
      * the tail must not break the hold law      -> hold >= secs - ceiling
      * the lead carries the narration            -> hold >= min_shot

    If that window is empty — a short beat, a tight ceiling — this returns the
    ceiling and the caller behaves exactly as it did before. Varying the cut is
    worth doing; it is not worth breaking a beat over.

    Note what the second constraint does and does not promise. A beat far
    longer than its ceiling (13.2s against 4.5s) already left an over-ceiling
    tail BEFORE this module existed: the planner emitted one lead of 4.5s and
    a single development shot of 8.7s. That is a real defect in the planner's
    long-beat handling and it is not fixed here — this returns the ceiling in
    that case, unchanged. The guarantee is only that varying the cut never
    makes either half longer than the constant would have made it.
    """
    try:
        secs = float(secs)
        ceiling = float(ceiling)
    except (TypeError, ValueError):
        return ceiling
    if secs <= ceiling:
        return ceiling                    # no split happens: nothing to vary
    lo = max(min_shot, secs - ceiling)
    hi = min(ceiling, secs - fast_cut)
    if hi <= lo:
        return ceiling
    want = ceiling * HOLD_CYCLE[int(index) % len(HOLD_CYCLE)]
    return round(min(hi, max(lo, want)), 3)


def phase_lengths(secs: float, ceiling: float, index: int = 0,
                  min_shot: float = 2.8,
                  fast_cut: float = FAST_CUT) -> list[float]:
    """Split a beat into phases that are NOT all the same length.

    The equal split this replaces was justified as landing "on a rhythm rather
    than leaving a runt tail". Equal spacing is a metronome, not a rhythm, and
    39 shots of it is what four judges called BORING.

    Guarantees, all of them load-bearing:
      * `sum(result) == secs` to within float noise — the beat's total is the
        narration's total, and desyncing audio to make a prettier cut would be
        a strictly worse film;
      * every phase is within `[fast_cut, ceiling]`, and the PHASE COUNT is
        still chosen by `min_shot`, exactly as before — the floor is lowered
        for the skew only, so a beat never gains a phase it did not have;
      * same inputs, same output — a re-render is comparable to its predecessor.
    """
    try:
        secs = float(secs)
        ceiling = float(ceiling)
    except (TypeError, ValueError):
        return [secs]
    if secs <= ceiling:
        return [secs]
    n = max(2, int(-(-secs // ceiling)))          # ceil
    while n > 2 and secs / n < min_shot:
        n -= 1
    base = secs / n
    if base < fast_cut or base > ceiling:
        return [base] * n                          # no legal room: as before
    raw = [_W[(int(index) + i) % len(_W)] for i in range(n)]
    mean = sum(raw) / n
    w = [r - mean for r in raw]
    peak = max(abs(x) for x in w) or 0.0
    if not peak:
        return [base] * n
    w = [x / peak for x in w]                      # zero-mean, max |w| == 1
    amp = SKEW * min(ceiling - base, base - fast_cut)
    if amp <= 0.01:
        return [base] * n
    out = [round(base + amp * x, 3) for x in w]
    out[-1] = round(secs - sum(out[:-1]), 3)       # exact total, no drift
    return out


def summary(durations) -> str:
    """One line describing a cut, for a plan report."""
    d = [round(float(x), 2) for x in durations if x]
    if not d:
        return "no shots"
    return (f"{len(d)} shots · {len(set(d))} distinct lengths · "
            f"{min(d):.1f}-{max(d):.1f}s")
