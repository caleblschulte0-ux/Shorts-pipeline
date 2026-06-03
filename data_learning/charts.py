"""Chart rendering (matplotlib) in the channel house style.

Charts are sized 1080x960 to fill the *top half* of the 1080x1920 stacked
short — the existing renderer scales/crops a shot image into that region.
The bottom half stays gameplay, so the format is unchanged.

matplotlib is optional: if it isn't installed, :func:`render_chart` returns
None and the caller falls back to a stock B-roll query, so the base
pipeline still produces a video.
"""
from __future__ import annotations

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
SERIES_W, SERIES_H, SERIES_DPI = 10.0, 9.2, 100   # -> 1000x920 px


def _vfmt(v: float) -> str:
    """Value label: drop the .0 on whole numbers, else one decimal."""
    return f"{v:.0f}" if float(v).is_integer() else f"{v:.1f}"


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


def _arrow_to_bar(ax, insight: Insight, items, values):
    """Draw a bright pointer at the highlighted bar so viewers know where to
    look (the mascot gestures; this is the precise pointer)."""
    try:
        i = next(k for k, p in enumerate(items)
                 if p.label == insight.highlight_label)
    except StopIteration:
        return
    v = values[i]
    # Bright emphasis ring around the star bar — the precise "look here" cue
    # (the mascot gestures toward it).
    ax.barh(i, v, color="none", edgecolor=TEXT, linewidth=4, height=0.62,
            zorder=5)


def render_story_chart(insight: Insight, out_path: Path) -> Path | None:
    """One *full* chart for a story segment (its own data), on a card, with a
    pointer at the key datum. Returns the path or None if matplotlib absent."""
    if not _have_mpl():
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax, plt = _new_card()
    ax.set_title(insight.topic, color=TEXT, fontsize=36, fontweight="bold",
                 pad=22, loc="left")
    if insight.kind == "trend":
        _draw_trend_state(ax, insight, len(insight.items) - 1)
    else:
        items = _ordered_items(insight)
        _draw_bars_state(ax, insight, len(items))
        _arrow_to_bar(ax, insight, items, [p.value for p in items])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=SUBTLE, length=0)
    fig.text(0.5, 0.05, insight.source.footer(), ha="center",
             fontsize=12, color=SUBTLE)
    fig.savefig(out_path, transparent=True)
    plt.close(fig)
    return out_path


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
