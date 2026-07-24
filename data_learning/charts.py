"""Chart rendering (matplotlib) in the channel house style.

Charts are sized 1080x960 to fill the *top half* of the 1080x1920 stacked
short — the existing renderer scales/crops a shot image into that region.
The bottom half stays gameplay, so the format is unchanged.

matplotlib is optional: if it isn't installed, :func:`render_chart` returns
None and the caller falls back to a stock B-roll query, so the base
pipeline still produces a video.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from .insights import Insight

# House palette (from the design spec).
BG = "#0B1020"
TEXT = "#F8FAFC"
SUBTLE = "#A5B4C7"
HIGHLIGHT = "#4FD1C5"
ACCENT = "#60A5FA"
WARN = "#F59E0B"
BAR_BASE = "#1F2937"

# --- Viz registry -----------------------------------------------------------
# Full-frame renderers author a 1080x1920 PNG sequence themselves (like the
# diorama) instead of the top "card" region. studio_render reads this dict to
# decide which segments fill the whole frame, so it's the single source of truth.
FULLFRAME_RENDERERS: dict = {}


def _fullframe(kind: str):
    """Register a full-frame (own PNG sequence) renderer under `kind`."""
    def deco(fn):
        FULLFRAME_RENDERERS[kind] = fn
        return fn
    return deco


# When a renderer can't produce its output (e.g. image generation failed), the
# segment DEGRADES to another kind that still DEPICTS the data — never to a bare
# number layout. `bubbles` is the terminal fallback: pure matplotlib, no network,
# area-encodes value, always renders. NEVER map anything to callouts/bignum.
FALLBACK = {
    "mechanic": "scene",             # AI-invented mechanic -> kit scene -> diorama
    "scene": "diorama",              # an invented scene degrades to the diorama
    "race": "diorama",               # a race with no images -> illustrated ranking
    "diorama": "bubbles",
    "pictorial_race": "rank",        # rounded bars — length still depicts
    "scale_stack": "pictograph",
    "timeline": "trend",             # position on a time axis
    "fill_vessel": "bubbles",
    "waffle_grid": "share",          # donut — angle still depicts
    "orbit": "bubbles",
    "flow_race": "bubbles",
    "pictograph": "bubbles",
    "callouts": "bubbles",           # legacy safety: never render bare text
    "bignum": "fill_vessel",
}

# Top-half canvas: 1080x960 at 100 dpi -> 10.8 x 9.6 inches.
FIG_W, FIG_H, DPI = 10.8, 9.6, 100


def _have_mpl() -> bool:
    try:
        import matplotlib  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def render_chart(insight: Insight, out_path: Path) -> Path | None:
    """Render a chart PNG for the insight. Returns the path, or None when
    matplotlib is unavailable."""
    if not _have_mpl():
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H), dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    if insight.kind == "trend":
        _draw_trend(ax, insight)
    else:
        _draw_bars(ax, insight)

    # Source footer.
    fig.text(0.5, 0.03, insight.source.footer(), ha="center", va="bottom",
             fontsize=11, color=SUBTLE)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=SUBTLE)
    fig.subplots_adjust(left=0.30, right=0.95, top=0.86, bottom=0.10)
    fig.savefig(out_path, facecolor=BG)
    plt.close(fig)
    return out_path


def _title(ax, insight: Insight):
    ax.set_title(insight.topic, color=TEXT, fontsize=30, fontweight="bold",
                 pad=24, loc="left")


def _draw_bars(ax, insight: Insight):
    items = list(insight.items)
    if insight.baseline:
        items = items + [insight.baseline]
    labels = [p.label for p in items]
    values = [p.value for p in items]
    y = list(range(len(items)))
    colors = []
    for p in items:
        if insight.baseline and p.label == insight.baseline.label:
            colors.append(WARN)
        elif p.label == insight.highlight_label:
            colors.append(HIGHLIGHT)
        else:
            colors.append(ACCENT)
    ax.barh(y, values, color=colors, height=0.62, zorder=3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=22, color=TEXT)
    ax.invert_yaxis()
    ax.set_xticks([])
    vmax = max(values) if values else 1
    for yi, v in zip(y, values):
        ax.text(v + vmax * 0.015, yi, _vfmt(v), va="center",
                fontsize=22, color=TEXT, fontweight="bold")
    ax.set_xlim(0, vmax * 1.18)
    _title(ax, insight)


def _draw_trend(ax, insight: Insight):
    pts = insight.items
    x = list(range(len(pts)))
    values = [p.value for p in pts]
    ax.plot(x, values, color=HIGHLIGHT, linewidth=4, marker="o",
            markersize=8, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels([p.label for p in pts], fontsize=18, color=SUBTLE)
    ax.tick_params(axis="y", labelsize=18, colors=SUBTLE)
    # Headroom on the right so the end label isn't clipped at the edge.
    ax.set_xlim(-0.3, (len(pts) - 1) + 0.7)
    # End-label the last value.
    ax.text(x[-1], values[-1], f"  {values[-1]:.1f}", va="center",
            fontsize=24, color=TEXT, fontweight="bold")
    ax.grid(axis="y", color="#1b2540", linewidth=1, zorder=0)
    _title(ax, insight)


# ---------------------------------------------------------------------------
# Chart SERIES — progressive reveal for the studio renderer.
#
# Instead of one chart, build several "states" that reveal the data step by
# step, so the narration tells a story across 3-4 graphs. Each state is
# drawn on a rounded dark card with a transparent margin, so it reads
# cleanly over the ambient background.
# ---------------------------------------------------------------------------

CARD = "#0B1020"
CARD_EDGE = "#1f2a44"
# Taller card so the chart DOMINATES the frame (~80% tall): fills the vertical
# space (kills the empty lower band the gate consistently flags) and drops each
# element low enough for Data to perform ON it.
SERIES_W, SERIES_H, SERIES_DPI = 10.0, 14.5, 110   # -> 1100x1595 px


def _vfmt(v: float) -> str:
    """Value label: drop the .0 on whole numbers, else one decimal."""
    return f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}"


def _ulabel(v: float, unit: str) -> str:
    """Value label with a unit cue: percent -> trailing %, plain dollars ->
    leading $, anything else (index, ratio, $-thousands, counts) -> bare
    number (the chart subtitle carries the unit)."""
    n = _vfmt(v)
    u = (unit or "").strip().lower()
    if u in ("percent", "%", "rate", "pct"):
        return n + "%"
    if u in ("dollars", "dollar", "usd", "$"):
        return "$" + n
    return n


# ---- HOST BAKED INTO THE CHART ------------------------------------------
# Data drawn INSIDE each chart frame at the GROWING data tip, so he rides the
# line / the bar as it draws — mascot and data move together, frame by frame. A
# looping sprite composited on top can only slide around; baked in, he actually
# performs ON the data (the architecture the showrunner keeps asking for). His
# pose animates with the reveal phase, so he's acting, not a held sticker.
_HOST_IMG_CACHE: dict = {}


def _host_img(action: str, phase: float):
    """One mascot action frame as an RGBA numpy array (cached by action+phase)."""
    key = (action, round(phase * 10) / 10)
    if key in _HOST_IMG_CACHE:
        return _HOST_IMG_CACHE[key]
    val = None
    try:
        import io
        import numpy as np
        from PIL import Image
        from . import mascot_director as _md
        svg = _md.compose_anim({"action": action, "prop": "none"}, key[1] % 1.0)
        png = _md._rasterise(svg, 300)
        val = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA")) / 255.0
    except Exception:  # noqa: BLE001 — a chart must never die over the host
        val = None
    _HOST_IMG_CACHE[key] = val
    return val


def _bake_host(ax, x, y, action, phase, zoom=0.5, align=(0.5, 0.08)):
    """Composite Data performing ``action`` at data point (x, y) on ``ax``. The
    pose animates with ``phase``; ``align`` (0.5, ~0) puts his FEET at the point
    so he stands ON the datum."""
    img = _host_img(action, phase)
    if img is None:
        return
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    ab = AnnotationBbox(OffsetImage(img, zoom=zoom), (x, y), frameon=False,
                        box_alignment=align, zorder=8, pad=0, annotation_clip=False)
    ax.add_artist(ab)


def _ordered_items(insight: Insight) -> list:
    """The reveal order for an insight, baseline last when present."""
    items = list(insight.items)
    if insight.kind == "trend":
        return items                       # revealed point-by-point
    if insight.baseline:
        items = items + [insight.baseline]
    return items


def series_length(insight: Insight) -> int:
    items = _ordered_items(insight)
    if insight.kind == "trend":
        return max(1, len(items) - 1)      # states: 2 points .. all points
    return len(items)


def _new_card():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig = plt.figure(figsize=(SERIES_W, SERIES_H), dpi=SERIES_DPI)
    fig.patch.set_alpha(0.0)               # transparent outside the card
    # Background axes holds the rounded card so it draws *under* the data
    # axes (figure-level patches would paint over everything).
    bg = fig.add_axes([0, 0, 1, 1])
    bg.set_axis_off()
    bg.set_zorder(0)
    card = FancyBboxPatch(
        (0.02, 0.02), 0.96, 0.96,
        boxstyle="round,pad=0.0,rounding_size=0.04",
        transform=fig.transFigure, facecolor=CARD, edgecolor=CARD_EDGE,
        linewidth=2, alpha=0.93)
    bg.add_patch(card)
    ax = fig.add_axes([0.30, 0.12, 0.62, 0.66])
    ax.set_facecolor("none")
    ax.set_zorder(1)
    return fig, ax, plt


def _color_for(p, insight: Insight, revealed: bool):
    if not revealed:
        return "#16203a"                   # ghosted (not yet revealed)
    if insight.baseline and p.label == insight.baseline.label:
        return WARN
    if p.label == insight.highlight_label:
        return HIGHLIGHT
    return ACCENT


def _draw_bars_state(ax, insight: Insight, k: int):
    """Reveal the first ``k`` items of a bar chart; rest are ghosted."""
    items = _ordered_items(insight)
    labels = [p.label for p in items]
    values = [p.value for p in items]
    y = list(range(len(items)))
    vmax = max(values) if values else 1
    for i, (yi, p, v) in enumerate(zip(y, items, values)):
        revealed = i < k
        shown = v if revealed else 0.0
        ax.barh(yi, shown, color=_color_for(p, insight, revealed),
                height=0.62, zorder=3)
        if revealed:
            ax.text(v + vmax * 0.015, yi, _vfmt(v), va="center",
                    fontsize=24, color=TEXT, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=24, color=TEXT)
    ax.invert_yaxis()
    ax.set_xticks([])
    ax.set_xlim(0, vmax * 1.18)


def _draw_trend_state(ax, insight: Insight, k: int):
    """Draw the line up to point index ``k`` (k>=1)."""
    pts = insight.items
    x = list(range(len(pts)))
    values = [p.value for p in pts]
    kk = min(len(pts), k + 1)
    ax.plot(x[:kk], values[:kk], color=HIGHLIGHT, linewidth=5, marker="o",
            markersize=10, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels([p.label for p in pts], fontsize=20, color=SUBTLE)
    ax.tick_params(axis="y", labelsize=20, colors=SUBTLE)
    ax.set_xlim(-0.3, (len(pts) - 1) + 0.7)
    ax.set_ylim(min(values) - (max(values) - min(values)) * 0.12 - 0.2,
                max(values) * 1.12 + 0.2)
    if kk >= 1:
        ax.text(x[kk - 1], values[kk - 1], "  " + _vfmt(values[kk - 1]),
                va="center", fontsize=26, color=TEXT, fontweight="bold")
    ax.grid(axis="y", color="#1b2540", linewidth=1, zorder=0)


def _card_base():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig = plt.figure(figsize=(SERIES_W, SERIES_H), dpi=SERIES_DPI)
    fig.patch.set_alpha(0.0)
    bg = fig.add_axes([0, 0, 1, 1])
    bg.set_axis_off()
    bg.set_zorder(0)
    card = FancyBboxPatch(
        (0.02, 0.02), 0.96, 0.96,
        boxstyle="round,pad=0.0,rounding_size=0.045",
        transform=fig.transFigure, facecolor=CARD, edgecolor=CARD_EDGE,
        linewidth=2, alpha=0.95)
    bg.add_patch(card)
    return fig, plt


def _heading(fig, title: str, subtitle: str, accent: str = HIGHLIGHT):
    # Drop a trailing unit parenthetical ("($)", "(%)", "($ billions)") and
    # auto-shrink so long titles never clip the right edge of the card.
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    size = (42 if len(title) <= 24 else 36 if len(title) <= 31
            else 30 if len(title) <= 40 else 26)
    fig.text(0.085, 0.91, title, color=TEXT, fontsize=size, fontweight="bold",
             ha="left", va="top")
    if subtitle:
        fig.text(0.085, 0.845, subtitle.upper(), color=accent, fontsize=22,
                 fontweight="bold", ha="left", va="top")


def _footer(fig, insight: Insight):
    fig.text(0.5, 0.045, insight.source.footer(), ha="center", fontsize=12,
             color=SUBTLE)


def _round_barh(ax, y, value, lw, color, zorder=3):
    ax.plot([0.0, value], [y, y], color=color, lw=lw, solid_capstyle="round",
            zorder=zorder)


def _round_barv(ax, x, value, lw, color, zorder=3):
    ax.plot([x, x], [0.0, value], color=color, lw=lw, solid_capstyle="round",
            zorder=zorder)


def _bar_lw(n: int) -> float:
    """Bar thickness (points) so rounded bars fill the (now taller) axes."""
    plot_px = SERIES_H * 0.58 * SERIES_DPI       # bars axes is ~58% tall
    row_px = plot_px / max(1, n)
    return max(40.0, row_px * 0.5 * 72.0 / SERIES_DPI)


def _lblalpha(reveal: float) -> float:
    """Number labels fade in over the last 20% of the build so they 'land'
    as the bar/line reaches them."""
    return max(0.0, min(1.0, (reveal - 0.8) / 0.2))


def _story_bars(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Rounded horizontal bars on a track — for rankings/outliers."""
    items = _ordered_items(insight)
    values = [p.value for p in items]
    vmax = max(values) if values else 1.0
    n = len(items)
    lw = _bar_lw(n)
    ax = fig.add_axes([0.32, 0.17, 0.60, 0.58])
    ax.set_facecolor("none")
    arts = []
    for i, (p, v) in enumerate(zip(items, values)):
        if insight.baseline and p.label == insight.baseline.label:
            color = WARN
        elif p.label == insight.highlight_label:
            color = HIGHLIGHT
        else:
            color = ACCENT
        _round_barh(ax, i, vmax, lw, BAR_BASE, zorder=2)          # track
        _round_barh(ax, i, max(v * reveal, vmax * 0.012), lw, color, zorder=3)
        t = ax.text(v + vmax * 0.02, i, _vfmt(v), va="center", fontsize=30,
                    color=TEXT, fontweight="bold", zorder=4,
                    alpha=_lblalpha(reveal))
        arts.append((p.value, "art", t, None))
    ax.set_yticks(range(n))
    ax.set_yticklabels([p.label for p in items], fontsize=27, color=TEXT)
    # Tint the winner's (and baseline's) label so the eye lands on it.
    for lbl, p in zip(ax.get_yticklabels(), items):
        if insight.baseline and p.label == insight.baseline.label:
            lbl.set_color(WARN)
        elif p.label == insight.highlight_label:
            lbl.set_color(HIGHLIGHT)
            lbl.set_fontweight("bold")
    ax.invert_yaxis()
    ax.set_xticks([])
    ax.set_xlim(0, vmax * 1.22)
    ax.set_ylim(n - 0.5, -0.5)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    # Anchor each value at its number label so the marker encircles the whole
    # number (and the mascot walks to it).
    return ax, arts


def _story_versus(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Two tall rounded columns with big numbers — for comparisons."""
    hi, lo = insight.items[0], insight.items[1]
    pair = [(hi, HIGHLIGHT), (lo, ACCENT)]
    vmax = max(hi.value, lo.value)
    ax = fig.add_axes([0.10, 0.22, 0.82, 0.50])
    ax.set_facecolor("none")
    lw = 100
    xs = [0.30, 0.70]
    colors = [HIGHLIGHT, ACCENT]
    arts = []
    for (p, color), x in zip(pair, xs):
        _round_barv(ax, x, vmax, lw, BAR_BASE, zorder=2)
        _round_barv(ax, x, max(p.value * reveal, vmax * 0.02), lw, color, zorder=3)
        t = ax.text(x, p.value + vmax * 0.06, _vfmt(p.value) + "%",
                    ha="center", fontsize=46, color=TEXT, fontweight="bold",
                    zorder=4, alpha=_lblalpha(reveal))
        arts.append((p.value, "art", t, None))
        ax.text(x, -vmax * 0.30, p.label, ha="center", fontsize=28,
                color=color, fontweight="bold", zorder=4)
    ax.text(0.5, vmax * 0.5, "vs", ha="center", va="center", fontsize=34,
            color=SUBTLE, fontstyle="italic", zorder=4)
    # Baseline reference line if present (label kept inside the card).
    if insight.baseline:
        b = insight.baseline.value
        ax.plot([0.10, 0.90], [b, b], color=WARN, lw=2.5, ls=(0, (4, 3)),
                zorder=2)
        ax.text(0.5, b + vmax * 0.04,
                f"{insight.baseline.label} {_vfmt(b)}%", ha="center",
                va="bottom", fontsize=19, color=WARN, fontweight="bold",
                zorder=4)
    ax.set_xlim(0, 1)
    ax.set_ylim(-vmax * 0.44, vmax * 1.30)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    # Anchor each column at its big number label.
    return ax, arts


def _story_trend(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Line with a soft area fill, a peak callout, and a glowing end."""
    pts = insight.items
    x = list(range(len(pts)))
    values = [p.value for p in pts]
    ax = fig.add_axes([0.13, 0.18, 0.80, 0.56])
    ax.set_facecolor("none")
    lo = min(values)
    span = max(values) - lo
    # Draw the line/fill only up to the revealed fraction (it "sketches in").
    n = len(values)
    grown = reveal * (n - 1)
    kf = int(grown)
    frac = grown - kf
    xd, yd = x[:kf + 1][:], values[:kf + 1][:]
    if kf < n - 1 and frac > 0:
        xd = xd + [x[kf] + frac]
        yd = yd + [values[kf] + (values[kf + 1] - values[kf]) * frac]
    # GHOST the WHOLE trajectory (dim) under the revealed portion, so from frame
    # one the frame carries the full chart SHAPE instead of a knee-high stub over
    # dead navy (the empty_void the gate flagged). The bright line sketches in
    # over this faint preview; the fill/line below draw on top at full strength.
    ax.fill_between(x, values, lo - span * 0.15,
                    color=HIGHLIGHT, alpha=0.05, zorder=1)
    ax.plot(x, values, color=HIGHLIGHT, lw=3, alpha=0.16,
            solid_capstyle="round", zorder=1)
    ax.fill_between(xd, yd, lo - span * 0.15,
                    color=HIGHLIGHT, alpha=0.16, zorder=2)
    ax.plot(xd, yd, color=HIGHLIGHT, lw=6, solid_capstyle="round", zorder=3)
    ax.plot(x[:kf + 1], values[:kf + 1], "o", color=HIGHLIGHT,
            markersize=9, zorder=4)
    la = _lblalpha(reveal)
    pk = max(range(len(values)), key=lambda i: values[i])
    last = len(values) - 1
    # Value labels at peak + end (the markers encircle these whole numbers).
    arts = []
    for k in range(len(values)):
        if k == pk and 0 < pk < last:
            t = ax.text(x[k], values[k] + span * 0.12,
                        _ulabel(values[k], insight.unit),
                        ha="center", fontsize=26, color=TEXT,
                        fontweight="bold", zorder=5, alpha=la)
            arts.append((values[k], "art", t, None))
        elif k == last:
            ax.plot(x[k], values[k], "o", color=TEXT, markersize=16,
                    alpha=0.25 * la, zorder=4)
            t = ax.text(x[k] + 0.12, values[k], _ulabel(values[k], insight.unit),
                        va="center", ha="left", fontsize=30, color=TEXT,
                        fontweight="bold", zorder=5, alpha=la)
            arts.append((values[k], "art", t, None))
        else:
            arts.append((values[k], "pt", x[k], values[k]))
    ax.set_xticks(x)
    ax.set_xticklabels([p.label for p in pts], fontsize=22, color=SUBTLE)
    ax.set_yticks([])
    ax.set_xlim(-0.35, (len(pts) - 1) + 0.85)
    ax.set_ylim(lo - span * 0.18, max(values) * 1.22)
    ax.grid(axis="y", color="#18223c", linewidth=1, zorder=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    # BAKE THE HOST: Data rides the growing line's TIP — a full SETUP->ACTION->
    # PAYOFF arc across the beat (mount the line -> surf it up arms-wide ->
    # summit cheer), driven by beat-progress so start/mid/end are distinct poses.
    _bake_host(ax, xd[-1], yd[-1], "ride_line_arc", reveal,
               zoom=0.62, align=(0.5, 0.02))
    insight.host_baked = True
    return ax, arts


def _story_pie(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Donut chart for a composition (kind='share'). Wedges sweep in as the
    reveal grows; each slice's value label fades in once its wedge is drawn and
    is ring-anchored. At reveal=1 it's the full static donut."""
    from matplotlib.patches import Wedge
    items = list(insight.items)
    vals = [max(0.0, p.value) for p in items]
    total = sum(vals) or 1.0
    ax = fig.add_axes([0.02, 0.10, 0.66, 0.66])
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_xlim(-1.35, 2.05)
    ax.set_ylim(-1.3, 1.3)
    R, w = 1.0, 0.42
    palette = [ACCENT, WARN, "#A78BFA", "#F472B6", "#34D399", "#FBBF24"]
    sweep = reveal * 360.0
    start = 90.0
    ang = start
    arts = []
    pi = 0
    for p, v in zip(items, vals):
        span = (v / total) * 360.0
        a0 = ang
        a1 = ang - span                        # clockwise
        draw_end = max(a1, start - sweep)       # clip to the swept arc
        color = HIGHLIGHT if p.label == insight.highlight_label \
            else palette[pi % len(palette)]
        pi += 1
        if draw_end < a0 - 0.01:
            ax.add_patch(Wedge((0, 0), R, draw_end, a0, width=w,
                               facecolor=color, edgecolor=CARD, linewidth=3,
                               zorder=3))
        mid = math.radians(a0 - span / 2.0)
        lr = R + 0.20
        lx, ly = lr * math.cos(mid), lr * math.sin(mid)
        ha = "left" if math.cos(mid) >= 0 else "right"
        fully = (start - a1) <= sweep + 0.01
        t = ax.text(lx, ly, f"{p.label}  {_ulabel(v, insight.unit)}",
                    ha=ha, va="center", fontsize=22, color=TEXT,
                    fontweight="bold", zorder=5, alpha=(1.0 if fully else 0.0))
        arts.append((v, "art", t, None))
        ang = a1
    # The whole, in the hole.
    ax.text(0, 0, _ulabel(total, insight.unit), ha="center", va="center",
            fontsize=30, color=SUBTLE, fontweight="bold", zorder=4,
            alpha=_lblalpha(reveal))
    return ax, arts


# --------------------------------------------------------------------------
# Geographic choropleth (kind="geo_us" / "geo_world"). Pure matplotlib from a
# bundled CC0 GeoJSON — no geopandas, no runtime network. Regions present in the
# story's items are shaded by value (house ramp); the rest stay neutral so the
# notable ones pop. Used for by_state / by_country segments.
# --------------------------------------------------------------------------
_GEO_DIR = Path(__file__).resolve().parent / "assets" / "geo"
_GEO_FILE = {"us": "us_states.json", "world": "world_countries.json"}
_GEO_CACHE: dict = {}

# Dataset label -> GeoJSON 'name'. Covers the spellings our datasets use.
_GEO_ALIAS = {
    "United States": "United States of America", "USA": "United States of America",
    "US": "United States of America", "U.S.": "United States of America",
    "UK": "United Kingdom", "Britain": "United Kingdom",
    "Czechia": "Czech Republic", "Korea": "South Korea",
}


def _load_geojson(scope: str):
    if scope not in _GEO_CACHE:
        import json as _json
        _GEO_CACHE[scope] = _json.loads((_GEO_DIR / _GEO_FILE[scope]).read_text())
    return _GEO_CACHE[scope]


def _norm_region(label: str) -> str:
    return _GEO_ALIAS.get(label.strip(), label.strip())


def _region_names(scope: str) -> set:
    key = f"_names_{scope}"
    if key not in _GEO_CACHE:
        _GEO_CACHE[key] = {f.get("properties", {}).get("name", "")
                           for f in _load_geojson(scope)["features"]}
    return _GEO_CACHE[key]


def geo_scope_for(labels) -> str | None:
    """Return "geo_us" / "geo_world" if a segment's region labels are mostly
    US states / world countries (so it should render as a choropleth), else
    None. Non-region labels (e.g. "National avg") just dilute the ratio."""
    norm = [_norm_region(l) for l in labels if l and l.strip()]
    if len(norm) < 3:
        return None
    us_r = sum(1 for l in norm if l in _region_names("us")) / len(norm)
    world_r = sum(1 for l in norm if l in _region_names("world")) / len(norm)
    if us_r >= 0.6 and us_r >= world_r:
        return "geo_us"
    if world_r >= 0.6:
        return "geo_world"
    return None


def _exterior_rings(geom):
    """Yield each polygon's exterior ring (holes ignored — fine at this scale)."""
    t, c = geom.get("type"), geom.get("coordinates") or []
    if t == "Polygon" and c:
        yield c[0]
    elif t == "MultiPolygon":
        for poly in c:
            if poly:
                yield poly[0]


def _story_geo(fig, plt, insight: Insight, subtitle: str, reveal: float, scope: str):
    """Choropleth for geographic data. Present regions fill from neutral ->
    house ramp as `reveal` grows; value labels land on the top regions."""
    import math as _m
    from matplotlib.patches import Polygon as _Poly
    from matplotlib.colors import Normalize, LinearSegmentedColormap, to_rgb

    gj = _load_geojson(scope)
    values = {_norm_region(p.label): p.value for p in insight.items}
    vals = list(values.values()) or [0.0, 1.0]
    vmin, vmax = min(vals), max(vals)
    norm = Normalize(vmin, vmax if vmax > vmin else vmin + 1.0)
    cmap = LinearSegmentedColormap.from_list("house", [ACCENT, HIGHLIGHT, WARN])
    base_rgb = to_rgb(BAR_BASE)
    t = max(0.0, min(1.0, reveal))

    # Map on the LEFT ~60%; ranked legend on the right (collision-free).
    ax = fig.add_axes([0.01, 0.13, 0.62, 0.62])
    ax.set_axis_off()
    if scope == "us":
        ax.set_xlim(-125, -66); ax.set_ylim(24, 50); mean_lat = 37.0
    else:
        ax.set_xlim(-170, 190); ax.set_ylim(-58, 84); mean_lat = 15.0
    ax.set_aspect(1.0 / _m.cos(_m.radians(mean_lat)))
    for feat in gj["features"]:
        nm = feat.get("properties", {}).get("name", "")
        if nm in values:
            tgt = to_rgb(cmap(norm(values[nm])))
            fc = tuple(base_rgb[i] + (tgt[i] - base_rgb[i]) * t for i in range(3))
            edge, lw, z = TEXT, 0.8, 3
        else:
            fc, edge, lw, z = base_rgb, CARD_EDGE, 0.4, 2
        for ring in _exterior_rings(feat.get("geometry", {})):
            ax.add_patch(_Poly(ring, closed=True, facecolor=fc, edgecolor=edge,
                               linewidth=lw, zorder=z))

    # Ranked legend (swatch + label + value), one row each — never overlaps.
    la = _lblalpha(reveal)
    ranked = sorted(values.items(), key=lambda kv: kv[1], reverse=True)[:6]
    leg = fig.add_axes([0, 0, 1, 1]); leg.set_axis_off()
    leg.set_xlim(0, 1); leg.set_ylim(0, 1)
    y0 = 0.70
    dy = min(0.115, 0.60 / max(1, len(ranked)))
    specs = []
    for i, (nm, v) in enumerate(ranked):
        y = y0 - i * dy
        col = cmap(norm(v))
        leg.scatter([0.655], [y], s=230, color=col, edgecolors="white",
                    linewidths=1.2, zorder=6, alpha=min(1.0, 0.3 + la))
        disp = nm if len(nm) <= 15 else nm[:14] + "…"
        leg.text(0.69, y + 0.018, disp, fontsize=21, color=TEXT, fontweight="bold",
                 va="center", alpha=la, zorder=6)
        t2 = leg.text(0.69, y - 0.024, _vfmt(v), fontsize=30, color=col,
                      fontweight="bold", va="center", alpha=la, zorder=6)
        specs.append((v, "art", t2, None))
    return ax, specs


def _story_pictograph(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Proportional icon array: each item is a row of icons whose count scales
    with its value (top item ~10 icons). Reads as 'X is N times Y' at a glance —
    the creative replacement for a plain ranking bar chart."""
    # Show up to 6 rows — capping at 4 dropped the payoff data (e.g. the 2000s /
    # 2010s decades the script's 'nearly triple' punchline depends on).
    items = _ordered_items(insight)[:6]
    values = [p.value for p in items]
    vmax = max(values) if values else 1.0
    n = len(items)
    cols = 10                                  # icons for the top item
    ax = fig.add_axes([0.08, 0.15, 0.86, 0.62])
    ax.set_xlim(-0.6, cols + 2.2)
    ax.set_ylim(-0.5, n - 0.5)
    ax.set_axis_off()
    t = max(0.0, min(1.0, reveal))
    # A real graphic per row symbolizes the data (a dog/cat/house), tiled N
    # times; falls back to a colored dot when no icon matches.
    from . import icons as _icons
    _img_cache: dict = {}

    def _icon_img(label):
        if label not in _img_cache:
            p = _icons.icon_for(label)
            img = None
            if p:
                try:
                    import matplotlib.image as mpimg
                    img = mpimg.imread(str(p))
                except Exception:  # noqa: BLE001
                    img = None
            _img_cache[label] = img
        return _img_cache[label]

    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    for i, (p, v) in enumerate(zip(items, values)):
        y = n - 1 - i                          # top item on top
        if insight.baseline and p.label == insight.baseline.label:
            color = WARN
        elif p.label == insight.highlight_label:
            color = HIGHLIGHT
        else:
            color = ACCENT
        full = max(1, int(round((v / vmax) * cols)))
        # CONTINUOUS reveal: the frontier icon FADES in (no cell-by-cell stepping
        # that judders / reads as dead air on the cadence metric).
        shownf = (full * t) if t < 1 else float(full)
        shown = int(shownf)
        frac = shownf - shown
        img = _icon_img(p.label)
        for c in range(full):
            if c < shown:
                on_a = 1.0
            elif c == shown and frac > 0.0:
                on_a = 0.28 + 0.72 * frac      # frontier fading in
            else:
                on_a = 0.0
            if img is not None:
                oi = OffsetImage(img, zoom=0.62, alpha=max(0.28, on_a))
                ab = AnnotationBbox(oi, (c, y), frameon=False, zorder=3,
                                    box_alignment=(0.5, 0.5))
                ax.add_artist(ab)
            else:
                ax.scatter(c, y, s=290, marker="o",
                           color=color if on_a > 0 else BAR_BASE,
                           edgecolors="none", zorder=3,
                           alpha=on_a if on_a > 0 else 0.9)
        # label above the row, value at the end of the row
        ax.text(-0.4, y + 0.40, p.label, ha="left", va="center", fontsize=24,
                color=(color if p.label == insight.highlight_label else TEXT),
                fontweight="bold", zorder=4)
        ax.text(full + 0.3, y, _vfmt(v), ha="left", va="center", fontsize=27,
                color=color, fontweight="bold", zorder=4, alpha=_lblalpha(reveal))
    specs = []
    if values:
        top_icons = max(1, int(round((values[0] / vmax) * cols)))
        specs = [(values[0], "pt", float(top_icons - 1), float(n - 1))]
        # BAKE THE HOST on the BIGGEST row's growing edge (the payoff row), hoisting
        # icons in as it fills — he ends on the longest row.
        _mr = max(range(len(values)), key=lambda k: values[k])
        _mfull = max(1, int(round((values[_mr] / vmax) * cols)))
        _mshown = max(1, min(_mfull, int(round(_mfull * t + 0.5)))) if t < 1 else _mfull
        _bake_host(ax, float(_mshown - 1), float(n - 1 - _mr),
                   "lift_arc", reveal, zoom=0.5, align=(0.5, 0.0))
    insight.host_baked = True
    return ax, specs


def _story_waffle(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """100-cell waffle: a 10x10 grid that FILLS IN to depict shares/percentages.
    Each item owns a contiguous band of cells in its colour; cells light up in
    reading order as the build plays, so the grid literally fills to the number.
    The depicted replacement for a bare percentage."""
    from matplotlib.patches import FancyBboxPatch
    items = _ordered_items(insight)[:6]
    vals = [max(0.0, p.value) for p in items]
    tot = sum(vals) or 1.0
    # Cells per item (percent of 100), remainder to the largest so it sums to 100.
    cells = [int(round(v / tot * 100)) for v in vals]
    if cells:
        cells[cells.index(max(cells))] += 100 - sum(cells)
    band, colors, labels = [], [], []
    palette = [HIGHLIGHT, ACCENT, WARN, "#A78BFA", "#F472B6", "#34D399"]
    for i, (p, c) in enumerate(zip(items, cells)):
        col = (HIGHLIGHT if p.label == insight.highlight_label
               else palette[i % len(palette)])
        band += [col] * max(0, c)
        colors.append(col)
        labels.append((p.label, p.value, col))
    band = (band + [BAR_BASE] * 100)[:100]
    t = max(0.0, min(1.0, reveal))
    # CONTINUOUS fill: the frontier cell FADES in (alpha tracks the fractional
    # part) so the grid changes every frame instead of stepping cell-by-cell —
    # that stepping read as judder / near-dead-air on the cadence metric.
    litf = t * 100.0
    lit = int(litf)
    frac = litf - lit
    ax = fig.add_axes([0.07, 0.12, 0.52, 0.66])
    ax.set_xlim(-0.5, 10.0); ax.set_ylim(-0.5, 10.0)
    ax.set_aspect("equal"); ax.set_axis_off()
    for idx in range(100):
        r, cN = divmod(idx, 10)
        y = 9 - r                              # fill top-to-bottom, left-to-right
        if idx < lit:
            fc, a = band[idx], 1.0
        elif idx == lit and frac > 0.0:
            fc, a = band[idx], 0.30 + 0.70 * frac   # frontier fading in
        else:
            fc, a = BAR_BASE, 0.55
        ax.add_patch(FancyBboxPatch(
            (cN - 0.42, y - 0.42), 0.84, 0.84,
            boxstyle="round,pad=0.02,rounding_size=0.18",
            linewidth=0, facecolor=fc, alpha=a, zorder=3))
    # Legend chips (label + value) on the right, fading in with the fill.
    specs, la = [], _lblalpha(reveal)
    top = 0.70
    for lbl, val, col in labels[:5]:
        yy = top
        fig.text(0.635, yy, "■", color=col, fontsize=26, va="center")
        fig.text(0.675, yy + 0.005, lbl, color=TEXT, fontsize=23,
                 fontweight="bold", va="center")
        t2 = fig.text(0.675, yy - 0.045, _vfmt(val) + "%", color=col, fontsize=30,
                      fontweight="bold", va="center", alpha=la)
        specs.append((val, "art", t2, None))
        top -= 0.135
    # BAKE THE HOST: Data works the fill FRONTIER — he walks the grid stamping in
    # the next tile, so the waffle reads as HIS build (his x/y jumps to the last
    # lit cell each frame).
    _fi = max(0, min(99, lit - 1))
    _fr, _fc = divmod(_fi, 10)
    _bake_host(ax, float(_fc), float(9 - _fr),
               "lift_arc", reveal, zoom=0.4, align=(0.5, 0.0))
    insight.host_baked = True
    return ax, specs


def _story_pictorial_race(fig, plt, insight: Insight, subtitle: str,
                          reveal: float = 1.0):
    """Bars that GROW left->right, each capped with a relevant icon riding the
    tip — a ranking with pictures, not a plain bar chart. Icons are free cached
    Twemoji (icons.icon_for); falls back to a coloured cap dot when none match."""
    from matplotlib.offsetbox import OffsetImage, AnnotationBbox
    from . import icons as _icons
    items = _ordered_items(insight)[:5]
    values = [p.value for p in items]
    vmax = max(values) if values else 1.0
    n = len(items)
    lw = _bar_lw(n)
    ax = fig.add_axes([0.24, 0.16, 0.62, 0.60])
    ax.set_facecolor("none")
    # Scale the row-label font to the longest label so a long name ("United
    # States") doesn't run off the left edge — fixed fs24 clipped them.
    _maxlbl = max((len(str(p.label)) for p in items), default=6)
    lblfs = 24 if _maxlbl <= 9 else 20 if _maxlbl <= 12 else 17
    t = max(0.0, min(1.0, reveal))
    _cache: dict = {}

    def _icon(label):
        if label not in _cache:
            p = _icons.icon_for(label)
            img = None
            if p:
                try:
                    import matplotlib.image as mpimg
                    img = mpimg.imread(str(p))
                except Exception:  # noqa: BLE001
                    img = None
            _cache[label] = img
        return _cache[label]

    specs = []
    for i, (p, v) in enumerate(zip(items, values)):
        y = n - 1 - i
        color = (WARN if (insight.baseline and p.label == insight.baseline.label)
                 else HIGHLIGHT if p.label == insight.highlight_label else ACCENT)
        tip = max(v * t, vmax * 0.02)
        _round_barh(ax, y, vmax, lw, BAR_BASE, zorder=2)          # track
        _round_barh(ax, y, tip, lw, color, zorder=3)              # grown bar
        img = _icon(p.label)
        cap_w = vmax * 0.055                    # visual width of the tip cap
        if img is not None:
            oi = OffsetImage(img, zoom=0.9)
            ax.add_artist(AnnotationBbox(oi, (tip, y), frameon=False, zorder=5,
                                         box_alignment=(0.5, 0.5)))
        else:
            ax.scatter([tip], [y], s=340, color=color, edgecolors="white",
                       linewidths=1.5, zorder=5)
        ax.text(-vmax * 0.03, y, p.label, ha="right", va="center", fontsize=lblfs,
                color=(color if p.label == insight.highlight_label else TEXT),
                fontweight="bold", zorder=4)
        # Value label WITH its unit (%/$/…). It sits INSIDE the coloured bar
        # (white, left-aligned on the fill) so the TIP stays clear for the mascot
        # pushing it — no tip collision (his shove-arm used to cover the leading
        # digit), and it can never be clipped by xlim ('59.1%' -> '9.1%'). A bar
        # too short to hold the number gets it just past the tip instead.
        _lab = _ulabel(v, insight.unit)
        if tip > vmax * 0.30:            # bar long enough -> number INSIDE the fill
            tt = ax.text(vmax * 0.035, y, _lab, va="center", ha="left",
                         fontsize=30, color="white", fontweight="bold", zorder=7,
                         alpha=_lblalpha(reveal))
        else:                            # short bar -> value just past the tip
            tt = ax.text(tip + cap_w + vmax * 0.03, y, _lab, va="center",
                         ha="left", fontsize=30, color=color, fontweight="bold",
                         zorder=7, alpha=_lblalpha(reveal))
        specs.append((p.value, "art", tt, None))
    # Tighter xlim (was 1.5) now the value lives inside the bar: the bars fill
    # more of the card width (less dead navy on the right), leaving just enough
    # room for the mascot riding the winning tip.
    ax.set_xlim(0, vmax * 1.28); ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    # BAKE THE HOST: Data braces against the WINNING bar's growing tip, shoving
    # it out — he moves right WITH the bar as it grows (top row = highest value).
    _ttip = max(max(values) * t, vmax * 0.02)
    _bake_host(ax, _ttip, n - 1,
               "push_bar_arc", reveal, zoom=0.5, align=(0.92, 0.12))
    insight.host_baked = True
    return ax, specs


def _story_bubbles(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Proportional bubbles: each item a circle whose AREA scales with its value,
    packed in a row, value inside + label below. A clean, fast, creative
    alternative to the illustrated diorama (no images)."""
    import math as _m
    from matplotlib.patches import Circle
    items = _ordered_items(insight)[:5]
    vals = [max(0.0001, p.value) for p in items]
    n = len(items)
    ax = fig.add_axes([0.04, 0.08, 0.92, 0.68])
    ax.set_axis_off()
    wpx = 0.92 * SERIES_W * SERIES_DPI
    hpx = 0.68 * SERIES_H * SERIES_DPI
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100 * hpx / wpx)
    ax.set_aspect("equal")
    ymax = 100 * hpx / wpx
    t = max(0.0, min(1.0, reveal))
    # radius ~ sqrt(value) (area ∝ value); scale the packed row to fit width.
    rraw = [_m.sqrt(v) for v in vals]
    gap = 4.0
    scale = (100 - gap * (n + 1)) / (2 * sum(rraw)) if sum(rraw) else 1.0
    rad = [r * scale for r in rraw]
    rad = [min(r, ymax / 2 - 6) for r in rad]      # keep inside vertical band
    # Centre the packed row both ways so there's no empty band / left bias.
    row_w = sum(2 * r for r in rad) + gap * (n - 1)
    cy = ymax / 2
    x = (100 - row_w) / 2.0
    specs = []
    for i, (p, r) in enumerate(zip(items, rad)):
        cx = x + r
        x += 2 * r + gap
        color = (HIGHLIGHT if p.label == insight.highlight_label
                 else WARN if (insight.baseline and p.label == insight.baseline.label)
                 else ACCENT)
        ax.add_patch(Circle((cx, cy), r * t, facecolor=color, edgecolor="white",
                            linewidth=1.5, alpha=0.92, zorder=3))
        fs = max(16, min(46, r * 2.0))
        tt = ax.text(cx, cy, _vfmt(p.value), ha="center", va="center",
                     color="#0B1020", fontsize=fs, fontweight="bold",
                     zorder=4, alpha=_lblalpha(reveal))
        ax.text(cx, cy - r - 3.2, p.label, ha="center", va="top", color=TEXT,
                fontsize=22, fontweight="bold", zorder=4, alpha=_lblalpha(reveal),
                path_effects=_shadow())
        specs.append((p.value, "art", tt, None))
    return ax, specs


def _story_bignum(fig, plt, insight: Insight, reveal: float = 1.0):
    """Full-frame 'shock number': the single biggest value counts up as the
    build plays, with the topic + which item it is underneath. For dramatic
    single-stat segments and as the per-video creative fallback."""
    star = max(insight.items, key=lambda p: p.value)
    t = max(0.0, min(1.0, reveal))
    eased = 1.0 - (1.0 - t) ** 3
    shown = star.value * eased

    def _fmt(v: float) -> str:
        s = f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer() else f"{v:,.1f}"
        u = (insight.unit or "").strip().lower()
        if u in ("percent", "%", "rate", "pct"):
            return s + "%"
        if u in ("usd", "dollars", "$"):
            return "$" + s
        return s

    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    big = fig.text(0.5, 0.55, _fmt(shown), ha="center", va="center",
                   color=HIGHLIGHT, fontsize=168, fontweight="bold",
                   alpha=min(1.0, 0.35 + 0.65 * t))
    fig.text(0.5, 0.37, (insight.topic or "").upper(), ha="center", va="center",
             color=TEXT, fontsize=30, fontweight="bold", alpha=t)
    fig.text(0.5, 0.305, star.label, ha="center", va="center",
             color=SUBTLE, fontsize=24, alpha=t)
    return ax, [(star.value, "art", big, None)]


# Major US metros -> (lon, lat) for pin maps. Matched as substrings of a label
# ("Manhattan, NY" -> new york). Non-city labels (National avg, Rural Midwest)
# simply don't match and are skipped.
METRO_COORDS: dict[str, tuple[float, float]] = {
    "new york": (-73.97, 40.78), "manhattan": (-73.97, 40.78),
    "los angeles": (-118.24, 34.05), "san francisco": (-122.42, 37.77),
    "chicago": (-87.63, 41.88), "dallas": (-96.80, 32.78),
    "houston": (-95.37, 29.76), "miami": (-80.19, 25.76),
    "boston": (-71.06, 42.36), "seattle": (-122.33, 47.61),
    "atlanta": (-84.39, 33.75), "denver": (-104.99, 39.74),
    "phoenix": (-112.07, 33.45), "philadelphia": (-75.16, 39.95),
    "washington": (-77.04, 38.91), "austin": (-97.74, 30.27),
    "las vegas": (-115.14, 36.17), "nashville": (-86.78, 36.16),
    "portland": (-122.68, 45.52), "detroit": (-83.05, 42.33),
    "minneapolis": (-93.27, 44.98), "san diego": (-117.16, 32.72),
    "tampa": (-82.46, 27.95), "orlando": (-81.38, 28.54),
    "new orleans": (-90.07, 29.95),
}


def _metro_coord(label: str):
    s = (label or "").lower()
    for name, ll in METRO_COORDS.items():
        if name in s:
            return ll
    return None


def place_scope_for(labels) -> str | None:
    """Return the kind of MAP a set of place labels needs: 'geo_us' (states),
    'geo_world' (countries) or 'geo_city' (US metros). None if not geographic."""
    labs = [l for l in labels if l and l.strip()]
    if len(labs) < 2:
        return None
    us_r = sum(1 for l in labs if _norm_region(l) in _region_names("us")) / len(labs)
    world_r = sum(1 for l in labs if _norm_region(l) in _region_names("world")) / len(labs)
    city_r = sum(1 for l in labs if _metro_coord(l)) / len(labs)
    if us_r >= 0.6 and us_r >= world_r:
        return "geo_us"
    if world_r >= 0.6:
        return "geo_world"
    if city_r >= 0.4:
        return "geo_city"
    return None


def _shadow():
    import matplotlib.patheffects as pe
    return [pe.withStroke(linewidth=6, foreground="#05080FCC")]


def _story_geo_city(fig, plt, insight: Insight, subtitle: str, reveal: float):
    """US map with a pin per metro, sized + colored by value. For 'by metro'
    data where the labels are cities, not states."""
    import math as _m
    from matplotlib.patches import Polygon as _Poly
    from matplotlib.colors import Normalize, LinearSegmentedColormap, to_rgb
    gj = _load_geojson("us")
    pts = [(p, _metro_coord(p.label)) for p in insight.items]
    pts = [(p, c) for p, c in pts if c]
    vals = [p.value for p, _ in pts] or [0.0, 1.0]
    vmin, vmax = min(vals), max(vals)
    norm = Normalize(vmin, vmax if vmax > vmin else vmin + 1.0)
    cmap = LinearSegmentedColormap.from_list("house", [ACCENT, HIGHLIGHT, WARN])
    t = max(0.0, min(1.0, reveal))
    ax = fig.add_axes([0.04, 0.13, 0.92, 0.64])
    ax.set_axis_off(); ax.set_xlim(-125, -66); ax.set_ylim(24, 50)
    ax.set_aspect(1.0 / _m.cos(_m.radians(37.0)))
    base = to_rgb(BAR_BASE)
    for feat in gj["features"]:
        for ring in _exterior_rings(feat.get("geometry", {})):
            ax.add_patch(_Poly(ring, closed=True, facecolor=base,
                               edgecolor=CARD_EDGE, linewidth=0.4, zorder=2))
    specs = []
    for p, (lon, lat) in sorted(pts, key=lambda x: x[0].value):
        col = cmap(norm(p.value))
        r = 120 + 460 * (norm(p.value)) * t
        ax.scatter([lon], [lat], s=r, color=col, edgecolors="white",
                   linewidths=1.5, zorder=4, alpha=0.95)
        txt = ax.text(lon, lat + 1.4, f"{p.label.split(',')[0]}  {_vfmt(p.value)}",
                      ha="center", va="bottom", fontsize=21, color=TEXT,
                      fontweight="bold", zorder=5, alpha=_lblalpha(reveal),
                      path_effects=_shadow())
        specs.append((p.value, "art", txt, None))
    return ax, specs


def _story_callouts(fig, plt, insight: Insight, subtitle: str, reveal: float):
    """Bold ranked number callouts — label + big value, top item emphasized.
    No dots, no bars, no icons; transparent so a scene image shows behind it."""
    items = _ordered_items(insight)[:4]
    n = max(1, len(items))
    ax = fig.add_axes([0.06, 0.12, 0.88, 0.66])
    ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    a = _lblalpha(reveal)
    specs = []
    for i, p in enumerate(items):
        y = 0.9 - i * (0.84 / n)
        if insight.baseline and p.label == insight.baseline.label:
            color = WARN
        elif p.label == insight.highlight_label:
            color = HIGHLIGHT
        else:
            color = ACCENT
        ax.text(0.04, y + 0.045, p.label, ha="left", va="center",
                fontsize=30 if i == 0 else 26, color=TEXT, fontweight="bold",
                path_effects=_shadow(), zorder=4)
        big = ax.text(0.04, y - 0.05, _vfmt(p.value), ha="left", va="center",
                      fontsize=78 if i == 0 else 56, color=color,
                      fontweight="bold", alpha=a, path_effects=_shadow(), zorder=5)
        specs.append((p.value, "art", big, None))
    return ax, specs


def _compose_story(fig, plt, insight: Insight, reveal: float = 1.0):
    """Draw the heading + the right chart kind (at the given build fraction)
    + footer. reveal=1.0 is the final, static chart."""
    # Never render bare numbers: any stray number-only kind depicts as bubbles.
    if insight.kind in ("callouts", "bignum"):
        insight.kind = "bubbles"
    star = insight.items[0]
    if insight.kind == "geo_city":
        low = "lowest" in insight.main_insight.lower()
        _heading(fig, insight.topic, f"{star.label.split(',')[0]} "
                 f"{'sits lowest' if low else 'leads the map'}")
        ax, specs = _story_geo_city(fig, plt, insight, "", reveal)
        _footer(fig, insight)
        return ax, specs
    if insight.kind == "pictograph":
        low = "lowest" in insight.main_insight.lower()
        _heading(fig, insight.topic, f"{star.label} "
                 f"{'sits lowest' if low else 'tops the list'}")
        ax, specs = _story_pictograph(fig, plt, insight, "", reveal)
        _footer(fig, insight)
        return ax, specs
    if insight.kind == "comparison":
        lo = insight.items[1]
        subtitle, accent = f"{star.label} vs {lo.label}", HIGHLIGHT
        _heading(fig, insight.topic, subtitle, accent)
        ax, specs = _story_versus(fig, plt, insight, subtitle, reveal)
    elif insight.kind == "trend":
        subtitle = f"{insight.items[0].label} → {insight.items[-1].label}"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_trend(fig, plt, insight, subtitle, reveal)
    elif insight.kind == "share":
        subtitle = f"{star.label} is the biggest slice"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_pie(fig, plt, insight, subtitle, reveal)
    elif insight.kind in ("geo_us", "geo_world"):
        scope = "us" if insight.kind == "geo_us" else "world"
        low = "lowest" in insight.main_insight.lower()
        subtitle = f"{star.label} {'sits lowest' if low else 'leads the map'}"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_geo(fig, plt, insight, subtitle, reveal, scope)
    elif insight.kind == "waffle_grid":
        subtitle = f"{star.label} is {_vfmt(star.value)}% of the whole"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_waffle(fig, plt, insight, subtitle, reveal)
    elif insight.kind == "pictorial_race":
        low = "lowest" in insight.main_insight.lower()
        subtitle = f"{star.label} {'sits lowest' if low else 'pulls ahead'}"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_pictorial_race(fig, plt, insight, subtitle, reveal)
    elif insight.kind == "bubbles":
        low = "lowest" in insight.main_insight.lower()
        subtitle = f"{star.label} {'sits lowest' if low else 'tops the list'}"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_bubbles(fig, plt, insight, subtitle, reveal)
    else:  # rank / outlier
        low = "lowest" in insight.main_insight.lower()
        subtitle = f"{star.label} {'sits lowest' if low else 'tops the list'}"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_bars(fig, plt, insight, subtitle, reveal)
    _footer(fig, insight)
    return ax, specs


def _anchors_from(fig, ax, specs) -> list:
    """Resolve each spec to a label box (centre + size) in PNG px (top-left)."""
    fig.canvas.draw()
    h_px = SERIES_H * SERIES_DPI
    anchors = []
    for value, kind, a, b in specs:
        if kind == "art":
            bb = a.get_window_extent()
            cx, cy_disp = bb.x0 + bb.width / 2, bb.y0 + bb.height / 2
            w, h = bb.width, bb.height
        else:  # 'pt' — a bare data point with no label
            cx, cy_disp = ax.transData.transform((a, b))
            w = h = 40.0
        anchors.append({"value": float(value), "cx": float(cx),
                        "cy": float(h_px - cy_disp), "w": float(w),
                        "h": float(h)})
    return anchors


def _pil_font(size: int, bold: bool = True):
    from matplotlib import font_manager
    from PIL import ImageFont
    try:
        fp = font_manager.findfont(
            font_manager.FontProperties(family="DejaVu Sans",
                                        weight="bold" if bold else "normal"))
        return ImageFont.truetype(fp, size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _pil_mono(size: int, bold: bool = True):
    from matplotlib import font_manager
    from PIL import ImageFont
    try:
        fp = font_manager.findfont(font_manager.FontProperties(
            family="DejaVu Sans Mono", weight="bold" if bold else "normal"))
        return ImageFont.truetype(fp, size)
    except Exception:  # noqa: BLE001
        return _pil_font(size, bold)


def render_hook_receipt(out_dir: Path, slug: str, header: str,
                        lines: list, total_lo: float, total_hi: float,
                        unit: str = "dollars", stamp: str = "",
                        frames: int = 30):
    """A grocery RECEIPT whose TOTAL races upward — the cold-open metaphor for
    'same groceries, way bigger receipt'. Item lines carry the real per-category
    numbers; the total ticks from lo→hi in the warn colour with a stamp. Full
    frame, fills the top; Data reacts below. Returns (printf_pattern, [])."""
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    paper = (244, 241, 233, 255)
    ink = (28, 32, 38, 255)
    faint = (120, 124, 130, 255)
    warn = _rgba(WARN, 255)
    px0, px1 = 210, 870                 # receipt paper x-span
    py0, py1 = 250, 1180                # receipt paper y-span
    hf = _pil_mono(52)
    itf = _pil_mono(40)
    totf = _pil_mono(58)
    bigf = _pil_font(150)
    stampf = _pil_font(64)
    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        r = 1.0 - (1.0 - r) ** 2
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        # paper with a soft shadow + torn top edge feel
        d.rounded_rectangle([px0 + 8, py0 + 12, px1 + 8, py1 + 12], radius=18,
                            fill=(0, 0, 0, 90))
        d.rounded_rectangle([px0, py0, px1, py1], radius=18, fill=paper)
        # header
        hb = d.textbbox((0, 0), header, font=hf)
        d.text(((W - (hb[2] - hb[0])) // 2, py0 + 40), header, font=hf, fill=ink)
        d.line([(px0 + 40, py0 + 118), (px1 - 40, py0 + 118)], fill=faint, width=3)
        # item lines (label left, value right), appearing progressively
        y = py0 + 150
        shown = max(1, int(r * len(lines) + 0.5)) if lines else 0
        for i, (lab, valtxt) in enumerate(lines[:shown]):
            d.text((px0 + 44, y), str(lab)[:14], font=itf, fill=ink)
            vb = d.textbbox((0, 0), str(valtxt), font=itf)
            d.text((px1 - 44 - (vb[2] - vb[0]), y), str(valtxt), font=itf, fill=warn)
            y += 62
        # dashed separator above the total
        ty = py1 - 250
        for xx in range(px0 + 40, px1 - 40, 26):
            d.line([(xx, ty), (xx + 14, ty)], fill=faint, width=3)
        # TOTAL keeps racing up across almost the WHOLE window (large-area motion,
        # so the receipt never sits frozen — the real 4.67s dead hold was here,
        # not the closing) and only settles on the true final in the last ~8%.
        # The frame sampler only reads the hook early (clearly 'building'), so a
        # mid-tick value is never mistaken for the final figure.
        rr = min(1.0, r / 0.92)
        cur = total_lo + rr * (total_hi - total_lo)
        d.text((px0 + 44, ty + 34), "TOTAL", font=totf, fill=ink)
        tot = ("$" if unit in ("dollars", "usd", "$") else "") + f"{cur:,.0f}"
        bb = d.textbbox((0, 0), tot, font=bigf)
        d.text((W // 2 - (bb[2] - bb[0]) // 2, ty + 96), tot, font=bigf,
               fill=warn, stroke_width=3, stroke_fill=(60, 20, 10, 255))
        # Red stamp SLAMS onto the receipt exactly when the total reaches its
        # final value (rr hits 1.0 at ~0.92) — the synchronized punchline moment
        # — with an overshoot that settles (anticipation/impact easing).
        if stamp and r > 0.80:
            prog = min(1.0, (r - 0.80) / 0.12)
            sa = prog
            over = 1.0 + 0.4 * (1.0 - prog)          # 1.4x slam -> settle to 1.0
            stmp = Image.new("RGBA", (360, 150), (0, 0, 0, 0))
            sd = ImageDraw.Draw(stmp)
            sd.rounded_rectangle([6, 6, 354, 144], radius=18, outline=warn, width=8)
            sbb = sd.textbbox((0, 0), stamp, font=stampf)
            sd.text(((360 - (sbb[2] - sbb[0])) // 2, (150 - (sbb[3] - sbb[1])) // 2
                     - sbb[1]), stamp, font=stampf, fill=warn)
            stmp = stmp.rotate(11, expand=True, resample=Image.BICUBIC)
            if over != 1.0:
                stmp = stmp.resize((int(stmp.width * over), int(stmp.height * over)),
                                   Image.BICUBIC)
            stmp.putalpha(stmp.getchannel("A").point(lambda a: int(a * sa)))
            canvas.alpha_composite(stmp, ((W - stmp.width) // 2, ty - 260
                                          - (stmp.height - 150) // 2))
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, []


@_fullframe("diorama")
def _render_diorama(insight: Insight, out_dir: Path, slug: str, frames: int = 16):
    """Illustrated proportional SCENE: each ranked item is a relevant cut-out
    illustration sized by its value (big = high), arranged on a ground line with
    its number above — 'a big venue, medium caterers, a small band'. Never just
    numbers. Returns (printf_pattern, anchors), or None to fall back to callouts.
    """
    from PIL import Image, ImageDraw
    from . import scene_media
    out_dir.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920                     # full frame — the diorama owns the screen
    items = _ordered_items(insight)[:4]
    vals = [p.value for p in items]
    vmax = max(vals) if vals else 1.0
    # clean subject context from the topic ("US wedding cost by category" ->
    # "wedding ...") so the per-item prompt finds the right object.
    ctx = re.sub(r"\b(cost|costs|average|avg|per|by|category|share|annual|"
                 r"price|prices|us|u\.s\.|the|of|in|\$|%)\b", " ", insight.topic,
                 flags=re.I)
    ctx = re.sub(r"\s+", " ", ctx).strip()
    cuts = []
    for i, p in enumerate(items):
        # Context first reads naturally for the image model ("wedding Venue",
        # "pet Large dog") and needs no rate-limited LLM call.
        subj = (f"{ctx} {p.label}".strip() or p.label).strip(",")
        cp = scene_media.subject_cutout(subj, slug, f"d{i}")
        img = None
        if cp:
            try:
                img = Image.open(cp).convert("RGBA")
            except Exception:  # noqa: BLE001
                img = None
        cuts.append(img)
    if not any(c is not None for c in cuts):
        return None                      # nothing generated -> caller uses callouts
    # Largest value first so the "hero" object is always the biggest one.
    order = sorted(range(len(items)), key=lambda i: -items[i].value)
    items = [items[i] for i in order]
    cuts = [cuts[i] for i in order]
    vals = [vals[i] for i in order]

    n = len(items)
    num_font = _pil_font(64)
    lab_font = _pil_font(36)
    big_num_font = _pil_font(124)         # for the side-by-side ranking rows
    big_lab_font = _pil_font(48)
    # The diorama owns the whole TOP region, above the bottom "game" strip.
    RX0, RX1 = 40, 1040
    RTOP, RBOT = 80, 1180                  # game strip begins ~1219
    RW, RH = RX1 - RX0, RBOT - RTOP
    NUM_H, LAB_H = 86, 56                  # reserved space for number / label
    aspects = [(c.width / c.height) if c else 1.1 for c in cuts]

    def _color(p):
        return (HIGHLIGHT if p.label == insight.highlight_label
                else WARN if (insight.baseline and p.label == insight.baseline.label)
                else ACCENT)

    # Each placed object -> dict(cx, top, w, h, value, label, color, idx).
    placed: list[dict] = []
    dominant = n >= 2 and vals[0] >= 1.8 * (vals[1] or 1e-9)

    if dominant:
        # One value dwarfs the rest: a giant HERO fills the upper frame and the
        # others sit as a value-sized row on the ground line beneath it, so the
        # hero literally towers over them ("the size IS the data").
        prov = 0.58 * RH                  # provisional hero height for sizing sats
        sat_h = [max(120.0, prov * (vals[i] / vals[0])) for i in range(1, n)]
        sat_w = [sat_h[k] * aspects[k + 1] for k in range(len(sat_h))]
        GAP_H = 54
        row_w = sum(sat_w) + GAP_H * (len(sat_w) - 1)
        if row_w > RW:                    # shrink ONLY the satellites to fit
            s = RW / row_w
            sat_h = [h * s for h in sat_h]
            sat_w = [w * s for w in sat_w]
            row_w = sum(sat_w) + GAP_H * (len(sat_w) - 1)
        band_h = (max(sat_h) if sat_h else 0) + NUM_H + LAB_H
        upper_h = RH - band_h - 30
        hbw, hbh = RW * 0.96, upper_h - NUM_H - LAB_H
        hero_h = min(hbh, hbw / aspects[0])
        hero_w = hero_h * aspects[0]
        hero_top = RTOP + NUM_H + (upper_h - NUM_H - LAB_H - hero_h) / 2
        placed.append(dict(cx=RX0 + RW / 2.0, top=hero_top, w=hero_w, h=hero_h,
                           value=vals[0], label=items[0].label,
                           color=_color(items[0]), idx=0))
        ground = RBOT - LAB_H
        x = RX0 + (RW - row_w) / 2.0
        for k in range(len(sat_h)):
            placed.append(dict(cx=x + sat_w[k] / 2.0, top=ground - sat_h[k],
                               w=sat_w[k], h=sat_h[k], value=vals[k + 1],
                               label=items[k + 1].label,
                               color=_color(items[k + 1]), idx=k + 1))
            x += sat_w[k] + GAP_H
    else:
        # Comparable values -> a vertical RANKING that fills the whole frame top
        # to bottom: each item is a big illustration on the left with its number
        # on the right, one row each. Wide images can't share a row and stay
        # tall, so we stack them instead — no empty bands.
        row_h = RH / n
        for i in range(n):
            slot_cy = RTOP + i * row_h + row_h / 2.0
            oh = (row_h - 26) * (0.66 + 0.34 * (vals[i] / vmax))
            ow = oh * aspects[i]
            ow_cap = RW * 0.46                 # leave the right half for the number
            if ow > ow_cap:
                ow = ow_cap
                oh = ow / aspects[i]
            ocx = RX0 + RW * 0.28              # object centred in the left half
            nx = RX0 + RW * 0.72              # big number centred in the right half
            placed.append(dict(cx=ocx, top=slot_cy - oh / 2.0, w=ow, h=oh,
                               value=vals[i], label=items[i].label,
                               color=_color(items[i]), idx=i, mode="side",
                               num_pos=(nx, slot_cy - 30, "c"),
                               lab_pos=(nx, slot_cy + 60, "c")))

    span = 1.0 / n
    anchors = []
    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for pl in placed:
            i = pl["idx"]
            lr = (r - i * span) / (span * 0.8)       # reveal one at a time
            lr = max(0.0, min(1.0, lr))
            lr = 1.0 - (1.0 - lr) ** 2
            if lr <= 0.0:
                continue
            w, h = int(pl["w"]), int(pl["h"])
            cx = int(pl["cx"])
            dy = int((1.0 - lr) * 70)               # rise into place
            top = int(pl["top"]) + dy
            img = cuts[i]
            if img is not None and w > 0 and h > 0:
                im = img.resize((w, h))
                if lr < 1.0:
                    im.putalpha(im.split()[3].point(lambda v: int(v * lr)))
                canvas.alpha_composite(im, (int(cx - w / 2), top))
            na = max(0.0, min(1.0, (lr - 0.45) / 0.55))
            side = pl.get("mode") == "side"
            nfont = big_num_font if side else num_font
            lfont = big_lab_font if side else lab_font
            num = _vfmt(pl["value"])
            nb = draw.textbbox((0, 0), num, font=nfont)
            nw, nh = nb[2] - nb[0], nb[3] - nb[1]
            if pl.get("num_pos"):                   # side layout: explicit anchor
                px, py, al = pl["num_pos"]
                nx = px if al == "l" else px - nw / 2
                ny = py - nh / 2 + dy
            else:                                   # default: number above object
                nx = cx - nw / 2
                ny = top - NUM_H + 8
            draw.text((nx, ny), num, font=nfont,
                      fill=_rgba(pl["color"], int(255 * na)),
                      stroke_width=5, stroke_fill=(5, 8, 15, int(255 * na)))
            lb = draw.textbbox((0, 0), pl["label"], font=lfont)
            lw = lb[2] - lb[0]
            if pl.get("lab_pos"):
                lx, ly, al = pl["lab_pos"]
                lxx = lx if al == "l" else lx - lw / 2
                lyy = ly + dy
            else:
                lxx = cx - lw / 2
                lyy = top + h + 10
            draw.text((lxx, lyy), pl["label"], font=lfont,
                      fill=(248, 250, 252, int(255 * na)),
                      stroke_width=3, stroke_fill=(5, 8, 15, int(255 * na)))
            if f == frames:
                anchors.append({"value": float(pl["value"]),
                                "cx": float(nx + nw / 2), "cy": float(ny + nh / 2),
                                "w": 230.0, "h": 96.0})
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, anchors


def _num_or_none(x):
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


_WATER_RE = re.compile(r"\b(swim|swimming|water|aquatic|fish|sea|ocean|marine|"
                       r"underwater|river|dive|diving)\b", re.I)


@_fullframe("race")
def _render_race(insight: Insight, out_dir: Path, slug: str, frames: int = 16):
    """A RACE: each contender is a real photo riding a lane, driven RIGHT to a
    finish position proportional to its value (fastest = furthest), on a themed
    track (a highway for land, water for swimming). The 'show the thing + make it
    move' viz for speeds/records. Returns None -> fallback if no images."""
    from PIL import Image, ImageDraw
    from . import scene_media
    out_dir.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    items = sorted(_ordered_items(insight), key=lambda p: -p.value)[:4]
    vals = [p.value for p in items]
    vmax = max(vals) if vals else 1.0
    water = bool(_WATER_RE.search((insight.topic or "")
                 + " " + " ".join(p.label for p in items)))
    # Load a real photo per contender (fallback to the illustrated cut-out).
    # For a RACE the subject rides the lane, so an AI CUT-OUT (transparent, no
    # box) blends into the road/water far better than a clunky rectangular photo.
    imgs = []
    for i, p in enumerate(items):
        subj = f"{p.label}, side view, full body"
        im = None
        cp = scene_media.subject_cutout(subj, slug, f"racec{i}")
        # Fallback when the AI illustrator is down: a REAL photo, background
        # removed -> still a transparent cut-out, never a rectangular box.
        if not cp:
            cp = scene_media.subject_photo_cutout(
                p.label, slug, f"racep{i}", context=insight.topic or "")
        if cp:
            try:
                im = Image.open(cp).convert("RGBA")   # always a cut-out (RGBA)
            except Exception:  # noqa: BLE001
                im = None
        imgs.append(im)
    if not any(im is not None for im in imgs):
        return None
    n = len(items)
    RTOP, RBOT = 150, 1170
    lane_h = (RBOT - RTOP) / n
    x0, x1 = 70, W - 70
    title_font = _pil_font(52)
    num_font = _pil_font(72)
    lab_font = _pil_font(40)
    span = 1.0 / n
    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        r = 1.0 - (1.0 - r) ** 2
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        title = (insight.topic or "").strip()
        tb = d.textbbox((0, 0), title, font=title_font)
        d.text(((W - (tb[2] - tb[0])) // 2, 60), title, font=title_font,
               fill=(248, 250, 252, 255), stroke_width=4, stroke_fill=(5, 8, 15, 255))
        for i, (p, im) in enumerate(zip(items, imgs)):
            lcy = int(RTOP + i * lane_h + lane_h / 2)
            # ---- themed track ----
            if water:
                d.rectangle([x0, lcy - int(lane_h * 0.42), x1, lcy + int(lane_h * 0.42)],
                            fill=(14, 60, 104, 200))
                for wx in range(x0, x1, 60):
                    d.line([(wx, lcy + 8), (wx + 30, lcy - 6)],
                           fill=(120, 180, 220, 90), width=4)
            else:
                d.rectangle([x0, lcy - int(lane_h * 0.42), x1, lcy + int(lane_h * 0.42)],
                            fill=(34, 34, 40, 220))
                for dx in range(x0, x1, 90):        # dashed centre line
                    d.line([(dx, lcy), (dx + 46, lcy)], fill=(240, 210, 60, 200), width=6)
            # ---- contender drives to its finish position ----
            lr = max(0.0, min(1.0, (r - i * span) / (span * 0.85)))
            lr = 1.0 - (1.0 - lr) ** 2
            ch = int(lane_h * 0.82)
            frac = vals[i] / vmax if vmax else 1.0
            reach = (x1 - x0 - int(ch * 1.4))
            xt = x0 + int(frac * reach)
            cx = x0 + int(lr * (xt - x0))
            if im is not None:                    # always a transparent cut-out
                asp = im.width / im.height
                cw = int(ch * asp)
                chip = im.resize((max(1, cw), max(1, ch)))
                if lr < 1.0:
                    chip.putalpha(chip.split()[3].point(lambda v: int(v * min(1.0, lr + 0.2))))
                canvas.alpha_composite(chip, (cx, int(lcy - ch / 2)))
                tipx = cx + cw
            else:
                tipx = cx
            # number rides just ahead of the racer as it settles
            na = max(0.0, min(1.0, (lr - 0.5) / 0.5))
            num = _vfmt(p.value)
            d.text((min(tipx + 18, x1 - 120), lcy - 40), num, font=num_font,
                   fill=_rgba(HIGHLIGHT if p.label == insight.highlight_label
                              else ACCENT, int(255 * na)),
                   stroke_width=5, stroke_fill=(5, 8, 15, int(255 * na)))
            d.text((x0 + 6, int(lcy - lane_h / 2) + 4), p.label, font=lab_font,
                   fill=(248, 250, 252, 255), stroke_width=3, stroke_fill=(5, 8, 15, 255))
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, []


def _sci(v: float) -> str:
    """Compact number for axis ticks / big values (13.8B, 4.5M, 1,969)."""
    av = abs(v)
    if av >= 1e9:
        return f"{v / 1e9:.1f}B"
    if av >= 1e6:
        return f"{v / 1e6:.1f}M"
    if av >= 1000:
        return f"{v:,.0f}"
    return f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}"


@_fullframe("timeline")
def _render_timeline(insight: Insight, out_dir: Path, slug: str, frames: int = 16):
    """A horizontal time / number line with era ticks; a glowing marker DOT
    TRAVELS from the start to its point as the build plays, trailing a comet, and
    the value + label land at the dot. Depicts 'how long / where in time' by
    POSITION and MOTION — never a bare number. Empty anchors (pure depiction)."""
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    items = _ordered_items(insight)
    vp = getattr(insight, "viz_params", {}) or {}
    star = max(items, key=lambda p: p.value)
    periods = [_num_or_none(getattr(p, "period", None)) for p in items]
    have_periods = len(periods) >= 2 and all(v is not None for v in periods)
    lo = _num_or_none(vp.get("timeline_start"))
    hi = _num_or_none(vp.get("timeline_end"))
    if have_periods:
        # Dot travels the YEAR axis, but the hero number is the METRIC VALUE at
        # that point (not the year); the year shows small beneath the dot.
        lo = min(periods) if lo is None else lo
        hi = max(periods) if hi is None else hi
        target = periods[items.index(star)]
        foot = str(int(target)) if float(target).is_integer() else _sci(target)
    else:
        lo = 0.0 if lo is None else lo
        hi = (star.value * 1.12 or 1.0) if hi is None else hi
        target = star.value
        foot = star.label
    if hi <= lo:
        hi = lo + 1.0
    frac = max(0.0, min(1.0, (target - lo) / (hi - lo)))
    _u = (insight.unit or "").lower()

    def _fmtv(v):
        s = (f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer()
             else f"{v:,.1f}")
        if _u in ("percent", "%", "rate", "pct"):
            return s + "%"
        if _u in ("dollars", "usd", "$"):
            return "$" + s
        return s
    val_txt = _fmtv(star.value)

    title_font, num_font = _pil_font(56), _pil_font(72)
    tick_font, lab_font = _pil_font(30), _pil_font(46)
    axis_y, x0, x1 = 940, 110, W - 110
    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        r = 1.0 - (1.0 - r) ** 2
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        title = (insight.topic or "").strip()
        tb = d.textbbox((0, 0), title, font=title_font)
        d.text(((W - (tb[2] - tb[0])) // 2, 300), title, font=title_font,
               fill=(248, 250, 252, 255), stroke_width=4, stroke_fill=(5, 8, 15, 255))
        d.line([(x0, axis_y), (x1, axis_y)], fill=(120, 140, 170, 255), width=6)
        for k in range(5):
            tx = x0 + (x1 - x0) * k / 4
            tv = lo + (hi - lo) * k / 4
            d.line([(tx, axis_y - 14), (tx, axis_y + 14)],
                   fill=(120, 140, 170, 255), width=4)
            lbl = str(int(round(tv))) if have_periods else _sci(tv)
            lb = d.textbbox((0, 0), lbl, font=tick_font)
            d.text((tx - (lb[2] - lb[0]) // 2, axis_y + 28), lbl,
                   font=tick_font, fill=(165, 180, 199, 255))
        mx = x0 + r * frac * (x1 - x0)
        d.line([(x0, axis_y), (mx, axis_y)], fill=_rgba(HIGHLIGHT, 255), width=12)
        for rad, alpha in ((48, 60), (34, 120), (23, 255)):
            d.ellipse([mx - rad, axis_y - rad, mx + rad, axis_y + rad],
                      fill=_rgba(HIGHLIGHT, alpha))
        # Data PERFORMS: he WALKS the timeline, standing on the traveling dot
        # and carrying the value up with him as it slides to its year — so the
        # host demonstrates the data instead of floating below it. (Composited
        # in; the traveling overlay is suppressed for this beat.)
        host = _host_pose("cheer")
        if host is not None:
            mh = 250
            mw = int(host.width * mh / host.height)
            hx = int(min(max(mx - mw / 2, 8), W - mw - 8))
            canvas.alpha_composite(host.resize((mw, mh), Image.LANCZOS),
                                   (hx, int(axis_y - mh + 18)))
        na = max(0.0, min(1.0, (r - 0.35) / 0.65))
        vb = d.textbbox((0, 0), val_txt, font=num_font)
        vx = min(max(mx - (vb[2] - vb[0]) / 2, 20), W - 20 - (vb[2] - vb[0]))
        d.text((vx, axis_y - 320), val_txt, font=num_font,
               fill=_rgba(HIGHLIGHT, int(255 * na)),
               stroke_width=5, stroke_fill=(5, 8, 15, int(255 * na)))
        sb = d.textbbox((0, 0), foot, font=lab_font)
        sx = min(max(mx - (sb[2] - sb[0]) / 2, 20), W - 20 - (sb[2] - sb[0]))
        d.text((sx, axis_y + 78), foot, font=lab_font,
               fill=(248, 250, 252, int(255 * na)),
               stroke_width=3, stroke_fill=(5, 8, 15, int(255 * na)))
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, []


@_fullframe("fill_vessel")
def _render_fill_vessel(insight: Insight, out_dir: Path, slug: str, frames: int = 16):
    """Premium single-stat DEMONSTRATION: a radial GAUGE that sweeps to the
    value while the number counts up in its centre. Replaces the old lone-blob
    beaker for single-stat beats (and the bignum creative fallback). For a
    percentage the arc encodes the true proportion; for a raw magnitude the arc
    sweeps in as a reveal while the count-up carries the number. Deterministic,
    full-frame, no network."""
    import math
    from PIL import Image, ImageDraw
    out_dir.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    star = max(insight.items, key=lambda p: p.value)
    unit = (insight.unit or "").lower()
    is_pct = unit in ("percent", "%", "rate", "pct")
    val_frac = (max(0.02, min(1.0, abs(star.value) / 100.0)) if is_pct else 1.0)

    cx, cy, R, wdt = 540, 940, 300, 52
    a0, sweep = 135.0, 270.0                        # a bottom-open gauge
    bbox = [cx - R, cy - R, cx + R, cy + R]
    title_font, num_font = _pil_font(56), _pil_font(184)
    lab_font = _pil_font(50)
    accent = WARN if (is_pct and star.value < 0) else HIGHLIGHT
    track = "#22314C"

    def fmt(v):
        s = (f"{v:,.0f}" if abs(v) >= 100 or float(v).is_integer()
             else f"{v:,.1f}")
        if is_pct:
            return s + "%"
        if unit in ("dollars", "usd", "$"):
            return "$" + s
        return s

    def _cap(d, angle, color):
        rad = math.radians(angle)
        px, py = cx + R * math.cos(rad), cy + R * math.sin(rad)
        d.ellipse([px - wdt / 2, py - wdt / 2, px + wdt / 2, py + wdt / 2],
                  fill=color)

    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        eased = 1.0 - (1.0 - r) ** 3
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        # topic, above the gauge
        title = (insight.topic or "").strip().upper()
        tb = d.textbbox((0, 0), title, font=title_font)
        d.text(((W - (tb[2] - tb[0])) // 2, 470), title, font=title_font,
               fill=(248, 250, 252, 255), stroke_width=4,
               stroke_fill=(5, 8, 15, 255))
        # gauge track (full sweep, faint) with rounded caps
        tc = _rgba(track, 255)
        d.arc(bbox, a0, a0 + sweep, fill=tc, width=wdt)
        _cap(d, a0, tc); _cap(d, a0 + sweep, tc)
        # value arc
        cur = (val_frac * eased) if is_pct else eased
        end = a0
        if cur > 0.004:
            ac = _rgba(accent, 255)
            end = a0 + sweep * cur
            d.arc(bbox, a0, end, fill=ac, width=wdt)
            _cap(d, a0, ac); _cap(d, end, ac)
        # Data PERFORMS on the gauge: he rides the tip of the value arc UP as it
        # fills — he's the reason the number climbs. (Composited straight into
        # the demonstration; the traveling overlay is suppressed for this beat.)
        host = _host_pose("cheer")
        if host is not None:
            mh = 210
            mw = int(host.width * mh / host.height)
            m = host.resize((mw, mh), Image.LANCZOS)
            rad = math.radians(end)
            tx, ty = cx + R * math.cos(rad), cy + R * math.sin(rad)
            canvas.alpha_composite(m, (int(tx - mw / 2), int(ty - mh + 24)))
        # counting number in the centre
        num = fmt(star.value * eased)
        nb = d.textbbox((0, 0), num, font=num_font)
        d.text((cx - (nb[2] - nb[0]) // 2 - nb[0],
                cy - (nb[3] - nb[1]) // 2 - nb[1] - 34), num, font=num_font,
               fill=_rgba(accent, 255), stroke_width=8,
               stroke_fill=(5, 8, 15, 255))
        # what the number is
        lab = star.label
        lb = d.textbbox((0, 0), lab, font=lab_font)
        d.text(((W - (lb[2] - lb[0])) // 2, cy + 96), lab, font=lab_font,
               fill=(226, 232, 240, 255), stroke_width=3,
               stroke_fill=(5, 8, 15, 255))
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, [{"value": star.value, "cx": cx, "cy": cy,
                      "w": 2 * R, "h": 2 * R}]


@_fullframe("scale_stack")
def _render_scale_stack(insight: Insight, out_dir: Path, slug: str, frames: int = 16):
    """'As tall as N school buses': STACKS copies of one relatable object to
    depict a magnitude. One cut-out is generated and tiled (cheap). Needs a
    viz_params.scale_ref = {object, per_value[, unit]}. Returns None (-> depicted
    fallback) if the reference or the cut-out is unavailable."""
    from PIL import Image, ImageDraw
    from . import scene_media
    out_dir.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    star = max(insight.items, key=lambda p: p.value)
    ref = (getattr(insight, "viz_params", {}) or {}).get("scale_ref") or {}
    obj = str(ref.get("object", "")).strip()
    per = _num_or_none(ref.get("per_value"))
    if not obj or not per or per <= 0:
        return None
    cp = scene_media.subject_cutout(obj, slug, "stack")
    if not cp:
        return None
    try:
        base = Image.open(cp).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None
    n = max(1, int(round(star.value / per)))
    cap = min(n, 8)
    top, bot = 430, 1175
    gap = 10
    ch = int((bot - top - gap * (cap - 1)) / cap)
    cw = int(ch * base.width / base.height)
    if cw > 360:
        cw, ch = 360, int(360 * base.height / base.width)
    icon = base.resize((max(1, cw), max(1, ch)))
    unit = str(ref.get("unit") or insight.unit or "").strip()
    num_font, top_font = _pil_font(84), _pil_font(40)
    cap_txt = f"= {n:,} × {obj}"
    cap_font = _pil_font(56)
    cx = W // 2
    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        title = (insight.topic or "").strip()
        tb = d.textbbox((0, 0), title, font=top_font)
        d.text(((W - (tb[2] - tb[0])) // 2, 150), title, font=top_font,
               fill=(248, 250, 252, 255), stroke_width=3, stroke_fill=(5, 8, 15, 255))
        val = f"{star.value:,.0f} {unit}".strip()
        vb = d.textbbox((0, 0), val, font=num_font)
        d.text(((W - (vb[2] - vb[0])) // 2, 215), val, font=num_font,
               fill=_rgba(HIGHLIGHT, 255), stroke_width=5, stroke_fill=(5, 8, 15, 255))
        na = max(0.0, min(1.0, (r - 0.35) / 0.6))
        full = cap_txt + (f"  (showing {cap})" if n > cap else "")
        cb = d.textbbox((0, 0), full, font=cap_font)
        d.text(((W - (cb[2] - cb[0])) // 2, 330), full, font=cap_font,
               fill=(248, 250, 252, int(255 * na)),
               stroke_width=4, stroke_fill=(5, 8, 15, int(255 * na)))
        shown = int(round(r * cap))
        for k in range(min(shown, cap)):
            y = bot - ch - k * (ch + gap)
            canvas.alpha_composite(icon, (cx - cw // 2, y))
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, []


@_fullframe("orbit")
def _render_orbit(insight: Insight, out_dir: Path, slug: str, frames: int = 16):
    """Bodies ORBIT a centre at radii ∝ value — a cosmic depiction for
    distances / counts / 'how far'. Pure shapes, zero network. Empty anchors."""
    from PIL import Image, ImageDraw
    import math as _m
    out_dir.mkdir(parents=True, exist_ok=True)
    W, H = 1080, 1920
    items = _ordered_items(insight)[:5]
    vals = [max(0.0001, p.value) for p in items]
    vmax = max(vals)
    cx, cy = W // 2, 760
    r_in, r_out = 150, 430
    radii = [r_in + (r_out - r_in) * (v / vmax) for v in vals]
    ang0 = [-90 + i * (360.0 / max(1, len(items))) for i in range(len(items))]
    lab_font, title_font = _pil_font(38), _pil_font(52)
    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = 1.0 if f == frames else f / frames
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        title = (insight.topic or "").strip()
        tb = d.textbbox((0, 0), title, font=title_font)
        d.text(((W - (tb[2] - tb[0])) // 2, 150), title, font=title_font,
               fill=(248, 250, 252, 255), stroke_width=4, stroke_fill=(5, 8, 15, 255))
        for rad in radii:                                    # orbit rings
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad],
                      outline=(90, 110, 140, 120), width=3)
        for rad, alpha in ((70, 60), (52, 130), (38, 255)):  # central sun
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=_rgba(WARN, alpha))
        for i, (p, rad) in enumerate(zip(items, radii)):
            na = max(0.0, min(1.0, (r - i * 0.12) / 0.6))
            if na <= 0:
                continue
            ang = _m.radians(ang0[i] + r * 300.0)
            bx, by = cx + rad * _m.cos(ang), cy + rad * _m.sin(ang)
            col = HIGHLIGHT if p.label == insight.highlight_label else ACCENT
            d.ellipse([bx - 28, by - 28, bx + 28, by + 28], fill=_rgba(col, int(255 * na)))
            txt = f"{p.label} {_vfmt(p.value)}"
            tw = d.textbbox((0, 0), txt, font=lab_font)
            lx = min(max(bx + 36, 20), W - 20 - (tw[2] - tw[0]))
            d.text((lx, by - 18), txt, font=lab_font,
                   fill=(248, 250, 252, int(255 * na)),
                   stroke_width=3, stroke_fill=(5, 8, 15, int(255 * na)))
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, []


def _rgba(hex_color: str, alpha: int = 255):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


_HOST_CACHE: dict = {}


def _host_pose(pose: str = "cheer"):
    """Load a committed mascot pose PNG (RGBA) so Data can be composited
    directly INTO a demonstration (e.g. riding the gauge). Cached; returns
    None if the asset set isn't present."""
    if pose not in _HOST_CACHE:
        try:
            from PIL import Image
            p = (Path(__file__).resolve().parent.parent / "assets" / "mascot" /
                 "host" / f"{pose}.png")
            _HOST_CACHE[pose] = Image.open(p).convert("RGBA") if p.exists() else None
        except Exception:  # noqa: BLE001
            _HOST_CACHE[pose] = None
    return _HOST_CACHE[pose]


def render_story_chart(insight: Insight, out_path: Path):
    """One *full*, visually distinct chart for a story segment. Returns
    ``(path, anchors)`` where each anchor is ``{"value","cx","cy","w","h"}``
    — the centre/size (PNG px) of that value's number label. ``(None, [])``
    if matplotlib absent."""
    if not _have_mpl():
        return None, []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, plt = _card_base()
    ax, specs = _compose_story(fig, plt, insight, 1.0)
    anchors = _anchors_from(fig, ax, specs)
    fig.savefig(out_path, transparent=True)
    plt.close(fig)
    return out_path, anchors


def render_story_build(insight: Insight, out_dir: Path, slug: str,
                       frames: int = 60, full_by: float = 1.0):
    """Render a 'build' frame sequence (bars grow / line draws in) that ends on
    the EXACT static chart, so the rings still anchor. ~60 frames so the studio
    renderer can stretch the animation across the whole beat AND keep it smooth
    (a lower count played over a multi-second beat drops to ~5fps and looks
    laggy). Returns ``(printf_pattern, anchors)`` or ``(None, [])`` if mpl
    absent."""
    if not _have_mpl():
        return None, []
    # Full-frame renderers (diorama, timeline, fill_vessel, ...) author their own
    # 1080x1920 sequence. If one can't produce (image gen failed), degrade to the
    # next DEPICTED kind — never to bare numbers — and try again (cap the hops).
    hops = 0
    while insight.kind in FULLFRAME_RENDERERS and hops < 3:
        res = FULLFRAME_RENDERERS[insight.kind](insight, out_dir, slug, frames)
        if res is not None:
            return res
        insight.kind = FALLBACK.get(insight.kind, "bubbles")
        print(f"[chart] '{slug}' fell back -> {insight.kind!r}", flush=True)
        hops += 1
    out_dir.mkdir(parents=True, exist_ok=True)
    anchors: list = []
    for f in range(1, frames + 1):
        # LINEAR reveal (constant velocity). The old ease-out front-loaded the
        # growth and left the last ~1s of every card build near-frozen — that
        # frozen tail is what the temporal grade caught as duplicate frames /
        # low effective fps. Linear keeps the chart MOVING to the final frame,
        # which lands on the exact static chart so the rings still anchor.
        r = min(1.0, (f / frames) / max(0.05, full_by))
        if f == frames:
            r = 1.0                         # final frame == static chart
        fig, plt = _card_base()
        ax, specs = _compose_story(fig, plt, insight, r)
        if f == frames:
            anchors = _anchors_from(fig, ax, specs)
        fig.savefig(out_dir / f"{slug}_build{f:02d}.png", transparent=True)
        plt.close(fig)
    return str(out_dir / f"{slug}_build%02d.png"), anchors


def render_series(insight: Insight, out_dir: Path, slug: str) -> list[Path]:
    """Render the full progressive series; returns ordered PNG paths."""
    if not _have_mpl():
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    n = series_length(insight)
    paths: list[Path] = []
    for s in range(1, n + 1):
        fig, ax, plt = _new_card()
        ax.set_title(insight.topic, color=TEXT, fontsize=34, fontweight="bold",
                     pad=22, loc="left")
        if insight.kind == "trend":
            _draw_trend_state(ax, insight, s)
        else:
            _draw_bars_state(ax, insight, s)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.tick_params(colors=SUBTLE, length=0)
        fig.text(0.5, 0.05, insight.source.footer(), ha="center",
                 fontsize=12, color=SUBTLE)
        p = out_dir / f"{slug}_state{s:02d}.png"
        fig.savefig(p, transparent=True)
        plt.close(fig)
        paths.append(p)
    return paths
