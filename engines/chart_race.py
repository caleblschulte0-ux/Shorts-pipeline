"""chart_race — animated multi-series line-chart race (graphfather style).

Shared engine: any channel can hand it a spec and get back a silent
portrait mp4 of lines growing over time with tip dots, tip labels, a live
leaderboard, a climbing year counter, and a dynamic "camera" y-axis that
zooms out as the data grows. Audio (music/VO) is the caller's job — mux it
on top of the silent render.

Spec (same shape as the trending channel's graph_race package):
  {"title": "Staffed Lighthouses by Country Since 1900",
   "y_label": "Staffed lighthouses", "source": "Sources: ...",
   "years": [1900, 1920, ..., 2020],
   "series": [{"name": "USA", "color": "#4a90e2", "values": [...]}, ...],
   "duration": 12, "hook": "Wait for 1990..."}          # hook optional
Colors are optional — a curated palette fills gaps deterministically.

Contract (engines/__init__.py): available() is offline; maybe_chart_race()
returns a Path or None, never raises; nothing here mutates repo state.
"""
from __future__ import annotations

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


def _smoothstep(p: float) -> float:
    return p * p * (3.0 - 2.0 * p)


def _fmt_compact(v: float) -> str:
    """1234 -> '1,234', 12400 -> '12.4K', 3400000 -> '3.4M'."""
    a = abs(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            s = f"{v / div:.1f}".rstrip("0").rstrip(".")
            return s + suf
    return f"{int(round(v)):,}"


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
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    W, H = int(size[0]), int(size[1])
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
        print(f"[chart_race] {n_frames + hold} frames @ {W}x{H}")
        for f in range(n_frames + hold):
            p = _smoothstep(min(1.0, f / max(1, n_frames - 1)))
            cur = years[0] + p * (years[-1] - years[0])
            in_hold = f >= n_frames

            ax.clear()
            for t in fig.texts[:]:
                t.remove()
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

            # tip value labels, de-cluttered: min separation in data coords;
            # flip to the left of the dot near the right edge so the label
            # never runs off-frame on the final (most-seen) frames
            min_sep = cam_top * 0.055
            near_end = (cur - years[0]) > 0.82 * (years[-1] - years[0])
            placed = []
            for rank, (cv, s, _xs, _ys) in enumerate(tips):
                ly = cv
                for py in placed:
                    if abs(ly - py) < min_sep:
                        ly = py - min_sep
                placed.append(ly)
                ax.annotate(f"{s['name']}  {_fmt_compact(cv)}",
                            xy=(cur, ly),
                            xytext=(-12, 0) if near_end else (8, 0),
                            textcoords="offset points", color=s["color"],
                            fontsize=15, fontweight="bold", va="center",
                            ha="right" if near_end else "left",
                            zorder=5, clip_on=False,
                            annotation_clip=False)

            # live leaderboard, upper-left of the chart band
            ly = 0.70
            for rank, (cv, s, _xs, _ys) in enumerate(tips):
                fig.text(0.16, ly, f"{rank + 1}. {s['name']}",
                         color=s["color"], ha="left", va="center",
                         fontsize=21, fontweight="bold")
                fig.text(0.16, ly - 0.024, _fmt_compact(cv), color="white",
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
