"""Fit a title into a band — MEASURED, never guessed.

Both publishing channels had the same bug and only one of them had solved
it. `engines/chart_race.py` measured the real rendered width with the canvas
renderer and stepped the size down until the text fit; its own docstring
recorded why ("matplotlib's own `wrap=True` measures against the figure, not
the band we allot, and silently overflowed long titles off both edges — seen
in production"). Meanwhile `data_learning/charts._heading` claimed in a
comment to "auto-shrink so long titles never clip the right edge of the
card" and actually picked a font size from the CHARACTER COUNT.

Character count is not width. Measured on the explainer's own card, with
real production titles (right edge as a fraction of figure width; the card
content ends at ~0.915):

    "Urban growth just hit a 50-year low"               0.929
    "World hydropower fell below its 1990 level"        0.966   <- shipped
    "Prevalence of undernourishment in the population"  1.120
    "Agricultural land area as a share of total land"   1.352
    "MMMMMMMMMMMMMMMMMMMMMMMM"  (24 chars)              1.481

The showrunner's note on the hydropower story on 2026-08-11 was, in its own
words, "a headline clipped off the right edge". A comment asserting a
property the code does not have is the thing CLAUDE.md calls worse than no
comment at all: the next session reads it and looks elsewhere.

So the measuring implementation moves here and both channels call it.
`tests/test_fit_title.py` holds it against the original chart_race code,
kept verbatim as an oracle — a consolidation is only a consolidation if the
output is identical.
"""
from __future__ import annotations


def fit_title(fig, text: str, font_path: str | None, max_w_px: float,
              max_lines: int = 2, hi: int = 46, lo: int = 26):
    """Wrap + auto-shrink `text` so it NEVER runs off frame.

    Steps the font size down from `hi` to `lo` (by 2), greedily wrapping at
    each size, and returns the first size whose every line measures within
    `max_w_px` and which uses no more than `max_lines` lines. Measurement is
    the real rendered extent from the canvas renderer, so it is correct for
    caps, wide glyphs and any font.

    When nothing fits — a single token wider than the band at the smallest
    size — the line is truncated with an ellipsis rather than allowed off
    frame. The original returned it untouched, which is how a function whose
    docstring says "NEVER runs off frame" shipped one that does.

    Returns `(text_with_newlines, FontProperties)`. Falls back to the
    caller's `hi` untouched when no renderer is available — a missing
    renderer is not a reason to mangle the title.
    """
    import matplotlib.font_manager as fm
    words = text.split()
    if not words:
        return text, fm.FontProperties(size=hi)
    try:
        renderer = fig.canvas.get_renderer()
    except Exception:  # noqa: BLE001 — no renderer: trust the caller's size
        return text, (fm.FontProperties(fname=font_path, size=hi)
                      if font_path else fm.FontProperties(weight="bold",
                                                          size=hi))

    def _fp(size):
        return (fm.FontProperties(fname=font_path, size=size) if font_path
                else fm.FontProperties(weight="bold", size=size))

    def _width(s, fp):
        probe = fig.text(0, 0, s, fontproperties=fp)
        w = probe.get_window_extent(renderer=renderer).width
        probe.remove()
        return w

    def _ellipsize(line, fp):
        """Longest prefix of `line` that fits the band with a trailing
        ellipsis. The last resort, for a token no wrapping can break."""
        if _width(line, fp) <= max_w_px:
            return line
        lo_i, hi_i = 0, len(line)
        while lo_i < hi_i:
            mid = (lo_i + hi_i + 1) // 2
            if _width(line[:mid].rstrip() + "\u2026", fp) <= max_w_px:
                lo_i = mid
            else:
                hi_i = mid - 1
        return (line[:lo_i].rstrip() + "\u2026") if lo_i else ""

    for size in range(hi, lo - 1, -2):
        fp = _fp(size)
        lines, cur = [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if cur and _width(trial, fp) > max_w_px:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        if cur:
            lines.append(cur)
        # a single word wider than the band can't be fixed by wrapping
        if len(lines) <= max_lines and all(_width(x, fp) <= max_w_px
                                           for x in lines):
            return "\n".join(lines), fp
    # NOTHING FITS. The original returned the over-wide words untouched, so a
    # single unbreakable token — a long compound, a URL, a run of caps — ran
    # straight off the card while the docstring promised it never would. A
    # truncated title is readable; one that leaves the frame is not.
    fp = _fp(lo)
    return ("\n".join(_ellipsize(w, fp) for w in words[:max_lines]), fp)
