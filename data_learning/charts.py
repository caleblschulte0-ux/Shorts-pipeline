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
    # Transparent canvas: the renderer now puts a full-frame cinematic scene
    # image behind every segment, so the viz composites ON the scene (no dark
    # floating card). Text/shapes carry their own shadows for legibility.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(SERIES_W, SERIES_H), dpi=SERIES_DPI)
    fig.patch.set_alpha(0.0)
    return fig, plt


def _heading(fig, title: str, subtitle: str, accent: str = HIGHLIGHT):
    # Drop a trailing unit parenthetical ("($)", "(%)", "($ billions)") and
    # auto-shrink so long titles never clip the right edge of the card.
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    size = (42 if len(title) <= 24 else 36 if len(title) <= 31
            else 30 if len(title) <= 40 else 26)
    fig.text(0.085, 0.91, title, color=TEXT, fontsize=size, fontweight="bold",
             ha="left", va="top", path_effects=_shadow())
    if subtitle:
        fig.text(0.085, 0.845, subtitle.upper(), color=accent, fontsize=22,
                 fontweight="bold", ha="left", va="top", path_effects=_shadow())


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

    ax = fig.add_axes([0.05, 0.14, 0.90, 0.62])
    ax.set_axis_off()
    if scope == "us":
        ax.set_xlim(-125, -66); ax.set_ylim(24, 50); mean_lat = 37.0
    else:
        ax.set_xlim(-170, 190); ax.set_ylim(-58, 84); mean_lat = 15.0
    ax.set_aspect(1.0 / _m.cos(_m.radians(mean_lat)))

    centroids: dict = {}
    for feat in gj["features"]:
        nm = feat.get("properties", {}).get("name", "")
        present = nm in values
        if present:
            tgt = to_rgb(cmap(norm(values[nm])))
            fc = tuple(base_rgb[i] + (tgt[i] - base_rgb[i]) * t for i in range(3))
            edge, lw, z = TEXT, 0.8, 3
        else:
            fc, edge, lw, z = base_rgb, CARD_EDGE, 0.4, 2
        best = None
        for ring in _exterior_rings(feat.get("geometry", {})):
            ax.add_patch(_Poly(ring, closed=True, facecolor=fc, edgecolor=edge,
                               linewidth=lw, zorder=z))
            if present and (best is None or len(ring) > len(best)):
                best = ring
        if present and best is not None:
            xs = [pt[0] for pt in best]; ys = [pt[1] for pt in best]
            centroids[nm] = (sum(xs) / len(xs), sum(ys) / len(ys))

    specs = []
    la = _lblalpha(reveal)
    for nm, v in sorted(values.items(), key=lambda kv: kv[1], reverse=True):
        if nm not in centroids:
            continue
        cx, cy = centroids[nm]
        txt = ax.text(cx, cy, _vfmt(v), ha="center", va="center", fontsize=23,
                      color=TEXT, fontweight="bold", zorder=5, alpha=la,
                      bbox=dict(boxstyle="round,pad=0.18", fc=(0, 0, 0, 0.5 * la),
                                ec="none"))
        specs.append((v, "art", txt, None))
    return ax, specs


def _story_pictograph(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Proportional icon array: each item is a row of icons whose count scales
    with its value (top item ~10 icons). Reads as 'X is N times Y' at a glance —
    the creative replacement for a plain ranking bar chart."""
    items = _ordered_items(insight)[:4]
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
        shown = max(0, min(full, int(round(full * t + 0.5)))) if t < 1 else full
        img = _icon_img(p.label)
        for c in range(full):
            on = c < shown
            if img is not None:
                oi = OffsetImage(img, zoom=0.62, alpha=1.0 if on else 0.28)
                ab = AnnotationBbox(oi, (c, y), frameon=False, zorder=3,
                                    box_alignment=(0.5, 0.5))
                ax.add_artist(ab)
            else:
                ax.scatter(c, y, s=290, marker="o",
                           color=color if on else BAR_BASE,
                           edgecolors="none", zorder=3, alpha=1.0 if on else 0.9)
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
    star = insight.items[0]
    if insight.kind == "geo_city":
        low = "lowest" in insight.main_insight.lower()
        _heading(fig, insight.topic, f"{star.label.split(',')[0]} "
                 f"{'sits lowest' if low else 'leads the map'}")
        ax, specs = _story_geo_city(fig, plt, insight, "", reveal)
        _footer(fig, insight)
        return ax, specs
    if insight.kind in ("callouts", "pictograph", "bignum"):
        # callouts is the creative replacement for dot/bar/bare-number viz.
        low = "lowest" in insight.main_insight.lower()
        _heading(fig, insight.topic, f"{star.label} "
                 f"{'sits lowest' if low else 'tops the list'}")
        ax, specs = _story_callouts(fig, plt, insight, "", reveal)
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
    elif insight.kind == "pictograph":
        low = "lowest" in insight.main_insight.lower()
        subtitle = f"{star.label} {'sits lowest' if low else 'tops the list'}"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_pictograph(fig, plt, insight, subtitle, reveal)
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


def _render_diorama(insight: Insight, out_dir: Path, slug: str, frames: int = 16):
    """Illustrated proportional SCENE: each ranked item is a relevant cut-out
    illustration sized by its value (big = high), arranged on a ground line with
    its number above — 'a big venue, medium caterers, a small band'. Never just
    numbers. Returns (printf_pattern, anchors), or None to fall back to callouts.
    """
    from PIL import Image, ImageDraw
    from . import scene_media
    out_dir.mkdir(parents=True, exist_ok=True)
    W = int(SERIES_W * SERIES_DPI)
    H = int(SERIES_H * SERIES_DPI)
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

    n = len(items)
    baseline = H - 120
    floor_h = H - 300                    # vertical room for the tallest object
    num_font = _pil_font(58)
    lab_font = _pil_font(30)
    slot = W // n
    max_w = int(slot * 0.86)             # cap width to the slot so nothing overlaps
    span = 1.0 / n                       # each object owns 1/n of the timeline
    anchors = []
    pattern = str(out_dir / f"{slug}_build%02d.png")
    for f in range(1, frames + 1):
        r = f / frames
        if f == frames:
            r = 1.0
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for i, (p, img) in enumerate(zip(items, cuts)):
            # Sequential entrance: object i rises/fades in during its own slice
            # of the timeline, so they arrive one at a time, never all at once.
            lr = (r - i * span) / (span * 0.85)
            lr = max(0.0, min(1.0, lr))
            lr = 1.0 - (1.0 - lr) ** 2    # ease-out
            if lr <= 0.0:
                continue
            frac = (p.value / vmax) if vmax else 1.0
            target_h = (0.34 + 0.66 * frac) * floor_h
            cx = slot * i + slot // 2
            color = (HIGHLIGHT if p.label == insight.highlight_label
                     else WARN if (insight.baseline and p.label == insight.baseline.label)
                     else ACCENT)
            top = baseline
            if img is not None:
                scale = min(target_h / img.height, max_w / img.width) * lr
                w = max(1, int(img.width * scale))
                h = max(1, int(img.height * scale))
                im = img.resize((w, h))
                x = int(max(0, min(W - w, cx - w // 2)))
                canvas.alpha_composite(im, (x, baseline - h))
                top = baseline - h
            na = max(0.0, min(1.0, (lr - 0.55) / 0.45))   # number lands as it settles
            num = _vfmt(p.value)
            nb = draw.textbbox((0, 0), num, font=num_font)
            nx = cx - (nb[2] - nb[0]) // 2
            ny = top - 78
            draw.text((nx, ny), num, font=num_font, fill=_rgba(color, int(255 * na)))
            lb = draw.textbbox((0, 0), p.label, font=lab_font)
            draw.text((cx - (lb[2] - lb[0]) // 2, baseline + 12), p.label,
                      font=lab_font, fill=(248, 250, 252, int(255 * na)))
            if f == frames:
                anchors.append({"value": float(p.value), "cx": float(cx),
                                "cy": float(ny + 30), "w": 200.0, "h": 70.0})
        canvas.save(out_dir / f"{slug}_build{f:02d}.png")
    return pattern, anchors


def _rgba(hex_color: str, alpha: int = 255):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


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
    if insight.kind == "diorama":
        res = _render_diorama(insight, out_dir, slug, frames)
        if res is not None:
            return res
        insight.kind = "callouts"        # cutouts failed -> graceful fallback
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
