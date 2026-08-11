"""chart_race — animated multi-series line-chart race (graphfather style).

Shared engine: any channel can hand it a spec and get back a silent
portrait mp4 of lines growing over time with tip dots, tip labels, a live
leaderboard, a climbing year counter, and a dynamic "camera" y-axis that
zooms out as the data grows. Audio (music/VO) is the caller's job — mux it
on top of the silent render.

Each series can carry an ICON so viewers know who's who without decoding
colours: a country code / flag emoji / brand name / image URL, resolved by
funnel.series_icons. When nothing resolves (or the funnel is unreachable)
the engine draws a deterministic initials badge instead — icons never
block a render.

Spec (same shape as the trending channel's graph_race package):
  {"title": "Staffed Lighthouses by Country Since 1900",
   "y_label": "Staffed lighthouses", "source": "Sources: ...",
   "years": [1900, 1920, ..., 2020],
   "series": [{"name": "USA", "color": "#4a90e2", "icon": "US",
               "values": [...]}, ...],
   "duration": 12, "hook": "Wait for 1990..."}   # hook + icon optional
Colors are optional — a curated palette fills gaps deterministically.

The KEY (icon + name + value per series) is parked in the dead band
between the title and the plot, and the title is measured + wrapped to fit
the frame, so neither can ever cover the lines or run off-screen.

`assess(spec)` scores DATA DRAMA (magnitude + movement) and callers should
gate on it before rendering: small, slow, flat numbers make a boring
video, and a single-series chart is not a race at all (see MIN_SERIES /
MIN_PEAK / MIN_SWING). Units are normalized first, so a spec
written as 11.5 with y_label "EVs sold (millions)" both renders as
"11.5M" and is judged on its real magnitude — see `normalize()`.

Contract (engines/__init__.py): available() is offline; maybe_chart_race()
returns a Path or None, never raises; nothing here mutates repo state.
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from shared import camera_float                                    # noqa: E402
from shared.fit_title import fit_title                              # noqa: E402

FPS = 24
HOLD_S = 1.4                 # hold the finished chart at the end
HOOK_S = 1.6                 # optional hook text fades out over this window
PING_S = 0.9                 # leader-tip ring: one expand-and-fade cycle
PALETTE = ["#4a90e2", "#e74c3c", "#f5c518", "#2ecc71",
           "#9b59b6", "#e67e22", "#1abc9c", "#fd79a8"]
_FONT = str(Path(__file__).resolve().parent.parent / "assets" / "fonts"
            / "Anton-Regular.ttf")

# ---- DATA DRAMA BAR (the "bigger numbers are better" rule) -------------
# A race is only worth watching if the numbers are BIG and they MOVE.
#
# "Big" is about what's ON SCREEN, so units are normalized first: an
# author writing 11.5 with y_label "EVs sold (millions)" becomes
# 11,500,000 and renders as "11.5M". Small-but-correct unit choices are
# therefore not punished — only genuinely trivial magnitudes are.
#
# "Moves" is the hard gate: the biggest swing (peak/trough, in EITHER
# direction — a 600 -> 1 collapse is as dramatic as 1 -> 600) must clear
# MIN_SWING, or MIN_SWING_CROSSOVER when the lead actually changes hands.
MIN_SERIES = 2             # a one-line chart is not a race
MIN_PEAK = 50.0            # post-normalization; catches 0-10 index data
# RAISED 3.0 -> 5.0 on 2026-08-05, from measurement rather than taste.
#
# Four of that day's charts were rendered and measured against the
# showrunner's motion floor. The swing of the biggest-moving series
# predicted the result almost perfectly:
#
#     bald eagles   171x swing  -> 13.7 effective fps   PASS
#     Dow           4.2x swing  -> 13.1 fps, duplicate ratio 0.453 (ceiling
#                                  0.45) — marginal
#     cocoa         3.3x swing  -> 6.6 fps               well under the floor
#
# A 3.3x swing spread over seven points and thirteen seconds moves the line
# a couple of pixels per frame: technically "dramatic", visually a still
# image. No amount of renderer work fixes that — the fault is upstream, in
# data that was never going to make a watchable race.
#
# This is a gate getting STRONGER, which is always allowed, and it is only
# affordable because a refused slot is now re-authored rather than lost
# (`run_trending_daily._backfill`). Calibrated on four samples: revisit as
# more accumulate.
MIN_SWING = 5.0
CROSSOVER_SWING = 1.6
SWING_CAP = 999.0        # a series touching 0 is an infinite ratio

# A series whose whole range is within this fraction of its own peak is a
# REFERENCE LINE, not a competitor — "2018-2022 average", "target", "break
# even". It is drawn, but it can never take the lead, so a moving line
# crossing it is not a lead change.
#
# This closes a real loophole. On 2026-08-05 the cocoa chart paired a moving
# price with a flat 2423 baseline; the price crossed it twice, `crossovers`
# read 2, and the spec was granted the lenient 1.6x bar with a swing of only
# 3.3x. It rendered at 6.6 effective fps — half the showrunner's floor. The
# lenient bar exists because two competitors trading the lead is dramatic
# even when neither moves much; one line drifting past a constant is not
# that, and must be held to the full MIN_SWING.
FLAT_SERIES_TOL = 0.02

# Multipliers detected in y_label/title (or set explicitly via
# spec["unit_scale"]). Longest match wins, so "billion" beats "bn".
_UNIT_WORDS = [
    ("trillions", 1e12), ("trillion", 1e12),
    ("billions", 1e9), ("billion", 1e9), ("bn", 1e9),
    ("millions", 1e6), ("million", 1e6), ("mn", 1e6),
    ("thousands", 1e3), ("thousand", 1e3),
]

# Icon sizes in px (portrait 1080x1920). Leaderboard icons stay small
# so they never crowd the rank + name text beside them.
TIP_ICON_PX = 40
TIP_ICON_MAX_W = 92        # wordmarks are wide — cap so they don't sprawl
BOARD_ICON_PX = 24
BOARD_ICON_MAX_W = 52

# Rough advance width of the tip label's 15pt bold face, in px. Only used to
# decide which SIDE of the tip the label goes on, so an approximation is
# fine and far cheaper than measuring text on every frame.
TIP_LABEL_PX_PER_CHAR = 9.4

# Vertical layout in figure fractions. The key lives in the dead band
# between the title and the plot, so it can never cover the lines.
TITLE_TOP = 0.965          # title grows DOWNWARD from here (va="top")
KEY_TOP = 0.855
KEY_STEP = 0.030           # 4 series -> lowest row 0.765, plot top 0.74
KEY_X_ICON = 0.155
KEY_X_NAME = 0.225
KEY_X_VALUE = 0.90

# Plot rect in figure fractions. The top is computed per render (it hangs
# under the measured title + key), the rest is fixed. Widened and dropped on
# 2026-08-05: the old [0.13, 0.30, 0.82, ...] left a quarter of a portrait
# frame as dead black band between the plot floor and the year counter, and
# a chart that fills less of the screen moves fewer pixels per frame — which
# is literally what the showrunner's motion floor measures.
AX_LEFT = 0.10
AX_BOTTOM = 0.205
AX_WIDTH = 0.87


def _race_ease(p: float) -> float:
    """Timeline easing for a RACE: move immediately, land softly.

    This used to be a smoothstep (`p*p*(3-2p)`) — an ease-IN-out, slope zero
    at BOTH ends — so the chart stood still through the opening seconds and
    again through the finish. On
    2026-08-05 that put three of four graph races under the showrunner's
    motion floor, and measuring proved the gate right: the first three
    seconds moved by a max block-diff of 1.3 against a threshold of 6.0.

    The opening of a Short is the entire hook. A chart that has not moved by
    second three has been scrolled past. Near-linear for the first 80% (a
    race advances at a steady rate). Measured, in this order: ease-in-out
    5.7 effective fps, cubic ease-out 8.1 (it reached 87% of the data by
    halfway then sat for five seconds), an 80/20 linear-then-landing 12.0
    (still a 1.4s freeze at t=11s where the landing began), and finally
    LINEAR — because the end-hold's winner animation is the landing beat,
    so the timeline has no reason to decelerate at all.
    """
    return p


def _is_ratio(spec: dict) -> bool:
    """Percent/share metrics top out near 100 by definition, so the
    magnitude floor doesn't apply to them."""
    blob = f"{spec.get('y_label', '')} {spec.get('title', '')}".lower()
    return ("%" in blob or "percent" in blob or "share" in blob
            or "per capita" in blob or "rate" in blob)


def unit_scale(spec: dict) -> tuple[float, str]:
    """Detect the unit multiplier hiding in the label. Returns
    (factor, cleaned_label). "EVs sold (millions)" -> (1e6, "EVs sold").

    Rendering 11.5 as "11.5M" is the whole point of the bigger-is-better
    rule, and the cleaned label is REQUIRED for correctness: leaving
    "(millions)" on an axis that now reads 11.5M would say 11.5M million.
    """
    label = spec.get("y_label", "") or ""
    explicit = spec.get("unit_scale")
    if explicit:
        try:
            return float(explicit), label
        except (TypeError, ValueError):
            return 1.0, label
    if _is_ratio(spec):
        return 1.0, label
    low = label.lower()
    for word, factor in _UNIT_WORDS:
        if not re.search(rf"\b{word}\b", low):
            continue
        # Case 1: the unit sits in a parenthetical — "revenue ($ billions)".
        # Rewrite the whole group so no "($" fragment survives; a bare
        # currency symbol is worth keeping ("revenue ($)").
        def _fix_group(m: re.Match) -> str:
            inner = re.sub(rf"\b{word}\b", "", m.group(1), flags=re.I)
            inner = inner.replace(",", " ").strip(" -")
            return f"({inner})" if inner else ""

        cleaned, n = re.subn(rf"\(([^)]*\b{word}\b[^)]*)\)", _fix_group,
                             label, flags=re.I)
        if not n:
            # Case 2: bare prefix/suffix — "Millions of EVs sold".
            cleaned = re.sub(rf"\b{word}\b(\s+of)?", "", label, flags=re.I)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,-")
        return factor, cleaned or label
    return 1.0, label


def normalize(spec: dict) -> dict:
    """Copy of `spec` with unit-scaled values and a de-scaled y_label, so
    the chart shows the biggest truthful numbers it can. Idempotent for
    specs with no unit hint."""
    factor, label = unit_scale(spec)
    if factor == 1.0:
        return spec
    out = dict(spec)
    out["y_label"] = label
    out["series"] = [dict(s, values=[v * factor for v in s["values"]])
                     for s in spec["series"]]
    out["unit_scale"] = 1.0        # already applied — never scale twice
    return out


def is_reference_line(values) -> bool:
    """True when a series is scenery rather than a competitor.

    A baseline, target or long-run average is legitimate to plot — it gives
    the moving line something to be measured against — but it cannot race.
    Treating a moving line crossing it as a "lead change" hands the spec the
    lenient CROSSOVER_SWING bar it has not earned.
    """
    vals = list(values or [])
    if not vals:
        return True
    hi, lo = max(vals), min(vals)
    if hi <= 0:
        return True
    return (hi - lo) <= FLAT_SERIES_TOL * hi


CREDIT_MAX_CHARS = 78


def credit_line(source: str) -> str:
    """Condense a provenance blob into ONE readable on-screen credit.

    Specs carry full provenance — publisher, dataset, survey years, release
    notes — and that is right: it is what makes a claim checkable. Printed
    verbatim it was three wrapped lines of 11px grey at the bottom of the
    frame, illegible at phone size and reading as visual noise on a chart
    whose whole job is to look clean.

    Nothing is lost: `run_trending_daily._description` puts the FULL source
    string in the video description, which is where attribution is actually
    legible and where a viewer can copy a link. On screen we show the
    publisher(s) only.
    """
    s = re.sub(r"\s+", " ", str(source or "")).strip()
    if not s:
        return ""
    s = re.sub(r"^sources?\s*:\s*", "", s, flags=re.I)
    # Publishers are the leading fragment(s) before the first detail clause.
    # Splitting on ';' then ',' keeps "U.S. Fish & Wildlife Service" whole
    # while dropping "nesting-pair counts for the lower 48 states (1963 ...".
    head = s.split(";")[0]
    head = re.split(r",\s*(?=[a-z0-9])", head)[0]     # drop lowercase clauses
    head = head.strip(" .,;—-")
    if len(head) > CREDIT_MAX_CHARS:
        head = head[:CREDIT_MAX_CHARS - 1].rstrip(" .,;—-") + "…"
    return f"Source: {head}" if head else ""


def assess(spec: dict) -> dict:
    """Score a spec's DATA DRAMA (after unit normalization). Returns
    {ok, peak, swing, crossovers, reasons[]}. `ok` is False when the
    numbers are too trivial or too flat to carry a video."""
    spec = normalize(spec)
    series = spec.get("series") or []
    if not series or not spec.get("years"):
        return {"ok": False, "peak": 0.0, "swing": 0.0, "crossovers": 0,
                "reasons": ["no series/years"]}

    reasons: list[str] = []
    # A single line is not a race — there is nobody to beat, so there is no
    # reason to keep watching. Operator ruling: always at least 2 things.
    if len(series) < MIN_SERIES:
        reasons.append(f"only {len(series)} series — a race needs at least "
                       f"{MIN_SERIES} things to compare")
    peak = max(max(s["values"]) for s in series)
    # biggest peak-to-trough swing across the series — direction agnostic.
    # A series touching 0 is an infinite ratio; report it as the cap
    # (SWING_CAP) rather than a nonsense 1000000x.
    swing = 0.0
    for s in series:
        hi, lo = max(s["values"]), min(s["values"])
        if hi <= 0:
            continue
        swing = max(swing, min(hi / max(abs(lo), hi / SWING_CAP), SWING_CAP))

    # lead changes: how many times the top-ranked series swaps — counting
    # ONLY swaps between two series that actually move. A flat reference
    # line is scenery; a price drifting past it is not a race (see
    # FLAT_SERIES_TOL).
    order = [max(range(len(series)), key=lambda i: series[i]["values"][t])
             for t in range(len(spec["years"]))]
    moving = [not is_reference_line(s["values"]) for s in series]
    swaps = [(a, b) for a, b in zip(order, order[1:]) if a != b]
    crossovers = sum(1 for a, b in swaps if moving[a] and moving[b])
    scenery = len(swaps) - crossovers

    need = CROSSOVER_SWING if crossovers else MIN_SWING
    if peak < MIN_PEAK and not _is_ratio(spec):
        reasons.append(f"peak {peak:g} < {MIN_PEAK:g} — numbers too small to "
                       f"feel big on screen (scale the metric up, or pick a "
                       f"bigger one)")
    if swing < need:
        why = ""
        if not crossovers:
            why = (" and nobody ever takes the lead"
                   if not scenery else
                   f" and the {scenery} lead change(s) are only a line "
                   f"crossing a flat reference series, which is scenery, "
                   f"not a race")
        reasons.append(f"biggest swing {swing:.1f}x < {need:g}x — the lines "
                       f"barely move{why}")
    return {"ok": not reasons, "peak": peak, "swing": round(swing, 2),
            "crossovers": crossovers, "reasons": reasons}


def _fmt_compact(v: float) -> str:
    """1234 -> '1,234', 12400 -> '12.4K', 3400000 -> '3.4M'."""
    a = abs(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            s = f"{v / div:.1f}".rstrip("0").rstrip(".")
            return s + suf
    return f"{int(round(v)):,}"


def _initials(name: str) -> str:
    """Offline icon fallback text: 'United States' -> 'US', 'Netflix' -> 'NE'."""
    words = [w for w in re.split(r"[\s\-/]+", name.strip()) if w]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return (name.strip()[:2] or "?").upper()


def _icon_zoom(arr, target_h: float, max_w: float | None = None) -> float:
    """Scale factor for `arr` at ~target_h tall, capped so a very wide
    wordmark ("ANTHROPIC" at 160x18) doesn't sprawl across the chart."""
    shape = getattr(arr, "shape", None)
    if not shape or len(shape) < 2 or not shape[0]:
        return 1.0
    h, w = float(shape[0]), float(shape[1])
    zoom = target_h / h
    if max_w and w * zoom > max_w:
        zoom = max_w / w
    return zoom


def _icon_width(arr, target_h: float, max_w: float | None = None) -> float:
    """On-screen width in px at the same scale `_icon_zoom` would pick —
    the tip label has to clear the icon, and flags/wordmarks are wide."""
    shape = getattr(arr, "shape", None)
    if not shape or len(shape) < 2 or not shape[0]:
        return target_h
    return float(shape[1]) * _icon_zoom(arr, target_h, max_w)


def _fit_title(fig, text: str, font_path: str | None, max_w_px: float,
               max_lines: int = 2, hi: int = 46, lo: int = 26):
    """Wrap + auto-shrink a title so it NEVER runs off frame.

    The implementation moved to `shared/fit_title.py` when the explainer
    turned out to need the identical thing and had been guessing font size
    from the character count instead — shipping "a headline clipped off the
    right edge" (the showrunner's words, 2026-08-11). This delegates with
    the same defaults, and `tests/test_fit_title.py` holds the shared
    version against the original code kept verbatim as an oracle.
    """
    return fit_title(fig, text, font_path, max_w_px,
                     max_lines=max_lines, hi=hi, lo=lo)


def _spread(pos: list[float], min_sep: float, floor: float,
            ceil: float) -> list[float]:
    """Push a descending list of label positions apart by at least
    `min_sep`, preserving order, keeping the block inside [floor, ceil].
    Labels sit on their true value whenever there is room."""
    out: list[float] = []
    for v in pos:
        out.append(v if not out else min(v, out[-1] - min_sep))
    if out and out[-1] < floor:
        shift = floor - out[-1]
        out = [min(p + shift, ceil) for p in out]
        for i in range(1, len(out)):        # re-assert spacing after clamp
            out[i] = min(out[i], out[i - 1] - min_sep)
    return out


def _interp(years, values, x):
    if x <= years[0]:
        return values[0]
    for i in range(1, len(years)):
        if x <= years[i]:
            y0, y1 = years[i - 1], years[i]
            t = (x - y0) / (y1 - y0) if y1 != y0 else 0.0
            return values[i - 1] + t * (values[i] - values[i - 1])
    return values[-1]


def render(spec: dict, out: str | Path, *,
           size: tuple[int, int] = (1080, 1920), fps: int = FPS) -> Path:
    """Render the race to a SILENT h264 mp4. Raises on failure."""
    import os
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import matplotlib.image as mpimg
    from matplotlib.offsetbox import AnnotationBbox, OffsetImage
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    W, H = int(size[0]), int(size[1])
    # biggest truthful numbers on screen: 11.5 "(millions)" -> 11.5M
    spec = normalize(spec)
    duration = float(spec.get("duration") or 12.0)
    title = spec.get("title", "")
    y_label = spec.get("y_label", "")
    source = spec.get("source", "")
    credit = credit_line(source)
    hook = (spec.get("hook") or "").strip()
    years = [float(y) for y in spec["years"]]
    series = [dict(s) for s in spec["series"]]
    for i, s in enumerate(series):
        s.setdefault("color", PALETTE[i % len(PALETTE)])
    global_max = max(max(s["values"]) for s in series)

    # Icons: resolved ONCE up front (network, best-effort). A miss just
    # means that series gets the offline initials badge instead.
    icons: dict[str, object] = {}
    if spec.get("icons", True):
        try:
            from funnel import series_icons
            for name, path in series_icons.resolve_many(
                    series, context=title).items():
                try:
                    icons[name] = mpimg.imread(str(path))
                except Exception:  # noqa: BLE001
                    continue
        except Exception as e:  # noqa: BLE001
            print(f"[chart_race] icons unavailable ({type(e).__name__}: {e}) "
                  f"— using initials badges")

    have_font = os.path.exists(_FONT)
    year_font = fm.FontProperties(fname=_FONT, size=96) if have_font \
        else fm.FontProperties(weight="bold", size=84)
    hook_font = fm.FontProperties(fname=_FONT, size=54) if have_font \
        else fm.FontProperties(weight="bold", size=48)

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="chartrace_"))
    frames_dir = workdir / "frames"
    frames_dir.mkdir()
    try:
        n_frames = int(duration * fps)
        hold = int(fps * HOLD_S)
        dpi = 100
        # one persistent figure — creating/destroying ~300 figures dominates
        # render time otherwise
        fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi)
        fig.patch.set_facecolor("#000000")
        ax = fig.add_axes([AX_LEFT, AX_BOTTOM, AX_WIDTH, 0.565])
        # Fit the title ONCE (measuring costs a canvas draw), not per frame.
        fig.canvas.draw()
        # Plot width in px — fixed for the whole render, so measure it here
        # and not 345 times. Drives the tip-label side flip below.
        ax_w_px = float(ax.get_window_extent().width)
        title_text, title_font = _fit_title(
            fig, title, _FONT if have_font else None, max_w_px=W * 0.92)

        # ADAPTIVE VERTICAL LAYOUT. A 1-line title leaves room a 2-line one
        # doesn't, and 4 series need a taller key than 2 — so measure the
        # real title block, hang the key under it, and shrink the plot to
        # whatever is left. Nothing can then collide at any title length.
        key_top = KEY_TOP
        try:
            probe = fig.text(0.5, TITLE_TOP, title_text, ha="center",
                             va="top", fontproperties=title_font,
                             linespacing=1.15)
            renderer = fig.canvas.get_renderer()
            key_top = probe.get_window_extent(renderer).y0 / H - 0.025
            probe.remove()
        except Exception:  # noqa: BLE001 — fall back to the static constant
            pass
        key_bottom = key_top - KEY_STEP * max(0, len(series) - 1)
        ax_top = max(0.45, key_bottom - 0.035)
        # NOTE: this overrides the rect passed to `add_axes` above, so the
        # plot geometry is defined HERE and only here. A 2026-08-05 change
        # to the `add_axes` call alone did nothing for exactly that reason.
        ax.set_position([AX_LEFT, AX_BOTTOM, AX_WIDTH, ax_top - AX_BOTTOM])
        cam_top = 0.0            # dynamic y "camera": only ever zooms out
        extra: list = []         # per-frame figure-level artists to recycle
        print(f"[chart_race] {n_frames + hold} frames @ {W}x{H}")
        for f in range(n_frames + hold):
            p = _race_ease(min(1.0, f / max(1, n_frames - 1)))
            cur = years[0] + p * (years[-1] - years[0])
            in_hold = f >= n_frames
            # Progress through the end-hold, 0..1 — drives the winner's
            # landing animation below so the payoff is never a frozen frame.
            hp = ((f - n_frames) / max(1, hold - 1)) if in_hold else 0.0

            ax.clear()
            for t in fig.texts[:]:
                t.remove()
            # figure-level artists (leaderboard icons) aren't covered by
            # ax.clear() / fig.texts — drop last frame's explicitly
            for a in extra:
                a.remove()
            extra = []
            ax.set_facecolor("#000000")
            fig.text(0.5, TITLE_TOP, title_text, color="white",
                     ha="center", va="top", fontproperties=title_font,
                     linespacing=1.15)

            tips = []
            for s in series:
                vals = s["values"]
                xs = [y for y in years if y <= cur] + [cur]
                ys = [vals[i] for i, y in enumerate(years) if y <= cur]
                cv = _interp(years, vals, cur)
                ys = ys + [cv]
                tips.append((cv, s, xs, ys))
            tips.sort(key=lambda t: -t[0])

            for rank, (cv, s, xs, ys) in enumerate(tips):
                lw = 9 if rank == 0 else 7
                ax.plot(xs, ys, color=s["color"], linewidth=lw,
                        solid_capstyle="round", zorder=3)
                ax.plot([cur], [cv], "o", color=s["color"],
                        markersize=16 if rank == 0 else 13, zorder=4,
                        markeredgecolor="white", markeredgewidth=1.4)
                # THE PING. A ring expands out of the leader's tip and fades,
                # once every PING_S. It reads as live data, and it is the
                # only motion source in the frame that does not depend on
                # the DATA moving — which matters because the showrunner
                # measures motion on a 192px downscale of the frame.
                #
                # An earlier attempt breathed the tip MARKER instead
                # (16px +/- 28%). Measured: no change at all. At 192px a
                # 16px dot is under 3px and a 28% wobble is sub-pixel — it
                # was invisible to the metric and very nearly to the eye.
                # A ring sweeping 20 -> 78px covers ~10px at sample scale,
                # which is most of a measurement block.
                if rank == 0:
                    ring = (f % max(1, int(fps * PING_S))) / (fps * PING_S)
                    ax.plot([cur], [cv], "o", markersize=20 + 58 * ring,
                            markerfacecolor="none", markeredgecolor=s["color"],
                            markeredgewidth=2.6, alpha=0.6 * (1.0 - ring) ** 2,
                            zorder=3.5)

            cam_top = max(cam_top, max(t[0] for t in tips) * 1.22,
                          global_max * 0.12)
            ax.set_xlim(years[0], years[-1])
            ax.set_ylim(0, cam_top)
            ax.set_ylabel(y_label, color="#9aa4b2", fontsize=15)
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda v, _: _fmt_compact(v)))
            ax.xaxis.set_major_locator(MaxNLocator(5, integer=True))
            ax.xaxis.set_major_formatter(
                FuncFormatter(lambda v, _: str(int(round(v)))))
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)
            for spine in ("left", "bottom"):
                ax.spines[spine].set_color("#3a4252")
            ax.tick_params(colors="#9aa4b2", labelsize=14)
            ax.grid(axis="y", color="#141a26", linewidth=1)

            # Tip icon + value label, at DE-CLUTTERED y positions: when the
            # lines converge (everyone collapsing to near-zero) the raw tip
            # values pile on top of each other. The dot stays on the true
            # value; the icon+label pair slides to a spread slot, keeping
            # rank order. Floored just above the axis so nothing lands on
            # the x tick labels.
            placed = _spread(pos=[t[0] for t in tips],
                             min_sep=cam_top * 0.058,
                             floor=cam_top * 0.045, ceil=cam_top * 0.98)
            for rank, (cv, s, _xs, _ys) in enumerate(tips):
                ly = placed[rank]
                art = icons.get(s["name"])
                label = f"{s['name']}  {_fmt_compact(cv)}"
                iw = 0.0 if art is None else _icon_width(art, TIP_ICON_PX,
                                                         TIP_ICON_MAX_W)
                off = 8 if art is None else iw + 16
                # Flip the icon+label to the LEFT of the tip once they would
                # not fit to its right. This used to be one shared
                # `cur > 82% of the span` flag, which is wrong twice over: it
                # ignores how WIDE the label is, and it flips every series at
                # once. A 30-character series name ran off the right edge for
                # seconds before the flag tripped — visible in the 2016 frame
                # of the disaster-costs chart as "Disaster cost that".
                span = (years[-1] - years[0]) or 1.0
                avail = (1.0 - (cur - years[0]) / span) * ax_w_px
                flip = (len(label) * TIP_LABEL_PX_PER_CHAR + off + 14) > avail
                if art is not None:
                    ax.add_artist(AnnotationBbox(
                        OffsetImage(art, zoom=_icon_zoom(art, TIP_ICON_PX,
                                                         TIP_ICON_MAX_W)),
                        (cur, ly),
                        xybox=(-(iw / 2 + 6) if flip else iw / 2 + 6, 0),
                        boxcoords="offset points",
                        frameon=True, pad=0.15, zorder=6,
                        bboxprops=dict(edgecolor=s["color"], linewidth=2,
                                       facecolor="white",
                                       boxstyle="round,pad=0.18"),
                        annotation_clip=False))
                ax.annotate(label,
                            xy=(cur, ly),
                            xytext=(-off, 0) if flip else (off, 0),
                            textcoords="offset points", color=s["color"],
                            fontsize=15, fontweight="bold", va="center",
                            ha="right" if flip else "left",
                            zorder=5, clip_on=False,
                            annotation_clip=False,
                            # The label sits AT its series' value, which is
                            # exactly where that series' line is — so grey
                            # text landed on a grey line and vanished. A
                            # near-opaque plate makes every tip readable
                            # over lines, gridlines and other labels.
                            bbox=dict(boxstyle="round,pad=0.25",
                                      facecolor="#000000", alpha=0.78,
                                      edgecolor="none"))

            # THE KEY: compact icon + name + value rows parked in the
            # dead band between the title and the plot, so it never sits
            # on top of the lines it is labelling (operator note: "move
            # the key, make it a bit smaller and out of the way").
            ly = key_top
            for rank, (cv, s, _xs, _ys) in enumerate(tips):
                art = icons.get(s["name"])
                if art is not None:
                    ab = AnnotationBbox(
                        OffsetImage(art, zoom=_icon_zoom(art, BOARD_ICON_PX,
                                                         BOARD_ICON_MAX_W)),
                        (KEY_X_ICON, ly), xycoords="figure fraction",
                        frameon=True, zorder=6,
                        bboxprops=dict(edgecolor=s["color"], linewidth=1.5,
                                       facecolor="white",
                                       boxstyle="round,pad=0.18"),
                        annotation_clip=False)
                    fig.add_artist(ab)
                    extra.append(ab)
                else:
                    fig.text(KEY_X_ICON, ly, _initials(s["name"]),
                             color="#0b0f17", ha="center", va="center",
                             fontsize=11, fontweight="bold",
                             bbox=dict(boxstyle="circle,pad=0.34",
                                       facecolor=s["color"],
                                       edgecolor="none"))
                fig.text(KEY_X_NAME, ly, f"{rank + 1}. {s['name']}",
                         color=s["color"], ha="left", va="center",
                         fontsize=17, fontweight="bold")
                fig.text(KEY_X_VALUE, ly, _fmt_compact(cv), color="white",
                         ha="right", va="center", fontsize=19,
                         fontweight="bold")
                ly -= KEY_STEP

            # big year counter under the chart
            fig.text(0.5, 0.140, str(int(round(cur))), color="white",
                     ha="center", va="center", fontproperties=year_font)
            if in_hold:
                lead = tips[0][1]
                # THE PAYOFF BEAT. This used to redraw one identical frame
                # `hold` times — a literal freeze on the last thing the
                # viewer sees, and the moment they decide whether to watch
                # another. The winner now LANDS: a quick scale-up and fade
                # over the first 40% of the hold, then a slow drift, so no
                # two frames are the same right through to the cut.
                land = min(1.0, hp / 0.4)
                ease = 1.0 - (1.0 - land) ** 3
                fig.text(0.5, 0.078 + 0.014 * (1.0 - ease) + 0.004 * hp,
                         f"#1  {lead['name']}",
                         color=lead["color"], ha="center", va="center",
                         fontsize=32 + 10 * ease, fontweight="bold",
                         alpha=0.25 + 0.75 * ease)
            if credit:
                fig.text(0.5, 0.030, credit, color="#8b93a1", ha="center",
                         va="center", fontsize=15)

            if hook and f < HOOK_S * fps:
                # The hook used to sit at 0.79 — right on top of the key
                # rows, so on a 2-series chart it printed straight through
                # "S&P 500 close". Put it INSIDE the plot area, where there
                # is always empty space above the lines early in the race,
                # with a panel behind it so it reads over gridlines.
                alpha = max(0.0, 1.0 - f / (HOOK_S * fps))
                fig.text(0.5, 0.63, hook, color="#f5c518", ha="center",
                         va="center", fontproperties=hook_font, alpha=alpha,
                         bbox=dict(boxstyle="round,pad=0.45",
                                   facecolor="#000000",
                                   edgecolor="#f5c518",
                                   alpha=min(0.82, alpha)))

            fig.savefig(frames_dir / f"f{f:05d}.png", facecolor="#000000")
        plt.close(fig)

        # CAMERA FLOAT — see shared/camera_float.py. The race eases in, so
        # its opening seconds are near-still: on 2026-08-11 three of six
        # trending videos were blocked before vision review at 4.5 / 8.7 /
        # 8.9 effective fps against an 11.0 floor. The float is cyclic, so
        # unlike the race itself it does not thin out over a longer chart —
        # measured 23.1 fps on a completely static 20-second clip. It costs
        # 20px of edge (1.9%) and never exposes background.
        _float = camera_float.crop_vf(W, H)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-framerate", str(fps), "-i", str(frames_dir / "f%05d.png"),
             "-vf", f"{_float},format=yuv420p", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "20", "-r", str(fps),
             "-an", "-movflags", "+faststart", str(out)],
            check=True)
        return out
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def maybe_chart_race(spec: dict, out, **kwargs) -> Path | None:
    """Best-effort wrapper: Path on success, None on any failure."""
    try:
        return render(spec, out, **kwargs)
    except Exception as e:  # noqa: BLE001 — contract: never raise into a caller
        print(f"[engines.chart_race] failed: {e}")
        return None


def available() -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    try:
        import matplotlib  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False
