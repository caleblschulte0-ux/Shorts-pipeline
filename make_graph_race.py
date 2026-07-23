#!/usr/bin/env python3
"""Animated line-chart race renderer (graphfather style).

Multiple series (countries/categories) drawn over time: the lines grow, a dot
tracks each line's tip and moves up/down with the data, a big year counter
climbs, and a live leaderboard shows current values sorted high→low. Black
background, portrait 1080x1920.

Renders each frame with matplotlib (Agg) to a PNG, then ffmpeg stitches them
into an mp4 with a music bed.

Package schema:
  {"format":"graph_race","title":"Staffed Lighthouses by Country Since 1900",
   "y_label":"Staffed lighthouses","source":"Sources: ...",
   "years":[1900,1920,...,2020],
   "series":[{"name":"USA","color":"#4a90e2","values":[600,...,1]}, ...],
   "duration":12,"music_vibe":"dark"}
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import make_explainer_stacked as base

W, H, FPS = base.W, base.H, 24
BG = "#000000"
FONT = str(Path(__file__).resolve().parent / "assets" / "fonts"
           / "Anton-Regular.ttf")


def _run(cmd):
    subprocess.run(cmd, check=True)


def _interp(years, values, x):
    """Linear-interpolate a series value at fractional year x."""
    if x <= years[0]:
        return values[0]
    for i in range(1, len(years)):
        if x <= years[i]:
            y0, y1 = years[i - 1], years[i]
            v0, v1 = values[i - 1], values[i]
            t = (x - y0) / (y1 - y0) if y1 != y0 else 0
            return v0 + t * (v1 - v0)
    return values[-1]


def build_graph_race(pkg: dict, out_path: Path, *, duration: float = 12.0,
                     gameplay_tag: str = "minecraft") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib import font_manager

    duration = float(pkg.get("duration") or duration)
    title = pkg.get("title", "")
    y_label = pkg.get("y_label", "")
    source = pkg.get("source", "")
    years = [float(y) for y in pkg["years"]]
    series = pkg["series"]
    y_max = max(max(s["values"]) for s in series) * 1.12

    title_font = fm.FontProperties(fname=FONT, size=46) \
        if os.path.exists(FONT) else fm.FontProperties(weight="bold", size=40)
    year_font = fm.FontProperties(fname=FONT, size=90) \
        if os.path.exists(FONT) else fm.FontProperties(weight="bold", size=80)

    workdir = Path(tempfile.mkdtemp(prefix="graphrace_"))
    frames_dir = workdir / "frames"
    frames_dir.mkdir()
    try:
        n_frames = int(duration * FPS)
        hold = int(FPS * 1.2)          # hold the final frame ~1.2s
        dpi = 100
        figsize = (W / dpi, H / dpi)
        print(f"[1/3] rendering {n_frames + hold} frames")
        for f in range(n_frames + hold):
            p = min(1.0, f / max(1, n_frames - 1))
            cur = years[0] + p * (years[-1] - years[0])

            fig = plt.figure(figsize=figsize, dpi=dpi)
            fig.patch.set_facecolor(BG)
            # title band (top ~18%), chart (middle), year+leaderboard overlaid
            ax = fig.add_axes([0.12, 0.30, 0.83, 0.42])
            ax.set_facecolor(BG)
            fig.text(0.5, 0.88, title, color="white", ha="center",
                     va="center", fontproperties=title_font, wrap=True)

            leaderboard = []
            for s in series:
                vals = s["values"]
                xs = [y for y in years if y <= cur]
                ys = [vals[i] for i, y in enumerate(years) if y <= cur]
                cv = _interp(years, vals, cur)
                xs = xs + [cur]
                ys = ys + [cv]
                ax.plot(xs, ys, color=s["color"], linewidth=5,
                        solid_capstyle="round", zorder=3)
                ax.plot([cur], [cv], "o", color=s["color"], markersize=13,
                        zorder=4)
                leaderboard.append((cv, s))

            ax.set_xlim(years[0], years[-1])
            ax.set_ylim(0, y_max)
            ax.set_ylabel(y_label, color="#9aa4b2", fontsize=15)
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)
            for spine in ("left", "bottom"):
                ax.spines[spine].set_color("#3a4252")
            ax.tick_params(colors="#9aa4b2", labelsize=14)
            ax.grid(axis="y", color="#141a26", linewidth=1)

            # live leaderboard (sorted desc), upper-right of the chart area
            leaderboard.sort(key=lambda t: -t[0])
            ly = 0.68
            for cv, s in leaderboard:
                fig.text(0.60, ly, s["name"], color=s["color"], ha="left",
                         va="center", fontsize=22, fontweight="bold")
                fig.text(0.60, ly - 0.028, f"{int(round(cv)):,}", color="white",
                         ha="left", va="center", fontsize=30, fontweight="bold")
                ly -= 0.075

            # big year counter under the chart
            fig.text(0.5, 0.235, str(int(round(cur))), color="white",
                     ha="center", va="center", fontproperties=year_font)
            if source:
                fig.text(0.5, 0.06, source, color="#6b7280", ha="center",
                         va="center", fontsize=11, wrap=True)

            fig.savefig(frames_dir / f"f{f:05d}.png", facecolor=BG)
            plt.close(fig)

        print("[2/3] music bed")
        total = (n_frames + hold) / FPS
        music = workdir / "music.wav"
        has_music = True
        try:
            base.synth_music(total, music, pkg.get("music_vibe", "dark"))
        except Exception as e:  # noqa: BLE001
            print(f"      music skipped: {e}")
            has_music = False

        print("[3/3] compose")
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-framerate", str(FPS), "-i", str(frames_dir / "f%05d.png")]
        if has_music:
            cmd += ["-i", str(music)]
        cmd += ["-vf", f"scale={W}:{H},format=yuv420p", "-c:v", "libx264",
                "-preset", "veryfast", "-crf", "20", "-r", str(FPS)]
        if has_music:
            cmd += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
        cmd += ["-movflags", "+faststart", str(out_path)]
        _run(cmd)
        try:
            Path(str(out_path) + ".audit.json").write_text(json.dumps({
                "out": str(out_path), "format": "graph_race",
                "series": [s["name"] for s in series]}, indent=2) + "\n")
        except Exception:  # noqa: BLE001
            pass
        print(f"done -> {out_path}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    import sys
    pkg = json.loads(Path(sys.argv[1]).read_text())
    build_graph_race(pkg, Path(sys.argv[2] if len(sys.argv) > 2
                               else "graphrace.mp4"))
