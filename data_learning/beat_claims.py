"""ONE FACT IS ONE BEAT.

Operator, 2026-09-08, on a video that had just posted: *"we would say the same
thing in 3 different beats just show it a different way that's dumb af."*

They were describing `driving-side-of-the-road` exactly:

    beat 1  30% of the world's PEOPLE drive on the left        30 / 70
    beat 2  76 COUNTRIES drive on the left, 163 on the right   32 / 68
    beat 3  25% of the world's ROAD MILES are left-hand        25 / 75

Three beats, three datasets, three different machines — and one fact. The
third beat's own narration gives it away: *"it's even more lopsided"*. 75/25
is not more lopsided than 70/30 in any way a viewer can see; it is the same
claim measured again. A viewer who understood beat one has nothing to learn
from beats two and three, so the video is a nine-second idea stretched over
forty.

This is not a rendering problem and no machine can fix it. Drawing the same
split as a balance, then a race, then a set of icons makes it WORSE — it
looks like variety while saying nothing new, which is how a channel teaches
people that its videos have no information in them.

So: a beat that restates an earlier beat is dropped, and a story that is
nothing BUT restatements is refused rather than posted short.

WHAT COUNTS AS A RESTATEMENT is deliberately narrow, because two beats that
happen to share a shape are usually two real facts:

1. the same RELATIONSHIP (both are duels, both are rankings, ...), and
2. the same number of items, and
3. proportions within `REL_TOL` of each other once normalised, measured
   relative to the larger share, and
4. overlapping vocabulary in the LABELS — the categories themselves.

All four. Rule 4 is what separates "30% of people drive on the left" from
"30% of households own a cat" — the numbers match and nothing else does, and
those are two facts, not one said twice. It reads the labels and NOT the
topic, because every beat in a story shares the story's topic by
construction; see `subject_tokens`.

AND ONLY FOR SMALL SPLITS. `MAX_ITEMS` is 3, and it is the correction that
saved this from being worse than the bug. A first version compared every
beat and flagged `two-americas-cost` — cost-of-living index, then household
income, then rent, across the same six states. Those are three different
facts, and the story's whole point is that they DIVERGE. They were flagged
because any six-item ranking of a positive quantity normalises to roughly
the same gentle descending curve, and because the same six state names
appear in all three, so the subject-overlap rule that was supposed to be the
safety net voted to convict.

A ranking's shape carries almost no claim. A two-way split's shape IS the
claim. So restatement is only ever judged on splits of two or three, and a
ranking or a series is left alone — dropping a real beat is a worse failure
than keeping a repeated one.
"""
from __future__ import annotations

import re

from data_learning import relationships as rel

# How close two normalised splits have to be to count as the same claim,
# measured RELATIVE to the larger share rather than as a flat difference.
#
# The flat version was tried first and it convicted `colorblind-by-the-
# numbers`: 8% of men vs 0.5% of women is 94/6, and 8% vs achromatopsia's
# 0.0033% is 99.96/0.04. Those differ by 0.058 in absolute terms — inside any
# flat tolerance — while the minority share differs by a factor of 150. On
# screen one is a sliver and the other is invisible, and the claims are not
# remotely the same. Relative distance says 0.99 and refuses.
#
# 0.25 is where the real cases sit: the driving-side beats are 0.17 apart at
# their widest and the three deepest-ocean rankings 0.19, while the two false
# positives above land at 0.99.
REL_TOL = 0.25

# Above this many items the normalised shape stops being a claim and starts
# being the generic shape of "a ranking". See the module docstring: this
# number is the difference between catching the driving-side video and
# gutting `two-americas-cost`.
MAX_ITEMS = 3

# Words that carry no subject. Kept short on purpose — this is a similarity
# hint, not a language model, and the fourth rule only has to stop the
# coincidence case.
_STOP = frozenset("""
the a an of in on at by for to from and or vs versus with per each every
is are was were be been that this those these it its as into over under
than then all any some most more less least much many number total share
percent percentage rate count average mean median world global
""".split())

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return {w for w in _WORD.findall(str(text or "").lower())
            if len(w) >= 3 and w not in _STOP}


def subject_tokens(insight) -> set:
    """The vocabulary a beat is ABOUT — its LABELS, and deliberately not its
    topic.

    The topic was included at first and it is worse than useless: every beat
    in a story shares the story's subject, so `fruit-is-not-created-equal`
    matched on the word "fruit" and a banana tree's yield was ruled a
    restatement of a watermelon's water content. Two facts, no shared
    categories, one shared noun.

    The labels are what is actually on screen and what the claim is made of.
    "Left-hand traffic" and "Drive on the left" share `left`; "Banana tree"
    and "Watermelon" share nothing, which is the correct answer.
    """
    out: set = set()
    for p in (getattr(insight, "items", None) or []):
        out |= _tokens(getattr(p, "label", ""))
    return out


def shape(insight) -> tuple | None:
    """The claim's PROPORTIONS, normalised and sorted — its shape, not its
    units. 30/70 and 163/76 are the same shape; that is the point.

    Returns None when there is nothing to compare: a single item, or values
    that do not sum to anything (a set that includes negatives is a change,
    not a split, and two changes with matching magnitudes are not one claim).
    """
    vals = []
    for p in (getattr(insight, "items", None) or []):
        try:
            v = float(getattr(p, "value", 0) or 0)
        except (TypeError, ValueError):
            return None
        if v < 0:
            return None
        vals.append(v)
    if len(vals) < 2:
        return None
    tot = sum(vals)
    if tot <= 0:
        return None
    return tuple(sorted((v / tot for v in vals), reverse=True))


def restates(a, b, tol: float = REL_TOL) -> bool:
    """Does beat `b` say what beat `a` already said?

    All four rules, in the cheapest order. `classify` never raises, so this
    never does either — a beat we cannot read is a beat we keep.
    """
    sa, sb = shape(a), shape(b)
    if sa is None or sb is None or len(sa) != len(sb):
        return False
    if len(sa) > MAX_ITEMS:
        return False
    # A SERIES IS NEVER A RESTATEMENT OF A SERIES. Two things that both rose
    # over the same eight years are two facts — house prices and mortgage
    # rates both climbing is the whole point of that story, not a repeat.
    if rel.is_time_series(a) or rel.is_time_series(b):
        return False
    if rel.classify(a) != rel.classify(b):
        return False
    if any(abs(x - y) > tol * max(x, y) for x, y in zip(sa, sb)):
        return False
    # THE FOURTH RULE. Without it "30% of people drive on the left" folds
    # into "30% of households own a cat", which is two facts.
    ta, tb = subject_tokens(a), subject_tokens(b)
    return bool(ta and tb and (ta & tb))


# A BEAT THAT LEANS ON THE ONE BEFORE IT.
#
# The narration is authored per beat and the words travel with the segment,
# so dropping a beat is usually safe. It is not safe when the NEXT beat opens
# by pointing backwards: `driving-side-of-the-road` beat three begins "It's
# even more lopsided in road miles", and cutting beat two leaves that
# sentence reaching for something the viewer never saw.
#
# Measured across the catalogue: one story in the twenty-one that prune, and
# in that one the sentence still reads correctly against the surviving beat.
# So this is a rare failure rather than a common one — which is exactly the
# kind that ships unnoticed, so it is guarded rather than gambled on.
_BACKREF = re.compile(
    r"^\s*(it'?s|that'?s|and that|even so|even more|then|so|but|which|"
    r"those|these|the other|meanwhile|worse|better)\b", re.I)


def leans_backward(say: str) -> bool:
    """Does this narration open by pointing at the beat before it?"""
    return bool(_BACKREF.match(str(say or "")))


def _distance(a, b) -> float:
    """How unlike two claims are, on the same relative scale `restates` uses.
    Only meaningful for comparable shapes; incomparable ones are maximally
    far apart, which is the answer that keeps them."""
    sa, sb = shape(a), shape(b)
    if sa is None or sb is None or len(sa) != len(sb):
        return 1e9
    return max(abs(x - y) / max(x, y, 1e-9) for x, y in zip(sa, sb))


def prune_restatements(insights: list, *, floor: int = 0,
                       says: list | None = None) -> tuple[list, list]:
    """Keep the first statement of each claim; return (kept, dropped).

    FIRST, not best, and deliberately: the beats arrive in the order the
    story tells them, and the opening statement of a fact is the one the
    narration builds on. Dropping beat one to keep beat three would leave the
    script referring back to something the viewer never saw.

    `floor` is what makes this safe to run in the render path. Some stories
    are one fact three times over — `driving-side-of-the-road` prunes to a
    single beat — and a one-beat video is not an improvement on a repetitive
    one. Rather than refuse the story and empty the slot, the pruner re-admits
    the dropped beats that are FURTHEST from what it already kept, until the
    floor is met. The result is the least repetitive cut this story can
    produce, which is the most a renderer can do about an authoring problem.

    Refusing outright is still the right answer at AUTHORING time, where
    there is another story to write instead — that is `one_fact_stretched`.
    """
    kept: list = []
    dropped: list = []
    for ins in insights:
        if any(restates(k, ins) for k in kept):
            dropped.append(ins)
        else:
            kept.append(ins)
    while dropped and len(kept) < min(floor, len(insights)):
        far = max(dropped, key=lambda d: min(_distance(k, d) for k in kept))
        dropped.remove(far)
        kept.append(far)
    # DO NOT STRAND A SENTENCE THAT POINTS BACKWARDS. See `_BACKREF`: a kept
    # beat whose narration opens with "it's even more..." needs the beat it
    # is referring to, so the restatement in front of it is kept as well. A
    # repeated picture is a smaller failure than a line of narration with
    # nothing behind it.
    if says is not None and len(says) == len(insights):
        keep_ids = {id(k) for k in kept}
        for j, ins in enumerate(insights):
            if id(ins) in keep_ids or j + 1 >= len(insights):
                continue
            nxt = insights[j + 1]
            if id(nxt) in keep_ids and leans_backward(says[j + 1]):
                dropped.remove(ins)
                kept.append(ins)
                keep_ids.add(id(ins))
    # Back into the story's own order — the narration was written in it.
    order = {id(x): i for i, x in enumerate(insights)}
    kept.sort(key=lambda x: order[id(x)])
    return kept, dropped


def one_fact_stretched(insights: list, *, floor: int = 2) -> bool:
    """Is this whole story one fact wearing a video's clothes?

    A story that loses so many beats to restatement that it cannot reach the
    floor is not a short story — it is a single fact somebody padded, and it
    should be refused so the forge writes a real one instead of the channel
    posting a stretched one.
    """
    kept, _ = prune_restatements(insights)
    return len(insights) >= floor and len(kept) < floor
