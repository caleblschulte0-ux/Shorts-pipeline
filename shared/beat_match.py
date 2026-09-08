"""Does the picture show the number the narration SAYS?

The operator's words, 2026-09-07: *"we need to be matching the beats a lot
better."* Measured over the 858 configured explainer beats that speak a
quantity, 84.5% have their headline number written on the frame and 15.5% do
not — and the misses are one clear class:

    "In 1990, 22 percent of the world was nearsighted. By 2020 that hit
     34 percent — 2.6 billion people."          chart shows 22% / 34%
    "Auto loan rates peaked at 8.1 percent. On a 50 thousand dollar car..."
                                                 chart shows 5.2% / 8.1%
    "We've named about 240 thousand ocean species and think there are
     2 million."                                 chart shows 240K

In every case the writer converts the measured figure into a second, LOUDER
one the dataset does not contain — a rate into a headcount, a rate into a
dollar amount — and the viewer hears a number they cannot find on screen.

That is an AUTHORING fault, not a rendering one, and it is already against
this repo's standing rule that the brain writes only the words while every
number comes from the source. This module is the check: the loudest quantity
in a say line must be derivable from that beat's own data.

Derivable is generous on purpose — a difference between two values, a
percentage change, a share of the total and a unit rescale are all things the
beat can legitimately state and the chart can legitimately be showing. What it
refuses is a number that appears from nowhere.
"""
from __future__ import annotations

import re

_NUM = re.compile(r"\d[\d,]*\.?\d*")
_MULT = (("trillion", 1e12), ("billion", 1e9), ("million", 1e6),
         ("thousand", 1e3))
# Tolerance: the writer rounds, and should. "nearly 1.4 trillion" for 1,370
# billion is the same fact said aloud.
_TOL = 0.03


def spoken_quantities(say: str) -> list:
    """Every quantity a LISTENER hears, scaled by any magnitude word after it.

    Years are skipped: "since 2007" is a date, not a quantity, and counting it
    would make every beat trivially match.
    """
    out = []
    for m in _NUM.finditer(say or ""):
        try:
            v = float(m.group(0).replace(",", ""))
        except ValueError:
            continue
        if 1900 <= v <= 2100 and float(v).is_integer():
            continue
        tail = (say[m.end():m.end() + 14] or "").lstrip().lower()
        for word, mul in _MULT:
            if tail.startswith(word):
                v *= mul
                break
        out.append(v)
    return out


def _unit_scale(unit: str) -> float:
    u = (unit or "").lower()
    for word, mul in _MULT:
        if word in u:
            return mul
    return 1.0


def sayable(values, unit: str = "") -> set:
    """Every quantity this beat could honestly put on screen."""
    scale = _unit_scale(unit)
    vals = [float(v) for v in values]
    out = set()
    for v in vals:
        out.add(v)
        out.add(v * scale)
    total = sum(vals) or 1.0
    for a in vals:
        out.add(round(a / total * 100, 1))
        for b in vals:
            out.add(abs(a - b))
            out.add(abs(a - b) * scale)
            if b:
                out.add(round(a / b * 100, 1))
                out.add(round((a - b) / b * 100, 1))
    return out


def _near(a: float, b: float) -> bool:
    if a == 0 or b == 0:
        return abs(a - b) < 0.05
    return abs(a - b) / max(abs(a), abs(b)) <= _TOL


def check(say: str, values, unit: str = "") -> dict:
    """`{"ok", "headline", "why"}` for one beat.

    Only the HEADLINE — the loudest quantity in the line — has to be on
    screen. A supporting number the writer mentions in passing is fine; the
    one the beat is ABOUT is not allowed to be missing from the picture.
    """
    spoken = spoken_quantities(say)
    if not spoken or not list(values):
        return {"ok": True, "headline": None, "why": ""}
    head = max(spoken, key=abs)
    on = sayable(values, unit)
    if any(_near(head, v) for v in on):
        return {"ok": True, "headline": head, "why": ""}
    return {"ok": False, "headline": head,
            "why": (f"the line's loudest number ({head:,.6g}) is not in this "
                    f"beat's data and cannot be on screen when it is spoken — "
                    f"say a number the picture shows")}
