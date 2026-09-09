"""Does a picture USE the 9:16 frame, or leave half of it empty?

`empty_void` is the showrunner's most-cited block on the data channel. Its
notes are exact and repeatable — "the seesaw in the top ~40% and the entire
bottom half as empty gradient", "the entire lower two-thirds blank blue
gradient", "a hairline timeline with everything below it empty" — and every
one of them describes a measurable thing: a wide horizontal band of the frame
with no ink in it.

A vision model catching that is expensive, slow and non-deterministic, and it
catches it AFTER a full render. The same fact is computable from the frame in
milliseconds, which is what lets a machine be TUNED against it instead of
argued about.

Two numbers, both on the drawn layer only (never the background gradient, so
the measure does not move when the backdrop is restyled):

    coverage   fraction of the frame carrying ink
    void       the largest horizontal band with effectively none, as a
               fraction of frame height

`void` is the one that matters. A dark, line-art picture is legitimately
sparse — coverage of 8% can be a perfectly good chart — but a 40% band of
nothing is the thing a viewer reads as an unfinished frame.
"""
from __future__ import annotations

# A row is "empty" below this fraction of lit pixels. Deliberately not zero:
# a 1px rule, a source line or an anti-aliased edge is not content.
ROW_INK = 0.004
# Alpha above which a pixel counts as drawn.
ALPHA = 24


def _rows(img):
    """Per-row lit fraction of an RGBA layer, top to bottom."""
    try:
        import numpy as np
    except ImportError:                       # noqa: BLE001
        return None
    a = np.asarray(img.convert("RGBA"), dtype="uint8")
    lit = a[:, :, 3] > ALPHA
    return lit.mean(axis=1)


def measure(img, *, top: int = None, bottom: int = None) -> dict:
    """`{"coverage", "void", "void_at", "head", "tail"}` for one drawn layer.

    `img` is the TRANSPARENT layer a machine drew onto, not a composited
    frame: alpha is an exact record of what was drawn, where a brightness
    threshold against a gradient is a guess that changes with the backdrop.

    `top`/`bottom` restrict the measurement to a band of the frame, and every
    fraction returned is then relative to THAT band. Pass the box a machine
    was handed and you get its own account of itself, with the studio's
    furniture out of the arithmetic — see `verdict` for why that matters.

    `head` and `tail` are the empty runs at the two ends of the band. They are
    reported separately because they are a different defect from a hole in the
    middle: a `tail` is a picture that stopped early, a `head` is one that
    started late, and an interior `void` is two pictures with a gap between
    them. The showrunner's notes distinguish all three, and so should the
    number that stands in for it.
    """
    rows = _rows(img)
    if rows is None or not len(rows):
        return {"coverage": 0.0, "void": 1.0, "void_at": 0.0,
                "head": 1.0, "tail": 1.0}
    lo = 0 if top is None else max(0, min(int(top), len(rows)))
    hi = len(rows) if bottom is None else max(lo, min(int(bottom), len(rows)))
    rows = rows[lo:hi]
    n = len(rows)
    if not n:
        return {"coverage": 0.0, "void": 1.0, "void_at": 0.0,
                "head": 1.0, "tail": 1.0}
    best = cur = start = best_start = 0
    first = last = None
    for i, v in enumerate(rows):
        if v < ROW_INK:
            if cur == 0:
                start = i
            cur += 1
            if cur > best:
                best, best_start = cur, start
        else:
            cur = 0
            if first is None:
                first = i
            last = i
    return {"coverage": float(rows.mean()),
            "void": best / n,
            "void_at": best_start / n,
            "head": (first / n) if first is not None else 1.0,
            "tail": ((n - 1 - last) / n) if last is not None else 1.0}


def verdict(img, *, max_void: float = 0.34, min_coverage: float = 0.02,
            top: int = None, bottom: int = None) -> dict:
    """Pass/fail plus the reason, in the reviewer's own vocabulary.

    `max_void` 0.34: a third of the frame is the point at which the
    showrunner's notes stop saying "sparse" and start saying "empty". Every
    block it wrote on 2026-09-07 described a band of a half or more.

    **A band is only as long as the first thing that interrupts it, and the
    studio interrupts everything.** Measured over the whole composited frame,
    the burnt-in caption at y≈1690 and the progress rule at y≈1860 sit inside
    the bottom void and cut it into pieces, none of which reaches the ceiling.
    A picture that stops at 55% of the frame height therefore scores 24% —
    comfortably inside a 34% limit — while a viewer sees the bottom half as
    empty gradient and the showrunner writes `empty_void` in those words.
    Measured across the whole kit on 2026-09-09: not one machine exceeded the
    ceiling on the composite, and ten exceeded 22% inside their own box.

    So there are two questions and they need two calls. Over the whole frame
    with the furniture composited, `max_void=0.34` asks *is the finished frame
    acceptable*. Over `top`/`bottom` set to the machine's own box, a tighter
    ceiling asks *did the machine fill the space it was given* — which is the
    question a machine can be tuned against, because its answer does not
    depend on furniture the machine never drew.
    """
    m = measure(img, top=top, bottom=bottom)
    why = []
    if m["void"] > max_void:
        why.append(f"empty_void: {m['void'] * 100:.0f}% of the frame height "
                   f"carries nothing, starting at {m['void_at'] * 100:.0f}%")
    if m["coverage"] < min_coverage:
        why.append(f"almost nothing drawn: {m['coverage'] * 100:.1f}% coverage")
    return {**m, "ok": not why, "why": "; ".join(why)}
