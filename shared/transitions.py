"""TRANSITIONS — choose each join, instead of dissolving all of them.

WHY. Third constant of the same shape as `cut_rhythm` and `camera_grammar`,
and the one with the widest reach: `pro_render.XFADE = 0.6` is applied to
EVERY join. A 39-shot film is 38 identical 0.6-second crossfades. The film
never once hard-cuts.

A dissolve says "time passed" or "these are related". Using it 38 times in a
row says nothing at all, and it drains energy: a hard cut between two moving
shots is the single cheapest way to make an edit feel alive. LOW_ENERGY
appeared in two verdicts and BORING in four.

WHAT SURVIVES. `footage_hybrid.dissolve_join` documents a real rule, arrived
at from judge panels: "never a hard cut from motion to a near-static image,
never a fade to black". That rule is kept exactly — it just stops being
applied to joins it was never about. A cut into or out of a held still still
dissolves. So does a join WITHIN a beat, where both sides are the same source
and a hard cut would read as a jump cut rather than as an edit.

WHY A CUT IS 0.08s AND NOT 0. ffmpeg's `xfade` filter needs a positive
duration; a true zero would mean building a mixed concat/xfade filter graph,
where the offset arithmetic for the audio, the SRT cues and the beatmap all
have to agree with a second code path. Two frames at 25fps is perceptually a
hard cut and keeps one graph and one set of sums. The risk of a desynced film
is not worth the two frames.

SHARED ON PURPOSE. Takes shot dicts, returns seconds. No slug, no channel.
"""
from __future__ import annotations

# A crossfade long enough to read as "time passed / these belong together".
DISSOLVE = 0.6
# Perceptually a hard cut. See the note above on why it is not 0.0.
CUT = 0.08

# Shot kinds that are a HELD STILL: a photograph with a Ken Burns move over
# it. The no-hard-cut-into-static rule is about these.
_STILL_PREFIX = ("image",)


def _kind(sh) -> str:
    return str((sh or {}).get("kind") or "")


def _beat(sh):
    return (sh or {}).get("_beat")


def join_for(a: dict, b: dict) -> float:
    """The crossfade between shot `a` and the shot `b` that follows it.

    READ THE DOCUMENTED RULE PRECISELY. It is "never a hard cut FROM motion TO
    a near-static image" — it is about the ARRIVAL. Cutting to a photograph
    that then begins to drift is the jarring one: the movement stops dead and
    restarts. Leaving a still ON a cut, into a moving shot, is the most
    ordinary move in editing and was never what the rule addressed.

    The first version of this function dissolved BOTH sides of every still,
    which on shared-air left 33 dissolves and 5 cuts out of 38 joins — the
    plan alternates depict/image, so almost every join touches a still and
    almost nothing changed. That is a rule applied wider than its evidence,
    which is how `NEUTRAL_SCENES` came to be described as topic-agnostic when
    every scene in it named a subject.
    """
    ka, kb = _kind(a), _kind(b)
    if kb.startswith(_STILL_PREFIX):
        return DISSOLVE          # the documented rule: never cut INTO a still
    ba, bb = _beat(a), _beat(b)
    if ba is not None and ba == bb:
        return DISSOLVE          # same beat, same source: a cut is a jump cut
    return CUT                   # anything else, including out of a still


def plan_joins(shots: list[dict]) -> list[float]:
    """One crossfade per join. `len(result) == max(0, len(shots) - 1)`."""
    shots = list(shots or [])
    return [join_for(shots[i], shots[i + 1]) for i in range(len(shots) - 1)]


def starts(seconds: list[float], joins: list[float]) -> list[float]:
    """Where each shot begins in the finished film, given per-join overlaps.

    THIS IS THE LOAD-BEARING FUNCTION. The old code did
    `offset += seconds[i] - XFADE` inline, in three places — the voice delays,
    the SRT cues, and the beatmap — each re-deriving the same sum from the
    same constant. With per-join overlaps that constant is gone, so the sum
    lives here once and every consumer reads it. Three hand-maintained copies
    of a timing sum is how a film silently desyncs from its own captions.
    """
    out, off = [], 0.0
    for i, s in enumerate(seconds or []):
        out.append(off)
        off += float(s) - (joins[i] if i < len(joins) else 0.0)
    return out


def total(seconds: list[float], joins: list[float]) -> float:
    """The finished film's duration — the last start plus the last shot."""
    if not seconds:
        return 0.0
    st = starts(seconds, joins)
    return st[-1] + float(seconds[-1])


def summary(joins: list[float]) -> str:
    cuts = sum(1 for j in joins if j <= CUT + 1e-9)
    return (f"{len(joins)} joins · {cuts} cuts / {len(joins) - cuts} dissolves"
            if joins else "no joins")
