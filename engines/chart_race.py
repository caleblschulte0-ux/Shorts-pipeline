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

from shared import look as _look                                    # noqa: E402
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
#: How long a race that passed only on its crossover may run (see `render`).
CROSSOVER_MAX_S = 7.0
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

# ---- composition floors (doctor finding d17724dfb1c0) ---------------------
# The drama numbers above are TIMELINE-WIDE; the renderer's axes are not:
# the full year span is exposed from frame one and the y-camera floors at
# `global_max * 0.12`. A package whose values sit near zero for the first
# fifth therefore passes peak/swing while OPENING as a tiny lower-left stub
# in a mostly empty plot — two chart races were blocked for exactly that on
# 2026-08-09, after preflight had said ok. These floors are derived from
# the SAME axis math the renderer uses (see `render`: xlim = full span,
# cam_top = max(tips * 1.22, global_max * 0.12)) — no render needed.
OPEN_FRAC = 0.20         # "the opening" = the first fifth of the timeline
OPEN_AREA_MIN = 0.05     # painted fraction of the plot at the OPEN_FRAC mark
TRAVEL_MIN = 0.30        # top moving line's total |Δ| relative to global max

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


CREDIT_MAX_CHARS = 96


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
    # A CREDIT IS NEVER CUT MID-THOUGHT. This used to cut at 78 characters
    # with an ellipsis, so the frame read "US per-capita meat availability
    # (boneless/retail-weight basis), USDA Economic…" and the judge wrote
    # "the source line is cut off with '...' in every frame" on all three
    # graph races of 2026-09-25; another cut landed inside a bracket, "IMF
    # World Economic Outlook (nominal GDP". Pulling organisation names out
    # of free text was tried and rejected: it confidently printed "American
    # Society for Metabolic". The source's own words, whole, are safer.
    head = re.split(r":\s|(?<=[a-z]{3})\.\s+", head)[0].strip(" .,;—-")
    if len(head) <= CREDIT_MAX_CHARS and _balanced(head):
        return f"Source: {head}" if head else ""
    head = _trim_words(head)
    return f"Source: {head}" if head else ""


_TRAILING = {"of", "for", "and", "&", "the", "on", "a", "an", "by", "in", "to",
             "from", "with", "vs", "or"}


def _balanced(t: str) -> bool:
    return t.count("(") == t.count(")") and t.count("[") == t.count("]")


def _trim_words(t: str) -> str:
    """Whole words only, bracketed asides dropped, and no ellipsis: a credit
    that ends on "USDA Economic…" reads as broken, one that ends on a whole
    word reads as a credit."""
    t = re.sub(r"\s*\([^)]*\)", "", t)
    t = re.sub(r"\s*\([^)]*$", "", t).strip(" .,;:—-")
    words = t.split()
    cut = False
    while words and len(" ".join(words)) > CREDIT_MAX_CHARS:
        words.pop()
        cut = True
    # A trimmed credit ends on the last NAMED word: "...Research Institute",
    # not "...Research Institute homeschool".
    if cut:
        k = max((i for i, w in enumerate(words) if w[:1].isupper()),
                default=-1)
        if k >= 0 and len(" ".join(words[:k + 1])) >= 0.6 * len(" ".join(words)):
            words = words[:k + 1]
    def _dangles(w: str) -> bool:
        return (w.lower().strip(",;") in _TRAILING or w.endswith((",", ";"))
                or not re.search(r"[A-Za-z0-9]", w)
                or w.endswith(("'s", "’s"))           # "Eli Lilly's" — whose what?
                or (w.count("'") % 2 == 1 and not re.search(r"\w'\w|s'$", w))
                or w.count('"') % 2 == 1)
    while words and _dangles(words[-1]):
        words.pop()
    return " ".join(words).strip(" .,;:—-")


def _spec_data_problems(spec: dict) -> list[str]:
    """Data defects that make DRAMA unjudgeable: non-numeric / non-finite
    values, unsorted years, length mismatches. Checked BEFORE `normalize`
    (which multiplies values) — until 2026-08-24 a spec whose values were
    strings crashed `assess` with a TypeError, and the one caller that
    gates on it (shared/package_schema) swallowed that crash as "engine
    absent" and passed the package (doctor d64b063a21bd). A spec assess
    cannot do arithmetic on is a refusal with named reasons, not a crash
    for callers to misread."""
    years = spec.get("years") or []
    series = spec.get("series") or []

    def _num(v) -> bool:
        # bool excluded on purpose: True is an int in Python, not data.
        return (isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v))

    bad: list[str] = []
    non_num = [y for y in years if not _num(y)]
    if non_num:
        bad.append(f"years are not all finite numbers: {non_num[:4]!r}")
    elif any(b <= a for a, b in zip(years, years[1:])):
        bad.append(f"years are not strictly increasing: {years!r}")
    for s in series:
        vals = (s or {}).get("values") or []
        non_num = [v for v in vals if not _num(v)]
        if non_num:
            bad.append(f"series {(s or {}).get('name')!r} values are not "
                       f"all finite numbers: {non_num[:4]!r}")
        elif len(vals) != len(years):
            bad.append(f"series {(s or {}).get('name')!r} has {len(vals)} "
                       f"values for {len(years)} years")
    return bad


def assess(spec: dict) -> dict:
    """Score a spec's DATA DRAMA (after unit normalization). Returns
    {ok, peak, swing, crossovers, reasons[]}. `ok` is False when the
    numbers are too trivial or too flat to carry a video — or when the
    data is not judgeable at all (non-numeric, unsorted, mismatched; see
    `_spec_data_problems`), which is a refusal, never a raise."""
    series = spec.get("series") or []
    if not series or not spec.get("years"):
        return {"ok": False, "peak": 0.0, "swing": 0.0, "crossovers": 0,
                "reasons": ["no series/years"]}
    data_bad = _spec_data_problems(spec)
    if data_bad:
        return {"ok": False, "peak": 0.0, "swing": 0.0, "crossovers": 0,
                "reasons": data_bad}
    spec = normalize(spec)
    series = spec.get("series") or []

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

    # ---- composition floors: what the OPENING actually paints -----------
    # See the OPEN_FRAC block up top. w = how far into the fixed year axis
    # the reveal has reached at the first-fifth mark; h = the tallest tip so
    # far against the camera the renderer would actually show (which floors
    # at 12% of the global max — the exact reason a near-zero opening reads
    # as an empty black frame instead of a zoomed-in one).
    years = spec["years"]
    span = float(years[-1] - years[0]) or 1.0
    k = max(1, int(round(OPEN_FRAC * (len(years) - 1))))
    w_open = (years[k] - years[0]) / span
    tip_open = max(max(s["values"][:k + 1]) for s in series)
    cam_open = max(tip_open * 1.22, peak * 0.12)
    h_open = (tip_open / cam_open) if cam_open > 0 else 0.0
    area_open = w_open * h_open
    if area_open < OPEN_AREA_MIN:
        reasons.append(
            f"opening paints ~{area_open:.0%} of the plot (first "
            f"{OPEN_FRAC:.0%} of the timeline is a stub against the "
            f"12%-of-max camera floor) < {OPEN_AREA_MIN:.0%} — trim the "
            f"flat early years or pick a window where the story has "
            f"already started")
    # Expected on-screen travel: total |Δ| of the tallest MOVING line,
    # relative to the global max. A ratio-shaped swing can pass while the
    # line barely climbs the frame (the 08-09 case that passed preflight
    # and then measured almost no effective motion).
    moving_series = [s for s, m in zip(series, moving) if m]
    if moving_series:
        top = max(moving_series, key=lambda s: max(s["values"]))
        travel = sum(abs(b - a)
                     for a, b in zip(top["values"], top["values"][1:]))
        travel_frac = (travel / peak) if peak > 0 else 0.0
    else:
        travel_frac = 0.0
    if travel_frac < TRAVEL_MIN:
        reasons.append(
            f"expected screen travel ~{travel_frac:.0%} of the frame < "
            f"{TRAVEL_MIN:.0%} — the leading line never really climbs; "
            f"this renders as a near-static plot however good the ratio "
            f"looks")
    return {"ok": not reasons, "peak": peak, "swing": round(swing, 2),
            "crossovers": crossovers, "reasons": reasons,
            "open_area": round(area_open, 3),
            "travel": round(travel_frac, 3)}


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


_PX_CACHE: dict = {}


def _text_px(fig, text: str, size: float) -> float:
    """Rendered width of `text` in PIXELS, measured on this figure.

    Cached per (text, size): a race draws every tip label on every one of
    ~400 frames, and a canvas measurement per label per frame is real time.
    """
    key = (text, size)
    hit = _PX_CACHE.get(key)
    if hit is not None:
        return hit
    try:
        r = fig.canvas.get_renderer()
        probe = fig.text(0, 0, text, fontsize=size, fontweight="bold")
        w = float(probe.get_window_extent(renderer=r).width)
        probe.remove()
    except Exception:  # noqa: BLE001 — fall back to the old estimate
        w = len(text) * TIP_LABEL_PX_PER_CHAR
    _PX_CACHE[key] = w
    return w


def _fit_axis_name(fig, text: str, band_px: float) -> str:
    """The y-axis name, truncated to the band it is drawn in.

    "Commercial aircraft delivered (count" — clipped mid-word by the frame
    edge with no closing paren, in a video the showrunner blocked. A y
    label is drawn ROTATED, so its band is the axes HEIGHT, and nothing
    was comparing the two.
    """
    text = " ".join(str(text or "").split())
    if not text or band_px <= 0:
        return text
    if _text_px(fig, text, 15) <= band_px:
        return text
    # Drop a trailing unit parenthetical first — "(count)", "($ billions)"
    # — which is the part a reader can infer from the tick labels anyway.
    short = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    if short and _text_px(fig, short, 15) <= band_px:
        return short
    lo, hi = 0, len(short or text)
    src = short or text
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_px(fig, src[:mid].rstrip() + "\u2026", 15) <= band_px:
            lo = mid
        else:
            hi = mid - 1
    return (src[:lo].rstrip() + "\u2026") if lo else ""


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


YEAR_TRACK = (0.24, 0.76)  # the year counter's travel, figure x, start -> end
YEAR_TRACK_Y = 0.101
RIGHT_PAD_PX = 24          # the leader's tip dot, whole, inside the plot
BURST_S = 0.7              # the crossover ring's one expanding burst


def year_ticks(years) -> list[int]:
    """ONE tick step for the whole race, chosen from its full span.

    `MaxNLocator` re-chose its step every frame as the x camera opened, so
    the axis read 1972/1975/1978, then decades, then 1980/1995/2010 — "the
    x-axis ticks rescale unevenly ... which looks jumpy" (c-sections race,
    2026-09-25). A fixed step only ever ADDS ticks as the camera opens, and
    never labels a year past the data."""
    y0, y1 = float(years[0]), float(years[-1])
    span = max(1.0, y1 - y0)
    step = next((st for st in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500)
                 if span / st <= 6), 1000)
    first = int(math.ceil(y0 / step) * step)
    return list(range(first, int(math.floor(y1)) + 1, step))


def pass_caption(leader: str, passed: str) -> str:
    """"Chicken passes Beef", "C-Sections pass Vaginal Births"."""
    word = str(leader).split()[-1] if str(leader).split() else ""
    plural = (word.lower().endswith("s") and not word.lower().endswith("ss")
              and len(word) > 3)
    return f"{leader} {'pass' if plural else 'passes'} {passed}"


def lead_change(years, series) -> dict | None:
    """Where the FINAL leader took the lead for the last time: the moment a
    "X passed Y" race exists to show.

    The judge on chicken-vs-beef, 2026-09-25: "the payoff is a small '#1
    Chicken' caption with no highlight of the crossover year". Returns the
    crossing's x (interpolated between the two samples it falls between —
    it is where the drawn lines visibly cross, nothing more), the value
    there, the leader and the series it passed. None when the leader led
    throughout: then there is no pass to mark, and none is invented."""
    if len(series) < 2 or len(years) < 2:
        return None
    lead = max(series, key=lambda s: s["values"][-1])
    best = None
    for o in series:
        if o is lead:
            continue
        d = [a - b for a, b in zip(lead["values"], o["values"])]
        for k in range(len(d) - 1, 0, -1):
            if d[k - 1] <= 0 < d[k]:
                t = -d[k - 1] / (d[k] - d[k - 1])
                x = years[k - 1] + t * (years[k] - years[k - 1])
                if best is None or x > best["x"]:
                    best = {"x": float(x), "y": float(_interp(years,
                                                              lead["values"], x)),
                            "leader": lead["name"], "passed": o["name"]}
                break
    return best


def race_duration(spec: dict) -> float:
    """How long the race runs, in seconds.

    A RACE THAT ONLY PASSED ON ITS CROSSOVER RUNS SHORT. The lenient bar (a
    lead that changes hands, CROSSOVER_SWING) lets in lines that barely
    move, and spread over 13 seconds they move under a pixel a frame at the
    gate's 192px: all three graph_races of 2026-09-25 ("chicken passed
    beef", "homeschool passed Catholic school", "C-sections passed vaginal
    births") were blocked at 7.9-10.5 effective fps. Measured on those same
    three specs at CROSSOVER_MAX_S: 20.2, 15.3 and 14.0 fps. A crossover is
    one moment — a short story, told fast.
    """
    duration = float(spec.get("duration") or 12.0)
    try:
        if assess(spec).get("swing", MIN_SWING) < MIN_SWING:
            duration = min(duration, CROSSOVER_MAX_S)
    except Exception:  # noqa: BLE001 — an unassessable spec keeps its pace
        pass
    return duration


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
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FixedLocator, FuncFormatter

    W, H = int(size[0]), int(size[1])
    # biggest truthful numbers on screen: 11.5 "(millions)" -> 11.5M
    spec = normalize(spec)
    duration = race_duration(spec)
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
        cam_bot = None           # ...and its FLOOR, which only ever drops
        cam_x = None             # ...and the x camera, which only opens out
        extra: list = []         # per-frame figure-level artists to recycle
        ticks = year_ticks(years)
        cross = lead_change(years, series)
        cross_f = None           # the frame the lead changed hands on
        # A share reads as "57%", not "57": the unit was only on the axis
        # name, rotated, in 15px grey.
        # the credit is fitted by MEASURED width, not a character count
        credit_size = 15
        while credit and credit_size > 11 and \
                _text_px(fig, credit, credit_size) > W * 0.92:
            credit_size -= 1
        unit = "%" if re.search(r"%|\bpercent", y_label, re.I) else ""
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

            # FILL UNDER THE LINES, so the space beneath them is part of
            # the picture. Three of the four blocks on 2026-09-10 named the
            # same thing in different words — "the entire middle ~60% of the
            # frame unbroken black", "the bottom two-thirds and right
            # two-thirds empty black with only gridlines". A line on a dark
            # ground leaves that space empty by construction.
            #
            # Only up to three series: past that the fills overlap into mud
            # and the chart is worse, not fuller.
            if len(tips) <= 3:
                for _r, (_cv, _s, _xs, _ys) in enumerate(reversed(tips)):
                    _look.gradient_fill(ax, _xs, _ys, cam_bot, _s["color"],
                                        zorder=1.5, top=0.26)
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
            # THE FLOOR IS FRAMED, NOT NAILED TO ZERO.
            #
            # `ax.set_ylim(0, cam_top)` is the `empty_void` auto-fail, and
            # on 2026-09-10 it blocked three graph_races out of four in one
            # slate. The oil race is the clearest: "the whole 0-5M band of
            # the plot is pure black in every frame ... roughly the lower
            # 40% of the picture is empty because the y-axis floors at 0
            # while all data lives 5.5M-12.9M."
            #
            # `look.frame_the_data` keeps zero when the data reaches for it
            # (417 -> 71,467 eagles is a growth story and must start at 0)
            # and frames the band otherwise. Like `cam_top` it is a CAMERA:
            # it only ever moves outward, so it cannot jitter frame to frame
            # — and a jitter here is not cosmetic, the cadence gate measures
            # motion on a downscale of the frame and would read a breathing
            # axis as the story moving.
            # THE X AXIS IS A CAMERA TOO.
            #
            # It was pinned to the full year range from frame one, so for
            # the first third of every race the data sat in a sliver at the
            # far left: "the x-axis is pre-scaled out to 2022+ ... leaving
            # roughly the bottom two-thirds and RIGHT TWO-THIRDS of the plot
            # as empty black with only gridlines" (`empty_void`, box-office
            # race, 2026-09-10). Following `cur` with a lead margin keeps
            # the line filling the width, and like the other two cameras it
            # only ever opens out, so it cannot jitter.
            _xspan = (years[-1] - years[0]) or 1.0
            _want_hi = min(years[-1],
                           max(years[0] + _xspan * 0.28, cur + _xspan * 0.07))
            cam_x = _want_hi if cam_x is None else max(cam_x, _want_hi)
            _seen_lo = min(min(t[3]) for t in tips)
            _want_bot = _look.frame_the_data(_seen_lo, cam_top)
            cam_bot = _want_bot if cam_bot is None else min(cam_bot, _want_bot)
            # THE TIP GETS ROOM. The x camera ends exactly on the last year,
            # which put the leader's dot ON the right spine and half of it
            # outside the axes — "the tip markers are clipped at the right
            # edge of the frame" (chicken race, payoff, 2026-09-25).
            x_hi = cam_x + (cam_x - years[0]) * (RIGHT_PAD_PX / ax_w_px)
            ax.set_xlim(years[0], x_hi)
            ax.set_ylim(cam_bot, cam_top)
            # ...AND THE AXIS NAME HAS TO FIT. The Boeing race shipped
            # "Commercial aircraft delivered (count" — clipped mid-word by
            # the frame edge, with no closing paren, which the showrunner
            # read under `unreadable`. The band is the axes height, because
            # a y label is drawn rotated.
            ax.set_ylabel(_fit_axis_name(fig, y_label,
                                         ax.get_window_extent().height),
                          color="#9aa4b2", fontsize=15)
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda v, _: _fmt_compact(v)))
            ax.xaxis.set_major_locator(FixedLocator(ticks))
            ax.xaxis.set_major_formatter(
                FuncFormatter(lambda v, _: str(int(round(v)))))
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)
            for spine in ("left", "bottom"):
                ax.spines[spine].set_color("#3a4252")
            ax.tick_params(colors="#9aa4b2", labelsize=14)
            ax.grid(axis="y", color="#141a26", linewidth=1)

            # THE PASS IS MARKED WHERE IT HAPPENS, AND STAYS MARKED.
            #
            # A "X passed Y" race is about one moment, and it went by with
            # nothing on it: "at 2013 the tip labels and markers overlap
            # exactly as chicken passes beef, which is the moment the video
            # exists to show", and "no highlight of the crossing point"
            # (chicken 79 and c-sections 74, 2026-09-25). A ring bursts out
            # of the crossing when the pen reaches it, then a dashed line and
            # a ring hold the spot for the rest of the race, captioned in the
            # headroom — which `cam_top` keeps empty of tips by construction
            # — so the caption never lands on the labels crowding the tip.
            if cross is not None and cur >= cross["x"]:
                if cross_f is None:
                    cross_f = f
                lead_c = next(s_["color"] for s_ in series
                              if s_["name"] == cross["leader"])
                cx, cy = cross["x"], cross["y"]
                cap_y = cam_top - (cam_top - cam_bot) * 0.075
                ax.plot([cx, cx], [cam_bot, cap_y], color="white", alpha=0.32,
                        linewidth=2, linestyle=(0, (4, 4)), zorder=2)
                ax.plot([cx], [cy], "o", markersize=26, markerfacecolor="none",
                        markeredgecolor="white", markeredgewidth=3, zorder=4.5)
                bt = (f - cross_f) / (fps * BURST_S)
                if bt < 1.0:
                    ax.plot([cx], [cy], "o", markersize=26 + 130 * bt,
                            markerfacecolor="none", markeredgecolor=lead_c,
                            markeredgewidth=4, alpha=(1.0 - bt) ** 1.5,
                            zorder=4.4, clip_on=False)
                if not (hook and f < HOOK_S * fps):
                    cap = pass_caption(cross["leader"], cross["passed"])
                    csize = 18
                    while csize > 12 and _text_px(fig, cap, csize) > ax_w_px * 0.62:
                        csize -= 1
                    half = (_text_px(fig, cap, csize) / 2 + 14) / ax_w_px \
                        * (x_hi - years[0])
                    cap_x = min(max(cx, years[0] + half), x_hi - half)
                    ax.text(cap_x, cap_y, cap, color=lead_c, fontsize=csize,
                            fontweight="bold", ha="center", va="center",
                            zorder=6, bbox=dict(boxstyle="round,pad=0.35",
                                                facecolor="#000000",
                                                edgecolor=lead_c,
                                                linewidth=1.6, alpha=0.9))

            # Tip icon + value label, at DE-CLUTTERED y positions: when the
            # lines converge (everyone collapsing to near-zero) the raw tip
            # values pile on top of each other. The dot stays on the true
            # value; the icon+label pair slides to a spread slot, keeping
            # rank order. Floored just above the axis so nothing lands on
            # the x tick labels.
            # THE SEPARATION IS A LABEL HEIGHT, IN DATA UNITS.
            #
            # It was `cam_top * 0.058` — a fraction of the axis TOP, which
            # is not the axis HEIGHT once the floor is framed, and was never
            # the height of the thing being separated. On the box-office
            # race "China 6.1B" and "North America 5.8B" printed on top of
            # each other and over both marker icons (`unreadable`,
            # 2026-09-10). A 15pt label with its plate is ~34px; convert
            # that to data units through the axes actually on screen.
            _ax_px = max(1.0, float(ax.get_window_extent().height))
            _sep = (cam_top - cam_bot) * (38.0 / _ax_px)
            placed = _spread(pos=[t[0] for t in tips],
                             min_sep=_sep,
                             floor=cam_bot + _sep * 0.8,
                             ceil=cam_top - _sep * 0.4)
            for rank, (cv, s, _xs, _ys) in enumerate(tips):
                ly = placed[rank]
                art = icons.get(s["name"])
                label = f"{s['name']}  {_fmt_compact(cv)}{unit}"
                iw = 0.0 if art is None else _icon_width(art, TIP_ICON_PX,
                                                         TIP_ICON_MAX_W)
                # WITHOUT AN ICON THE TIP STILL CARRIES THE MARKER DOT. The
                # label used to start 8pt from the tip's centre, inside a
                # 16pt marker — so whenever it flipped LEFT of the tip its
                # last glyph sat under the dot ("1276.8B" with the B behind
                # the leader's marker, clean-energy race, 2026-09-22; the
                # showrunner's "colliding, edge-clipped tip badges"). Clear
                # the dot's radius and its white edge before the text.
                _dot_r = (16 if rank == 0 else 13) / 2.0 + 1.4
                off = (_dot_r + 8) if art is None else iw + 16
                # Flip the icon+label to the LEFT of the tip once they would
                # not fit to its right. This used to be one shared
                # `cur > 82% of the span` flag, which is wrong twice over: it
                # ignores how WIDE the label is, and it flips every series at
                # once. A 30-character series name ran off the right edge for
                # seconds before the flag tripped — visible in the 2016 frame
                # of the disaster-costs chart as "Disaster cost that".
                # ...against the CURRENT x window, now that it moves.
                span = (x_hi - years[0]) or 1.0
                avail = (1.0 - (cur - years[0]) / span) * ax_w_px
                # MEASURED, NOT COUNTED. `len(label) * 9.4` is the same
                # character-count-as-width guess `shared.fit_title` exists
                # to replace, and it under-measures every wide glyph: the
                # oil race shipped "United States  11.6" with the M clipped
                # off by the frame edge, and the box-office race clipped its
                # flag mid-glyph. Both were `unreadable` on 2026-09-10.
                flip = (_text_px(fig, label, 15) + off + 14) > avail
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
                fig.text(KEY_X_VALUE, ly, _fmt_compact(cv) + unit, color="white",
                         ha="right", va="center", fontsize=19,
                         fontweight="bold")
                ly -= KEY_STEP

            # THE YEAR RIDES A TIMELINE. It sat centred and still, which left
            # the pen tip as the frame's only moving thing — and the x camera
            # FOLLOWS the pen, so the tip is stationary on screen. On a slow
            # stretch the only change in the frame was the year's last digit
            # turning over every third frame: the c-sections race measured
            # 0.425 duplicate frames against a 0.45 ceiling, and its middle
            # read `#..#...#..#` to the cadence gate. A counter that travels
            # a track as the years pass says where we are in time, and moves
            # on every frame the race moves.
            yx = YEAR_TRACK[0] + (YEAR_TRACK[1] - YEAR_TRACK[0]) * p
            for _x1, _c in ((0.94, "#1f2633"), (yx, "#9aa4b2")):
                extra.append(fig.add_artist(Line2D(
                    [0.06, _x1], [YEAR_TRACK_Y] * 2, transform=fig.transFigure,
                    color=_c, linewidth=3, solid_capstyle="round")))
            fig.text(yx, 0.140, str(int(round(cur))), color="white",
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
                         va="center", fontsize=credit_size)

            if hook and f < HOOK_S * fps:
                # The hook used to sit at 0.79 — right on top of the key
                # rows, so on a 2-series chart it printed straight through
                # "S&P 500 close". Put it INSIDE the plot area, where there
                # is always empty space above the lines early in the race,
                # with a panel behind it so it reads over gridlines.
                # ...AND IT GOES WHERE THE DATA IS NOT.
                #
                # Centred at 0.5 it printed over the very labels it was
                # introducing — "the 'Nobody saw this coming.' card is
                # printed on top of the chart and covers the 'Saudi Arabia
                # 8.5M' series label, which shows only as a smear behind
                # it" (`unreadable`, oil race, 2026-09-10). During the hook
                # window the drawn data is by definition at the LEFT of the
                # plot, so the card is anchored to the right of the pen and
                # only falls back to centre if it cannot fit there.
                # ...AND IT SITS IN THE HEADROOM, NOT ON THE DATA.
                #
                # A dodge to the right of the pen is not enough: the card is
                # most of the frame wide, so wherever it goes horizontally
                # it can still land on a tip label at the same height. The
                # reliable empty band is VERTICAL and it is guaranteed —
                # `cam_top` is the top tip times 1.22, so the top ~18% of
                # the plot has nothing in it by construction, every frame.
                # Anchored just under the axes top, the card clears every
                # label instead of hoping to miss them.
                # ...AT FULL INK, CUT NOT FADED, AND NO WIDER THAN THE PLOT.
                #
                # A linear fade over the whole window spent most of it in
                # the dark browns between gold and black — "the hook card
                # 'Tesla Out-Valued Toyota' sits on top of the y-axis tick
                # labels and the plot gridlines, then fades through a dark
                # brown that is unreadable on the black ground" (auto-fail
                # `unreadable`, 2026-09-22). The card now holds full contrast
                # and cuts out at the end of its window; and it is fitted to the
                # AXES box and centred on it, so it never reaches the tick
                # labels to the left of the plot however long the line runs.
                _bb = ax.get_window_extent()
                # A HARD CUT. Even a quarter-second tail spends frames in
                # the dimmed gold the judge read as unreadable; the card
                # is either at full ink or gone.
                alpha = 1.0
                _hy = _bb.y1 / H - 0.030
                _hx = (_bb.x0 + _bb.x1) / 2.0 / W
                _hsize = 54
                while _hsize > 30 and _text_px(fig, hook, _hsize) > _bb.width * 0.86:
                    _hsize -= 2
                _hfont = (fm.FontProperties(fname=_FONT, size=_hsize) if have_font
                          else fm.FontProperties(size=_hsize, weight="bold"))
                fig.text(_hx, _hy, hook, color="#f5c518", ha="center",
                         va="center", fontproperties=_hfont, alpha=alpha,
                         bbox=dict(boxstyle="round,pad=0.45",
                                   facecolor="#000000",
                                   edgecolor="#f5c518",
                                   alpha=min(0.82, alpha)))

            fig.savefig(frames_dir / f"f{f:05d}.png", facecolor="#000000")
        plt.close(fig)

        # NO CAMERA FLOAT (operator ruling 2026-08-25: rip the camera shake
        # out all the way). It was added on 2026-08-11 because the race EASES
        # IN and its opening seconds were near-still — three of six trending
        # videos blocked at 4.5 / 8.7 / 8.9 effective fps against an 11.0
        # floor. The float made the meter happy without making the opening
        # any better to watch.
        #
        # The opening is the thing to fix, and the drama gate now refuses a
        # chart whose first seconds are an empty plot (doctor d17724dfb1c0:
        # `assess()` derives the opening's painted area and the leader's
        # screen travel from the renderer's own axis math, BEFORE a slot is
        # spent). A race that passes that gate is moving in its opening by
        # construction; one that is not should be replaced, not shaken.
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-framerate", str(fps), "-i", str(frames_dir / "f%05d.png"),
             "-vf", "format=yuv420p", "-c:v", "libx264",
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
