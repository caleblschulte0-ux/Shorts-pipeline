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
# Taller card so the chart can dominate the frame (data is the focus).
SERIES_W, SERIES_H, SERIES_DPI = 10.0, 11.2, 110   # -> 1100x1232 px


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
    fig.text(0.085, 0.91, title, color=TEXT, fontsize=42, fontweight="bold",
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


def _compose_story(fig, plt, insight: Insight, reveal: float = 1.0):
    """Draw the heading + the right chart kind (at the given build fraction)
    + footer. reveal=1.0 is the final, static chart."""
    star = insight.items[0]
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
                       frames: int = 16):
    """Render a short 'build' frame sequence (bars grow / line draws in) that
    ends on the EXACT static chart, so the rings still anchor. Returns
    ``(printf_pattern, anchors)`` with anchors from the final frame, or
    ``(None, [])`` if matplotlib is absent."""
    if not _have_mpl():
        return None, []
    out_dir.mkdir(parents=True, exist_ok=True)
    anchors: list = []
    for f in range(1, frames + 1):
        r = f / frames
        r = 1.0 - (1.0 - r) ** 2            # ease-out
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
