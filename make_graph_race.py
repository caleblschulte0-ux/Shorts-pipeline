#!/usr/bin/env python3
"""Animated line-chart race renderer (graphfather style) — channel wrapper.

The actual chart animation is the shared engine `engines.chart_race`
(eased timeline, dynamic y-camera, tip labels, leaderboard, winner tag,
optional hook overlay). This wrapper is the trending channel's glue: it
renders the silent race, lays a synthesized music bed under it, and writes
the audit sidecar the preview/publish tooling expects.

Package schema:
  {"format":"graph_race","title":"Staffed Lighthouses by Country Since 1900",
   "y_label":"Staffed lighthouses","source":"Sources: ...",
   "years":[1900,1920,...,2020],
   "series":[{"name":"USA","color":"#4a90e2","icon":"US",
               "values":[600,...,1]}, ...],
   "duration":12,"music_vibe":"dark","hook":"Wait for 1990..."}
`color`, `icon` and `hook` are optional. `icon` (country code / flag emoji /
brand name / URL) draws a badge at the line tip + in the leaderboard so
viewers know who is who; it degrades to an initials badge. Values written in
scaled units ("11.5" with y_label "EVs sold (millions)") are normalized by
the engine so the chart shows the bigger number ("11.5M").
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import make_explainer_stacked as base
from engines import chart_race

W, H = base.W, base.H


def _dur(p: Path) -> float:
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    try:
        return float(o.stdout.strip())
    except ValueError:
        return 0.0


def build_graph_race(pkg: dict, out_path: Path, *, duration: float = 12.0,
                     gameplay_tag: str = "minecraft") -> None:
    workdir = Path(tempfile.mkdtemp(prefix="graphrace_"))
    try:
        spec = dict(pkg)
        spec.setdefault("duration", duration)
        silent = workdir / "silent.mp4"
        print("[1/3] chart race (engines.chart_race)")
        chart_race.render(spec, silent, size=(W, H))

        print("[2/3] music bed")
        total = _dur(silent) or float(spec["duration"])
        music = workdir / "music.wav"
        has_music = True
        try:
            base.synth_music(total, music, pkg.get("music_vibe", "dark"))
        except Exception as e:  # noqa: BLE001
            print(f"      music skipped: {e}")
            has_music = False

        print("[3/3] mux")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent)]
        if has_music:
            cmd += ["-i", str(music), "-c:v", "copy", "-c:a", "aac",
                    "-b:a", "160k", "-shortest"]
        else:
            cmd += ["-c:v", "copy", "-an"]
        cmd += ["-movflags", "+faststart", str(out_path)]
        subprocess.run(cmd, check=True)
        try:
            Path(str(out_path) + ".audit.json").write_text(json.dumps({
                "out": str(out_path), "format": "graph_race",
                "engine": "engines.chart_race",
                "series": [s["name"] for s in pkg["series"]]},
                indent=2) + "\n")
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
