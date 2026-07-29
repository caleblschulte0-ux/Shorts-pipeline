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

`assess(spec)` scores DATA DRAMA (magnitude + movement) and callers should
gate on it before rendering: small, slow, flat numbers make a boring
video (see MIN_PEAK / MIN_SWING). Units are normalized first, so a spec
written as 11.5 with y_label "EVs sold (millions)" both renders as
"11.5M" and is judged on its real magnitude — see `normalize()`.

Contract (engines/__init__.py): available() is offline; maybe_chart_race()
returns a Path or None, never raises; nothing here mutates repo state.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

FPS = 24
HOLD_S = 1.4                 # hold the finished chart at the end
HOOK_S = 1.6                 # optional hook text fades out over this window
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
MIN_PEAK = 50.0            # post-normalization; catches 0-10 index data
MIN_SWING = 3.0
CROSSOVER_SWING = 1.6
SWING_CAP = 999.0        # a series touching 0 is an infinite ratio

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
BOARD_ICON_PX = 34


def _smoothstep(p: float) -> float:
    return p * p * (3.0 - 2.0 * p)


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

    # lead changes: how many times the top-ranked series swaps
    order = [max(range(len(series)), key=lambda i: series[i]["values"][t])
             for t in range(len(spec["years"]))]
    crossovers = sum(1 for a, b in zip(order, order[1:]) if a != b)

    need = CROSSOVER_SWING if crossovers else MIN_SWING
    if peak < MIN_PEAK and not _is_ratio(spec):
        reasons.append(f"peak {peak:g} < {MIN_PEAK:g} — numbers too small to "
                       f"feel big on screen (scale the metric up, or pick a "
                       f"bigger one)")
    if swing < need:
        reasons.append(f"biggest swing {swing:.1f}x < {need:g}x — the lines "
                       f"barely move"
                       + ("" if crossovers else " and nobody ever takes the "
                                                "lead"))
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


def _icon_zoom(arr, target_px: float) -> float:
    """Scale factor that renders `arr` at ~target_px tall."""
    h = getattr(arr, "shape", [target_px])[0] or target_px
    return float(target_px) / float(h)


def _icon_width(arr, target_px: float) -> float:
    """On-screen width in px when drawn `target_px` tall (flags are wide,
    so the tip label has to clear more than the icon's height)."""
    shape = getattr(arr, "shape", None)
    if not shape or len(shape) < 2 or not shape[0]:
        return target_px
    return target_px * (shape[1] / shape[0])


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
    from matplotlib.offsetbox import AnnotationBbox, OffsetImage
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    W, H = int(size[0]), int(size[1])
    # biggest truthful numbers on screen: 11.5 "(millions)" -> 11.5M
    spec = normalize(spec)
    duration = float(spec.get("duration") or 12.0)
    title = spec.get("title", "")
    y_label = spec.get("y_label", "")
    source = spec.get("source", "")
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
            import matplotlib.image as mpimg
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
    title_font = fm.FontProperties(fname=_FONT, size=46) if have_font \
        else fm.FontProperties(weight="bold", size=40)
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
        ax = fig.add_axes([0.13, 0.30, 0.82, 0.44])
        cam_top = 0.0            # dynamic y "camera": only ever zooms out
        extra: list = []         # per-frame figure-level artists to recycle
        print(f"[chart_race] {n_frames + hold} frames @ {W}x{H}")
        for f in range(n_frames + hold):
            p = _smoothstep(min(1.0, f / max(1, n_frames - 1)))
            cur = years[0] + p * (years[-1] - years[0])
            in_hold = f >= n_frames

            ax.clear()
            for t in fig.texts[:]:
                t.remove()
            # figure-level artists (leaderboard icons) aren't covered by
            # ax.clear() / fig.texts — drop last frame's explicitly
            for a in extra:
                a.remove()
            extra = []
            ax.set_facecolor("#000000")
            fig.text(0.5, 0.88, title, color="white", ha="center",
                     va="center", fontproperties=title_font, wrap=True)

            tips = []
            for s in series:
                vals = s["values"]
                xs = [y for y in years if y <= cur] + [cur]
                ys = [vals[i] for i, y in enumerate(years) if y <= cur]
                cv = _interp(years, vals, cur)
                ys = ys + [cv]
                tips.append((cv, s, xs, ys))
            tips.sort(key=lambda t: -t[0])

            # Past ~82% of the timeline the tip sits at the right edge, so
            # icons AND labels flip to the inside of the dot — otherwise
            # they hang off-frame exactly on the most-watched final frames.
            near_end = (cur - years[0]) > 0.82 * (years[-1] - years[0])

            for rank, (cv, s, xs, ys) in enumerate(tips):
                lw = 6 if rank == 0 else 4.5
                ax.plot(xs, ys, color=s["color"], linewidth=lw,
                        solid_capstyle="round", zorder=3)
                ax.plot([cur], [cv], "o", color=s["color"],
                        markersize=14 if rank == 0 else 12, zorder=4,
                        markeredgecolor="white", markeredgewidth=1.2)

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
                if art is None:
                    off = 8
                else:
                    iw = _icon_width(art, TIP_ICON_PX)
                    ax.add_artist(AnnotationBbox(
                        OffsetImage(art, zoom=_icon_zoom(art, TIP_ICON_PX)),
                        (cur, ly),
                        xybox=(-(iw / 2 + 6) if near_end else iw / 2 + 6, 0),
                        boxcoords="offset points",
                        frameon=True, pad=0.15, zorder=6,
                        bboxprops=dict(edgecolor=s["color"], linewidth=2,
                                       facecolor="#0b0f17",
                                       boxstyle="round,pad=0.18"),
                        annotation_clip=False))
                    off = iw + 16
                ax.annotate(f"{s['name']}  {_fmt_compact(cv)}",
                            xy=(cur, ly),
                            xytext=(-off, 0) if near_end else (off, 0),
                            textcoords="offset points", color=s["color"],
                            fontsize=15, fontweight="bold", va="center",
                            ha="right" if near_end else "left",
                            zorder=5, clip_on=False,
                            annotation_clip=False)

            # live leaderboard, upper-left of the chart band. Every row is
            # icon (or initials badge) + name + value, so the viewer never
            # has to map a colour back to a legend.
            ly = 0.70
            for rank, (cv, s, _xs, _ys) in enumerate(tips):
                art = icons.get(s["name"])
                if art is not None:
                    ab = AnnotationBbox(
                        OffsetImage(art, zoom=_icon_zoom(art, BOARD_ICON_PX)),
                        (0.205, ly - 0.012), xycoords="figure fraction",
                        frameon=True, zorder=6,
                        bboxprops=dict(edgecolor=s["color"], linewidth=2,
                                       facecolor="#0b0f17",
                                       boxstyle="round,pad=0.2"),
                        annotation_clip=False)
                    fig.add_artist(ab)
                    extra.append(ab)
                else:
                    fig.text(0.205, ly - 0.012, _initials(s["name"]),
                             color="#0b0f17", ha="center", va="center",
                             fontsize=17, fontweight="bold",
                             bbox=dict(boxstyle="circle,pad=0.42",
                                       facecolor=s["color"],
                                       edgecolor="none"))
                fig.text(0.272, ly, f"{rank + 1}. {s['name']}",
                         color=s["color"], ha="left", va="center",
                         fontsize=21, fontweight="bold")
                fig.text(0.272, ly - 0.024, _fmt_compact(cv), color="white",
                         ha="left", va="center", fontsize=27,
                         fontweight="bold")
                ly -= 0.066

            # big year counter under the chart
            fig.text(0.5, 0.225, str(int(round(cur))), color="white",
                     ha="center", va="center", fontproperties=year_font)
            if in_hold:
                lead = tips[0][1]
                fig.text(0.5, 0.155, f"#1  {lead['name']}",
                         color=lead["color"], ha="center", va="center",
                         fontsize=34, fontweight="bold")
            if source:
                fig.text(0.5, 0.06, source, color="#6b7280", ha="center",
                         va="center", fontsize=11, wrap=True)

            if hook and f < HOOK_S * fps:
                alpha = max(0.0, 1.0 - f / (HOOK_S * fps))
                fig.text(0.5, 0.79, hook, color="#f5c518", ha="center",
                         va="center", fontproperties=hook_font, alpha=alpha)

            fig.savefig(frames_dir / f"f{f:05d}.png", facecolor="#000000")
        plt.close(fig)

        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-framerate", str(fps), "-i", str(frames_dir / "f%05d.png"),
             "-vf", f"scale={W}:{H},format=yuv420p", "-c:v", "libx264",
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
