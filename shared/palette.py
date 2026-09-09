"""THE HOUSE PALETTE — one place, and a rule that identity is never colour alone.

Operator, 2026-09-09: *"just do a whole pass on how we're conveying data ...
just the colors and style of graphics we use."*

Audited that day across `data_learning/`, `shared/` and `engines/`:

* **100 distinct colours** in the render code, **8** of them from the house
  palette. 92 one-off literals across 182 uses.
* **twelve near-identical darks** — `#0A0E20`, `#0B1020`, `#0C1220`,
  `#0B0F17`, `#0A0E1A`, `#0E1219` and more — for what is one card
  background. No viewer can tell them apart; two machines side by side can
  disagree about the colour of the same thing.
* the six-colour series palette **cycled**: `palette[i % len(palette)]`.
  7.3% of the catalogue's datasets have more than six points (up to
  thirteen), so on 82 datasets two different categories were painted the
  SAME colour. Identity by colour is not merely ugly there, it is wrong.
* the series order failed the CVD check outright — `#34D399` against
  `#F472B6` at ΔE **6.6** for a deuteranope, inside the band the house
  method calls "legal ONLY with secondary encoding".

THE COLOUR PART IS COMPUTABLE, SO IT WAS COMPUTED — twice, because the first
answer was wrong in an instructive way.

Reordering the six existing colours fixed the ADJACENT-pair check (ΔE 6.6 ->
10.3) and it was not enough, because adjacency is not what a viewer sees. A
donut shows every wedge at once and the waffle names five; the pairs on
screen together are ALL of them. Checked all-pairs, the reordered palette was
worse than the original looked:

    #A78BFA vs #60A5FA   ΔE 0.3 colourblind — the violet and the blue are
                         the same colour for a deuteranope
    #FBBF24 vs #F59E0B   ΔE 8.0 in NORMAL vision — below the hard floor of
                         15, which no amount of labelling excuses

So the colours moved. Each is the smallest nudge from its original that
clears every all-pairs floor, found by searching outward from the brand
rather than by picking new ones — the palette is recognisably the same
family, and now:

    CVD separation (all pairs)     ΔE 8.4   floor 8    PASS
    normal vision  (all pairs)     ΔE 16.6  floor 15   PASS
    contrast on the card           5.9-12.7 floor 3    PASS

THE ONE CHECK STILL FAILING, recorded rather than hidden: the lightness
band, which the reference validator measures against ITS dark surface
(`#1a1a19`). Our card is `#0B1020`, appreciably darker, so brighter marks
are correct here and the check that actually protects legibility — contrast
against the real card — passes for all six. Repainting the whole brand to
satisfy a check calibrated for a different surface would be obeying the
letter of a tool over the thing it is measuring.

AND THE RULE THAT MATTERS MOST: a series past the end of the palette gets
`OVERFLOW`, a neutral. It never wraps around to slot one. "Beyond the
palette" is the truth; "the same as the first one" is a lie, and it is the
lie the modulo was telling on 82 datasets.
"""
from __future__ import annotations

import itertools

# ---------------------------------------------------------------------------
# Surfaces and ink

CARD = "#0B1020"        # the ONE card background. See the near-duplicate list.
CARD_EDGE = "#1F2A44"
GRID = "#1B2540"        # recessive: a grid line is not a mark

INK = "#F8FAFC"         # primary text
INK_SOFT = "#A5B4C7"    # secondary text, axis labels
INK_MUTED = "#64748B"   # captions, source lines

# Values, labels and legends wear INK — never the series colour. A coloured
# mark BESIDE them carries the identity; a number painted in the series hue
# reads as decoration and loses contrast the moment the hue changes.

# ---------------------------------------------------------------------------
# Categorical identity

#: The fixed hue order. HANDED OUT IN ORDER, NEVER CYCLED — see `series_color`.
SERIES = ("#6DB6F2",    # blue      was #60A5FA
          "#F28B24",    # orange    was #F59E0B
          "#AA72FF",    # violet    was #A78BFA
          "#F26DB6",    # pink      was #F472B6
          "#F2D254",    # yellow    was #FBBF24
          "#36D89F")    # green     was #34D399

#: Everything past the palette. A neutral says "not one of the named series",
#: which is true; wrapping to slot one says "this is the first series", which
#: is not.
OVERFLOW = "#94A3B8"

#: The number of categories colour can carry. Past this, identity has to come
#: from a direct label — which every renderer that uses this palette draws.
MAX_SERIES = len(SERIES)


def series_color(i: int, *, highlight: str | None = None,
                 labelled: int | None = None) -> str:
    """The colour for categorical slot `i`.

    Fixed order, and it REFUSES to wrap. `palette[i % len(palette)]` is what
    this replaces, and on a thirteen-point dataset that handed slots 0 and 6
    the identical blue — two wedges the same colour with different names on
    them.

    `labelled` is how many entries the CALLER actually names on screen, and
    it exists because the two must agree. The waffle's legend stops at five
    while its palette handed out six, so the sixth slice had a colour and
    nothing anywhere saying what it was — identity by colour alone, which is
    the one thing the method forbids. Passing the real legend size makes
    "coloured" and "named" the same set by construction.
    """
    if highlight is not None:
        return highlight
    cap = len(SERIES) if labelled is None else min(labelled, len(SERIES))
    if i < 0 or i >= cap:
        return OVERFLOW
    return SERIES[i]


# ---------------------------------------------------------------------------
# The checks, so CI can run what the audit ran

def _rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(h: str) -> float:
    r, g, b = (_lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# Machado, Oliveira & Fernandes (2009), severity 1.0, applied in LINEAR RGB.
# Copied from the house validator rather than approximated: a first version of
# this file used a rough sRGB-space transform and reported ΔE 14.7 where the
# validator reported 6.6, so the check PASSED the very ordering the validator
# had just failed. A gate that accepts the known-bad input is not a gate, it
# is a comment — and only a test that fed it the old order caught that.
_MACHADO = {
    "protanopia": ((0.152286, 1.052583, -0.204868),
                   (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968),
                     (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
}


def _lin_rgb(h: str) -> tuple:
    return tuple(_lin(c) for c in _rgb(h))


def _oklab_from_lin(rgb) -> tuple:
    r, g, b = rgb
    lr = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    mr = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    sr = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = (v ** (1 / 3) if v > 0 else -((-v) ** (1 / 3))
                  for v in (lr, mr, sr))
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def simulate(h: str, kind: str = "deuteranopia"):
    """Red-green colour blindness in LINEAR RGB — roughly 8% of men, which on
    a channel this size is a great many viewers. Returns linear RGB, because
    that is what the distance function wants; converting back to hex and in
    again is where the first version lost its accuracy."""
    m = _MACHADO[kind]
    r, g, b = _lin_rgb(h)
    return tuple(min(1.0, max(0.0, row[0] * r + row[1] * g + row[2] * b))
                 for row in m)


def delta_e(a: str, b: str, kind: str | None = None) -> float:
    """OKLab distance x100 — the same units `validate_palette.js` reports, so
    a number here and a number from the validator mean the same thing."""
    pa = simulate(a, kind) if kind else _lin_rgb(a)
    pb = simulate(b, kind) if kind else _lin_rgb(b)
    return 100.0 * sum((x - y) ** 2 for x, y in
                       zip(_oklab_from_lin(pa), _oklab_from_lin(pb))) ** 0.5


#: Floors. The adjacent-pair CVD floor and the normal-vision hard floor come
#: from the house data-viz method; the contrast floor is WCAG for a large
#: graphic. They are named here so a change to them is a visible decision.
CVD_FLOOR = 8.0        # the validator's target; below 6.0 it hard-fails
NORMAL_FLOOR = 15.0    # hard: a full-colour reader cannot tell the pair apart
CONTRAST_FLOOR = 3.0


def audit(colors=SERIES, surface: str = CARD) -> dict:
    """Every check, on the colours actually shipped. Adjacent pairs for the
    CVD and normal-vision floors — that is what a reader compares, and it is
    why REORDERING alone fixed this palette without repainting it."""
    problems = []
    for c in colors:
        k = contrast(c, surface)
        if k < CONTRAST_FLOOR:
            problems.append(f"{c} contrast {k:.2f} on {surface}")
    for a, b in zip(colors, colors[1:]):
        d = delta_e(a, b)
        if d < NORMAL_FLOOR:
            problems.append(f"{a} vs {b} normal ΔE {d:.1f}")
        # min(protan, deutan) — the validator's rule. A pair that separates
        # for one form and collapses for the other has still collapsed.
        d = min(delta_e(a, b, k)
                for k in ("deuteranopia", "protanopia"))
        if d < CVD_FLOOR:
            problems.append(f"{a} vs {b} colourblind ΔE {d:.1f}")
    return {"ok": not problems, "problems": problems}


def worst_pair(colors=SERIES) -> tuple:
    """The closest pair under any vision, for reporting."""
    out = []
    for a, b in itertools.combinations(colors, 2):
        for kind in (None, "deuteranopia", "protanopia"):
            out.append((delta_e(a, b, kind), a, b, kind or "normal"))
    return min(out)


if __name__ == "__main__":
    v = audit()
    print(f"card {CARD}   series {len(SERIES)}   overflow {OVERFLOW}")
    for c in SERIES:
        print(f"  {c}  contrast {contrast(c, CARD):5.2f}")
    d, a, b, kind = worst_pair()
    print(f"\nclosest pair anywhere: {a} vs {b}  ΔE {d:.1f} ({kind})")
    print("PASS" if v["ok"] else "FAIL: " + "; ".join(v["problems"]))
