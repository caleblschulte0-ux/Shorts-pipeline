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


def measure(img) -> dict:
    """`{"coverage", "void", "void_at"}` for one drawn layer.

    `img` is the TRANSPARENT layer a machine drew onto, not a composited
    frame: alpha is an exact record of what was drawn, where a brightness
    threshold against a gradient is a guess that changes with the backdrop.
    """
    rows = _rows(img)
    if rows is None or not len(rows):
        return {"coverage": 0.0, "void": 1.0, "void_at": 0.0}
    n = len(rows)
    best = cur = start = best_start = 0
    for i, v in enumerate(rows):
        if v < ROW_INK:
            if cur == 0:
                start = i
            cur += 1
            if cur > best:
                best, best_start = cur, start
        else:
            cur = 0
    return {"coverage": float(rows.mean()),
            "void": best / n,
            "void_at": best_start / n}


def verdict(img, *, max_void: float = 0.34, min_coverage: float = 0.02) -> dict:
    """Pass/fail plus the reason, in the reviewer's own vocabulary.

    `max_void` 0.34: a third of the frame is the point at which the
    showrunner's notes stop saying "sparse" and start saying "empty". Every
    block it wrote on 2026-09-07 described a band of a half or more.
    """
    m = measure(img)
    why = []
    if m["void"] > max_void:
        why.append(f"empty_void: {m['void'] * 100:.0f}% of the frame height "
                   f"carries nothing, starting at {m['void_at'] * 100:.0f}%")
    if m["coverage"] < min_coverage:
        why.append(f"almost nothing drawn: {m['coverage'] * 100:.1f}% coverage")
    return {**m, "ok": not why, "why": "; ".join(why)}
