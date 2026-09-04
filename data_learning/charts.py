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
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from shared.fit_title import fit_title

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
SERIES_W, SERIES_H, SERIES_DPI = 10.0, 15.6, 110   # taller card -> fills more
# of the 9:16 frame so the dead 'letterbox' band below it (the gate's empty_void)
# shrinks; the caption band still clears the chart's bottom axis.


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
# Actions where Data is mechanically ATTACHED to the chart object (his grip
# point is baked onto the datum, he has no floor contact).
_COUPLED_ACTIONS = frozenset({"drag_line", "shoved_bar", "hoist_stack",
                              "pull_down_win"})

# ---- attachment contract (charts emit anchors; the mascot attaches) --------
# Every _bake_host call records its grip point here; render_story_build collects
# one entry per frame and writes `{slug}_attach.json` — the scene's attachment
# record: which object Data grips, the full grip motion path, and the selected
# performance. Downstream (manifest, benchmark validator, repair loop) read it.
_ATTACH_FRAME: list = []           # grips recorded while drawing ONE frame
_LAST_PERF: dict = {}              # the performance spec chosen for this build


# ---- THE TOUR: where Data is, once the chart has finished drawing ---------
# The anchor every compositor bakes to is derived from `reveal`, and `reveal`
# saturates at `full_by` and then sits at 1.0 for the rest of the beat. So the
# host travels while the chart builds and is PINNED for everything after —
# which is what the 2026-08-24/25 verdicts kept describing in the same words:
# "Data just hovers/slides in the same spot above the 1972-1983 bars with no
# setup->action->payoff ... only at seg4:end does he finally ride the falling
# line down". The grip act was right by then; the anchor was standing still.
#
# `_TOUR` is beat progress (0..1), set per frame by `render_story_build` and
# INDEPENDENT of reveal. A ranked compositor uses it to choose WHICH datum he
# is working on, so he walks the ranking — shoving each bar in turn — instead
# of parking on the winner's tip for two-thirds of the runtime. The last fifth
# is reserved for the winner so the payoff still lands where the narration
# says it does (and so it agrees with `_perf_phase`'s finale window).
_TOUR: float = 1.0
TOUR_FINALE = 0.8          # from here on he is on the winner, committing


TOUR_WORK = 0.72           # of each step spent working the bar; rest is transit


def _tour_index(n: int, tour: float | None = None) -> float:
    """Where Data is on the ranking at this point in the beat, as a FLOAT
    item index (0 = the winner).

    He works his way from the BOTTOM of the field up and arrives at the
    winner for the finale — so he ends on the answer the narration lands on
    rather than starting there and wandering off it.

    The index is fractional ON PURPOSE. Snapping bar-to-bar every few
    seconds trades "hovers in one spot" for "teleports", which is the same
    note in a different costume. Each step is `TOUR_WORK` held on one bar
    (he struggles against it — that is what `_perf_phase` is animating) and
    the remainder TRANSIT, interpolated, so he visibly climbs from one bar
    to the next. Callers that need a real row round it; the y coordinate
    takes the float and lets him ride between rows while moving.
    """
    if n <= 1:
        return 0.0
    t = _TOUR if tour is None else tour
    t = min(1.0, max(0.0, float(t)))
    if t >= TOUR_FINALE:
        return 0.0
    step = TOUR_FINALE / n
    k, frac = divmod(t, step)
    k = int(k)
    within = frac / step                       # 0..1 inside this step
    # held on bar (n-1-k), then transit toward (n-1-k-1)
    move = 0.0 if within <= TOUR_WORK else (within - TOUR_WORK) / (1.0 - TOUR_WORK)
    pos = (n - 1 - k) - move
    return max(0.0, min(float(n - 1), pos))


def _tour_tip(values, pos: float, floor: float = 0.0) -> float:
    """The tip value at a fractional tour position — interpolated between the
    two bars he is moving between, so the transit is a diagonal climb across
    the chart rather than a horizontal jump followed by a vertical one."""
    if not values:
        return floor
    n = len(values)
    lo = max(0, min(n - 1, int(pos)))
    hi = max(0, min(n - 1, lo + 1))
    f = max(0.0, min(1.0, float(pos) - lo))
    return float(values[lo]) * (1.0 - f) + float(values[hi]) * f


def _perf_align(action: str, default: tuple) -> tuple:
    """Attachment alignment for the selected action (falls back to the chart
    site's default when the action has no registered contact geometry)."""
    try:
        from . import mascot_director as _md
        return _md.ACTION_ALIGN.get(action, default)
    except Exception:  # noqa: BLE001
        return default


def _perf_action(insight: Insight, kind: str) -> str:
    """The DIRECTED action for this beat: an explicit scene-plan override wins;
    otherwise the director selects a VERIFIED performance from the story's
    actual CLAIM (insight.main_insight), not merely the chart kind."""
    global _LAST_PERF
    ov = getattr(insight, "perf_override", None)
    if ov:
        # full spec when the story-level director (or a scene plan) chose it
        spec = getattr(insight, "perf_spec", None)
        _LAST_PERF = spec if isinstance(spec, dict) else {
            "action": ov, "goal": "scene-plan override",
            "target": getattr(insight, "highlight_label", "") or ""}
        return ov
    try:
        from . import mascot_director as _md
        # the object he fights: the line's latest point for a trend, else the
        # star (leading) item
        star = ""
        if insight.items:
            star = (insight.items[-1].label if kind in ("trend", "timeline")
                    else insight.items[0].label)
        spec = _md.performance_for(kind, insight.main_insight or "", star,
                                   require_contact=True)
        _LAST_PERF = spec
        return spec["action"]
    except Exception:  # noqa: BLE001 — never lose a render over direction
        _LAST_PERF = {"action": "shoved_bar", "goal": "", "target": ""}
        return "shoved_bar"


def _host_img(action: str, phase: float):
    """One mascot action frame as an RGBA numpy array (cached by action+phase).
    Granularity 0.025 (40 buckets): coarse 0.1 held each pose ~1/11 of the beat
    (~1.2s = a stack of duplicate frames that aliased the effort reps and tanked
    effective_fps); 40 buckets keep the arc's pushes SMOOTH and the mascot moving
    nearly every frame, while still caching (≤40 rasterises per action)."""
    # 80 buckets, raised from 40: `_perf_phase` folds six effort reps into
    # the arc, so a full rep spans ~1/6 of phase — at 40 buckets that is ~7
    # steps per rep, which staircases; 80 keeps reps smooth at ≤80 cached
    # rasterises per action.
    key = (action, round(phase * 80) / 80)
    if key in _HOST_IMG_CACHE:
        return _HOST_IMG_CACHE[key]
    val = None
    try:
        import io
        import numpy as np
        from PIL import Image
        from . import mascot_director as _md
        # CLAMP (do NOT modulo) — the arc actions are non-periodic beat-progress
        # in [0,1] where phase 1.0 is the PAYOFF climax. `% 1.0` wrapped 1.0 back
        # to 0.0, so the final frame snapped to the setup pose (no overhead cheer
        # ever landed). Clamp keeps 1.0 -> payoff.
        _t = min(1.0, max(0.0, key[1]))
        # COUPLED actions (Data mechanically attached to a chart object) render
        # groundless — no floor shadow, since he leaves the floor.
        _ground = action not in _COUPLED_ACTIONS
        svg = _md.compose_anim({"action": action, "prop": "none",
                                "ground": _ground}, _t)
        png = _md._rasterise(svg, 300)
        val = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA")) / 255.0
    except Exception:  # noqa: BLE001 — a chart must never die over the host
        val = None
    _HOST_IMG_CACHE[key] = val
    return val


def _perf_phase(phase: float) -> float:
    """Beat progress -> performance phase: the arc, plus EFFORT REPS.

    Every action animator is a one-way ARC — setup at 0, climax at 1 — and
    ``phase`` is beat progress, which crosses 0..1 ONCE. A beat is 10-18
    seconds, so Data performed one shove spread over fifteen seconds: at any
    human-scale window his limbs move a few pixels per SECOND, which is a
    statue. The showrunner said it in three different videos on 2026-08-16 —
    "the mascot is a sticker", "never does a bit" — and it was right; the
    per-quarter-beat frame diffs looked healthy while the per-second ones
    rounded to zero. (The phase-bucket comment in `_host_img` still talks
    about "effort reps" — an earlier incarnation had them; the plumbing that
    fed a cycling clock was lost when phase became raw reveal.)

    So: six visible strain-and-heave reps ride ON the arc — the pose works
    back and forth ±6% of arc around its forward progress, enveloped by
    (1-t) so the reps die out as the climax approaches and phase 1.0 still
    lands EXACTLY on the payoff pose (the clamp in `_host_img` that took a
    separate bug to win stays meaningful). At a 15s beat that is a rep every
    2.5s; at 6s, one per second — working tempo, not jiggle, and it is limb
    motion inside the sprite, not sprite translation, so it cannot re-open
    the "weird shaking" the camera-breath rework closed."""
    t = min(1.0, max(0.0, float(phase)))
    if t >= 0.8:
        # THE FINALE: one committed, uninterrupted run of the whole arc over
        # the beat's last fifth, landing phase 1.0 exactly on the payoff
        # pose. ~3s at a 15s beat — the decisive push after the struggle.
        return (t - 0.8) / 0.2
    # THE STRUGGLE: four ping-pong reps (strain toward the climax, get
    # pushed back, strain again) across the first 80% of the beat. Ping-pong
    # rather than modulo because the arcs are not seamless loops — a %-wrap
    # snaps the pose from climax back to setup in one frame, which reads as
    # a glitch; the mirror reads as effort and release. Capped at 0.85 so
    # the true climax is seen only once, in the finale.
    u = (t / 0.8) * 4.0
    frac = u - int(u)
    return 0.85 * (1.0 - abs(1.0 - 2.0 * frac))


def _clamp_host(ax, x, y, img_hw, zoom, align):
    """Nudge the host's anchor so his sprite box stays ON the card.

    `annotation_clip=False` lets the bake follow a data tip anywhere — which
    is the point — but with no bounds the top row of a bar race parks his
    head across the title ("floating over the title, occluding 'cereal'"),
    and a trend whose tip rides high hangs him over the x tick labels ("sits
    on top of the '1972' label"). Both were verbatim showrunner blocks on
    2026-08-22/23. The box is clamped to: inside the card horizontally,
    below the subtitle band, and (when the target axes sits above the card
    floor) no lower than the axes' own bottom edge, so tick labels stay
    readable. A bake already in bounds — the praised "arms on the Slovenia
    bar tip" — comes back untouched.

    OffsetImage with dpi_cor renders img_px * zoom * dpi/72 device pixels;
    as a figure fraction the dpi cancels: frac = img_px * zoom / (72 * inches).
    `tests/test_mascot_anchoring.py` pins that arithmetic against the real
    rendered extent, so a matplotlib behaviour change fails loudly."""
    try:
        fig = ax.figure
        try:
            ax.apply_aspect()      # aspect-set axes (maps) finalize their box
        except Exception:          # lazily; transforms lie until it's applied
            pass
        fw_in, fh_in = fig.get_size_inches()
        bw = img_hw[1] * zoom / (72.0 * fw_in)     # box width,  figure frac
        bh = img_hw[0] * zoom / (72.0 * fh_in)     # box height, figure frac
        fx, fy = fig.transFigure.inverted().transform(
            ax.transData.transform((float(x), float(y))))
        left, bottom = fx - bw * align[0], fy - bh * align[1]
        x0, x1 = 0.02, 0.98                        # card side margins
        y1 = SUB_Y - 0.012                         # stay below the subtitle
        y0 = 0.04
        ay0 = float(ax.get_position().y0)
        if ay0 > y0 + 0.02:                        # a real plot axes, not a
            y0 = ay0 - 0.015                       # full-figure overlay
        nl = min(max(left, x0), max(x0, x1 - bw))
        nb = min(max(bottom, y0), max(y0, y1 - bh))
        if abs(nl - left) < 1e-9 and abs(nb - bottom) < 1e-9:
            return float(x), float(y)
        nfx, nfy = nl + bw * align[0], nb + bh * align[1]
        return tuple(ax.transData.inverted().transform(
            fig.transFigure.transform((nfx, nfy))))
    except Exception:  # noqa: BLE001 — a chart must never die over the clamp
        return float(x), float(y)


def _bake_host(ax, x, y, action, phase, zoom=0.5, align=(0.5, 0.08)):
    """Composite Data performing ``action`` at data point (x, y) on ``ax``. The
    pose animates with ``phase``; ``align`` (0.5, ~0) puts his FEET at the point
    so he stands ON the datum. Records the grip into the attachment log
    (`_ATTACH_FRAME`) — the contract that the mascot is ATTACHED to a chart
    object, not floating near it."""
    img = _host_img(action, _perf_phase(phase))
    if img is not None:
        x, y = _clamp_host(ax, x, y, img.shape[:2], zoom, align)
    _ATTACH_FRAME.append({"action": action, "x": float(x), "y": float(y),
                          "phase": round(float(min(1.0, max(0.0, phase))), 3)})
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


# The title band: from the left text margin to a matching right margin
# inside the card. `_heading` fits the title to THIS width, measured.
HEAD_X = 0.085
HEAD_RIGHT = 0.915
HEAD_Y = 0.91
SUB_Y = 0.845


def _heading(fig, title: str, subtitle: str, accent: str = HIGHLIGHT):
    """Title + subtitle, fitted to the card by MEASUREMENT.

    This used to pick a font size from `len(title)` under a comment claiming
    it "auto-shrink[s] so long titles never clip the right edge of the card".
    Character count is not width, and it did not: measured on this very card,
    "World hydropower fell below its 1990 level" reached 0.966 of figure
    width against a 0.915 margin, and it shipped that way on 2026-08-11 —
    the showrunner's note was "a headline clipped off the right edge".
    Longer real titles reached 1.35, a third of the way off frame.

    `shared.fit_title` measures the rendered extent and steps the size down,
    wrapping to a second line only if shrinking alone cannot do it — and a
    wrapped title is capped at a size whose two lines still fit ABOVE the
    subtitle. Nothing below it moves. A fix that traded a clipped title for
    one printed over the chart would not be a fix.
    """
    # Drop a trailing unit parenthetical ("($)", "(%)", "($ billions)").
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip()
    W_px = fig.get_size_inches()[0] * fig.dpi
    band = (HEAD_RIGHT - HEAD_X) * W_px
    # SHRINK BEFORE WRAPPING. The tallest chart axes on this card top out at
    # 0.85, and the subtitle already sits at 0.845 — so a second title line
    # pushes the subtitle onto the plot. Trading a clipped title for one
    # printed over the chart is not a fix. One line down to 24pt first; only
    # a title that cannot fit even there is allowed to wrap.
    fitted, fp = fit_title(fig, title, None, band, max_lines=1, hi=42, lo=24)
    if "\n" in fitted or len(fitted.split()) < len(title.split()):
        # 32pt is the largest two-line block that still fits ABOVE the
        # subtitle: 2 * 32 * 1.08 linespacing = 105px against the 111px band
        # between HEAD_Y and SUB_Y. Staying inside it means the subtitle
        # never has to move, so it never lands on the plot.
        fitted, fp = fit_title(fig, title, None, band,
                               max_lines=2, hi=32, lo=20)
    fig.text(HEAD_X, HEAD_Y, fitted, color=TEXT, fontproperties=fp,
             ha="left", va="top", linespacing=1.08)
    if subtitle:
        fig.text(HEAD_X, SUB_Y, subtitle.upper(), color=accent,
                 fontsize=22, fontweight="bold", ha="left", va="top")


def _footer(fig, insight: Insight):
    fig.text(0.5, 0.045, insight.source.footer(), ha="center", fontsize=12,
             color=SUBTLE)


def _round_barh(ax, y, value, lw, color, zorder=3):
    ax.plot([0.0, value], [y, y], color=color, lw=lw, solid_capstyle="round",
            zorder=zorder)


def _round_barv(ax, x, value, lw, color, zorder=3):
    ax.plot([x, x], [0.0, value], color=color, lw=lw, solid_capstyle="round",
            zorder=zorder)


def _bar_lw(n: int, frac: float = 0.58) -> float:
    """Bar thickness (points) so rounded bars fill the axes (``frac`` of card)."""
    plot_px = SERIES_H * frac * SERIES_DPI
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
        tip = max(v * reveal, vmax * 0.012)
        _round_barh(ax, i, tip, lw, color, zorder=3)
        # Winner (i==0) carries the mascot on its tip, so its number lives INSIDE
        # the bar (white) — clear of the pushing host; the rest label outside.
        if i == 0 and tip > vmax * 0.30:
            t = ax.text(vmax * 0.03, i, _vfmt(v), va="center", ha="left",
                        fontsize=30, color="white", fontweight="bold", zorder=6,
                        alpha=_lblalpha(reveal))
        else:
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
    ax.set_xlim(0, vmax * 1.28)
    ax.set_ylim(n - 0.5, -0.5)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    # BAKE THE HOST: Data shoves the WINNING bar (i==0, top row) out along its
    # growing tip — a full setup->action->payoff arc across the beat. Without
    # this a rank/bars beat (kind is in BAKED_CHART_KINDS, overlay suppressed)
    # would show NO mascot at all.
    # THE TOUR (see `_tour_index`): he works his way UP the ranking as the
    # beat runs and lands on the winner for the finale, instead of standing
    # on the winner's tip from the moment the build finishes.
    _row = _tour_index(len(values))
    _wtip = max(_tour_tip(values, _row) * max(0.0, min(1.0, reveal)),
                vmax * 0.02)
    _act_b = _perf_action(insight, "rank")
    _bake_host(ax, _wtip, _row, _act_b, reveal,
               zoom=0.9, align=_perf_align(_act_b, (0.28, 0.5)))
    insight.host_baked = True
    return ax, arts


def _story_versus(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Two tall rounded columns with big numbers — for comparisons."""
    hi, lo = insight.items[0], insight.items[1]
    pair = [(hi, HIGHLIGHT), (lo, ACCENT)]
    vmax = max(hi.value, lo.value)
    # Tall axes + WIDE columns so two bars actually fill the 9:16 card (they used
    # to read as 'two short capsules in a narrow band' = empty_void).
    ax = fig.add_axes([0.08, 0.11, 0.84, 0.74])
    ax.set_facecolor("none")
    lw = 165
    xs = [0.28, 0.72]
    colors = [HIGHLIGHT, ACCENT]
    # Faint horizontal reference lines so the space above the shorter column reads
    # as chart, not void.
    for _gf in (0.25, 0.5, 0.75, 1.0):
        ax.axhline(vmax * _gf, color="#1E2A44", linewidth=1.2, zorder=0, alpha=0.7)
    arts = []
    for j, ((p, color), x) in enumerate(zip(pair, xs)):
        _round_barv(ax, x, vmax, lw, BAR_BASE, zorder=2)
        _round_barv(ax, x, max(p.value * reveal, vmax * 0.02), lw, color, zorder=3)
        # Winner (j==0) carries the mascot gripping its TOP, so its big number
        # sits LOW inside the column (white) — clear of the top-gripping host.
        # UNIT-AWARE label. This used to hardcode "%" on both columns, which is
        # right for a percent comparison and a lie for every other unit — and
        # _compose_story routes ANY two-item insight here, so a 2-row ranking in
        # metres/dollars/counts rendered "10211%". _ulabel is what every other
        # chart kind already uses.
        if j == 0:
            t = ax.text(x, vmax * 0.16, _ulabel(p.value, insight.unit),
                        ha="center",
                        va="center", fontsize=42, color="white",
                        fontweight="bold", zorder=6, alpha=_lblalpha(reveal))
        else:
            t = ax.text(x, p.value + vmax * 0.06, _ulabel(p.value, insight.unit),
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
                f"{insight.baseline.label} {_ulabel(b, insight.unit)}",
                ha="center",
                va="bottom", fontsize=19, color=WARN, fontweight="bold",
                zorder=4)
    ax.set_xlim(0, 1)
    ax.set_ylim(-vmax * 0.20, vmax * 1.12)   # winning column nearly fills the card
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    # BAKE THE HOST: Data rides the WINNING column's growing tip, hoisted UP as it
    # rises (setup->action->payoff). Feet at the tip; his body fills the space
    # above the column where the number used to sit (now moved inside).
    # COUPLE (vertical DRAG, like the trend/stack that pass): Data grips the top
    # of the winning column and is hauled UP as it grows — reads as data-driven,
    # unlike lift_arc which the gate read as 'perches on top, swallowed'.
    _htip = max(hi.value * max(0.0, min(1.0, reveal)), vmax * 0.02)
    _act_c = _perf_action(insight, "comparison")
    _bake_host(ax, xs[0], _htip, _act_c, reveal,
               zoom=0.8, align=_perf_align(_act_c, (0.5, 0.78)))
    insight.host_baked = True
    return ax, arts


def _story_trend(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """Line with a soft area fill, a peak callout, and a glowing end."""
    pts = insight.items
    x = list(range(len(pts)))
    values = [p.value for p in pts]
    # Top at 0.80, just under the subtitle band (SUB_Y 0.845). At 0.56 height
    # the plot stopped at 0.74 and left a further tenth of the card as bare
    # navy above it — part of the same "empty frame" the showrunner kept
    # naming. The peak callout sits inside the axes headroom, so raising the
    # box cannot push it into the subtitle.
    ax = fig.add_axes([0.13, 0.18, 0.80, 0.62])
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
    ax.set_xlim(-0.35, (len(pts) - 1) + 0.85)
    # FRAME THE DATA, NOT THE ORIGIN.
    #
    # This was `_yhi = max(values) * 1.22` — headroom as a fraction of the
    # ABSOLUTE VALUE rather than of the variation. For a series that lives in
    # a narrow band high above zero (a percentage, an index, a population)
    # that is enormous dead space, and it flattens the very change the video
    # is about. Measured on the hydropower story of 2026-08-11:
    #
    #     values 16.1 .. 18.7  (span 2.6)  ->  ylim 15.63 .. 22.81
    #     the data occupied 36% of the axis and 20% of the CARD
    #
    # The showrunner's notes were "a hairline timeline and an empty lower
    # frame that no scroller would stay for", "no frame is >30% empty", and
    # — decisively — "the headline stat, hydro falling from 18.4% to 16.1%,
    # is never actually shown". It was on screen the whole time, drawn nearly
    # flat. Padding is now proportional to the SPAN, so the fall reads.
    _pad = max(span, abs(max(values)) * 0.02, 1e-9)
    _ylo = lo - _pad * 0.28
    _yhi = max(values) + _pad * 0.50      # room for the peak callout
    ax.set_ylim(_ylo, _yhi)
    # A non-zero-based axis has to SAY so, or the framing above becomes a way
    # of overstating a change. `set_yticks([])` drew no scale at all — the
    # reader could not tell 16-19 from 0-19. Three labelled gridlines make the
    # framing legible instead of flattering.
    _ticks = [lo, (lo + max(values)) / 2.0, max(values)]
    ax.set_yticks(_ticks)
    ax.set_yticklabels([_ulabel(v, insight.unit) for v in _ticks],
                       fontsize=19, color=SUBTLE)
    # Gridlines ON the labelled ticks, so the lines and the scale agree.
    # These used to sit at four arbitrary fractions of the axis because
    # set_yticks([]) meant matplotlib's own grid drew nothing — decorative
    # rules that described no value.
    for _t in _ticks:
        ax.axhline(_t, color="#1E2A44", linewidth=1.3, zorder=0, alpha=0.8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    # COUPLE THE HOST: Data clamps both fists onto the line's advancing TIP and
    # tries to haul it down — but the line keeps climbing and drags him up (heels
    # dug in -> feet break contact -> airborne swing). His grip point (top of the
    # sprite, ~0.80 up) is baked ONTO the tip, so the line visibly acts on him —
    # contact + cause + consequence, not a sprite surfing above the line.
    _act_t = _perf_action(insight, "trend")
    _bake_host(ax, xd[-1], yd[-1], _act_t, reveal,
               zoom=1.15, align=_perf_align(_act_t, (0.5, 0.80)))
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
    # BAKE THE HOST on a side axes in the empty right third — Data hoists the
    # composition (lift arc, setup->action->payoff) so a share beat isn't
    # mascot-less (kind is in BAKED_CHART_KINDS, so the overlay is suppressed).
    _max = fig.add_axes([0.66, 0.14, 0.32, 0.56])
    _max.set_axis_off(); _max.set_xlim(0, 1); _max.set_ylim(0, 1)
    _bake_host(_max, 0.5, 0.12, "lift_arc", reveal, zoom=0.55, align=(0.5, 0.0))
    insight.host_baked = True
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


def _ring_area_centroid(ring):
    """Shoelace signed area + centroid of one ring. Fine at map-pin scale."""
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a) < 1e-12:
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    return a / 2.0, cx / (3.0 * a), cy / (3.0 * a)


def region_centroid(scope: str, label: str):
    """(lon, lat) for a region, from its LARGEST polygon — the mainland, so
    France pins on France, not averaged into the Atlantic by its islands.
    None when the label is not in the scope's geojson. This is what puts the
    ranked markers ON Slovenia / Malawi / Iceland instead of a decorative
    dot column beside the map (the 2026-08-22/23 bare_number_card blocks)."""
    key = f"_centroids_{scope}"
    if key not in _GEO_CACHE:
        table = {}
        for feat in _load_geojson(scope)["features"]:
            nm = feat.get("properties", {}).get("name", "")
            best = None
            for ring in _exterior_rings(feat.get("geometry", {})):
                a, cx, cy = _ring_area_centroid(ring)
                if best is None or abs(a) > best[0]:
                    best = (abs(a), cx, cy)
            if nm and best:
                table[nm] = (best[1], best[2])
        _GEO_CACHE[key] = table
    return _GEO_CACHE[key].get(_norm_region(label))


def _story_geo(fig, plt, insight: Insight, subtitle: str, reveal: float, scope: str):
    """Map + ranked bars for geographic data — a DEMONSTRATION, not a legend.

    The 2026-08-22/23 blocks named this beat three ways at once: empty_void
    (a world map ~280px tall inside a ~1064px axes, everything else blank),
    bare_number_card (a dot column at a fixed x with raw numbers, "not placed
    on Slovenia, Malawi, Costa Rica, Iceland or Estonia"), and a mascot
    parked at an empty hard-coded corner. All three were layout facts, so
    all three are fixed here structurally:

    * the map ZOOMS to the ranked regions' bounding box and its axes box is
      sized to the map's real aspect — no internal letterbox, no dead band;
    * rank markers sit ON each region (``region_centroid``), numbered, sized
      and colored by value — the geo_city pin pattern, worldwide;
    * the numbers live in a ranked ROUNDED-BAR strip under the map (length
      encodes value, colors match the pins) instead of a floating list;
    * Data performs on the WINNING BAR TIP — the exact contact the judge
      praised on 08-23 ("arms on the Slovenia bar tip") — not at (0.30, 0.10).
    """
    import math as _m
    from matplotlib.patches import Polygon as _Poly
    from matplotlib.colors import Normalize, LinearSegmentedColormap, to_rgb

    gj = _load_geojson(scope)
    values = {_norm_region(p.label): p.value for p in insight.items}
    vals = list(values.values()) or [0.0, 1.0]
    vmin, vmax = min(vals), max(vals)
    norm = Normalize(vmin, vmax if vmax > vmin else vmin + 1.0)
    cmap = LinearSegmentedColormap.from_list("house", [ACCENT, HIGHLIGHT, WARN])
    # Base fill lifted OFF near-black: #1F2937 at reveal 0 read as "a
    # near-black silhouette" (verbatim block); unmatched land now sits a
    # visible slate above the card so the map is a map from frame one.
    base_rgb = tuple(0.45 * b + 0.55 * g for b, g in
                     zip(to_rgb(BAR_BASE), to_rgb("#3A4A6B")))
    t = max(0.0, min(1.0, reveal))
    ranked = sorted(values.items(), key=lambda kv: kv[1], reverse=True)[:6]
    pins = [(nm, v, region_centroid(scope, nm)) for nm, v in ranked]
    pins = [(nm, v, c) for nm, v, c in pins if c]

    # --- map extent: zoom to the ranked regions, padded, clamped to scope ---
    if scope == "us":
        wx0, wx1, wy0, wy1 = -125.0, -66.0, 24.0, 50.0
        min_lon, min_lat = 16.0, 9.0
    else:
        wx0, wx1, wy0, wy1 = -170.0, 190.0, -58.0, 84.0
        min_lon, min_lat = 55.0, 26.0
    if pins:
        lons = [c[0] for _, _, c in pins]; lats = [c[1] for _, _, c in pins]
        pad_x = max(min_lon, (max(lons) - min(lons)) * 0.35)
        pad_y = max(min_lat, (max(lats) - min(lats)) * 0.35)
        x0 = max(wx0, min(lons) - pad_x); x1 = min(wx1, max(lons) + pad_x)
        y0m = max(wy0, min(lats) - pad_y); y1m = min(wy1, max(lats) + pad_y)
    else:
        x0, x1, y0m, y1m = wx0, wx1, wy0, wy1
    mean_lat = (y0m + y1m) / 2.0
    aspect = 1.0 / max(0.3, _m.cos(_m.radians(min(75.0, abs(mean_lat)))))

    # --- axes box sized to the map's REAL drawn aspect (no letterbox) ---
    fw_in, fh_in = fig.get_size_inches()
    map_top, bars_top_max = 0.795, 0.46
    wf = 0.94
    hf = wf * (fw_in / fh_in) * ((y1m - y0m) * aspect / max(1e-6, x1 - x0))
    hf = min(hf, map_top - bars_top_max)     # never squeeze the bar strip out
    wf2 = min(wf, wf * (map_top - bars_top_max) / max(1e-6, hf))
    ax = fig.add_axes([(1.0 - wf2) / 2.0, map_top - hf, wf2, hf])
    ax.set_axis_off()
    ax.set_xlim(x0, x1); ax.set_ylim(y0m, y1m)
    ax.set_aspect(aspect)
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

    # --- numbered rank markers ON the regions themselves ---
    la = _lblalpha(reveal)
    for i, (nm, v, (lon, lat)) in enumerate(pins):
        ri = max(0.0, min(1.0, (t - i * 0.07) / max(1e-6, 1.0 - i * 0.07)))
        col = cmap(norm(v))
        ax.scatter([lon], [lat], s=260 + 500 * float(norm(v)) * ri, color=col,
                   edgecolors="white", linewidths=1.5, zorder=5,
                   alpha=0.35 + 0.6 * ri)
        ax.text(lon, lat, str(i + 1), ha="center", va="center", fontsize=17,
                color="white", fontweight="bold", zorder=6,
                alpha=0.35 + 0.65 * ri, path_effects=_shadow())
    if pins:
        nm0, v0, (lon0, lat0) = pins[0]
        ax.text(lon0, lat0 + (y1m - y0m) * 0.055,
                f"{nm0}  {_vfmt(v0)}", ha="center", va="bottom", fontsize=23,
                color=TEXT, fontweight="bold", zorder=6, alpha=la,
                path_effects=_shadow())

    # --- ranked bar strip under the map: length IS the demonstration ---
    n = max(1, len(ranked))
    bax = fig.add_axes([0.08, 0.115, 0.84, (map_top - hf) - 0.145])
    bax.set_axis_off()
    # Bars run from the SMALLEST ranked value's floor so negative series
    # (e.g. growth rates) still read left-to-right; labels carry true values.
    floor = min(0.0, min(v for _, v in ranked)) if ranked else 0.0
    span = max(1e-9, (max(v for _, v in ranked) if ranked else 1.0) - floor)
    bax.set_xlim(0.0, span * 1.24)
    bax.set_ylim(n - 0.4, -0.85)             # rank 1 on top, host headroom
    bpos = bax.get_position()
    row_px = bpos.height * fh_in * fig.dpi / n
    blw = max(26.0, row_px * 0.42 * 72.0 / fig.dpi)
    specs = []
    for i, (nm, v) in enumerate(ranked):
        ri = max(0.0, min(1.0, (t - i * 0.07) / max(1e-6, 1.0 - i * 0.07)))
        col = cmap(norm(v))
        tip = max((v - floor) * ri, span * 0.02)
        _round_barh(bax, i, span * 1.02, blw, "#141B2E", zorder=2)
        _round_barh(bax, i, tip, blw, col, zorder=3)
        disp = nm if len(nm) <= 16 else nm[:15] + "…"
        bax.text(0.0, i - 0.33, f"{i + 1}. {disp}", ha="left", va="bottom",
                 fontsize=20, color=TEXT, fontweight="bold", zorder=4,
                 alpha=min(1.0, 0.35 + ri))
        if i == 0:
            # The host performs AT this tip — the value rides INSIDE the
            # bar so his body never covers the number.
            t2 = bax.text(tip - span * 0.015, i, _vfmt(v), ha="right",
                          va="center", fontsize=26, color="white",
                          fontweight="bold", zorder=4, alpha=la,
                          path_effects=_shadow())
        else:
            t2 = bax.text(tip, i, " " + _vfmt(v), ha="left", va="center",
                          fontsize=26, color=col, fontweight="bold", zorder=4,
                          alpha=la)
        specs.append((v, "art", t2, None))
    # THE HOST performs on the winning bar's tip — the contact the judge
    # praised — with the clamp keeping him off the map's markers above.
    if ranked:
        _act_g = _perf_action(insight, "rank")
        _bake_host(bax, max((ranked[0][1] - floor) * t, span * 0.02), 0,
                   _act_g, reveal,
                   zoom=0.78, align=_perf_align(_act_g, (0.28, 0.5)))
    insight.host_baked = True
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
        # COUPLE THE HOST: Data braces against the biggest row's advancing edge
        # and is shoved along as the row of icons outgrows him.
        _bake_host(ax, float(_mshown - 1), float(n - 1 - _mr),
                   "shoved_bar", reveal, zoom=1.0, align=(0.28, 0.5))
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
        # A waffle depicts SHARE — so the legend shows each item's % of the
        # total shown, not its raw value with a spurious '%' (that printed
        # '1425.9%' for absolute counts). For data already in percent that sums
        # to ~100 this is unchanged; for counts it normalises correctly.
        _share = abs(val) / tot * 100.0
        fig.text(0.635, yy, "■", color=col, fontsize=26, va="center")
        fig.text(0.675, yy + 0.005, lbl, color=TEXT, fontsize=23,
                 fontweight="bold", va="center")
        t2 = fig.text(0.675, yy - 0.045, f"{_share:.0f}%", color=col, fontsize=30,
                      fontweight="bold", va="center", alpha=la)
        specs.append((val, "art", t2, None))
        top -= 0.135
    # BAKE THE HOST: Data works the fill FRONTIER — he walks the grid stamping in
    # the next tile, so the waffle reads as HIS build (his x/y jumps to the last
    # lit cell each frame).
    _fi = max(0, min(99, lit - 1))
    _fr, _fc = divmod(_fi, 10)
    # COUPLE THE HOST: Data stands under the growing fill with arms pressed up on
    # its underside — the pile presses DOWN on him (buckle -> heave) as it fills.
    _bake_host(ax, float(_fc), float(9 - _fr),
               "hoist_stack", reveal, zoom=0.85, align=(0.5, 0.80))
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
    lw = _bar_lw(n, frac=0.72)
    # Taller axes that FILL the card so a few short bars don't leave the bottom
    # ~40% dead (empty_void). Thick bars (frac above) keep them from looking thin.
    ax = fig.add_axes([0.24, 0.10, 0.62, 0.72])
    ax.set_facecolor("none")
    # Faint vertical reference lines across the card so the space to the right of
    # short bars reads as chart, not void.
    for _gx in (0.25, 0.5, 0.75, 1.0):
        ax.axvline(vmax * _gx, color="#1E2A44", linewidth=1.2, zorder=0, alpha=0.7)
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
    # THE TOUR (see `_tour_index`): which bar he is shoving right now. Rows are
    # drawn y = n-1-i, so item `_row` sits at that y. He works up the field and
    # arrives at the winner for the finale instead of standing on the leader's
    # tip from the moment the race finishes drawing.
    _row = _tour_index(n)
    _ttip = max(_tour_tip(values, _row) * t, vmax * 0.02)
    # COUPLE THE HOST: Data braces against the bar's advancing right face
    # and is shoved along as it outgrows him (his left-side hands baked onto the
    # bar tip) — the bar drives him, not a sprite perched on the cap.
    _act_r = _perf_action(insight, "pictorial_race")
    _bake_host(ax, _ttip, n - 1 - _row, _act_r, reveal,
               zoom=1.0, align=_perf_align(_act_r, (0.28, 0.5)))
    insight.host_baked = True
    return ax, specs


def _story_stack(fig, plt, insight: Insight, subtitle: str, reveal: float = 1.0):
    """A single 100% STACKED COLUMN that grows bottom->top, each source a coloured
    segment sized to its share. Fills the tall 9:16 card (a vertical tower), and
    Data grips the TOP of the growing stack and is hauled UP as it rises — a
    vertical, clearly data-driven bit (the part-to-whole answer to the waffle)."""
    from matplotlib.patches import FancyBboxPatch
    items = _ordered_items(insight)[:6]
    vals = [max(0.0, p.value) for p in items]
    tot = sum(max(0.0, p.value) for p in insight.items) or 1.0   # of the WHOLE
    shares = [v / tot * 100.0 for v in vals]                     # (tail = a top gap)
    ax = fig.add_axes([0.10, 0.07, 0.80, 0.70])   # tops out below the heading so
    ax.set_xlim(0, 1); ax.set_ylim(0, 100)         # the top-gripping host clears it
    ax.set_axis_off()
    t = max(0.0, min(1.0, reveal))
    filled = t * 100.0
    palette = [HIGHLIGHT, ACCENT, WARN, "#A78BFA", "#F472B6", "#34D399"]
    cx0, cx1 = 0.20, 0.62                       # wider column (was a narrow strip)
    # Faint horizontal reference lines across the FULL card so the space beside
    # the tower reads as chart, not empty (empty_void).
    for _gy in (20, 40, 60, 80):
        ax.axhline(_gy, color="#1E2A44", linewidth=1.2, zorder=0, alpha=0.7)
    # GHOST the WHOLE tower (every segment, dim) from frame 1 so the early frames
    # carry the full shape instead of a near-empty column over dead navy
    # (empty_void). The bright fill rises over this preview.
    _gy = 0.0
    for i, (p, sh) in enumerate(zip(items, shares)):
        gcol = (HIGHLIGHT if p.label == insight.highlight_label
                else palette[i % len(palette)])
        ax.add_patch(FancyBboxPatch((cx0, _gy), cx1 - cx0, sh,
                     boxstyle="round,pad=0,rounding_size=1.4",
                     facecolor=gcol, edgecolor="none", alpha=0.16, zorder=1))
        gt = ax.text(cx1 + 0.03, _gy + sh / 2.0, f"{p.label}  {sh:.0f}%",
                     ha="left", va="center", fontsize=23, color=gcol,
                     fontweight="bold", zorder=2, alpha=0.22)
        _gy += sh
    specs, la = [], _lblalpha(reveal)
    y0, top_y = 0.0, 0.0
    for i, (p, sh) in enumerate(zip(items, shares)):
        col = (HIGHLIGHT if p.label == insight.highlight_label
               else palette[i % len(palette)])
        vis_top = min(y0 + sh, filled)
        if vis_top > y0 + 0.4:
            ax.add_patch(FancyBboxPatch((cx0, y0), cx1 - cx0, vis_top - y0,
                         boxstyle="round,pad=0,rounding_size=1.4",
                         facecolor=col, edgecolor=CARD, linewidth=2, zorder=3))
            top_y = vis_top
            if vis_top >= y0 + sh * 0.55:       # label once the segment is mostly in
                tt = ax.text(cx1 + 0.03, y0 + sh / 2.0,
                             f"{p.label}  {sh:.0f}%", ha="left", va="center",
                             fontsize=23, color=col, fontweight="bold",
                             zorder=5, alpha=la, path_effects=_shadow())
                specs.append((p.value, "art", tt, None))
        y0 += sh
    # COUPLE THE HOST: Data grips the top of the growing tower and is hauled up as
    # it stacks (vertical drag — a real bit, not a horizontal slide).
    _act_s = _perf_action(insight, "stack")
    _bake_host(ax, (cx0 + cx1) / 2.0, top_y, _act_s,
               reveal, zoom=0.92, align=_perf_align(_act_s, (0.5, 0.80)))
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
    # radius ~ sqrt(value) (area ∝ value)
    rraw = [_m.sqrt(v) for v in vals]
    gap = 4.0
    # LAY OUT ACROSS BOTH AXES, NOT JUST THE WIDTH.
    #
    # This packed every bubble into ONE row scaled to fit the WIDTH, in a
    # frame 1.15x TALLER than it is wide. With five items the row is already
    # 92% of the width, so the bubbles cannot grow — and the other 80%+ of
    # the frame stays empty. Measured on the final frame of the 2026-08-11
    # macao story, whose seg0 used exactly this:
    #
    #     items   ink coverage   frame height used
    #       5         8.7%            18.5%
    #       3        16.9%            31.4%
    #       2        27.7%            46.8%
    #
    # The showrunner's notes that day were "tiny bubbles in a mostly empty
    # frame", "a near-empty card with a flat bubble row" and "equal-size
    # blobs" — all three describing this. Four or more items now pack into
    # TWO staggered rows and scale to whichever of width/height binds first,
    # so the bubbles are as large as the frame allows.
    per_row = n if n <= 3 else (n + 1) // 2
    rows = [list(range(0, per_row)), list(range(per_row, n))]
    rows = [r for r in rows if r]

    # Solve the scale directly on each axis. GAPS DO NOT SCALE, so they come
    # out of the budget FIRST and only the circles divide what is left —
    # scaling the whole block instead silently shrinks every bubble.
    # Every row needs the label band UNDER it clear — the label sits 3.2
    # below the circle and a fontsize-22 line is ~3.3 units tall here, so
    # rows are separated by more than the in-row gap. At `gap` the top row's
    # labels landed 2.0 units inside the bottom row's circles.
    LABEL_BAND = 6.8
    row_gap = LABEL_BAND + 0.7
    avail_w = 100 - gap * 2
    avail_h = ymax - gap * 2 - LABEL_BAND
    scale_w = min(
        ((avail_w - gap * (len(row) - 1))
         / sum(2 * rraw[i] for i in row)) for row in rows)
    tall = sum(2 * max(rraw[i] for i in row) for row in rows)
    scale_h = ((avail_h - row_gap * (len(rows) - 1)) / tall
               if tall else scale_w)
    scale = max(0.0001, min(scale_w, scale_h))
    rad = [r * scale for r in rraw]
    row_h = [2 * max(rad[i] for i in row) for row in rows]
    block_h = sum(row_h) + row_gap * (len(rows) - 1)
    cy_top = ymax / 2 + block_h / 2.0
    specs = []
    # centre of each item, laid out row by row from the top of the block
    centres: list[tuple[float, float]] = [(0.0, 0.0)] * n
    _y = cy_top
    for ri, row in enumerate(rows):
        row_w = sum(2 * rad[i] for i in row) + gap * (len(row) - 1)
        _x = (100 - row_w) / 2.0
        cyr = _y - row_h[ri] / 2.0
        for i in row:
            centres[i] = (_x + rad[i], cyr)
            _x += 2 * rad[i] + gap
        _y -= row_h[ri] + row_gap
    cy = ymax / 2
    for i, (p, r) in enumerate(zip(items, rad)):
        cx, cy = centres[i]
        color = (HIGHLIGHT if p.label == insight.highlight_label
                 else WARN if (insight.baseline and p.label == insight.baseline.label)
                 else ACCENT)
        ax.add_patch(Circle((cx, cy), r * t, facecolor=color, edgecolor="white",
                            linewidth=1.5, alpha=0.92, zorder=3))
        fs = max(16, min(46, r * 2.0))
        # THE NUMBER RIDES THE BUBBLE, IT DOES NOT WAIT FOR IT.
        # `_lblalpha` holds every label at alpha 0 until 80% of the build,
        # which is right for a BAR — the label sits at the tip and lands as
        # the bar reaches it. A bubble's number sits at the CENTRE of a
        # circle that is on screen from frame one, so there is nothing to
        # land: on the hook beat, whose reveal curve does not pass 0.8 until
        # ~71% of a 20-second window, that left the values invisible for
        # fourteen seconds. The showrunner's note on 2026-08-11 was
        # "equal-size blobs that only reveal numbers at the very end".
        # Fade with the inflation instead, complete by a third of the way in.
        _balpha = max(0.0, min(1.0, (t - 0.05) / 0.28))
        tt = ax.text(cx, cy, _vfmt(p.value), ha="center", va="center",
                     color="#0B1020", fontsize=fs, fontweight="bold",
                     zorder=4, alpha=_balpha)
        ax.text(cx, cy - r - 3.2, p.label, ha="center", va="top", color=TEXT,
                fontsize=22, fontweight="bold", zorder=4, alpha=_balpha,
                path_effects=_shadow())
        specs.append((p.value, "art", tt, None))
        if i == 0:
            _star_top = (cx, cy + r * t)
    # COUPLE THE HOST: Data grips the TOP of the star (biggest) bubble and is
    # pushed UP as it inflates — contact + cause + consequence on the bubble.
    _act_bb = _perf_action(insight, "trend")
    _bake_host(ax, _star_top[0], _star_top[1], _act_bb,
               reveal, zoom=0.8, align=_perf_align(_act_bb, (0.5, 0.80)))
    insight.host_baked = True
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
    # Added 2026-09-04 after a shipped video captioned "SAN JOSE LEADS THE MAP"
    # over a map with no San Jose on it: a metro with no coordinate is dropped
    # from the plot while the heading still names it. Metro centres, which is
    # all a pin needs at national scale.
    "san jose": (-121.89, 37.34), "sacramento": (-121.49, 38.58),
    "riverside": (-117.40, 33.95), "san antonio": (-98.49, 29.42),
    "charlotte": (-80.84, 35.23), "columbus": (-82.99, 39.96),
    "indianapolis": (-86.16, 39.77), "kansas city": (-94.58, 39.10),
    "salt lake": (-111.89, 40.76), "st. louis": (-90.20, 38.63),
    "pittsburgh": (-79.996, 40.44), "baltimore": (-76.61, 39.29),
    "raleigh": (-78.64, 35.78), "cleveland": (-81.69, 41.50),
    "milwaukee": (-87.91, 43.04), "oklahoma city": (-97.52, 35.47),
    "boise": (-116.20, 43.62), "honolulu": (-157.86, 21.31),
    "anchorage": (-149.90, 61.22),
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
    # A map that can place only 40% of the points shows 40% of the story while
    # the heading speaks for all of it. If most metros cannot be pinned, a
    # ranking reads the data honestly and a map does not.
    if city_r >= 0.8:
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
    # PINS LAND ONE AT A TIME, in rank order, ending on the leader.
    #
    # They used to all appear together and grow on a single shared `t`: three
    # small dots swelling slightly on a dark map, then nothing for the rest of
    # the beat. It looked empty, it gave the viewer no reading order, and it
    # measured 4.2 effective fps against an 11.0 floor — the whole segment was
    # a near-still frame. Staggering costs nothing and fixes all three: each
    # pin pops with its label, the eye is led low-to-high, and the frame keeps
    # changing for the entire beat because something new keeps arriving.
    ordered = sorted(pts, key=lambda x: x[0].value)
    n_pins = max(1, len(ordered))
    # Occupied boxes in data coords. The host is baked at the winning pin and
    # is the biggest object on the map, so he is reserved FIRST — otherwise the
    # leader's label lands on him, which is the one label that matters most.
    _taken: list[tuple[float, float, float, float]] = []
    if pts:
        _wp, (_wlon, _wlat) = max(pts, key=lambda x: x[0].value)
        _taken.append((_wlon - 5.5, _wlat - 4.0, _wlon + 5.5, _wlat + 4.5))
    for i, (p, (lon, lat)) in enumerate(ordered):
        col = cmap(norm(p.value))
        # This pin's own progress. The whole stagger completes by 60% of the
        # beat, NOT at the end: the leader lands last, and the subtitle is
        # already claiming "SAN JOSE LEADS THE MAP" from frame one. Finishing
        # on the buzzer meant the beat ended with the leader still arriving and
        # the highest value ON SCREEN belonging to somebody else — the caption
        # and the picture disagreeing. Land them all early, then hold the
        # complete picture while the narration lands the point.
        tt = min(1.0, t / 0.6)
        ti = max(0.0, min(1.0, (tt - i / n_pins) * n_pins * 1.6))
        # a small overshoot so it LANDS rather than fading up
        pop = ti * (2.0 - ti)
        # floor the size well above the old 120: the smallest metro was a
        # speck at phone size, which is why the map read as three dots.
        r = (260 + 520 * norm(p.value)) * pop
        if r <= 0:
            continue
        ax.scatter([lon], [lat], s=r, color=col, edgecolors="white",
                   linewidths=1.8, zorder=4, alpha=0.95)
        # KEEP THE LABEL ON THE CARD. Centred on the pin, a west-coast metro
        # ran off the left edge and rendered as "eattle  6.8". Anchor the text
        # to the inside of the frame when the pin is near an edge.
        if lon < -114:
            ha, lx = "left", lon + 0.8
        elif lon > -76:
            ha, lx = "right", lon - 0.8
        else:
            ha, lx = "center", lon
        # DON'T STACK LABELS ON TOP OF EACH OTHER. The west coast puts San
        # Jose, Los Angeles and Seattle within a few degrees, and the host
        # stands on the leader's pin — so "San Jose 11.3" printed through
        # "Denver 5.4" and the host wore "Los Angeles 9.7" across his chest.
        # Nudge each label up the card until it clears everything already
        # placed (including the host's own box).
        text = f"{p.label.split(',')[0]}  {_vfmt(p.value)}"
        # Label extent in DEGREES, calibrated from the card's real geometry —
        # the first version guessed 0.62 deg/char and missed every collision,
        # because `set_aspect(1/cos(37))` compresses longitude: the axes box is
        # 0.92*SERIES_W*SERIES_DPI = 1012 px wide over 59 deg of longitude
        # (17.2 px/deg), while a 21pt glyph at this DPI is ~32 px tall and
        # ~17.6 px wide. So a character is a whole degree, not two thirds of
        # one, and a label is ~1.6 deg tall.
        w_deg = 1.02 * len(text)
        h_deg = 1.6
        x0 = lx if ha == "left" else (lx - w_deg if ha == "right"
                                      else lx - w_deg / 2)
        lift = 3.2 if (pts and p is max(pts, key=lambda x: x[0].value)[0]) else 1.4
        y = lat + lift
        for _ in range(8):
            box = (x0, y, x0 + w_deg, y + h_deg)
            if not any(box[0] < o[2] and o[0] < box[2]
                       and box[1] < o[3] and o[1] < box[3] for o in _taken):
                break
            y += h_deg + 0.5               # try the next line up
        _taken.append((x0, y, x0 + w_deg, y + h_deg))
        txt = ax.text(lx, y, text,
                      ha=ha, va="bottom", fontsize=21, color=TEXT,
                      fontweight="bold", zorder=6,
                      alpha=max(0.0, min(1.0, (ti - 0.25) / 0.5)),
                      path_effects=_shadow())
        specs.append((p.value, "art", txt, None))
    # FILL THE VOID WITH THE POINT, NOT WITH AIR. The US map is a wide shape
    # in a tall card, so once it fills the width there is a band of empty navy
    # above it — the "empty frame" the review gate keeps naming, and a third of
    # the screen saying nothing. Put the comparison the chart is actually
    # making there: leader vs the bottom of the same set, computed from the
    # plotted points so it can never disagree with the pins.
    if len(ordered) >= 2:
        _lo_p, _hi_p = ordered[0][0], ordered[-1][0]
        if _lo_p.value > 0:
            _ratio = _hi_p.value / _lo_p.value
            _line = (f"{_hi_p.label.split(',')[0]} costs {_ratio:.1f}x "
                     f"{_lo_p.label.split(',')[0]}")
            # Sits just under the subtitle, ABOVE the band that punch-in
            # shots crop away (studio_render._punch_crop's head guard) — a
            # close-up must not show half of this line.
            fig.text(0.5, 0.775, _line, ha="center", va="center",
                     fontsize=30, color=TEXT, fontweight="bold",
                     # early enough to be READ during the wide shots,
                     # before the closing card takes the top of the frame
                     alpha=max(0.0, min(1.0, (t - 0.18) / 0.22)),
                     path_effects=_shadow())

    # THE LEADER KEEPS BEING MARKED after the pins have all landed.
    #
    # The stagger deliberately finishes by 60% of the beat so the leader is up
    # while the narration makes its point — but that left the last 40% of the
    # build as identical frames, and with the beat's final shot sitting on this
    # card that measured as a 3.0s frozen stretch (73 frames against a ceiling
    # of 45). This ring grows from the moment the last pin lands until the beat
    # ends: one slow, one-way expansion that says "this is the one", so the
    # frame keeps changing because something is still being SAID, not because
    # the camera is moving.
    if pts:
        _lp, (_llon, _llat) = max(pts, key=lambda x: x[0].value)
        _rt = max(0.0, min(1.0, (t - 0.55) / 0.45))
        if _rt > 0:
            for _k in range(2):
                _grow = _rt + _k * 0.35
                if _grow > 1.0:
                    continue
                ax.scatter([_llon], [_llat],
                           s=900 + 5200 * _grow, facecolors="none",
                           edgecolors=cmap(norm(_lp.value)),
                           linewidths=max(0.6, 3.2 * (1.0 - _grow)),
                           alpha=max(0.0, 0.55 * (1.0 - _grow)), zorder=3)

    # THE HOST performs at the WINNING metro's pin (clamped on-card) — this
    # beat used to have no bake at all, so the drifting overlay covered it.
    if pts:
        top_p, (tlon, tlat) = max(pts, key=lambda x: x[0].value)
        _act_c = _perf_action(insight, "rank")
        _bake_host(ax, tlon, tlat, _act_c, reveal,
                   zoom=0.62, align=_perf_align(_act_c, (0.5, 0.04)))
    insight.host_baked = True
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
    # AUTO-ROUTING to frame-filling, mascot-coupled kinds. A scene-plan override
    # (state/scene_plans/{slug}.json, written by the scene repair loop) sets
    # plan_locked and SKIPS this — a deliberately chosen scene variant renders
    # exactly as planned.
    if not getattr(insight, "plan_locked", False):
        # A square waffle can't fill the tall 9:16 card (empty_void) and its
        # zig-zag frontier gives the mascot no clean travel. A vertical STACKED
        # COLUMN fills the tower, shows the same part-to-whole, and couples
        # VERTICALLY (Data hauled up the stack).
        if insight.kind in ("waffle_grid", "share"):
            insight.kind = "stack"          # any item count — stack takes 6
        # A pictograph reveals icons one cell at a time — a discrete ~3fps fill
        # that dragged carbon to tcraft=1. A race shows the same ranking with
        # smooth grow + the shoved_bar coupling.
        if insight.kind == "pictograph":
            insight.kind = "pictorial_race"
        # A 2-value split reads badly as a horizontal race (mascot slides). Send
        # it to VERTICAL versus columns where Data is hauled UP the winning
        # column — a distinct vertical bit that keeps a story from becoming
        # stack+stack (the monotony that reads as 'same pose twice').
        if insight.kind in ("pictorial_race", "rank") and \
                len(insight.items) == 2:
            insight.kind = "comparison"
    star = insight.items[0]
    if insight.kind == "geo_city":
        low = "lowest" in insight.main_insight.lower()
        # NAME A METRO THAT IS ACTUALLY ON THE MAP. `star` is the top item of
        # the DATASET, but the renderer can only pin a metro it has a
        # coordinate for — so a dropped leader shipped "San Jose leads the
        # map" over a map whose highest pin was Los Angeles. Adding the
        # coordinate fixes that case; this makes the class of bug impossible,
        # because the caption now defers to what actually gets drawn.
        placed = [p for p in insight.items if _metro_coord(p.label)]
        if placed:
            shown = (min(placed, key=lambda q: q.value) if low
                     else max(placed, key=lambda q: q.value))
        else:
            shown = star
        _heading(fig, insight.topic, f"{shown.label.split(',')[0]} "
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
    elif insight.kind == "stack":
        _tot = sum(abs(p.value) for p in insight.items) or 1.0
        subtitle = f"{star.label} is {abs(star.value) / _tot * 100:.0f}% of the whole"
        _heading(fig, insight.topic, subtitle)
        ax, specs = _story_stack(fig, plt, insight, subtitle, reveal)
    elif insight.kind == "waffle_grid":
        _tot = sum(abs(p.value) for p in insight.items) or 1.0
        subtitle = f"{star.label} is {abs(star.value) / _tot * 100:.0f}% of the whole"
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
                       frames: int = 60, full_by: float = 1.0,
                       hook_lead: bool = False):
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
    grip_path: list = []               # attachment record, one entry per frame
    for f in range(1, frames + 1):
        # LINEAR reveal (constant velocity). The old ease-out front-loaded the
        # growth and left the last ~1s of every card build near-frozen — that
        # frozen tail is what the temporal grade caught as duplicate frames /
        # low effective fps. Linear keeps the chart MOVING to the final frame,
        # which lands on the exact static chart so the rings still anchor.
        r = min(1.0, (f / frames) / max(0.05, full_by))
        if hook_lead:
            # HOOK BURST: the opening chart shoots up FAST in the first ~22% of the
            # beat (frame 1 is already big motion + the coupled mascot in action —
            # not a slow build the gate dings), then eases to a steady draw. Still
            # ends on the exact static chart; still never freezes (0.7x tail moves).
            hf = f / frames
            r = (hf / 0.22) * 0.46 if hf < 0.22 else 0.46 + (hf - 0.22) / 0.78 * 0.54
        if f == frames:
            r = 1.0                         # final frame == static chart
        # THE TOUR is BEAT PROGRESS, not reveal — that is the whole point.
        # `r` saturates at `full_by` and then sits at 1.0, so anything derived
        # from it stops moving for the rest of the beat; `_TOUR` keeps running
        # to 1.0 so the host still has somewhere to be at second twelve.
        global _TOUR
        _TOUR = f / max(1, frames)
        _ATTACH_FRAME.clear()
        fig, plt = _card_base()
        ax, specs = _compose_story(fig, plt, insight, r)
        if _ATTACH_FRAME:
            grip_path.append({"f": f, **_ATTACH_FRAME[-1]})
        if f == frames:
            anchors = _anchors_from(fig, ax, specs)
        fig.savefig(out_dir / f"{slug}_build{f:02d}.png", transparent=True)
        plt.close(fig)
    # ATTACHMENT SIDECAR: which object Data grips, his full grip motion path,
    # the directed performance, and the scene timeline — the scene's plan-of-
    # record for the manifest, benchmark validator and repair loop.
    try:
        import json as _json
        from . import scene_timeline as _tl
        perf = dict(_LAST_PERF)
        attach = {"slug": slug, "kind": insight.kind,
                  "performance": perf, "grip_path": grip_path,
                  "contact_frames": len(grip_path), "frames": frames,
                  "timeline": _tl.plan_scene(insight.kind,
                                             perf.get("action", ""),
                                             frames / 30.0,
                                             perf.get("target", ""),
                                             perf.get("goal", ""))}
        (out_dir / f"{slug}_attach.json").write_text(_json.dumps(attach))
    except Exception:  # noqa: BLE001 — sidecar must never kill a render
        pass
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
