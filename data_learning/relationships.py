#!/usr/bin/env python3
"""WHAT IS THIS DATA SAYING? — the question asked before any picture is chosen.

The channel picked its visual from the chart KIND: a `rank` insight got a bar
chart, a `trend` got a line. That is a rendering decision dressed as an
editorial one, and it is why every video looks like the last: the kinds are
few, so the pictures are few.

The operator's direction, 2026-09-07: choose the visual from the RELATIONSHIP
the data expresses, and let the mascot's world carry it physically.

    Speed becomes motion. Imbalance becomes weight. Progress becomes distance.
    Capacity becomes fill. Rank becomes position. A gap becomes literal space.

So this module answers one question — what relationship is this? — and answers
it from the DATA, not from whatever chart someone happened to author. Nothing
here draws anything; it is pure and testable, which matters because every
picture downstream inherits its judgement.

THE HONESTY RULE. A relationship is a CLAIM about the data, and a wrong claim
gets drawn at 200pt. `RANK` says these things are commensurable and ordered.
`GROWTH` says this rose over time and the rise is the point. `SHARE` says these
are parts of one whole — the claim that already shipped as "2019 IS 9% OF THE
WHOLE" over a mortgage rate. So each classifier refuses when it is not sure,
and `OTHER` (draw it as a chart) is always an acceptable answer. A chart is a
weaker picture and a fine one; a confident wrong metaphor is neither.
"""
from __future__ import annotations

import re

# The relationships this channel's data actually expresses. Deliberately not
# the full list of things data CAN express — a category nothing can produce is
# a category nobody maintains.
RANK = "rank"                  # 3-8 named things, ordered
DUEL = "duel"                  # exactly two things, weighed against each other
BEFORE_AFTER = "before_after"  # exactly two POINTS IN TIME — a then and a now
GROWTH = "growth"              # a series that rises, and the rise is the story
DECLINE = "decline"            # a series that falls
VOLATILE = "volatile"          # a series that goes both ways, repeatedly
SHARE = "share"                # parts of one countable whole
RATE = "rate"                  # a speed / per-unit figure, not a quantity
BURDEN = "burden"              # a cost, debt or price someone carries
DOMINANCE = "dominance"        # one item dwarfs the rest
THRESHOLD = "threshold"        # a value measured against a line it must clear
DROPOFF = "dropoff"            # named stages, each smaller than the last
FREQUENCY = "frequency"        # a count PER unit of time
UNCERTAINTY = "uncertainty"    # the range a number lived in, not its direction
STABLE = "stable"              # it barely moved, and that IS the finding
DELTA = "delta"                # the SIZE of a change between two points
GAP = "gap"                    # how far short of a line it falls
CENTRE = "centre"              # where the middle of a spread sits
ACCELERATION = "acceleration"  # the rate of change is itself changing
REVERSAL = "reversal"          # it went one way, then turned and stayed turned
SPREAD = "spread"              # how tightly the values cluster
CYCLE = "cycle"                # it repeats
QUEUE = "queue"                # a backlog, growing
DENSITY = "density"            # the same count packed into different space
BOTTLENECK = "bottleneck"      # one stage far narrower than the rest
RETENTION = "retention"        # what is kept versus what leaks away
INFLOW_OUTFLOW = "in_out"      # what comes in against what goes out
ROUTING = "routing"            # where a total is sent, by destination
CHAIN = "chain"                # named steps a thing passes through in order
OTHER = "other"                # say so, and draw a chart

_MONEY = re.compile(
    r"\b(cost|costs|price|prices|debt|rent|mortgage|bill|bills|spend|"
    r"spending|expense|fee|fees|tax|taxes|premium|tuition|payment|wage|"
    r"salary|income|afford|affordab\w*)\b", re.I)
_RATE_UNIT = re.compile(
    r"\b(per|rate|speed|mph|km/?h|kwh|per capita|per person|per year|"
    r"per hour|percent per|annual rate)\b", re.I)
_PER_TIME = re.compile(
    r"\b(per (second|minute|hour|day|week|month|year|capita|person|"
    r"household|1,?000|100,?000)|a (second|minute|hour|day|year)|"
    r"annually|each year|every year|per annum)\b", re.I)
_FLOW_IN_OUT = re.compile(
    r"\b(income|revenue|earn\w*|intake|inflow|deposits?|births?|hires?|"
    r"joiners?|arrivals?)\b.*\b(expense\w*|spend\w*|cost\w*|outflow|"
    r"withdraw\w*|deaths?|leavers?|departures?|exits?|churn)\b", re.I)
_RETAIN = re.compile(
    r"\b(retention|retained|churn|kept|stay\w*|drop out|dropout|leak\w*|"
    r"lost|renew\w*|cancel\w*|unsubscrib\w*)\b", re.I)
_ROUTE = re.compile(
    r"\b(rout(ed|ing|es to)|goes to|sent to|allocated|destination\w*|"
    r"where .* goes|split between|divided (among|between)|breakdown by|"
    r"spent on)\b", re.I)
# Explicit bottleneck language. Kept separate from the stage vocabulary
# because it is a DIAGNOSIS the writer has already made: if the claim names a
# chokepoint, draw the chokepoint, whatever shape the numbers happen to be.
_BOTTLENECK = re.compile(
    r"\b(bottleneck\w*|choke ?point\w*|held up (at|by)|jam\w*|"
    r"backed up (at|behind)|the constraint)\b", re.I)
_CHAIN = re.compile(
    r"\b(supply chain|from farm|farm to|factory to|port to|end to end|"
    r"journey|passes through|route from)\b", re.I)
_STAGE = re.compile(
    r"\b(stage|step|round|funnel|applied|accepted|enrolled|graduat\w*|"
    r"survive\w*|remain\w*|left|reach\w*|qualif\w*|shortlist\w*|"
    r"interview\w*|offer\w*|complet\w*|finish\w*|drop\w*)\b", re.I)
_SHARE_OF = re.compile(
    r"\b(share of|proportion of|percent(age)? of|of all|of every|"
    r"of american\w*|of household\w*|of adult\w*|of people|of population|"
    r"of worker\w*|of student\w*|of famil\w*|of home\w*|of car\w*)\b", re.I)


def _values(insight) -> list:
    return [float(getattr(p, "value", 0) or 0) for p in
            (getattr(insight, "items", None) or [])]


def _labels(insight) -> list:
    return [str(getattr(p, "label", "") or "") for p in
            (getattr(insight, "items", None) or [])]


def is_time_series(insight) -> bool:
    """Are the labels points in TIME? The single most load-bearing question
    here: it separates "this changed" from "these differ", and every physical
    metaphor downstream depends on which one it is."""
    labels = _labels(insight)
    if len(labels) < 3:
        return False
    yrs = sum(1 for l in labels
              if len(l) <= 7 and l[:4].isdigit() and 1800 <= int(l[:4]) <= 2200)
    return yrs >= max(3, len(labels) * 0.6)


def _turned(values: list) -> bool:
    """One direction, then the other, and it stuck.

    Split the series in half and require each half to move materially, in
    opposite directions. A single reversal inside noise is not a turn — that is
    what VOLATILE is for.
    """
    if len(values) < 6:
        return False
    mid = len(values) // 2
    a, b = values[:mid + 1], values[mid:]
    span = (max(values) - min(values)) or 1.0
    da, db = a[-1] - a[0], b[-1] - b[0]
    return (abs(da) > 0.25 * span and abs(db) > 0.25 * span
            and (da > 0) != (db > 0))


def _accelerating(values: list) -> bool:
    """Each step bigger than the last, in the same direction, most of the way.

    "Growth" says it rose. ACCELERATION says the rise itself is speeding up,
    which is a stronger and more interesting claim — so it needs most of the
    steps to agree, not just the endpoints.
    """
    if len(values) < 5:
        return False
    steps = [b - a for a, b in zip(values, values[1:])]
    if not all(x > 0 for x in steps) and not all(x < 0 for x in steps):
        return False
    # 1.25 and near-unanimity, not 1.05 and a majority. At the looser bar an
    # ordinary rise — 10, 14, 19, 25, 33, 41 — came back ACCELERATION, because
    # almost every growing series speeds up a little. The claim here is that
    # the rise is COMPOUNDING, which is a stronger thing to say and needs the
    # steps to agree.
    growing = sum(1 for a, b in zip(steps, steps[1:]) if abs(b) >= abs(a) * 1.25)
    return growing >= len(steps) - 1


def _cyclic(values: list) -> bool:
    """Up and down and up again, in swings of similar size.

    A cycle is a stronger claim than volatility: it says the movement REPEATS.
    So it needs at least two full swings and the swings must be comparable —
    otherwise a series that crashed once and recovered would be drawn as a
    season, which it is not.
    """
    if len(values) < 8:
        return False
    span = (max(values) - min(values)) or 1.0
    signs, runs, cur = [], [], 0
    for a, b in zip(values, values[1:]):
        s_ = 1 if b - a > 0.05 * span else (-1 if a - b > 0.05 * span else 0)
        if s_ == 0:
            continue
        if signs and s_ != signs[-1]:
            runs.append(cur)
            cur = 0
        signs.append(s_)
        cur += abs(b - a)
    runs.append(cur)
    runs = [r for r in runs if r > 0.15 * span]
    if len(runs) < 4:                       # fewer than two full swings
        return False
    return max(runs) <= 2.5 * min(runs)     # comparable in size


def _direction(values: list) -> tuple:
    """(net change as a fraction of the start, number of direction reversals).

    Reversals are what separate a trend from a rollercoaster: a series that
    ends higher having zig-zagged the whole way is not "growth" in any sense a
    rising tower would honestly depict.
    """
    if len(values) < 2 or values[0] == 0:
        net = 0.0
    else:
        net = (values[-1] - values[0]) / abs(values[0])
    # Only MEANINGFUL moves count as direction changes. Counting every wobble
    # made [50, 50.2, 50.1, 50.3, 50.2] — a flat line — come back "volatile",
    # which is a claim about the data ("this swings") that the data does not
    # support. A reversal has to be worth at least 8% of the whole range.
    span = (max(values) - min(values)) or 1.0
    floor = 0.08 * span
    signs = [1 if b - a > floor else (-1 if a - b > floor else 0)
             for a, b in zip(values, values[1:])]
    signs = [s for s in signs if s]
    rev = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    return net, rev


def classify(insight) -> str:
    """The relationship this insight expresses. Never raises; returns OTHER
    whenever it is not confident."""
    try:
        return _classify(insight)
    except Exception:  # noqa: BLE001 — an unclassifiable insight is a chart
        return OTHER


def _classify(insight) -> str:
    values = _values(insight)
    labels = _labels(insight)
    if len(values) < 2:
        return OTHER
    unit = (getattr(insight, "unit", "") or "").strip().lower()
    text = f"{getattr(insight, 'topic', '')} {getattr(insight, 'main_insight', '')}"

    # A BASELINE IS A LINE THE NUMBER HAS TO CLEAR.
    #
    # The config already carries one on comparison insights — the national
    # average, the target, the previous record — and nothing was doing anything
    # with it but drawing a dashed rule. A value measured against a line it
    # must clear is a hurdle, and that is a picture before it is a chart.
    base = getattr(insight, "baseline", None)
    if base is not None and getattr(base, "value", None) is not None:
        try:
            if abs(float(base.value)) > 0:
                return THRESHOLD
        except (TypeError, ValueError):
            pass

    if is_time_series(insight):
        # FLAT FIRST. [50, 50.2, 50.1, 50.3, 50.2] has a direction change at
        # every step and a range that is entirely noise; measured against its
        # own span every wobble looks decisive, so flatness has to be judged
        # against the LEVEL. Nothing to say is a real answer — it gets a line.
        level = sum(abs(v) for v in values) / len(values) or 1.0
        if (max(values) - min(values)) <= 0.03 * level:
            # STABLE is a finding, not an absence. "This has not moved in
            # twenty years" is a story, and it used to fall through to OTHER
            # and get a flat line — the one picture that makes it look like
            # nothing happened rather than like nothing CHANGED.
            return STABLE
        net, rev = _direction(values)
        # A TURN. Went one way, then the other, and STAYED — which is a
        # different claim from a zig-zag: there is a moment where it changed
        # its mind. Requires a real move each way so noise cannot fake it.
        if _turned(values):
            return REVERSAL
        # The rate of change is itself changing, consistently.
        if _accelerating(values):
            return ACCELERATION
        # It repeats. Needs several full swings of similar size, which is what
        # separates a season from a wobble.
        if _cyclic(values):
            return CYCLE
        # A trend has to actually go somewhere AND go there mostly one way.
        # Without the reversal test a series that wandered up and down and
        # happened to end high would be drawn as a clean climb, which is a
        # picture of a story the data does not tell.
        if rev >= max(2, len(values) // 3):
            return VOLATILE
        if net >= 0.15:
            return BURDEN if _MONEY.search(text) else GROWTH
        if net <= -0.15:
            return DECLINE
        return VOLATILE if rev else OTHER

    # HOW TIGHTLY THE VALUES CLUSTER is its own finding — "these are all
    # basically the same" and "one of these is nothing like the others" are
    # different stories from a ranking, and both get lost in a sorted bar
    # chart. Only claimed when the spread is genuinely extreme in one
    # direction or the other.
    if not is_time_series(insight) and len(values) >= 4:
        mean = sum(values) / len(values)
        if mean:
            import statistics as _st
            cv = _st.pstdev(values) / abs(mean)
            if cv <= 0.06:
                return SPREAD

    # Not a series: these are THINGS being compared.
    #
    # STAGES, each smaller than the last, are a funnel — people falling out at
    # every step — and that is a different claim from a ranking. It needs BOTH
    # the shape (monotonically down, and materially so) and the language,
    # because five cities sorted by cost are also "each smaller than the last"
    # and are emphatically not a funnel.
    text_l = (text or "").lower()

    # FLOW SHAPES. Each needs the CLAIM to say so, not just the numbers —
    # every one of these is also a plain ranking by shape alone, and drawing a
    # ranking as a supply chain invents a process the data never described.
    if len(values) >= 3 and _BOTTLENECK.search(text_l):
        return BOTTLENECK
    if len(values) >= 2 and _FLOW_IN_OUT.search(text_l):
        return INFLOW_OUTFLOW
    if len(values) >= 2 and _RETAIN.search(text_l):
        return RETENTION
    # CHAIN before ROUTE: "route from the port" is a journey, not an
    # allocation, and the chain vocabulary is the more specific of the two.
    if len(values) >= 3 and _CHAIN.search(text_l):
        return CHAIN
    if len(values) >= 3 and _ROUTE.search(text_l):
        return ROUTING

    # FUNNEL vs BOTTLENECK, decided on the per-stage SURVIVAL RATES rather
    # than the raw drops. A hiring funnel's biggest drop is also its first
    # one — 1,000 -> 380 -> 95 -> 41 loses more people at step one than
    # anywhere else — and it is a funnel, not a bottleneck, because every
    # stage bleeds. A bottleneck is the shape where the others DON'T: 12,000
    # -> 9,800 -> 2,100 -> 1,700 -> 1,500 keeps ~80% at every step except one,
    # which keeps 21%. Comparing drops alone called the funnel a bottleneck
    # and would have printed "here" over the wrong stage.
    if len(values) >= 3 and _STAGE.search(text_l):
        falling = all(b <= a for a, b in zip(values, values[1:]))
        if falling and values[0] > 0:
            rates = [b / a for a, b in zip(values, values[1:]) if a > 0]
            if len(rates) == len(values) - 1:
                k = rates.index(min(rates))
                others = rates[:k] + rates[k + 1:]
                if rates[k] <= 0.6 and others and min(others) >= 0.75:
                    return BOTTLENECK
            if values[-1] <= 0.6 * values[0]:
                return DROPOFF

    if len(values) == 2:
        # TWO YEARS IS NOT TWO THINGS. A then-and-now is a change in one
        # subject, and it wants to be shown as that subject growing — the
        # operator's list has a whole row for it ("object physically grows,
        # stack gains blocks, tank fills"). Measured on the live queue, 123 of
        # 222 beats came back `duel`, so over half the catalogue was heading
        # for the same set of scales. Splitting the pair by whether its labels
        # are DATES is what makes the picture follow the claim.
        yrs = sum(1 for l in labels
                  if len(l) <= 7 and l[:4].isdigit()
                  and 1800 <= int(l[:4]) <= 2200)
        return BEFORE_AFTER if yrs == 2 else DUEL
    if 3 <= len(values) <= 8:
        top = max(values)
        rest = sorted(values, reverse=True)[1:]
        # One item dwarfing the rest is its own story and its own picture —
        # a race where one runner is a mile ahead reads as a broken chart,
        # while a skyscraper among houses reads as the point.
        if rest and top >= 3.0 * (sum(rest) / len(rest)) and top > 0:
            return DOMINANCE
        if unit in ("percent", "%", "pct") and _SHARE_OF.search(text):
            return SHARE
        return RANK
    return OTHER


def is_frequency(insight) -> bool:
    """A count PER unit of time — events, not a quantity. A conveyor's items
    per second is only honest when the number really is a rate of arrival."""
    text = f"{getattr(insight, 'unit', '')} {getattr(insight, 'topic', '')} " \
           f"{getattr(insight, 'main_insight', '')}"
    return bool(_PER_TIME.search(text or ""))


def is_rate(insight) -> bool:
    """A per-unit figure rather than a quantity. Kept separate from `classify`
    because it CO-OCCURS: a rate can also be growing, and a speedometer riding
    a rising trend is two true things at once."""
    unit = (getattr(insight, "unit", "") or "").strip().lower()
    if unit in ("percent", "%", "pct", "rate"):
        return True
    text = f"{getattr(insight, 'topic', '')} {unit}"
    return bool(_RATE_UNIT.search(text))


def is_burden(insight) -> bool:
    """Money someone has to find. Also co-occurring: a cost is usually also a
    trend, and the BURDEN reading is the one a viewer feels."""
    text = f"{getattr(insight, 'topic', '')} " \
           f"{getattr(insight, 'main_insight', '')} " \
           f"{getattr(insight, 'unit', '')}"
    return bool(_MONEY.search(text))


def describe(insight) -> dict:
    """Everything the picture-chooser needs, in one call."""
    rel = classify(insight)
    return {"relationship": rel, "series": is_time_series(insight),
            "rate": is_rate(insight), "burden": is_burden(insight),
            "frequency": is_frequency(insight), "n": len(_values(insight))}
