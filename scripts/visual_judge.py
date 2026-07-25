#!/usr/bin/env python3
"""THE BLIND MEDIA PACKAGE builder (CURIOSITY_BRAIN §7.5 v9 — taste on pixels).

A rendered clip cannot be certified by the engine's own ledger. It is judged by
a panel of vision models that see ONLY pixels — never the code, the ledger, the
spec, the template name, or the intent (data_learning/VISUAL_STANDARD.md).

A Python script can't spawn those judges; the orchestrator does. This script
does the deterministic half: it turns a clip into a self-contained *blind media
package* a judge can read, containing NOTHING that reveals how the clip was
made:

    <pkg>/contact_sheet.png     dense N-frame grid, timestamped — temporal read
    <pkg>/frame_begin.png       full-res  ~5% in
    <pkg>/frame_mid.png         full-res  50%
    <pkg>/frame_end.png         full-res  ~95%
    <pkg>/camera_trace.png      per-sample mean pixel motion (smoothness/speed)
    <pkg>/camera_trace.txt      the same numbers + summary stats
    <pkg>/clip_lowres.mp4        the actual motion (for a human/orchestrator)
    <pkg>/manifest.json         paths + duration (NO source path, NO intent)

Motion is judged from the dense contact sheet (frame-to-frame change is visible)
plus the camera-motion trace (stalls, speed spikes, jitter). The judge prompt
lives in the orchestrator, not here, so this file never leaks intent.

    python3 scripts/visual_judge.py <clip.mp4> --out <pkgdir> [--grid 4x4]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def _dur(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(out.stdout.strip())


def _grab(clip: Path, t: float, dest: Path, scale: int = 1280):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
         "-i", str(clip), "-frames:v", "1",
         "-vf", f"scale={scale}:-1", str(dest)], check=True)


def _camera_trace(clip: Path, dur: float, pkg: Path, n: int = 60):
    """Per-sample mean absolute luminance change between frames 0.1s apart —
    a blind proxy for how the CAMERA/scene is moving: flat = stalled (dead
    air or a static photo), spikes = cuts or lurches, smooth ramp = a real
    move, high-frequency chatter = jitter / motion sickness."""
    import numpy as np
    from PIL import Image
    ts = [dur * i / n for i in range(n)]
    vals = []
    prev = None
    tmp = pkg / "_t.png"
    for t in ts:
        _grab(clip, min(dur - 0.05, t), tmp, scale=320)
        a = np.asarray(Image.open(tmp).convert("L"), dtype="float32")
        if prev is not None and prev.shape == a.shape:
            vals.append(float(np.abs(a - prev).mean()))
        else:
            vals.append(0.0)
        prev = a
    tmp.unlink(missing_ok=True)
    # numbers + summary
    import statistics
    body = vals[1:] or [0.0]
    stats = {"mean": round(statistics.mean(body), 2),
             "max": round(max(body), 2), "min": round(min(body), 2),
             "stdev": round(statistics.pstdev(body), 2),
             "stalls": sum(1 for v in body if v < 0.6),
             "spikes": sum(1 for v in body if v > stats_spike(body))}
    (pkg / "camera_trace.txt").write_text(
        "per-sample mean pixel motion (0=frozen, high=fast/cut)\n"
        + " ".join(f"{v:.1f}" for v in vals) + "\n\n"
        + json.dumps(stats, indent=1) + "\n"
        + "\nreading: long runs near 0 = the image stalls (dead air or a "
        "static photo pasted into motion); isolated tall spikes = hard cuts "
        "or lurches; a smooth hump = one continuous move; jagged = jitter.\n")
    # plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 3.2), dpi=110)
        ax.fill_between(range(len(vals)), vals, color="#4FD1C5", alpha=0.5)
        ax.plot(vals, color="#1c6f66", lw=1.4)
        ax.set_title("camera / scene motion over the clip "
                     "(0 = frozen, tall = fast or a cut)")
        ax.set_xlabel("time samples (left=start, right=end)")
        ax.set_ylabel("pixel motion")
        ax.margins(x=0)
        fig.tight_layout()
        fig.savefig(pkg / "camera_trace.png")
        plt.close(fig)
    except Exception:  # noqa: BLE001 — txt trace is the fallback
        pass
    return stats


def stats_spike(body):
    import statistics
    return statistics.mean(body) + 2.2 * (statistics.pstdev(body) or 1.0)


def _contact_sheet(clip: Path, dur: float, pkg: Path, cols: int, rows: int):
    n = cols * rows
    tiles = pkg / "_tiles"
    tiles.mkdir(exist_ok=True)
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    tw = 480
    frames = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        f = tiles / f"t{i:02d}.png"
        _grab(clip, min(dur - 0.05, t), f, scale=tw)
        im = Image.open(f).convert("RGB")
        d = ImageDraw.Draw(im)
        d.text((6, 6), f"{t:0.1f}s", font=font, fill=(255, 235, 120))
        frames.append(im)
    th = frames[0].height
    pad = 6
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * pad,
                              rows * th + (rows + 1) * pad), (10, 10, 16))
    for i, im in enumerate(frames):
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + pad)
        sheet.paste(im, (x, y))
    sheet.save(pkg / "contact_sheet.png")
    for f in tiles.glob("*.png"):
        f.unlink()
    tiles.rmdir()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--grid", default="4x4", help="contact sheet cols x rows")
    args = ap.parse_args()
    pkg = args.out
    pkg.mkdir(parents=True, exist_ok=True)
    dur = _dur(args.clip)
    cols, rows = (int(v) for v in args.grid.lower().split("x"))

    _contact_sheet(args.clip, dur, pkg, cols, rows)
    _grab(args.clip, min(dur - 0.05, dur * 0.05), pkg / "frame_begin.png")
    _grab(args.clip, dur * 0.5, pkg / "frame_mid.png")
    _grab(args.clip, min(dur - 0.05, dur * 0.95), pkg / "frame_end.png")
    stats = _camera_trace(args.clip, dur, pkg)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(args.clip),
         "-vf", "scale=640:-1", "-an", "-c:v", "libx264", "-crf", "30",
         str(pkg / "clip_lowres.mp4")], check=True)
    # manifest deliberately omits the source path + any intent
    (pkg / "manifest.json").write_text(json.dumps({
        "duration": round(dur, 2), "grid": args.grid,
        "motion_stats": stats,
        "files": ["contact_sheet.png", "frame_begin.png", "frame_mid.png",
                  "frame_end.png", "camera_trace.png", "camera_trace.txt",
                  "clip_lowres.mp4"]}, indent=1))
    print(f"blind media package -> {pkg}")
    print(f"duration {dur:.1f}s  motion {stats}")
    return 0


if __name__ == "__main__":
    main()
